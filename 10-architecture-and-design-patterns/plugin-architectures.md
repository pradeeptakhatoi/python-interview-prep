# Plugin Architectures: entry_points and Dynamic Loading

## Concept

Plugin architectures allow third-party code to extend an application without modifying the core. Python has three main mechanisms: `importlib.metadata.entry_points` (packaging-based), dynamic module loading, and class-registration hooks.

### `entry_points` — Packaging-Based Plugin Discovery

```toml
# Plugin package's pyproject.toml:
[project.entry-points."myapp.exporters"]
csv = "myplugin_csv:CSVExporter"
excel = "myplugin_excel:ExcelExporter"

[project.entry-points."myapp.commands"]
export = "myplugin_csv.cli:export_command"
```

```python
# Core application: discovers plugins at runtime
from importlib.metadata import entry_points
from typing import Protocol

class Exporter(Protocol):
    """Plugin interface."""
    name: str
    def export(self, data: list[dict], output_path: str) -> None: ...

def load_exporters() -> dict[str, type[Exporter]]:
    """Discover all installed exporters."""
    eps = entry_points(group='myapp.exporters')
    exporters = {}
    for ep in eps:
        try:
            cls = ep.load()   # imports the module and returns the attribute
            exporters[ep.name] = cls
        except Exception as e:
            logger.warning(f"Failed to load exporter {ep.name!r}: {e}")
    return exporters

# Usage:
exporters = load_exporters()
# {'csv': CSVExporter, 'excel': ExcelExporter, ...}

chosen = exporters.get(user_choice)
if chosen is None:
    raise ValueError(f"No exporter {user_choice!r}. Available: {list(exporters)}")
chosen().export(data, output_path)
```

### `__init_subclass__` — Auto-Registration

```python
class Plugin:
    """Base class that auto-registers all subclasses."""
    _registry: dict[str, type] = {}

    def __init_subclass__(cls, name: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if name:
            cls.plugin_name = name
            Plugin._registry[name] = cls

# Plugin authors:
class JSONPlugin(Plugin, name='json'):
    def process(self, data): ...

class XMLPlugin(Plugin, name='xml'):
    def process(self, data): ...

# Discovery:
plugin = Plugin._registry.get('json')
if plugin:
    plugin().process(data)
```

### Dynamic Loading via `importlib`

```python
import importlib
import importlib.util

def load_plugin_from_path(path: str, class_name: str):
    """Load a plugin class from an arbitrary .py file."""
    spec = importlib.util.spec_from_file_location("plugin_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)

def load_plugin_from_dotted_path(dotted_path: str):
    """Load a class from 'module.submodule:ClassName'."""
    if ':' in dotted_path:
        module_path, class_name = dotted_path.rsplit(':', 1)
    else:
        module_path, class_name = dotted_path.rsplit('.', 1)

    module = importlib.import_module(module_path)
    return getattr(module, class_name)

# Usage from config:
handler_class = load_plugin_from_dotted_path('myapp.handlers:RedisHandler')
handler = handler_class(config)
```

### Plugin Validation and Versioning

```python
from typing import Protocol, runtime_checkable
from importlib.metadata import entry_points, version
import packaging.version

@runtime_checkable
class ValidExporter(Protocol):
    name: str
    version: str
    def export(self, data: list[dict], output_path: str) -> None: ...
    def supports_format(self, fmt: str) -> bool: ...

MIN_PLUGIN_VERSION = "1.0.0"

def load_and_validate_exporters() -> dict[str, ValidExporter]:
    eps = entry_points(group='myapp.exporters')
    valid = {}
    for ep in eps:
        try:
            cls = ep.load()

            # Structural check:
            if not isinstance(cls(), ValidExporter):
                logger.warning(f"Plugin {ep.name!r} doesn't implement ValidExporter protocol")
                continue

            # Version check:
            try:
                pkg_version = version(ep.value.split('.')[0])
                if packaging.version.Version(pkg_version) < packaging.version.Version(MIN_PLUGIN_VERSION):
                    logger.warning(f"Plugin {ep.name!r} version {pkg_version} < {MIN_PLUGIN_VERSION}")
                    continue
            except Exception:
                pass  # version check is best-effort

            valid[ep.name] = cls
        except Exception as e:
            logger.error(f"Failed to load plugin {ep.name!r}: {e}", exc_info=True)

    return valid
```

---

## Interview Questions

### Q1: What are the trade-offs between entry_points vs `__init_subclass__` for plugin discovery?

**Model answer:**

| | `entry_points` | `__init_subclass__` |
|-|---------------|---------------------|
| Installation | Requires pip install | Just importing the module |
| Discovery | At runtime via metadata API | At class definition time |
| Coupling | Zero — core doesn't import plugins | Plugin must import base class |
| Order | Non-deterministic | Import order |
| Namespace isolation | Good (separate packages) | Shared class hierarchy |
| Testing | Needs installed package OR mock | Just define a subclass |

**Use `entry_points`** for: third-party plugins distributed as separate packages, cli extensions, backends selectable by config.

**Use `__init_subclass__`** for: internal plugin systems within one codebase, self-contained class hierarchies, simpler registration without packaging overhead.

### Q2: How do you prevent a buggy plugin from crashing the host application?

**Model answer:**
Isolate plugin failures:

```python
def load_plugins_safely(group: str) -> dict[str, Any]:
    results = {}
    for ep in entry_points(group=group):
        try:
            cls = ep.load()
            results[ep.name] = cls
        except ImportError as e:
            logger.warning("Plugin %r: missing dependency: %s", ep.name, e)
        except AttributeError as e:
            logger.error("Plugin %r: class not found: %s", ep.name, e)
        except Exception as e:
            logger.exception("Plugin %r: unexpected load error", ep.name)
    return results

# For runtime calls, wrap each call:
def safe_export(exporter, data, path):
    try:
        return exporter.export(data, path)
    except Exception as e:
        logger.error("Exporter %r failed: %s", type(exporter).__name__, e)
        raise ExporterError(f"Plugin failed") from e
```

For stricter isolation: run plugins in a subprocess (`multiprocessing`) or separate interpreter (`PyPy`, sub-interpreters). This is rare but appropriate for untrusted plugins.

### Q3: How do you make plugin discovery lazy (don't load all plugins at startup)?

**Model answer:**
Load metadata (entry point names/descriptions) eagerly, but load the actual classes lazily:

```python
from importlib.metadata import entry_points
from functools import cache

class LazyPluginRegistry:
    def __init__(self, group: str):
        self._group = group
        self._eps = {ep.name: ep for ep in entry_points(group=group)}

    def available(self) -> list[str]:
        return list(self._eps.keys())

    @cache
    def get(self, name: str):
        """Load plugin only when first requested."""
        ep = self._eps.get(name)
        if ep is None:
            raise KeyError(f"No plugin {name!r}. Available: {self.available()}")
        return ep.load()

registry = LazyPluginRegistry('myapp.backends')
print(registry.available())   # ['sqlite', 'postgres', 'redis'] — no imports yet
backend = registry.get('sqlite')  # only now is myplugin_sqlite imported
```

This reduces startup time and avoids importing plugins whose dependencies aren't installed.

### Q4: How do you document and enforce the plugin interface?

**Model answer:**
Use a `Protocol` for static checking and a validation function for runtime enforcement:

```python
from typing import Protocol, runtime_checkable
from abc import ABC, abstractmethod

# Option 1: Protocol (structural — zero coupling for plugin authors)
@runtime_checkable
class BackendProtocol(Protocol):
    """All plugins must implement this interface."""
    name: str
    description: str

    def connect(self, dsn: str) -> 'Connection': ...
    def disconnect(self) -> None: ...
    def execute(self, query: str, params: tuple = ()) -> list[dict]: ...

# Option 2: ABC (nominal — plugin authors explicitly inherit)
class BackendBase(ABC):
    """Install myapp-sdk to get this base class."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def connect(self, dsn: str) -> 'Connection': ...
    # ... abstract methods ...

    def validate_dsn(self, dsn: str) -> bool:
        """Provided by base — plugins get this for free."""
        return dsn.startswith(self.name + '://')

# Runtime validation:
def validate_plugin(cls) -> None:
    if not isinstance(cls(), BackendProtocol):
        missing = [m for m in ['connect', 'disconnect', 'execute']
                   if not hasattr(cls, m)]
        raise PluginError(f"Plugin {cls.__name__} missing: {missing}")
```

Document the protocol in `PLUGIN_API.md` with examples. Provide a test suite plugin authors can run: `pytest myapp/tests/plugin_compliance.py --plugin my_plugin`.

### Q5: How would you design a plugin system that supports plugin dependencies (plugin A requires plugin B)?

**Model answer:**
Use `importlib.metadata.requires()` to express dependencies, or manage them explicitly in a registry:

```python
from importlib.metadata import entry_points, requires
from graphlib import TopologicalSorter

def load_ordered_plugins(group: str) -> list:
    """Load plugins in dependency order using topological sort."""
    eps = {ep.name: ep for ep in entry_points(group=group)}

    # Build dependency graph from plugin metadata:
    # (Plugins declare dependencies via their pyproject.toml extras)
    graph = {}
    for name, ep in eps.items():
        # Plugins declare deps as: [project.entry-points."myapp.plugin.deps"]
        # dep_group = entry_points(group=f"myapp.plugin.deps.{name}")
        graph[name] = set()  # no deps by default

    # Topological sort:
    ts = TopologicalSorter(graph)
    order = list(ts.static_order())

    loaded = {}
    for name in order:
        if name in eps:
            try:
                loaded[name] = eps[name].load()
            except Exception as e:
                logger.error(f"Plugin {name!r} failed to load: {e}")

    return loaded
```

For complex dependency management: use the `entry_points` naming convention `myapp.plugins.<name>` for each plugin, and require that plugin packages declare their peer dependencies in `pyproject.toml` as package dependencies — `pip` then handles resolving compatible versions.

---

## Gotcha Follow-ups

**"What happens if two plugins register under the same entry point name?"**
`entry_points(group='myapp.backends')` returns ALL entry points in the group — including duplicates with the same `name`. You'll get a list of multiple eps with the same `name`. The `select(name='sqlite')` method returns the first match. In practice: if two packages provide the same name, it's a conflict the user must resolve by uninstalling one. Log a warning if duplicates are detected.

**"Can entry points be discovered without the package being installed?"**
No — `importlib.metadata` reads from installed package metadata in `site-packages`. For development: install the plugin as editable (`pip install -e ./plugin-pkg/`). For testing without installation: use `importlib_metadata`'s `EntryPoint` directly, or mock `entry_points()` in tests.

---

## Under the Hood

`importlib.metadata.entry_points()` reads `{package}.dist-info/entry_points.txt` files from all directories in `sys.path`. The `entry_points.txt` is a INI-style file: sections are groups, keys are entry point names, values are `module.path:attribute`. `ep.load()` calls `importlib.import_module(ep.module)` and then `getattr(module, ep.attr)`. The Python 3.9+ implementation uses `importlib.metadata.packages_distributions()` to build the index efficiently.
