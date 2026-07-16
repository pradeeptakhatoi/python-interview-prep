# Import System Internals

## Concept

`import foo` is deceptively simple. Under the hood it involves five distinct phases: cache check, meta path finders, path-based finding, loading, and initialization. Understanding this machinery lets you build plugin systems, mock modules, audit imports, and debug mysterious `ImportError`s.

### The Import Pipeline

```python
import foo

# CPython performs:
# 1. Check sys.modules['foo'] — return cached module if found
# 2. Find a finder in sys.meta_path that can locate 'foo'
# 3. Finder returns a spec (ModuleSpec) describing where 'foo' is
# 4. Create a module object and add it to sys.modules (before exec!)
# 5. Execute the module's code (load the file content)
# 6. Return the module
```

```python
import sys

# Step 1: cache check
print('os' in sys.modules)   # True after first import

# Step 2-3: finders
print(sys.meta_path)
# [BuiltinImporter, FrozenImporter, PathFinder]
# Each finder's find_spec() is called until one returns a ModuleSpec

# Step 4: sys.modules pre-population
# This is why circular imports can work if they only access attributes
# (the module exists but may be partially initialized)
```

### `sys.meta_path` Finders

```python
import sys, importlib
from importlib.machinery import ModuleSpec
from importlib.abc import MetaPathFinder, Loader
import types

class VirtualModuleFinder(MetaPathFinder):
    """Provides synthetic modules for any 'virtual.*' import."""

    VIRTUAL_MODULES = {
        'virtual.config': {'DEBUG': True, 'HOST': 'localhost'},
        'virtual.version': {'__version__': '1.0.0'},
    }

    def find_spec(self, fullname, path, target=None):
        if fullname in self.VIRTUAL_MODULES:
            return ModuleSpec(fullname, VirtualLoader(self.VIRTUAL_MODULES[fullname]))
        return None   # not our module — let other finders try

class VirtualLoader(Loader):
    def __init__(self, attrs: dict):
        self.attrs = attrs

    def create_module(self, spec):
        return None   # use default module creation

    def exec_module(self, module):
        module.__dict__.update(self.attrs)
        module.__file__ = None
        module.__package__ = ''

# Install:
sys.meta_path.insert(0, VirtualModuleFinder())

import virtual.config
print(virtual.config.DEBUG)   # True — no file on disk!
```

### Circular Import Resolution

The key: `sys.modules` is populated BEFORE the module code runs. This lets import A while A is loading (circular), but only attributes defined before the circular point are available:

```python
# a.py
import b                    # triggers b.py to load
print(b.B_VALUE)            # works if B_VALUE is defined before 'import a' in b.py

B_VALUE_FROM_A = 42

# b.py
import a                    # a is already in sys.modules (partially initialized)
print(a.B_VALUE_FROM_A)    # AttributeError! Not defined yet when b.py first ran

A_VALUE_PLACEHOLDER = 'placeholder'  # defined before circular point

# Solution: restructure, or use lazy imports, or use importlib.import_module() inside functions
```

```python
# Best fix: move shared things to a third module
# shared.py — no imports from a or b
SHARED_VALUE = 99

# a.py
from shared import SHARED_VALUE  # no cycle

# b.py
from shared import SHARED_VALUE  # no cycle
```

### The `importlib.machinery` API

```python
import importlib.util
import importlib.machinery

# Load a module from an arbitrary path:
spec = importlib.util.spec_from_file_location(
    "my_module",
    "/path/to/my_module.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules['my_module'] = module   # register before exec to handle circular imports
spec.loader.exec_module(module)

print(module.MY_FUNCTION())   # call something from the dynamically loaded module

# Reload a module (useful in REPL or hot-reload scenarios):
import importlib
importlib.reload(my_module)   # re-executes module code in existing module object
```

### Source Transformation: AST-Modifying Loader

```python
import ast, sys, types
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec, SourceFileLoader

class ProfilingLoader(Loader):
    """Injects timing calls around every function definition."""

    def __init__(self, source_path: str):
        self.source_path = source_path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        with open(self.source_path) as f:
            source = f.read()

        tree = ast.parse(source, self.source_path)
        # Transform AST here (e.g., add decorators to all functions)
        # tree = ProfilerTransformer().visit(tree)
        # ast.fix_missing_locations(tree)

        code = compile(tree, self.source_path, 'exec')
        exec(code, module.__dict__)
```

### `sys.modules` Manipulation

```python
import sys

# Replace a module with a mock (useful in tests):
import types
mock_requests = types.ModuleType('requests')
mock_requests.get = lambda url, **kw: type('R', (), {'status_code': 200, 'json': lambda self: {}})()
sys.modules['requests'] = mock_requests

import requests   # returns mock_requests
print(requests.get("https://...").status_code)   # 200

# Remove module to force reimport:
if 'mymodule' in sys.modules:
    del sys.modules['mymodule']
import mymodule   # fresh import

# Why this matters: importlib.reload() vs del + reimport
# reload() re-executes in the SAME module object (references stay valid)
# del + reimport creates a NEW module object (old references become stale)
```

---

## Interview Questions

### Q1: Walk me through exactly what happens when Python executes `import json`.

**Model answer:**
1. **Cache check:** `if 'json' in sys.modules: return sys.modules['json']`. If already imported, skip everything else.
2. **Meta path search:** iterate `sys.meta_path` (default: `[BuiltinImporter, FrozenImporter, PathFinder]`). Call `finder.find_spec('json', None, None)` on each.
3. `BuiltinImporter` checks if 'json' is a built-in C extension — it isn't.
4. `FrozenImporter` checks if 'json' is frozen into the interpreter — it isn't.
5. `PathFinder` searches `sys.path` for `json.py` or `json/__init__.py`. Finds it in stdlib.
6. **ModuleSpec created:** contains the file path, loader class, submodule search paths.
7. **Module object created:** `types.ModuleType('json')` with `__name__`, `__spec__`, `__file__`, etc.
8. **Pre-populate `sys.modules`:** `sys.modules['json'] = module` — done BEFORE exec, to handle circular imports.
9. **Execute:** `loader.exec_module(module)` — runs the source code in the module's namespace.
10. **Return:** `sys.modules['json']`.

### Q2: Why does Python add a module to `sys.modules` before executing it?

**Model answer:**
To handle circular imports. If A imports B and B imports A:

```
Import A:
  sys.modules['a'] = <module 'a' (partially initialized)>  ← added NOW
  exec a.py:
    import b
      sys.modules['b'] = <module 'b' (partially initialized)>
      exec b.py:
        import a  ← sys.modules['a'] exists! Return partially-initialized a
        use a.SOMETHING  ← only works if SOMETHING was defined before 'import b' in a.py
```

Without pre-population: `import a` in b.py would trigger a new import of a.py → infinite recursion → `RecursionError`.

With pre-population: circular imports are resolved by returning the partially-initialized module. The risk is accessing attributes of the partial module that haven't been defined yet — the source of most circular import `AttributeError`s.

### Q3: What is a meta path finder and when would you write one?

**Model answer:**
A meta path finder is an object in `sys.meta_path` with a `find_spec(fullname, path, target)` method. Python calls each finder in order until one returns a `ModuleSpec` (found) or `None` (pass to next).

Write one when:
1. **Synthetic/virtual modules:** provide modules with no files on disk (e.g., config from environment variables, database-backed modules).
2. **Redirecting imports:** transparently rename deprecated modules (`import old_name` → loads `new_name`).
3. **Encrypted source:** decrypt source code before executing.
4. **Remote imports:** load modules from a URL, database, or package registry (experimental/unusual).
5. **Import auditing:** log or deny certain imports (security sandboxes).

```python
class DeprecationRedirectFinder(MetaPathFinder):
    REDIRECTS = {'old_package.utils': 'new_package.utils'}

    def find_spec(self, fullname, path, target=None):
        if fullname in self.REDIRECTS:
            new_name = self.REDIRECTS[fullname]
            import warnings
            warnings.warn(f"Import {fullname!r} is deprecated, use {new_name!r}", DeprecationWarning, stacklevel=2)
            # Return spec for the new module but mapped to old name:
            spec = importlib.util.find_spec(new_name)
            if spec:
                spec.name = fullname  # pretend it's the old name
            return spec
        return None
```

### Q4: What happens when you `importlib.reload()` a module?

**Model answer:**
`reload()` re-executes the module's source code in the **existing module object's `__dict__`**. It does NOT create a new module object:

- Names defined in the reloaded module are updated.
- Names that were removed in the new version remain in the old `__dict__` (no cleanup).
- References held by other modules to functions/classes from the old version point to the old objects — they are NOT updated.

```python
import mymodule

old_func = mymodule.my_function   # hold a reference

importlib.reload(mymodule)

# mymodule.my_function is now the NEW function object
# old_func still points to the OLD function object
# Code that does `from mymodule import my_function` at import time
# has the old object and is NOT updated by reload!
```

This is why hot-reloading is fragile — you must also update all cached references. Libraries like `watchdog` + careful reference management can make it work, but it's not the default.

### Q5: How do namespace packages work and how do they differ from regular packages?

**Model answer:**
A regular package requires `__init__.py`. A namespace package (PEP 420) does NOT.

Regular package:
```
mypackage/
    __init__.py   ← required
    module.py
```

Namespace package: multiple directories across `sys.path` contribute to the same package:
```
/path1/myns/
    module_a.py   ← no __init__.py
/path2/myns/
    module_b.py   ← no __init__.py

# sys.path = ['/path1', '/path2']
# import myns.module_a  → /path1/myns/module_a.py
# import myns.module_b  → /path2/myns/module_b.py
# myns is a namespace package spanning both directories
```

The key difference: when `PathFinder` searches for a package and finds a directory without `__init__.py`, it continues searching all `sys.path` entries for more contributions to the same namespace. The namespace package's `__path__` is a list of all contributing directories.

Used for: splitting a large package across multiple repos/distributions while sharing a common import prefix.

---

## Gotcha Follow-ups

**"Why does `from package import *` only import what's in `__all__`?"**
`import *` imports either the names listed in `__all__` (if defined), or all names not starting with `_` (if `__all__` is not defined). Without `__all__`, every module-level name is exported — this is why well-designed public APIs define `__all__` explicitly to control their surface area.

**"What's the difference between `import foo.bar` and `from foo import bar`?"**
Both resolve and execute `foo/bar.py`. The difference is what name is bound in the local namespace. `import foo.bar` binds `foo` (the parent package), accessed as `foo.bar`. `from foo import bar` binds `bar` directly. In both cases, `foo`, `foo.bar` end up in `sys.modules`.

---

## Under the Hood

The import system is largely implemented in pure Python (`Lib/importlib/_bootstrap.py`, `Lib/importlib/_bootstrap_external.py`). These modules are frozen into the interpreter (`Python/frozen.c`) and bootstrapped before any user code runs. The C implementation of `__import__` (`Python/ceval.c`, `IMPORT_NAME` opcode) calls `importlib.__import__()` which delegates to the bootstrap code. `sys.meta_path` is a regular Python list — modifications take effect immediately for all subsequent imports.
