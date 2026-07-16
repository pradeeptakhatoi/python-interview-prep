"""
Plugin Loader via importlib.metadata entry_points

Demonstrates:
- Defining entry_points in pyproject.toml
- Discovering and loading plugins at runtime
- Plugin protocol via typing.Protocol
- Safe loading with error isolation
- Simulated entry_point discovery without installing packages
"""

from __future__ import annotations
import importlib
import importlib.metadata
import sys
import types
from typing import Protocol, runtime_checkable, Any


# =============================================================================
# Plugin Protocol — defines the interface all plugins must implement
# =============================================================================
@runtime_checkable
class DataProcessor(Protocol):
    """Protocol defining the plugin interface."""

    name: str          # plugin identifier

    def process(self, data: dict) -> dict:
        """Transform input data and return result."""
        ...

    def validate(self, data: dict) -> bool:
        """Return True if this plugin can handle the data."""
        ...


# =============================================================================
# Concrete plugin implementations (normally in separate installed packages)
# =============================================================================
class UpperCaseProcessor:
    """Built-in plugin: uppercases all string values."""
    name = "uppercase"

    def process(self, data: dict) -> dict:
        return {k: v.upper() if isinstance(v, str) else v for k, v in data.items()}

    def validate(self, data: dict) -> bool:
        return any(isinstance(v, str) for v in data.values())


class FilterProcessor:
    """Built-in plugin: removes keys with None values."""
    name = "filter_none"

    def process(self, data: dict) -> dict:
        return {k: v for k, v in data.items() if v is not None}

    def validate(self, data: dict) -> bool:
        return any(v is None for v in data.values())


class RenameProcessor:
    """Built-in plugin: renames keys via a mapping."""
    name = "rename"

    def __init__(self, key_map: dict[str, str]):
        self._map = key_map

    def process(self, data: dict) -> dict:
        return {self._map.get(k, k): v for k, v in data.items()}

    def validate(self, data: dict) -> bool:
        return bool(set(data.keys()) & set(self._map.keys()))


# =============================================================================
# Plugin Registry — manages discovered and registered plugins
# =============================================================================
class PluginRegistry:
    """
    Discovers plugins via importlib.metadata entry_points.

    In a real package, plugins register themselves in pyproject.toml:

        [project.entry-points."myapp.processors"]
        uppercase = "mypackage.plugins:UpperCaseProcessor"
        filter_none = "mypackage.plugins:FilterProcessor"

    Then discovered via:
        importlib.metadata.entry_points(group="myapp.processors")
    """

    def __init__(self, group: str):
        self._group = group
        self._plugins: dict[str, DataProcessor] = {}
        self._errors: dict[str, Exception] = {}

    def discover(self) -> int:
        """Load all plugins registered for this group. Returns count loaded."""
        try:
            eps = importlib.metadata.entry_points(group=self._group)
        except Exception as e:
            print(f"Warning: could not query entry_points: {e}")
            return 0

        loaded = 0
        for ep in eps:
            try:
                plugin_class = ep.load()
                plugin = plugin_class()
                self._register(plugin)
                loaded += 1
            except Exception as e:
                self._errors[ep.name] = e
                print(f"Warning: failed to load plugin '{ep.name}': {e}")

        return loaded

    def register(self, plugin: DataProcessor) -> None:
        """Manually register a plugin (useful for built-ins and testing)."""
        if not isinstance(plugin, DataProcessor):
            raise TypeError(
                f"{plugin!r} does not implement the DataProcessor protocol. "
                f"Missing: {self._missing_methods(plugin)}"
            )
        self._register(plugin)

    def _register(self, plugin: DataProcessor) -> None:
        self._plugins[plugin.name] = plugin
        print(f"Registered plugin: '{plugin.name}' ({type(plugin).__name__})")

    def get(self, name: str) -> DataProcessor | None:
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        return list(self._plugins.keys())

    def process_chain(
        self,
        data: dict,
        plugin_names: list[str] | None = None
    ) -> dict:
        """
        Apply a chain of plugins to data.
        If plugin_names is None, applies all plugins whose validate() returns True.
        """
        plugins = (
            [self._plugins[n] for n in plugin_names if n in self._plugins]
            if plugin_names is not None
            else [p for p in self._plugins.values() if p.validate(data)]
        )

        result = data.copy()
        for plugin in plugins:
            try:
                result = plugin.process(result)
            except Exception as e:
                print(f"Plugin '{plugin.name}' failed: {e}, skipping")
        return result

    @staticmethod
    def _missing_methods(obj: Any) -> list[str]:
        required = {'name', 'process', 'validate'}
        return [m for m in required if not hasattr(obj, m)]

    @property
    def errors(self) -> dict[str, Exception]:
        return dict(self._errors)


# =============================================================================
# Simulating entry_point discovery without installing packages
# =============================================================================
def simulate_entry_points(registry: PluginRegistry) -> None:
    """
    Simulate what importlib.metadata would do for installed packages.
    In real usage, this is replaced by registry.discover().
    """
    # Dynamically create a fake package module and load its class:
    plugin_module = types.ModuleType("example_plugins")
    plugin_module.UpperCaseProcessor = UpperCaseProcessor
    plugin_module.FilterProcessor = FilterProcessor
    sys.modules["example_plugins"] = plugin_module

    # Simulate loading from entry_points by class path:
    for cls_name in ["UpperCaseProcessor", "FilterProcessor"]:
        cls = getattr(plugin_module, cls_name)
        registry.register(cls())


# =============================================================================
# Dynamic import by dotted path (alternative to entry_points)
# =============================================================================
def load_by_dotted_path(dotted_path: str) -> Any:
    """
    Load any Python object by dotted path.
    e.g. "mypackage.plugins:UpperCaseProcessor"
    """
    if ":" in dotted_path:
        module_path, attr = dotted_path.split(":", 1)
    else:
        module_path, _, attr = dotted_path.rpartition(".")

    module = importlib.import_module(module_path)
    return getattr(module, attr)


# =============================================================================
# Demo
# =============================================================================
if __name__ == '__main__':
    print("=== Plugin Registry Demo ===\n")

    registry = PluginRegistry(group="myapp.processors")

    # In production: registry.discover() to load from installed packages
    # Here: simulate it manually
    simulate_entry_points(registry)

    # Also manually register a configured plugin:
    rename_plugin = RenameProcessor(key_map={"user_name": "username", "user_id": "id"})
    registry.register(rename_plugin)

    print(f"\nRegistered plugins: {registry.list_plugins()}")

    print("\n=== Processing data ===")
    test_data = {
        "user_name": "alice",
        "user_id": 42,
        "email": "alice@example.com",
        "status": None,
        "score": 99,
    }
    print(f"Input:  {test_data}")

    # Auto-select applicable plugins:
    result = registry.process_chain(test_data)
    print(f"Output (auto): {result}")

    # Explicit pipeline:
    result2 = registry.process_chain(
        test_data,
        plugin_names=["filter_none", "uppercase"]
    )
    print(f"Output (explicit pipeline): {result2}")

    print("\n=== Protocol check ===")
    class BadPlugin:
        pass  # missing name, process, validate

    try:
        registry.register(BadPlugin())  # type: ignore
    except TypeError as e:
        print(f"TypeError: {e}")

    print("\n=== Dynamic import demo ===")
    sys.modules["example_plugins"].RenameProcessor = RenameProcessor
    cls = load_by_dotted_path("example_plugins:RenameProcessor")
    plugin = cls(key_map={"a": "b"})
    print(f"Loaded class: {cls}, plugin name: {plugin.name}")

    print("\n=== pyproject.toml snippet for real usage ===")
    print("""
    # In your plugin package's pyproject.toml:
    [project.entry-points."myapp.processors"]
    uppercase = "my_plugin_package.processors:UpperCaseProcessor"

    # Then in the host app:
    registry = PluginRegistry(group="myapp.processors")
    n = registry.discover()
    print(f"Discovered {n} plugins")
    """)
