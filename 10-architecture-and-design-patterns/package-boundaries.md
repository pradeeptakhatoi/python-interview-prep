# Package Boundaries and Circular Dependencies

## Concept

Package boundaries define what each module is allowed to import. Violations — most commonly circular imports — produce `ImportError`, partial module state, or subtle attribute errors. Enforcing clean boundaries is a prerequisite for maintainable large Python codebases.

### Why Circular Imports Fail

```python
# a.py
from b import B_VALUE   # triggers import of b.py

# b.py
from a import A_VALUE   # a is already in sys.modules but not finished!
# A_VALUE hasn't been assigned yet → AttributeError / ImportError
```

Python's import system pre-populates `sys.modules['a']` with a partial module object before executing `a.py`'s body. When `b.py` imports `a`, it gets the partial module — which may be missing names defined later in `a.py`.

### Detecting Circular Imports

```python
# Run: python -X importtime -c "import mypackage" 2>&1 | grep cumtime
# Or use the stdlib:
import importlib
import sys

def find_circular_imports(package_name: str) -> list[tuple[str, str]]:
    """Simple cycle detector based on import order."""
    import ast, pathlib

    def get_imports(filepath: pathlib.Path) -> list[str]:
        try:
            tree = ast.parse(filepath.read_text())
        except SyntaxError:
            return []
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    # More robust: use `importlab` or `pydep` packages for this

# Quick manual test:
# python -c "import myapp.services"  # will raise on circular import at import time
```

### Breaking Circular Imports — Three Strategies

**Strategy 1: Move the import inside the function**

```python
# a.py
def get_b_value():
    from b import B_VALUE   # deferred import — runs after b.py has fully loaded
    return B_VALUE

# Only works if:
# - The import is not needed at module level (class definition, type annotations)
# - Performance is not critical (import cost on first call)
```

**Strategy 2: Extract the shared code to a third module**

```python
# Before (circular):
# user.py imports from auth.py
# auth.py imports from user.py

# After: extract the shared type to types.py
# types.py  ← user.py imports from here
#            ← auth.py imports from here
# user.py and auth.py no longer import each other

# types.py (no imports from this package):
from dataclasses import dataclass

@dataclass
class UserID:
    value: int

@dataclass
class AuthToken:
    token: str
    user_id: UserID
```

**Strategy 3: Use `TYPE_CHECKING` for type-only imports**

```python
from __future__ import annotations   # string annotations — no runtime eval
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myapp.auth import AuthService   # imported ONLY by mypy/pyright, not at runtime

class UserService:
    def __init__(self, auth: 'AuthService') -> None:   # string annotation
        self._auth = auth
```

### Acyclic Dependency Principle (ADP)

Enforce a strict layering where imports flow in one direction:

```
presentation layer   →  application layer  →  domain layer
                     →  infrastructure layer  (only from application/presentation)
domain layer         →  nothing (pure Python, no infrastructure)
```

```python
# myapp/domain/user.py — allowed: stdlib only
from dataclasses import dataclass

@dataclass
class User:
    id: int
    email: str
    name: str

# myapp/application/user_service.py — allowed: domain + stdlib
from myapp.domain.user import User
from myapp.domain.repositories import UserRepository   # abstract

class UserService:
    def __init__(self, repo: UserRepository): ...

# myapp/infrastructure/postgres_repo.py — allowed: domain + stdlib + third-party
import psycopg2
from myapp.domain.user import User
from myapp.domain.repositories import UserRepository

class PostgresUserRepository(UserRepository): ...

# myapp/presentation/api.py — allowed: application + stdlib + web framework
from myapp.application.user_service import UserService

# FORBIDDEN:
# domain/user.py importing from infrastructure/
# application/ importing from presentation/
```

### Enforcing Import Rules with `import-linter`

```toml
# pyproject.toml:
[tool.importlinter]
root_packages = ["myapp"]

[[tool.importlinter.contracts]]
name = "Domain independence"
type = "forbidden"
source_modules = ["myapp.domain"]
forbidden_modules = ["myapp.infrastructure", "myapp.presentation"]

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = ["myapp.presentation", "myapp.application", "myapp.domain"]
```

```bash
# Check in CI:
pip install import-linter
lint-imports
```

---

## Interview Questions

### Q1: What causes circular import errors and why are they sometimes silent?

**Model answer:**
Circular imports fail when a module tries to use a name from another module before that name has been defined.

The sequence for `a.py → b.py → a.py`:
1. `import a` starts; `sys.modules['a']` = empty module object
2. `a.py` body starts executing
3. `from b import B_VALUE` triggers `import b`
4. `b.py` body starts
5. `from a import A_VALUE` — `a` is in `sys.modules` (partial!) — `A_VALUE` doesn't exist yet
6. `AttributeError: partially initialized module 'a' has no attribute 'A_VALUE'`

**Why sometimes silent:** if `b.py` uses `import a` (not `from a import A_VALUE`), and only accesses `a.A_VALUE` at call time (not at import time), it silently works — `a.A_VALUE` exists by the time the function is called. This is a common "gotcha" — circular imports that work at runtime but are logically broken.

```python
# Silently broken circular import:
# a.py
import b

class A:
    def method(self):
        return b.B()  # b.B exists by call time — works (badly)

A_VALUE = 42  # defined after 'import b'

# b.py
import a

class B:
    pass

B_VALUE = a.A_VALUE  # defined at import time — fails if a not done!
```

### Q2: What is the Acyclic Dependency Principle and how do you enforce it in Python?

**Model answer:**
ADP states that the import dependency graph between packages must be a DAG — no cycles. Each layer can only import from layers below it.

Benefits:
- Independent testing of each layer (domain layer has no infrastructure imports — no DB needed)
- Independent deployment and release of packages
- Clear code ownership

Enforcement options:

1. **`import-linter`:** define contracts in `pyproject.toml`, run in CI. Fails on violations.
2. **`pylint` import-checker:** `pylint --check-import-order`
3. **Custom AST scan:** walk all `.py` files, build import graph, run cycle detection (`graphlib.TopologicalSorter`).

```python
# Detecting cycles with graphlib (stdlib, Python 3.9+):
from graphlib import TopologicalSorter, CycleError
import ast
import pathlib

def build_import_graph(root: pathlib.Path) -> dict[str, set[str]]:
    graph = {}
    for py_file in root.rglob('*.py'):
        module = str(py_file.relative_to(root).with_suffix('')).replace('/', '.')
        tree = ast.parse(py_file.read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split('.')[0])  # top-level package
        graph[module] = imports
    return graph

try:
    ts = TopologicalSorter(graph)
    list(ts.static_order())
    print("No circular imports!")
except CycleError as e:
    print(f"Circular import detected: {e}")
```

### Q3: What's the difference between `import a` and `from a import X` with respect to circular imports?

**Model answer:**
`import a` binds the name `a` to the module object (which may be partial). Attribute access `a.X` is resolved at call time — by then, the module is fully loaded.

`from a import X` binds `X` directly to the value at import time — if `a.X` doesn't exist yet (partial module), you get `ImportError` or `AttributeError`.

```python
# a.py
import b   # "safe" for circulars — b gets partial a object

def fn():
    return b.helper()  # b.helper resolved at call time, not import time

# vs:
# a.py
from b import helper  # "unsafe" for circulars — resolves helper NOW
```

**Which to prefer:** `from module import name` is generally more readable and should be the default. Only fall back to `import module` if you have a circular dependency you're working around (and document why).

### Q4: How do you structure a large Python codebase to prevent circular imports from occurring in the first place?

**Model answer:**
Four structural rules that prevent circulars:

1. **Layered architecture:** domain → application → infrastructure → presentation. Each layer only imports from layers below it.

2. **Shared types module:** put cross-cutting types (IDs, enums, base exceptions, value objects) in a `types.py` or `models.py` that imports nothing from this package.

3. **Protocol-based interfaces in the domain layer:** instead of the domain importing from infrastructure, define an abstract `Repository` protocol in the domain, implemented by infrastructure. Infrastructure imports domain; domain imports nothing from infrastructure.

4. **No circular initialization in module bodies:** only do cross-module imports inside functions or with `TYPE_CHECKING`.

```
myapp/
  domain/
    types.py        ← base types, imports nothing
    models.py       ← domain models, imports from types only
    repositories.py ← Protocol interfaces, imports from types + models
  application/
    services.py     ← imports from domain only
  infrastructure/
    postgres.py     ← imports from domain + third-party
  presentation/
    api.py          ← imports from application + framework
```

### Q5: How do you handle the case where a type annotation creates a circular import?

**Model answer:**
Type annotations are the most common source of "necessary" circular imports in typed Python.

```python
# user_service.py wants to annotate a return type from auth_service.py
# auth_service.py also imports from user_service.py — circular!

# Solution: TYPE_CHECKING guard + string annotations (pre-3.10)
from __future__ import annotations   # makes ALL annotations strings (lazy)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myapp.auth.service import AuthService

class UserService:
    def get_auth(self) -> AuthService:   # string at runtime, real type at type-check time
        ...

# Python 3.10+ with PEP 563 (from __future__ import annotations) is default
# Python 3.12+ "lazy annotations" (PEP 649) evaluates at access time — fixes this naturally
```

The `TYPE_CHECKING` block is only executed by type checkers (mypy sets it to `True`), not at runtime — so the import never happens in production code.

---

## Gotcha Follow-ups

**"Can `importlib.reload()` fix circular import errors?"**
No — `reload()` re-executes the module body but the circular dependency structure remains. If A imported B and B imported A, reloading either re-triggers the same cycle. `reload()` is useful for updating a module to pick up code changes in a REPL, not for resolving structural import errors.

**"Why does `__init__.py` make circular imports harder?"**
`package/__init__.py` often imports from submodules (`from .models import User`) to create a clean public API. If two submodules import each other through the package's `__init__.py`, a circular import forms through the `__init__`. Fix: import directly from the submodule (`from myapp.domain.models import User`), not through `__init__`.

---

## Under the Hood

`importlib._bootstrap._find_and_load()` is the core of the import system. It checks `sys.modules` first (fast path), then calls finders and loaders. The pre-population of `sys.modules` before `exec_module()` is intentional — it breaks infinite recursion for circular imports by returning the partial module. The partial module is a real module object (a `ModuleType` instance) with `__name__`, `__loader__`, `__package__` set, but without any of the names defined in the module body. `graphlib.TopologicalSorter` (Python 3.9+, `Lib/graphlib.py`) implements Kahn's algorithm for topological sort with cycle detection.
