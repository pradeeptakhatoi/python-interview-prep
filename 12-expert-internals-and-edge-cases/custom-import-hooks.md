# Custom Import Hooks: MetaPathFinder and Loader

## Concept

Python's import system is fully extensible. By installing custom `MetaPathFinder` and `Loader` objects into `sys.meta_path`, you can intercept any import, load modules from non-standard sources (databases, URLs, encrypted files, generated code), or transform source code before execution. This is how coverage tools, import rewriters (pytest assertion rewriting), and encrypted-module systems work.

### The Import Pipeline

```
import foo
  ↓
sys.modules cache check   ← fast path if already imported
  ↓ (miss)
for finder in sys.meta_path:   ← default: [BuiltinImporter, FrozenImporter, PathFinder]
    spec = finder.find_spec(name, path, target)
    if spec: break
  ↓
loader = spec.loader
module = types.ModuleType(name)    ← create module object
sys.modules[name] = module         ← pre-populate (handles circulars)
loader.exec_module(module)         ← execute module body in module's namespace
return module
```

### Minimal MetaPathFinder + Loader

```python
import sys
import types
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec

class VirtualModuleLoader(Loader):
    def __init__(self, name: str, source: str):
        self.name = name
        self.source = source

    def create_module(self, spec) -> types.ModuleType | None:
        return None  # use default creation (types.ModuleType)

    def exec_module(self, module: types.ModuleType) -> None:
        code = compile(self.source, f"<virtual:{self.name}>", "exec")
        exec(code, module.__dict__)

class VirtualModuleFinder(MetaPathFinder):
    def __init__(self):
        self._modules: dict[str, str] = {}

    def register(self, name: str, source: str) -> None:
        self._modules[name] = source

    def find_spec(
        self,
        fullname: str,
        path,
        target=None,
    ) -> ModuleSpec | None:
        if fullname in self._modules:
            loader = VirtualModuleLoader(fullname, self._modules[fullname])
            return ModuleSpec(fullname, loader)
        return None   # not our module — let next finder try

# Install the finder:
finder = VirtualModuleFinder()
finder.register("hello_virtual", """
def greet(name):
    return f"Hello, {name}! (from virtual module)"
""")

sys.meta_path.insert(0, finder)   # insert FIRST to take priority

import hello_virtual
print(hello_virtual.greet("World"))   # Hello, World! (from virtual module)

# Cleanup:
sys.meta_path.remove(finder)
del sys.modules.get('hello_virtual', None) and sys.modules.pop('hello_virtual')
```

### Source-Transforming Loader (Import Hook for Code Rewriting)

```python
import sys, ast, types, importlib
from importlib.machinery import ModuleSpec, SourceFileLoader
from importlib.util import spec_from_file_location

class InstrumentingLoader(SourceFileLoader):
    """Rewrites source code to add call counting instrumentation."""

    def get_code(self, fullname: str):
        source = self.get_source(fullname)
        if source is None:
            return super().get_code(fullname)

        # Parse → transform AST → compile:
        tree = ast.parse(source, filename=self.path)
        tree = CallCountTransformer().visit(tree)
        ast.fix_missing_locations(tree)
        return compile(tree, self.path, "exec")

class CallCountTransformer(ast.NodeTransformer):
    """Inserts a print before each function call."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)  # transform children first
        # Wrap each call with a print:
        wrapped = ast.Call(
            func=ast.Name(id='print', ctx=ast.Load()),
            args=[ast.Constant(value=f"CALL: {ast.dump(node.func)[:40]}")],
            keywords=[],
        )
        return ast.IfExp(  # print(...) or original_call
            test=ast.Constant(value=True),
            body=node,
            orelse=node,
        )

class InstrumentingFinder(MetaPathFinder):
    def __init__(self, package: str):
        self.package = package

    def find_spec(self, fullname, path, target=None):
        if not fullname.startswith(self.package):
            return None
        # Delegate to the normal file-based spec finding:
        spec = importlib.util.find_spec(fullname)
        if spec and spec.origin and spec.origin.endswith('.py'):
            return spec_from_file_location(
                fullname,
                spec.origin,
                loader=InstrumentingLoader(fullname, spec.origin),
            )
        return None
```

### Import Hook for Loading from a Database

```python
import sys, types, sqlite3
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec

class DatabaseLoader(Loader):
    def __init__(self, name: str, db_path: str):
        self.name = name
        self.db_path = db_path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT source FROM modules WHERE name = ?", (self.name,)
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            raise ImportError(f"Module {self.name!r} not found in database")
        exec(compile(row[0], f"<db:{self.name}>", "exec"), module.__dict__)

class DatabaseFinder(MetaPathFinder):
    def __init__(self, db_path: str, prefix: str = "db_"):
        self.db_path = db_path
        self.prefix = prefix

    def find_spec(self, fullname, path, target=None):
        if fullname.startswith(self.prefix):
            loader = DatabaseLoader(fullname, self.db_path)
            return ModuleSpec(fullname, loader, origin=f"db:{self.db_path}")
        return None

# Setup:
# conn = sqlite3.connect('modules.db')
# conn.execute("CREATE TABLE modules (name TEXT, source TEXT)")
# conn.execute("INSERT INTO modules VALUES ('db_utils', 'def helper(): return 42')")
# conn.commit()
# sys.meta_path.insert(0, DatabaseFinder('modules.db'))
# import db_utils
# print(db_utils.helper())  # 42
```

### Using `importlib.util` for One-Off Module Loading

```python
import importlib.util
import types

def load_module_from_path(name: str, path: str) -> types.ModuleType:
    """Load a module from a file path without installing a finder."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None:
        raise ImportError(f"Cannot find module at {path!r}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module   # pre-register for circular imports
    spec.loader.exec_module(module)
    return module

# Usage:
my_module = load_module_from_path("my_plugin", "/path/to/plugin.py")
```

---

## Interview Questions

### Q1: Explain the full import pipeline that executes when Python processes `import foo`.

**Model answer:**
1. **`sys.modules` cache:** check `sys.modules['foo']`. If present, return it immediately.
2. **`sys.meta_path` finders:** iterate `sys.meta_path` (default: `BuiltinImporter`, `FrozenImporter`, `PathFinder`). Call `finder.find_spec('foo', None, None)` on each. First non-`None` result wins.
3. **Module spec:** the returned `ModuleSpec` contains the module name, loader, origin (file path), and submodule_search_locations.
4. **Create module object:** call `spec.loader.create_module(spec)`. If `None`, create a default `types.ModuleType(name)`.
5. **Set `__spec__`, `__name__`, `__loader__`, `__package__`, `__path__`** on the module.
6. **Pre-populate `sys.modules[name] = module`** — BEFORE executing the module body. This breaks circular import cycles.
7. **Execute:** `spec.loader.exec_module(module)` — runs the module body in `module.__dict__`.
8. If step 7 raises: remove from `sys.modules` and propagate the exception.

The pre-population in step 6 is the critical subtlety: if `foo.py` imports `bar.py` which imports `foo`, bar gets the partial `foo` module (step 6 already ran) rather than infinite recursion.

### Q2: What's the difference between `sys.meta_path` and `sys.path_hooks`?

**Model answer:**
`sys.meta_path` is checked FIRST for ALL imports. A `MetaPathFinder` receives the full module name and can intercept any import regardless of where Python normally looks.

`sys.path_hooks` are called by `PathFinder` (the last entry in `sys.meta_path`) when searching for a module on `sys.path`. Each entry in `sys.path_hooks` is a callable that takes a path entry and returns a `FileFinder`-like object, or raises `ImportError` if it doesn't handle that path entry.

```python
# sys.meta_path: intercept ALL imports (highest priority)
class MyFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target):
        # Called for EVERY import, including builtins
        ...

# sys.path_hooks: intercept imports from specific sys.path entries
import zipimport
# zipimport.zipimporter is in sys.path_hooks by default — handles .egg/.zip:
print(sys.path_hooks)
# [<class 'zipimport.zipimporter'>, <function FileFinder.path_hook...>]

# Custom path hook: load from a custom directory format
def my_path_hook(path):
    if path.endswith('.mydir'):
        return MyDirFinder(path)
    raise ImportError

sys.path_hooks.insert(0, my_path_hook)
sys.path.append('/some/path.mydir')
# Now 'import foo' may load from MyDirFinder
```

Use `sys.meta_path` for: virtual modules, encrypted modules, database-backed modules, global import transformation. Use `sys.path_hooks` for: custom archive formats, custom directory structures.

### Q3: How does pytest's assertion rewriting work as an import hook?

**Model answer:**
pytest installs an `AssertionRewritingHook` on `sys.meta_path` that intercepts imports of test files and rewrites `assert` statements to provide detailed failure output.

The hook:
1. `find_spec()` is called for test module imports.
2. It reads the source, parses the AST.
3. `AssertionRewriter(ast.NodeTransformer)` transforms every `assert` statement:
   - Captures subexpressions and their values before the assertion
   - Generates code to produce a detailed failure message: `assert a == b → if not (a == b): raise AssertionError(f"a={a!r}, b={b!r}")`
4. Compiles the rewritten AST.
5. Writes the rewritten `.pyc` to cache (with a different magic number to distinguish from normal `.pyc`).

```python
# Original:
assert result == expected

# After rewriting (simplified):
@py_result = result
@py_expected = expected
if not (@py_result == @py_expected):
    raise AssertionError(
        f"assert {@py_result!r} == {py_expected!r}\n"
        f"  where {py_result!r} = result\n"
        f"  and {py_expected!r} = expected"
    )

# Register for non-test modules:
# import pytest; pytest.register_assert_rewrite('my_helper')
```

This is pure Python, no C required — the import hook + AST transformation is entirely in `_pytest/assertion/rewrite.py`.

### Q4: How do you unload a module and force reimport?

**Model answer:**

```python
import sys
import importlib

# Reload (same module object, re-executes body):
import mymodule
importlib.reload(mymodule)
# ⚠ Old references to mymodule's objects remain; new imports get new objects

# Full unload + fresh reimport (new module object):
if 'mymodule' in sys.modules:
    del sys.modules['mymodule']

import mymodule   # fresh import — new module object

# Unload a package and all its submodules:
def unload_package(package_name: str) -> None:
    keys = [k for k in sys.modules if k == package_name or k.startswith(package_name + '.')]
    for key in keys:
        del sys.modules[key]

# ⚠ Gotchas:
# 1. importlib.reload() re-executes the module body in the SAME module dict
# 2. Functions defined BEFORE reload keep the old module's globals
# 3. Class instances created before reload are instances of the OLD class
# 4. del sys.modules creates a new object — old references become orphaned

def demonstrate_reload_issue():
    import mymodule
    old_cls = mymodule.MyClass

    importlib.reload(mymodule)
    new_cls = mymodule.MyClass

    obj = old_cls()
    print(isinstance(obj, new_cls))   # False! Different class objects
    print(isinstance(obj, old_cls))   # True
```

### Q5: How would you implement an import hook that loads modules from an encrypted source?

**Model answer:**

```python
import sys, types, hashlib
from cryptography.fernet import Fernet
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec

class EncryptedLoader(Loader):
    def __init__(self, name: str, ciphertext: bytes, key: bytes):
        self.name = name
        self.ciphertext = ciphertext
        self.key = key

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        fernet = Fernet(self.key)
        source = fernet.decrypt(self.ciphertext).decode('utf-8')
        # Compile with a fake filename so tracebacks are readable:
        code = compile(source, f"<encrypted:{self.name}>", "exec")
        exec(code, module.__dict__)

    def get_source(self, fullname):
        return None   # don't expose decrypted source

class EncryptedFinder(MetaPathFinder):
    def __init__(self, key: bytes):
        self._key = key
        self._modules: dict[str, bytes] = {}  # name → encrypted bytes

    def add_module(self, name: str, source: str) -> None:
        fernet = Fernet(self._key)
        self._modules[name] = fernet.encrypt(source.encode())

    def find_spec(self, fullname, path, target=None):
        if fullname in self._modules:
            loader = EncryptedLoader(fullname, self._modules[fullname], self._key)
            return ModuleSpec(fullname, loader, origin=f"<encrypted:{fullname}>")
        return None

# Usage:
key = Fernet.generate_key()
finder = EncryptedFinder(key)
finder.add_module("secret_algo", """
def compute(x):
    return x ** 3 + 2 * x + 1  # proprietary algorithm!
""")
sys.meta_path.insert(0, finder)
import secret_algo
print(secret_algo.compute(3))  # 34

# Security consideration: the key must be protected at runtime.
# dis.dis(secret_algo.compute) still works — once executed, the code object is in memory.
# True IP protection requires a native extension or Cython compiled extension.
```

---

## Gotcha Follow-ups

**"What's the risk of inserting a finder at position 0 in `sys.meta_path`?"**
It will be called for EVERY import, including built-ins like `sys`, `os`, `types`. If your `find_spec` is slow (DB query, network call, slow glob), it will slow down every import. Use fast short-circuit checks: `if not fullname.startswith('my_prefix'): return None` before doing expensive work.

**"Can an import hook see `from foo import bar` separately from `import foo`?"**
No — `from foo import bar` still calls `find_spec('foo', ...)`, executes `foo`, then does `bar = foo.bar`. The import hook sees `'foo'` as the module name, not `'foo.bar'`. Submodule imports (`from foo.baz import bar`) call `find_spec('foo.baz', foo.__path__, ...)`.

---

## Under the Hood

`importlib._bootstrap._find_and_load()` (`Lib/importlib/_bootstrap.py`): the core import function. It's written in Python but executed from C (`Python/import.c: PyImport_ImportModuleLevelObject()`). `_find_spec()` iterates `sys.meta_path` and calls `finder.find_spec()`. The separation into finder + loader was introduced in Python 3.4 (PEP 302 originally had combined "importer" objects). `ModuleSpec` stores: `name`, `loader`, `origin`, `submodule_search_locations`, `loader_state`, `cached` (`.pyc` path), `has_location`. The importlib bootstrap module itself is frozen (compiled into the CPython binary) to avoid chicken-and-egg problems — you can't import `importlib` to run the import system.
