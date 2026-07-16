# Namespace Packages vs Regular Packages

## Concept

The choice between regular packages (with `__init__.py`) and namespace packages (PEP 420, no `__init__.py`) has significant architectural implications for large systems, monorepos, and split distributions.

### Regular Package (`__init__.py` present)

```
mypackage/
├── __init__.py       ← marks this as a regular package
├── core.py
└── utils/
    ├── __init__.py
    └── helpers.py
```

```python
# __init__.py controls the package's public API:
from .core import CoreClass, core_function
from .utils.helpers import helper

__all__ = ['CoreClass', 'core_function', 'helper']

# Usage:
import mypackage
print(dir(mypackage))    # only what __init__.py exposes

# __init__.py runs on package import:
# import mypackage.core → runs mypackage/__init__.py first, then core.py
```

### Namespace Package (no `__init__.py`)

```
/repo1/
    myns/               ← no __init__.py
        module_a.py

/repo2/
    myns/               ← no __init__.py
        module_b.py

# sys.path = ['/repo1', '/repo2']
```

```python
import myns.module_a    # from /repo1/myns/module_a.py
import myns.module_b    # from /repo2/myns/module_b.py

print(myns.__path__)
# _NamespacePath(['/repo1/myns', '/repo2/myns'])
# All contributing directories listed

print(myns.__file__)    # None — no __init__.py
```

### How Python Finds Namespace Packages

When `PathFinder` searches for `myns`:
1. For each directory in `sys.path`:
   - If `{dir}/myns/__init__.py` exists → regular package, stop searching.
   - If `{dir}/myns/` exists (no `__init__.py`) → potential namespace contribution, continue.
   - If `{dir}/myns.py` exists → module, stop searching.
2. If no `__init__.py` found but directories found → namespace package with `__path__` = all found dirs.

```python
import sys
sys.path = ['/path/a', '/path/b', '/path/c']

# /path/a/myns/               ← no __init__.py, contributes to namespace
# /path/b/myns/__init__.py    ← regular package found → stops here, uses only /path/b/myns
# /path/c/myns/               ← never reached once regular package found
```

This priority means: if ANY directory in `sys.path` has `myns/__init__.py`, namespace package discovery stops and that regular package wins.

### Monorepo Use Case

```
monorepo/
├── service-a/
│   └── company/         ← no __init__.py
│       └── service_a/
│           ├── __init__.py
│           └── api.py
├── service-b/
│   └── company/         ← no __init__.py
│       └── service_b/
│           ├── __init__.py
│           └── api.py
└── shared-lib/
    └── company/         ← no __init__.py
        └── shared/
            ├── __init__.py
            └── models.py
```

```python
# pyproject.toml for service-a:
# [tool.setuptools.packages.find]
# where = ["service-a"]

# After installation or with sys.path = ['service-a/', 'service-b/', 'shared-lib/']:
from company.service_a.api import ServiceAHandler
from company.service_b.api import ServiceBHandler
from company.shared.models import UserModel

# 'company' is a namespace package spanning three directories
```

### When to Use Which

| Scenario | Use |
|----------|-----|
| Single cohesive library | Regular package with `__init__.py` |
| Need public API control (`__all__`, lazy imports) | Regular package |
| Split distribution across multiple repos | Namespace package |
| Monorepo with shared namespace prefix | Namespace package |
| Plugin system where plugins share a prefix | Namespace package |
| Simple application code | Regular package |

### Gotcha: Mixing Regular and Namespace Packages

```python
# WRONG: some dirs have __init__.py, some don't:
# /path1/company/          ← namespace
# /path2/company/__init__.py  ← regular

# /path1 comes first in sys.path → namespace package from /path1
# /path2/company is NEVER searched (namespace already found)
# Result: modules from /path2/company are inaccessible!

# FIX: be consistent — either ALL dirs contributing to 'company' have __init__.py
# or NONE do
```

---

## Interview Questions

### Q1: What's the practical difference between a package with an empty `__init__.py` and a namespace package?

**Model answer:**
An empty `__init__.py` creates a regular package — Python finds it, stops searching `sys.path` for more contributions, and the package's `__path__` is just `['/path/to/package']`. Import resolution is complete once the `__init__.py` is found.

A namespace package (no `__init__.py`) tells Python to keep searching ALL `sys.path` directories for more contributions to the same package name. The namespace package's `__path__` becomes a list of all found directories.

```python
# With empty __init__.py:
# /site-packages/mypkg/__init__.py  ← empty file
# /dev/mypkg/                       ← no __init__.py

# Result: only /site-packages/mypkg is the package
# /dev/mypkg is ignored even if it appears later in sys.path

# Without __init__.py:
# /site-packages/myns/  ← no __init__.py
# /dev/myns/            ← no __init__.py

# Result: namespace package with __path__ = ['/site-packages/myns', '/dev/myns']
# modules from both directories are importable
```

The key implication: namespace packages enable multi-directory, multi-repo packages. Regular packages are isolated to a single directory.

### Q2: How do namespace packages enable plugin systems?

**Model answer:**
Plugins can be distributed as separate packages that all contribute to a shared namespace:

```bash
# Core library: myapp-core
# Plugin 1: myapp-plugin-redis  
# Plugin 2: myapp-plugin-postgres

# Each installs into:
# site-packages/myapp/          ← no __init__.py in any of them
#   core/...      (from myapp-core)
#   redis/...     (from myapp-plugin-redis)
#   postgres/...  (from myapp-plugin-postgres)
```

```python
# After installing any combination of plugins:
from myapp.core import BaseHandler         # from myapp-core
from myapp.redis import RedisHandler       # from myapp-plugin-redis (if installed)
from myapp.postgres import PostgresHandler # from myapp-plugin-postgres (if installed)

# The core package doesn't need to know about plugins at install time
# Plugins are discovered dynamically by the namespace
```

This is how `sphinxcontrib` works — dozens of independent Sphinx extensions under the `sphinxcontrib` namespace package. Compare with `entry_points` (see plugin-architectures.md) for explicit plugin registration.

### Q3: What happens if one directory in a namespace has `__init__.py` and another doesn't?

**Model answer:**
The regular package wins and the namespace is broken for that prefix. Python's search for `myns` stops at the FIRST match:

If `sys.path = ['/a', '/b']`:
- `/a/myns/` — no `__init__.py` → potential namespace contribution, continue.
- `/b/myns/__init__.py` → regular package found → use `/b/myns/`, stop.
- Result: `/a/myns/` is never accessible under `myns`.

Reverse order `sys.path = ['/b', '/a']`:
- `/b/myns/__init__.py` found first → regular package `/b/myns/`, stop.
- Result: `/a/myns/` still inaccessible.

In both cases, the regular package shadow the namespace. This creates silent bugs when a user installs a conflicting package that adds `__init__.py` to the namespace.

**Prevention:** namespace package owners should document that contributors MUST NOT add `__init__.py`, and CI should verify this.

### Q4: How would you detect at runtime whether a package is a namespace package?

**Model answer:**
```python
import importlib
import types

def is_namespace_package(package_name: str) -> bool:
    try:
        pkg = importlib.import_module(package_name)
    except ImportError:
        return False

    # Namespace packages have no __file__ and __path__ is a _NamespacePath
    return (
        getattr(pkg, '__file__', None) is None
        and hasattr(pkg, '__path__')
        and not isinstance(pkg.__path__, list)  # _NamespacePath, not plain list
    )

# Or more precisely:
from importlib.machinery import ModuleSpec
spec = importlib.util.find_spec('myns')
print(spec.origin)       # None for namespace package
print(spec.submodule_search_locations)  # _NamespacePath([...])
print(type(spec.submodule_search_locations).__name__)  # '_NamespacePath'
```

The definitive check: `spec.origin is None and spec.submodule_search_locations is not None`.

### Q5: In a monorepo, should you use namespace packages or editable installs?

**Model answer:**
Both work; the best choice depends on team size and tooling:

**Namespace packages + sys.path manipulation:**
```bash
# In dev environment (pytest.ini or .env):
PYTHONPATH=service-a:service-b:shared-lib pytest
```
Pros: simple, no installation step. Cons: path management is fragile, doesn't work without PYTHONPATH set correctly.

**Editable installs (`pip install -e`):**
```bash
pip install -e service-a/ -e service-b/ -e shared-lib/
# Each package installed as editable, namespace discovered via installed .pth files
```
Pros: no PYTHONPATH needed, works the same as production install, IDE support works. Cons: requires running pip for each package.

**Modern monorepo tools (uv workspaces, Poetry 1.2+ groups):**
```toml
# pyproject.toml at monorepo root:
[tool.uv.workspace]
members = ["service-a", "service-b", "shared-lib"]
```
```bash
uv sync  # installs all workspace members as editable
```
Pros: single command, lock file covers all packages. This is the recommended approach for new monorepos.

---

## Gotcha Follow-ups

**"Can a namespace package have an `__init__.py` somewhere in its contribution path?"**
Yes — but it becomes a regular package. If `a/myns/` has no `__init__.py` but `b/myns/__init__.py` exists, `b/myns` dominates. The resulting package is NOT a namespace across both — it's the regular package from `b/myns`.

**"Does pytest handle namespace packages correctly?"**
By default, pytest adds each `testpaths` root to `sys.path`. For namespace packages, this works if all roots are on `sys.path`. Use `pyproject.toml`'s `[tool.pytest.ini_options] pythonpath = [...]` to configure. With `conftest.py` at the root, pytest handles path setup automatically.

---

## Under the Hood

Namespace package support is in `importlib/_bootstrap_external.py`, `PathFinder.find_spec()`. For each directory in `sys.path`, `FileFinder` (the path entry finder) checks for `{name}/__init__.py` (regular) then `{name}/` (directory, namespace candidate). The result of finding a directory without `__init__.py` is stored as a "namespace path" candidate. After exhausting all `sys.path` entries, if namespace candidates exist and no regular package was found, a namespace `ModuleSpec` is created with `origin=None` and `submodule_search_locations=_NamespacePath(candidates)`.
