"""
Custom Descriptor Implementation

Demonstrates: data descriptor (__set__ defined), non-data descriptor,
descriptor protocol, how property() is built on descriptors.
"""

from __future__ import annotations
import weakref


# =============================================================================
# 1. Non-data descriptor (read-only, no __set__)
# =============================================================================
class cached_property:
    """Descriptor that computes a value once and caches it in the instance dict.

    Non-data descriptor: has __get__ but not __set__/__delete__.
    Instance dict takes priority over non-data descriptors, so after the first
    call, the cached value in __dict__ is returned directly (no descriptor call).
    """

    def __init__(self, func):
        self._func = func
        self.__doc__ = func.__doc__
        self.__name__ = func.__name__

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self                     # accessed on the class itself
        value = self._func(obj)
        obj.__dict__[self._name] = value   # store in instance dict — future reads bypass descriptor
        return value


class Circle:
    def __init__(self, radius: float):
        self.radius = radius

    @cached_property
    def area(self) -> float:
        import math
        print("computing area...")         # only prints once
        return math.pi * self.radius ** 2

    @cached_property
    def circumference(self) -> float:
        import math
        return 2 * math.pi * self.radius


# =============================================================================
# 2. Data descriptor (has __set__ — takes priority over instance __dict__)
# =============================================================================
class Validated:
    """Data descriptor that enforces a type and optional range constraint."""

    def __set_name__(self, owner, name):
        self._public_name = name
        self._private_name = f'_{name}'   # store actual value under private name

    def __init__(self, *, type_: type, min_val=None, max_val=None):
        self._type = type_
        self._min = min_val
        self._max = max_val

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self._private_name, None)

    def __set__(self, obj, value):
        if not isinstance(value, self._type):
            raise TypeError(
                f"{self._public_name} must be {self._type.__name__}, "
                f"got {type(value).__name__}"
            )
        if self._min is not None and value < self._min:
            raise ValueError(f"{self._public_name} must be >= {self._min}")
        if self._max is not None and value > self._max:
            raise ValueError(f"{self._public_name} must be <= {self._max}")
        setattr(obj, self._private_name, value)

    def __delete__(self, obj):
        delattr(obj, self._private_name)


class Temperature:
    celsius = Validated(type_=float, min_val=-273.15)
    humidity = Validated(type_=float, min_val=0.0, max_val=100.0)

    def __init__(self, celsius: float, humidity: float):
        self.celsius = celsius
        self.humidity = humidity

    @property
    def fahrenheit(self) -> float:
        return self.celsius * 9/5 + 32


# =============================================================================
# 3. Descriptor with weak reference (avoids holding strong ref to owner)
# =============================================================================
class ObservedAttribute:
    """Descriptor that notifies observers when the attribute changes."""

    def __set_name__(self, owner, name):
        self._name = name
        self._private = f'_{name}_value'
        self._observers_attr = f'_{name}_observers'

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self._private, None)

    def __set__(self, obj, value):
        old = getattr(obj, self._private, None)
        setattr(obj, self._private, value)
        if old != value:
            self._notify(obj, old, value)

    def _notify(self, obj, old, new):
        observers = getattr(obj, self._observers_attr, [])
        # Remove dead weakrefs while notifying:
        alive = []
        for ref in observers:
            cb = ref()
            if cb is not None:
                cb(obj, self._name, old, new)
                alive.append(ref)
        setattr(obj, self._observers_attr, alive)

    def subscribe(self, obj, callback):
        if not hasattr(obj, self._observers_attr):
            setattr(obj, self._observers_attr, [])
        getattr(obj, self._observers_attr).append(weakref.ref(callback))


class Model:
    name = ObservedAttribute()
    value = ObservedAttribute()

    def __init__(self, name: str, value: float):
        self.name = name
        self.value = value


# =============================================================================
# Demo
# =============================================================================
if __name__ == '__main__':
    print("=== cached_property ===")
    c = Circle(5.0)
    print(f"area = {c.area:.4f}")    # "computing area..."
    print(f"area = {c.area:.4f}")    # no recompute — reads from __dict__
    print(f"'area' in c.__dict__: {'area' in c.__dict__}")

    print("\n=== Validated descriptor ===")
    t = Temperature(25.0, 60.0)
    print(f"{t.celsius}°C = {t.fahrenheit}°F")
    try:
        t.celsius = "hot"
    except TypeError as e:
        print(f"TypeError: {e}")
    try:
        t.celsius = -300.0
    except ValueError as e:
        print(f"ValueError: {e}")

    print("\n=== ObservedAttribute descriptor ===")
    m = Model("test", 42.0)

    def on_change(obj, attr, old, new):
        print(f"  {attr} changed: {old!r} -> {new!r}")

    Model.value.subscribe(m, on_change)
    m.value = 100.0   # triggers callback
    m.value = 100.0   # no callback (same value)
    m.value = 200.0   # triggers callback

    print("\n=== Descriptor priority: data vs non-data ===")
    # Data descriptor WINS over instance __dict__:
    t.celsius = 30.0
    t.__dict__['celsius'] = 999.0  # this would shadow a non-data descriptor
    print(f"t.celsius = {t.celsius}")  # still 30.0 — data descriptor takes priority
