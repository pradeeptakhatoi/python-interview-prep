# Virtual Environments and Dependency Resolution

## Concept

A virtual environment is an isolated Python installation — its own `site-packages`, its own `python` executable (usually a symlink), and its own `pyvenv.cfg`. Understanding what happens under the hood separates informed dependency management from cargo-culting `pip install`.

### What `python -m venv` Creates

```
myenv/
├── pyvenv.cfg          ← home=<base python path>, include-system-site-packages=false
├── bin/ (or Scripts/ on Windows)
│   ├── python          ← symlink (or copy) to base Python
│   ├── python3         ← same
│   ├── pip             ← entry point script pointing to venv's pip
│   └── activate        ← shell function that prepends bin/ to PATH
└── lib/
    └── python3.11/
        └── site-packages/   ← installed packages land here
```

`pyvenv.cfg` tells CPython "this is a virtual environment." When the Python executable starts, it reads this file, sets `sys.prefix` to the venv directory, and adds `{sys.prefix}/lib/pythonX.Y/site-packages` to `sys.path`.

```python
import sys

# Inside a virtual environment:
print(sys.prefix)       # /path/to/myenv
print(sys.base_prefix)  # /usr/local (system Python)
print(sys.prefix == sys.base_prefix)  # False — we're in a venv

# sys.path includes the venv's site-packages:
print([p for p in sys.path if 'site-packages' in p])
# ['/path/to/myenv/lib/python3.11/site-packages']
```

### Dependency Pinning with `pip-compile`

```bash
# requirements.in (direct dependencies only):
requests>=2.28
pydantic>=2.0
fastapi

# Generate fully pinned requirements.txt:
pip-compile requirements.in   # uses pip-tools

# requirements.txt (all transitive deps, pinned):
# annotated-types==0.6.0
# anyio==4.2.0
# ...
# requests==2.31.0
#     # via -r requirements.in
# ...

# Install from pinned file:
pip install -r requirements.txt
```

### `pip`'s Dependency Resolution Algorithm

pip 20.3+ uses a **backtracking resolver**. It tries candidate versions from newest to oldest for each package and backtracks when a version conflict is found. Key concepts:

- **Direct dependencies:** what you explicitly require.
- **Transitive dependencies:** what your dependencies require.
- **Conflict:** two packages require incompatible versions of the same package.
- **Backtracking:** pip tries an older version of a package when a conflict is detected.

```bash
# Diagnosing conflicts:
pip install package-a package-b  # may fail with ResolutionImpossible

# Show what each package requires:
pip show package-a   # Requires: requests>=2.28
pip show package-b   # Requires: requests<2.0

# pip check — verify consistency:
pip check
# package-b 1.0 has requirement requests<2.0, but you have requests 2.31.0

# pip-tools for deterministic builds:
pip-compile --upgrade requirements.in
```

### `uv` — Modern Fast Resolver (Rust-Based)

```bash
# uv is 10-100x faster than pip for resolution and installation:
pip install uv

# Create venv and install:
uv venv
uv pip install -r requirements.txt

# Compile dependencies:
uv pip compile requirements.in > requirements.txt

# Sync environment to requirements.txt (add + remove as needed):
uv pip sync requirements.txt
```

### `sys.path` Manipulation and `.pth` Files

When Python starts, it processes `.pth` files in `site-packages`. Each line is either a path (added to `sys.path`) or a Python statement (executed):

```python
# /path/to/site-packages/mypackage.pth
/home/user/mypackage/src    # adds this path to sys.path

# Or with editable installs (pip install -e .):
# pip creates a direct_url.json and a .pth file pointing to source dir
```

```python
# Inspect current path manipulation:
import site
print(site.getsitepackages())    # list of site-packages dirs
print(site.getusersitepackages())  # ~/.local/lib/...

# Disable site-packages (e.g., for clean scripts):
# python -S script.py  (no site.py processing)
```

### `PYTHONPATH` and Import Priority

```python
# sys.path search order:
# 1. '' (current directory, or script's directory)
# 2. PYTHONPATH entries (if set)
# 3. Installation-dependent default paths
# 4. site-packages

import sys
print(sys.path)
```

`PYTHONPATH` can shadow installed packages — a common source of "why is the wrong version being imported":

```bash
PYTHONPATH=/my/dev/lib python -c "import requests; print(requests.__file__)"
# May pick up /my/dev/lib/requests.py instead of site-packages
```

---

## Interview Questions

### Q1: What exactly does `source activate` do, and what would you need to do manually without it?

**Model answer:**
`activate` is a shell script that modifies the current shell session:
1. Prepends `{venv}/bin` to `PATH` — so `python`, `pip`, etc. resolve to the venv.
2. Sets `VIRTUAL_ENV` environment variable to the venv path.
3. Saves and replaces `PS1` (prompt) to show the venv name.
4. Defines a `deactivate` function to undo these changes.

Without `activate`, you can use the venv by calling the full path:
```bash
/path/to/myenv/bin/python script.py
/path/to/myenv/bin/pip install package
```

The venv is active whenever CPython is started from `{venv}/bin/python` — `activate` is a convenience, not a requirement. This is important for scripts, CI/CD, and Docker, where you typically use the full path instead of sourcing activate.

### Q2: How does pip's dependency resolver work and what causes "ResolutionImpossible" errors?

**Model answer:**
pip's backtracking resolver works like constraint satisfaction:

1. Build a graph of all package requirements.
2. For each package, try the newest version that satisfies known constraints.
3. Check if that version's dependencies conflict with already-chosen versions.
4. If conflict: backtrack — try the next-older version of the conflicting package.
5. If exhausted all versions of a package: `ResolutionImpossible`.

Common causes:
- Two packages require incompatible ranges of the same dependency.
- A new version of a transitive dependency dropped support for the required Python version.
- Platform-specific packages with incompatible version pins.

Debugging:
```bash
# Verbose resolution output:
pip install package --verbose 2>&1 | grep "Conflict\|Backtrack"

# pip-tools with explanation:
pip-compile --verbose requirements.in

# Check current environment consistency:
pip check
```

### Q3: What is the difference between `pip install -e .` (editable install) and `pip install .`?

**Model answer:**
`pip install .` copies the package source to `site-packages` — like any other install. Subsequent changes to your source files require reinstalling.

`pip install -e .` (editable/development install) adds a `.pth` file to `site-packages` pointing back to your source directory. Python imports from your source directly — changes are reflected immediately without reinstalling:

```bash
# Editable install:
pip install -e .
# Creates: site-packages/mypackage.egg-link  (old setuptools)
# Or: site-packages/direct_url.json + site-packages/__editable__.mypackage.pth (modern)

cat $(python -c "import site; print(site.getsitepackages()[0])")/__editable__.mypackage.pth
# /path/to/mypackage/src
```

Use editable installs during development. Never use them in production — the installed environment depends on your source tree being present and unmodified.

### Q4: How do you ensure reproducible builds across environments?

**Model answer:**
Three layers of reproducibility:

1. **Pin all dependencies** (including transitive): use `pip-compile` or `uv pip compile` to generate a complete `requirements.txt` from `requirements.in`.

2. **Hash checking**: pip verifies package hashes to prevent tampering:
```bash
pip-compile --generate-hashes requirements.in
# requirements.txt includes:
# requests==2.31.0 \
#     --hash=sha256:58cd2187423d077...
pip install --require-hashes -r requirements.txt
```

3. **Platform consistency**: use Docker with a fixed base image (`python:3.11.7-slim`) to ensure the same Python, glibc, and system libraries. Use `--platform linux/amd64` for cross-platform builds.

```dockerfile
FROM python:3.11.7-slim
COPY requirements.txt .
RUN pip install --require-hashes --no-deps -r requirements.txt
```

`--no-deps` with `--require-hashes` ensures pip doesn't install unlisted transitive dependencies.

### Q5: What is `sys.path` and how does Python decide where to look for imports?

**Model answer:**
`sys.path` is a list of directories Python searches in order when importing. It's built at startup from:
1. `''` (empty string) — the current directory (or script's directory).
2. `PYTHONPATH` environment variable entries.
3. Installation-dependent defaults (stdlib paths).
4. `site-packages` dirs (added by `site.py`).

The first match wins:
```python
import sys

# If you have ./requests.py and site-packages has requests:
sys.path.insert(0, '.')   # current dir first → your requests.py imported
                           # a common source of "shadowing" bugs

# Best practice: never name your files the same as stdlib/third-party packages
# Always check: python -c "import mymodule; print(mymodule.__file__)"
```

In a virtual environment, `sys.path` includes the venv's `site-packages` and NOT the base Python's `site-packages` (unless `include-system-site-packages = true` in `pyvenv.cfg`).

---

## Gotcha Follow-ups

**"What's the difference between `pip freeze` and `pip list`?"**
`pip freeze` outputs in `requirements.txt` format (`package==version`) for all installed packages (including pip itself in newer versions). `pip list` outputs a human-readable table. Neither shows the dependency tree. Use `pipdeptree` for the tree, or `pip show package` for individual dependency info.

**"Can two virtual environments share packages to save disk space?"**
Not natively — each venv has its own `site-packages`. Tools like `virtualenvwrapper` and `pyenv` don't share either. For disk savings: `uv` uses a global package cache and hard-links packages into venvs, achieving near-zero additional disk usage per venv. Alternatively, `nix` and `conda` have their own sharing mechanisms.

---

## Under the Hood

`venv` module (`Lib/venv/__init__.py`): calls `EnvBuilder.create()` which creates the directory structure, writes `pyvenv.cfg`, copies or symlinks the Python executable, and installs `pip` via `ensurepip`. The critical file is `pyvenv.cfg` — CPython reads this at `Py_InitializeEx()` time in `Modules/getpath.py` (now a Python script inside CPython) to set `sys.prefix` and `sys.exec_prefix`.

`site.py` (`Lib/site.py`): runs at Python startup (unless `-S`). Reads `pyvenv.cfg`, computes `site-packages` paths, processes `.pth` files, adds paths to `sys.path`. The `getsitepackages()` return value comes from `PREFIXES` which is `[sys.prefix, sys.exec_prefix]`.
