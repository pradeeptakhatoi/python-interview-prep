# Custom Import Hooks: MetaPathFinder and Loader

## Concept

Python's import system is fully extensible. Every `import` statement goes through a pipeline you can intercept and customize. This is how tools like `coverage.py`, `pytest`, mock libraries, encrypted bytecode loaders, and remote module loaders work.

### Import System Pipeline

```
import foo
    ↓
1. sys.modules cache check → if found, return immediately
2. sys.meta_path finders → first finder that knows about 'foo' handles it
3. sys.path_hooks + sys.path → file-system based search
4. Loader.create_module() → create module object
5. Loader.exec_module() → execute module code in module's namespace
6. sys.modules['foo'] = module → cache it
    ↓
return module object
```

### `sys.modules` — The Module Cache

```python
import sys
import os

print('os' in sys.modules)  # True — already imported

# Force reimport (dangerous in production — breaks isinstance checks):
del sys.modules['os']
import os   # re-executes os/__init__.py

# Module replacement (used by mock libraries):
import types
fake_os = types.ModuleType('os')
fake_os.path = types.ModuleType('os.path')
sys.modules['os'] = fake_os  # subsequent 'import os' returns fake_os
```

### `sys.meta_path` — The Finder Chain

```python
import sys
print(sys.meta_path)
# [
#   <_frozen_importlib.BuiltinImporter>,      # built-in modules (sys, builtins)
#   <_frozen_importlib.FrozenImporter>,       # frozen modules
#   <_frozen_importlib_external.PathFinder>,  # file system (uses sys.path)
# ]
```

Each finder must implement `find_spec(fullname, path, target=None)`. If it can handle the import, it returns a `ModuleSpec`. If not, it returns `None`.

### Implementing a Custom MetaPathFinder

```python
import sys
import importlib
import importlib.abc
import importlib.machinery
import types

class VirtualModuleFinder(importlib.abc.MetaPathFinder):
    """Serves synthetic modules from a dict without touching the filesystem."""

    VIRTUAL_MODULES = {
        'config': """
HOST = 'localhost'
PORT = 5432
DEBUG = False
""",
        'version': """
__version__ = '1.2.3'
RELEASE_DATE = '2024-01-15'
""",
    }

    def find_spec(self, fullname, path, target=None):
        if fullname in self.VIRTUAL_MODULES:
            return importlib.machinery.ModuleSpec(
                name=fullname,
                loader=VirtualModuleLoader(self.VIRTUAL_MODULES[fullname]),
                is_package=False,
            )
        return None  # not handled — pass to next finder


class VirtualModuleLoader(importlib.abc.Loader):
    def __init__(self, source: str):
        self._source = source

    def create_module(self, spec):
        return None  # use default module creation

    def exec_module(self, module):
        exec(self._source, module.__dict__)

# Install at the FRONT of meta_path to take priority:
sys.meta_path.insert(0, VirtualModuleFinder())

# Now these modules are importable even though no files exist:
import config
print(config.HOST)   # 'localhost'

import version
print(version.__version__)   # '1.2.3'
```

### Module Spec and ModuleType Details

```python
import importlib.machinery
import importlib.abc
import types

# What a ModuleSpec contains:
spec = importlib.machinery.ModuleSpec(
    name='mymodule',
    loader=some_loader,
    origin='/path/to/mymodule.py',   # where it came from
    is_package=False,
)
spec.submodule_search_locations = None  # None for non-packages; list for packages

# Manual module creation:
module = types.ModuleType('mymodule')
module.__spec__ = spec
module.__loader__ = some_loader
module.__package__ = 'mypackage'
module.__file__ = '/path/to/mymodule.py'
```

### Source Transformation Hook (Bytecode Preprocessing)

```python
import sys
import importlib.abc
import importlib.machinery
import importlib.util
import ast

class TransformingFinder(importlib.abc.MetaPathFinder):
    """Intercepts .py files and transforms their AST before execution."""

    def find_spec(self, fullname, path, target=None):
        # Let the standard PathFinder find the file:
        spec = importlib.util.find_spec(fullname)
        if spec is None or spec.origin is None:
            return None
        if not spec.origin.endswith('.py'):
            return None

        # Replace the loader with our transforming loader:
        spec.loader = TransformingLoader(spec.loader)
        return spec


class TransformingLoader(importlib.abc.Loader):
    def __init__(self, original_loader):
        self._orig = original_loader

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        # Read source:
        source = self._orig.get_source(module.__spec__.name)
        if source is None:
            return self._orig.exec_module(module)

        # Transform AST:
        tree = ast.parse(source)
        tree = self.transform(tree)
        ast.fix_missing_locations(tree)

        # Compile and exec:
        code = compile(tree, module.__spec__.origin, 'exec')
        exec(code, module.__dict__)

    def transform(self, tree: ast.AST) -> ast.AST:
        # Example: add a print at the start of every function
        class Inserter(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                print_call = ast.Expr(
                    ast.Call(
                        ast.Name('print', ast.Load()),
                        [ast.Constant(f"Calling {node.name}")],
                        []
                    )
                )
                node.body.insert(0, print_call)
                return node
        return Inserter().visit(tree)
```

### Path Hooks — Importing from Non-Standard Sources

```python
import sys
import importlib.abc
import importlib.machinery
import zipfile
import io

class ZipImporter(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Import Python modules from a zip file."""

    def __init__(self, zip_path: str):
        self._zip_path = zip_path
        self._zip = zipfile.ZipFile(zip_path)
        self._modules = {
            name.replace('/', '.').removesuffix('.py')
            for name in self._zip.namelist()
            if name.endswith('.py')
        }

    def find_spec(self, fullname, path, target=None):
        if fullname in self._modules:
            return importlib.machinery.ModuleSpec(
                name=fullname,
                loader=self,
                origin=f"{self._zip_path}:{fullname.replace('.', '/')}.py"
            )
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        path = module.__spec__.name.replace('.', '/') + '.py'
        source = self._zip.read(path).decode()
        code = compile(source, module.__spec__.origin, 'exec')
        exec(code, module.__dict__)

# Usage:
sys.meta_path.insert(0, ZipImporter('modules.zip'))
import my_zipped_module  # loaded from modules.zip/my_zipped_module.py
```

---

## Interview Questions

### Q1: What is `sys.meta_path` and how does an import request flow through it?

**Model answer:**  
`sys.meta_path` is a list of **meta path finders** — objects that implement `find_spec(fullname, path, target)`. When `import foo` is executed:

1. Check `sys.modules['foo']` — if found, return immediately (cached).
2. Iterate `sys.meta_path` left to right, calling `finder.find_spec('foo', None, None)` on each.
3. First finder that returns a non-None `ModuleSpec` wins.
4. The spec's loader's `create_module(spec)` is called — returns `None` to use default module creation.
5. Module is added to `sys.modules['foo']` (important: before `exec_module` to handle circular imports).
6. `loader.exec_module(module)` is called — executes the module code in `module.__dict__`.

The three default finders:
- `BuiltinImporter` — handles C built-ins (`sys`, `builtins`, `_io`, etc.)
- `FrozenImporter` — handles frozen modules (code embedded in the interpreter)
- `PathFinder` — handles file system imports via `sys.path`

### Q2: How do you write an import hook that caches compiled bytecode for source-transformed modules?

**Model answer:**  
Standard `.pyc` caching (`__pycache__`) only works for unmodified source. For custom transformations, you need to manage the cache yourself:

```python
import hashlib
import marshal
import struct
import time
import importlib.abc

class CachingTransformLoader(importlib.abc.Loader):
    MAGIC = b'CUSTOM\x01'

    def get_cache_path(self, module_path: str) -> str:
        h = hashlib.sha256(module_path.encode()).hexdigest()[:8]
        return f"/tmp/custom_cache_{h}.pyc"

    def load_from_cache(self, source_path: str, source: bytes):
        cache_path = self.get_cache_path(source_path)
        try:
            with open(cache_path, 'rb') as f:
                magic = f.read(6)
                if magic != self.MAGIC:
                    return None
                cached_mtime = struct.unpack('<Q', f.read(8))[0]
                source_mtime = int(os.path.getmtime(source_path) * 1e9)
                if cached_mtime != source_mtime:
                    return None
                return marshal.load(f)
        except (FileNotFoundError, EOFError, struct.error):
            return None

    def save_to_cache(self, source_path: str, code):
        cache_path = self.get_cache_path(source_path)
        mtime = int(os.path.getmtime(source_path) * 1e9)
        with open(cache_path, 'wb') as f:
            f.write(self.MAGIC)
            f.write(struct.pack('<Q', mtime))
            marshal.dump(code, f)

    def exec_module(self, module):
        source_path = module.__spec__.origin
        with open(source_path, 'rb') as f:
            source = f.read()

        code = self.load_from_cache(source_path, source)
        if code is None:
            transformed_source = self.transform(source.decode())
            tree = ast.parse(transformed_source)
            ast.fix_missing_locations(tree)
            code = compile(tree, source_path, 'exec')
            self.save_to_cache(source_path, code)

        exec(code, module.__dict__)
```

### Q3: How do circular imports work? Why does Python add the module to `sys.modules` before executing it?

**Model answer:**  
Python adds the module to `sys.modules` immediately after creating the module object but BEFORE executing its code. This is intentional to handle circular imports:

```
# a.py:
import b
x = 10

# b.py:
import a
y = a.x  # may fail if a hasn't defined x yet
```

Execution flow:
1. `import a` — creates `module_a`, adds `sys.modules['a'] = module_a`, starts executing `a.py`.
2. `a.py` hits `import b` — creates `module_b`, adds `sys.modules['b'] = module_b`, starts executing `b.py`.
3. `b.py` hits `import a` — finds `sys.modules['a']` (partially initialized!) — returns it immediately.
4. `b.py` tries `a.x` — but `a.py` only defined `x = 10` AFTER `import b`, so `x` doesn't exist yet on `module_a`. `AttributeError`.

**Fix patterns:**
1. **Reorder imports** — move `import b` to after `x = 10` in a.py.
2. **Import inside function/method** — defer the import until after all module-level code runs.
3. **Restructure packages** — extract shared types to a third module that neither a nor b imports.
4. **`TYPE_CHECKING` guard** — for type hints only:
```python
from __future__ import annotations  # all annotations are strings (lazy)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from b import B  # not executed at runtime
```

### Q4: Implement an import hook that logs all import times.

**Model answer:**  
```python
import sys
import time
import importlib.abc
import importlib.machinery

class TimingFinder(importlib.abc.MetaPathFinder):
    def __init__(self):
        self._import_times = {}
        self._active = set()  # prevent re-entrancy on circular imports

    def find_spec(self, fullname, path, target=None):
        if fullname in self._active:
            return None

        # Find via the remaining finders (excluding self):
        idx = sys.meta_path.index(self)
        for finder in sys.meta_path[idx + 1:]:
            spec = finder.find_spec(fullname, path, target)
            if spec is not None:
                # Wrap the loader:
                original_loader = spec.loader
                spec.loader = TimingLoader(original_loader, fullname, self._import_times)
                return spec
        return None

    def report(self):
        for name, elapsed in sorted(self._import_times.items(), key=lambda x: -x[1]):
            print(f"{elapsed*1000:.1f}ms  {name}")


class TimingLoader(importlib.abc.Loader):
    def __init__(self, original, name, times_dict):
        self._orig = original
        self._name = name
        self._times = times_dict

    def create_module(self, spec):
        return getattr(self._orig, 'create_module', lambda s: None)(spec)

    def exec_module(self, module):
        start = time.perf_counter()
        self._orig.exec_module(module)
        self._times[self._name] = time.perf_counter() - start

timer = TimingFinder()
sys.meta_path.insert(0, timer)

import json
import pathlib
import urllib.parse

sys.meta_path.remove(timer)
timer.report()
```

### Q5: What is `importlib.resources` and how does it differ from `__file__`-based resource loading?

**Model answer:**  
`importlib.resources` (Python 3.7+, improved in 3.9+) provides access to data files inside packages without relying on `__file__` paths.

**Problem with `__file__`-based approach:**
```python
import os
# BAD: breaks when package is in a zip (zipimport), frozen, or namespace package
resource_path = os.path.join(os.path.dirname(__file__), 'data', 'config.json')
```

**Correct approach:**
```python
import importlib.resources as ir

# Python 3.9+ syntax:
def load_config():
    # Works whether the package is on disk, in a zip, or frozen:
    ref = ir.files('mypackage') / 'data' / 'config.json'
    with ir.as_file(ref) as path:
        return json.loads(path.read_text())

# Or directly:
def load_config_v2():
    data = (ir.files('mypackage') / 'data' / 'config.json').read_text()
    return json.loads(data)
```

`importlib.resources` works with custom loaders because it uses the module's `__spec__` and loader's `get_data()` method to read resources, which is virtualized. A zip importer, remote loader, or any custom loader can implement `get_data()` to serve resources correctly.

---

## Gotcha Follow-ups

**"What's the difference between `sys.meta_path` and `sys.path_hooks`?"**  
`sys.meta_path` contains finders that handle ANY import, regardless of path (including built-ins, virtual modules, database-backed modules). `sys.path_hooks` contains callables that create path-based finders for specific entries in `sys.path` — they only handle file-system-like imports. Each entry in `sys.path` is tried against each `sys.path_hooks` callable; if one returns a finder (not raises `ImportError`), that finder handles imports from that path entry. Zipfile imports work via `sys.path_hooks` — `.zip` files in `sys.path` are handled by `zipimport.zipimporter`.

**"Can you use an import hook to implement encrypted Python modules?"**  
Yes — a loader can read an encrypted `.pyc`, decrypt it, and pass the decrypted bytecode to `marshal.loads()` + `exec()`. This is a common approach for commercial Python software protection. The key concern: the decryption key must be embedded somewhere, and once the bytecode is in memory, it's readable (Python is not designed for strong code obfuscation). This provides minimal practical security but prevents casual inspection.

---

## Under the Hood

The import machinery is in `Lib/importlib/_bootstrap.py` (frozen into the interpreter) and `Lib/importlib/_bootstrap_external.py` (file-system specific). The `__import__` built-in calls `importlib._bootstrap._find_and_load()`. In CPython, `importlib` is bootstrapped very early during interpreter initialization, before even `sys` is fully initialized, which is why `_bootstrap.py` is frozen (cannot use normal imports to load itself).

The `sys.modules` dict is pre-populated with core modules during `Py_Initialize()`. This is why modules like `sys`, `builtins`, and `_warnings` are always available before any import runs.
