# Building Distributable Packages

## Concept

Modern Python packaging uses `pyproject.toml` as the single configuration file (PEP 517/518/621). Understanding the build pipeline — from source tree to wheel to installed package — is essential for library authors and CI engineers.

### `pyproject.toml` Structure

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mypackage"
version = "1.2.3"
description = "A well-packaged library"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "Alice", email = "alice@example.com"}]
keywords = ["python", "library"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "requests>=2.28",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=7", "mypy", "ruff"]
docs = ["sphinx", "furo"]

[project.scripts]
mypackage-cli = "mypackage.cli:main"

[project.entry-points."mypackage.plugins"]
default = "mypackage.plugins.default:DefaultPlugin"

[project.urls]
Homepage = "https://github.com/example/mypackage"
Documentation = "https://mypackage.readthedocs.io"

[tool.setuptools.packages.find]
where = ["src"]   # src layout: package under src/mypackage/
```

### `src` Layout vs Flat Layout

```
# src layout (recommended):
mypackage/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       └── core.py
├── tests/
│   └── test_core.py
└── pyproject.toml

# Flat layout (older style):
mypackage/
├── mypackage/
│   ├── __init__.py
│   └── core.py
├── tests/
└── pyproject.toml
```

**Why `src` layout:** prevents accidental import of the local directory during development. With flat layout, `import mypackage` finds the local `mypackage/` directory even without installation. With `src` layout, you must install (even editably) to import, ensuring tests run against the installed version.

### Building: Wheel and SDist

```bash
# Install build frontend:
pip install build

# Build both wheel (.whl) and source distribution (.tar.gz):
python -m build

# dist/
# ├── mypackage-1.2.3-py3-none-any.whl   ← pure Python wheel
# └── mypackage-1.2.3.tar.gz              ← source distribution

# Pure Python wheel name: {name}-{version}-{python_tag}-{abi_tag}-{platform_tag}.whl
# py3-none-any = Python 3, no ABI constraint, any platform
# cp311-cp311-manylinux_2_17_x86_64 = CPython 3.11, manylinux, x86_64
```

**Wheel vs SDist:**
- **Wheel (.whl)**: pre-built, just unzips to `site-packages`. Fastest install.
- **SDist (.tar.gz)**: source tarball, requires building (running setup/build hooks) on install. Needed for C extensions and as the fallback when no wheel matches the platform.

### Versioning with `__version__`

```python
# src/mypackage/__init__.py
__version__ = "1.2.3"

# Or use importlib.metadata (recommended — reads from installed package metadata):
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("mypackage")
except PackageNotFoundError:
    __version__ = "unknown"   # package not installed (running from source)
```

### Entry Points

Entry points are metadata-based discovery hooks — the mechanism behind `pip install` command installation and plugin systems:

```toml
[project.scripts]
my-tool = "mypackage.cli:main_function"
# After install: 'my-tool' command calls mypackage.cli.main_function()

[project.gui-scripts]
my-gui = "mypackage.gui:start"   # no console window on Windows

[project.entry-points."mypackage.plugins"]
csv = "mypackage.plugins.csv:CSVPlugin"
json = "mypackage.plugins.json:JSONPlugin"
```

```python
# Runtime discovery:
from importlib.metadata import entry_points

# Get all entry points in a group:
plugins = entry_points(group='mypackage.plugins')
for ep in plugins:
    plugin_class = ep.load()   # imports and returns the object
    print(f"Loaded plugin: {ep.name} → {plugin_class}")

# Pattern: auto-discover all installed plugins
def load_plugins() -> dict[str, type]:
    return {
        ep.name: ep.load()
        for ep in entry_points(group='mypackage.plugins')
    }
```

### Publishing to PyPI

```bash
# Build:
python -m build

# Check the package:
twine check dist/*

# Upload to TestPyPI first:
twine upload --repository testpypi dist/*

# Upload to PyPI:
twine upload dist/*

# Or use trusted publishing (no API token needed, recommended):
# Configure in GitHub Actions with OIDC:
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  # No API token needed with trusted publishing
```

---

## Interview Questions

### Q1: What's the difference between a wheel and an sdist? When does each matter?

**Model answer:**
A **wheel** is a pre-built package — a ZIP archive that pip simply unpacks into `site-packages`. No compilation or build step required. Wheels are platform-specific (for C extensions) or universal (for pure Python).

An **sdist** (source distribution) is a tarball of the source tree. Installing from sdist triggers the build system: setuptools runs, C extensions compile, `pyproject.toml` hooks execute. This takes longer and requires a compiler for C extensions.

**When wheel matters:**
- `pip install` prefers wheels because they're fast and don't require a compiler.
- If your package has C extensions, you need to build wheels for each supported platform/Python version combination (using `cibuildwheel` in CI).
- If only an sdist is available and the user has no compiler: install fails for C extensions.

**When sdist matters:**
- Embedding/vendoring: some environments only accept source code.
- Security audits: sdist is auditable source; wheels are binary.
- Always publish both — PyPI recommends: `python -m build` creates both.

### Q2: What does `pip install -e .` create in `site-packages` and how does it work?

**Model answer:**
Editable install creates a mechanism for Python to find your source directory. The mechanism changed in setuptools 64+ (PEP 660):

**Old mechanism** (egg-link):
```
site-packages/mypackage.egg-link → /path/to/source
site-packages/easy-install.pth → /path/to/source
```

**New mechanism** (importlib-based):
```
site-packages/__editable__.mypackage-1.2.3.pth
  → contains: /path/to/source/src
site-packages/mypackage-1.2.3.dist-info/
  → contains package metadata, direct_url.json
```

Python's `site.py` processes the `.pth` file and adds the path to `sys.path`. This means `import mypackage` imports from `/path/to/source/src/mypackage/` directly. Changes to source files are immediately visible without reinstalling.

### Q3: What are entry points and how do they enable plugin architectures?

**Model answer:**
Entry points are a metadata-based discovery mechanism in Python packaging. When you install a package, its `pyproject.toml` entry points are written to `{package}.dist-info/entry_points.txt`. Other code can discover these at runtime without knowing which packages are installed.

```toml
# Plugin declares itself:
[project.entry-points."myapp.backends"]
sqlite = "myapp_sqlite:SQLiteBackend"
```

```python
# Core app discovers plugins at runtime:
from importlib.metadata import entry_points

backends = {}
for ep in entry_points(group='myapp.backends'):
    backends[ep.name] = ep.load()   # lazy load — only imported when accessed

# Now: backends = {'sqlite': SQLiteBackend, 'postgres': PostgresBackend, ...}
# depending on which packages are installed
```

This is how `pytest` discovers plugins (`pytest11` group), `sphinx` discovers extensions, `click` discovers subcommands in some CLIs, and tools like `flake8` discover rules.

### Q4: How does semantic versioning apply to Python packages, and what do `~=` and `>=` mean in dependencies?

**Model answer:**
**SemVer:** `MAJOR.MINOR.PATCH`. Breaking change → MAJOR. New backward-compatible feature → MINOR. Bug fix → PATCH.

Dependency specifiers:
```
>=2.0          → version 2.0 or newer (no upper bound — risky)
>=2.0,<3.0     → version 2.x (safe for MAJOR upgrades)
~=2.1          → >=2.1, <3 (compatible release — same MAJOR, any newer MINOR)
~=2.1.0        → >=2.1.0, <2.2 (compatible release at MINOR level)
==2.1.3        → exactly 2.1.3 (pin — use in applications, not libraries)
!=2.1.4        → any version except 2.1.4 (exclude known bad version)
```

**Library vs application rule:**
- **Libraries**: use `>=` with a lower bound only, or `~=` for compatibility. Never pin exactly — you'd conflict with other dependencies.
- **Applications**: pin all transitive deps in `requirements.txt`. `pyproject.toml` specifies ranges; `requirements.txt` (from pip-compile) pins exactly.

```toml
# Library (pyproject.toml):
dependencies = ["requests>=2.28,<3"]   # range — lets pip resolve

# Application (requirements.txt, generated):
requests==2.31.0  # exact pin
```

### Q5: What is `manylinux` and why does it exist?

**Model answer:**
`manylinux` is a specification for binary Python wheels that can run on many Linux distributions. The problem: Linux distributions have different versions of `glibc` and system libraries. A wheel built on Ubuntu 22.04 may use a `glibc` version not available on RHEL 7.

`manylinux` defines a minimum `glibc` version and a set of permitted system libraries. Wheels tagged `manylinux_2_17_x86_64` are built in a minimal Docker container (typically CentOS 7-based) with `glibc 2.17` — compatible with virtually all modern Linux distributions.

```bash
# Build manylinux wheels with cibuildwheel:
pip install cibuildwheel

# .github/workflows/build.yml:
# - name: Build wheels
#   uses: pypa/cibuildwheel@v2
#   with:
#     package-dir: .
#     output-dir: wheelhouse
#   env:
#     CIBW_BUILD: cp311-manylinux_x86_64 cp312-manylinux_x86_64

# cibuildwheel runs your build inside a manylinux Docker container,
# then runs auditwheel to verify no disallowed library symbols are used
```

Without manylinux: users on Linux would need to compile from sdist (requires compiler). With manylinux wheels: `pip install your-package` just works on any modern Linux.

---

## Gotcha Follow-ups

**"What's the difference between `dependencies` and `optional-dependencies` in `pyproject.toml`?"**
`dependencies` are always installed. `optional-dependencies` (extras) are installed only when requested with `pip install mypackage[extra-name]`. Use extras for: dev tools (tests, linters), documentation (sphinx), optional feature backends (redis, postgres), heavy optional deps (numpy for a library that works without it).

**"Should version be in `pyproject.toml` or in `__init__.py`?"**
Modern approach: single source in `pyproject.toml` (or your VCS tag via `setuptools-scm`), and read it at runtime with `importlib.metadata.version()`. Avoid maintaining the version in two places. With `setuptools-scm`: version is derived from the git tag — no manual version bumping needed.

---

## Under the Hood

The PEP 517 build pipeline: `pip` is the **frontend** (user-facing), `setuptools`/`flit`/`hatch` are **backends** (build system). When `pip install .` runs: pip calls `build_backend.build_wheel(wheel_dir)` (via a subprocess to avoid import contamination). The backend creates the `.whl` file. pip then unpacks it. This separation (PEP 517) means you can swap build backends without changing pip.

`importlib.metadata.entry_points()` reads `{package}.dist-info/entry_points.txt` from all installed packages in `sys.path`. The `dist-info` directories are installed by pip alongside the package code. `entry_points.txt` format: `[group]\nname = module:attr\n`.
