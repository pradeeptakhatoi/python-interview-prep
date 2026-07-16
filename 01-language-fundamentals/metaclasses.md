# Metaclasses: type(), __new__ vs __init__, __init_subclass__

## Concept

A **metaclass** is the class of a class. Just as `int`, `str`, and `list` are instances of `type`, user-defined classes are also instances of `type` (or a custom metaclass). Metaclasses let you customize class creation — intercepting the moment a class is defined, not when it's instantiated.

```python
print(type(int))         # <class 'type'>
print(type(str))         # <class 'type'>
print(type(object))      # <class 'type'>

class MyClass: pass
print(type(MyClass))     # <class 'type'>
print(isinstance(MyClass, type))  # True — MyClass is an instance of type
```

### `type()` — Class Factory

`type(name, bases, namespace)` creates a class dynamically:

```python
# These two are equivalent:
class Point:
    x: int
    y: int
    def distance(self):
        return (self.x**2 + self.y**2)**0.5

Point = type('Point', (object,), {
    '__annotations__': {'x': int, 'y': int},
    'distance': lambda self: (self.x**2 + self.y**2)**0.5,
})

p = Point()
p.x, p.y = 3, 4
print(p.distance())  # 5.0
```

### Class Creation Process

When Python processes a `class` statement, it:

1. Collects the class body into a temporary dict (the `namespace`).
2. Determines the metaclass (from `metaclass=` kwarg, base classes, or defaults to `type`).
3. Calls `metaclass.__prepare__(name, bases, **kwargs)` → returns the namespace dict.
4. Executes the class body in that namespace.
5. Calls `metaclass(name, bases, namespace)` → this calls `metaclass.__new__` then `metaclass.__init__`.

```python
class Meta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        print(f"__prepare__: preparing namespace for {name}")
        return super().__prepare__(name, bases, **kwargs)

    def __new__(mcs, name, bases, namespace, **kwargs):
        print(f"__new__: creating class {name}")
        cls = super().__new__(mcs, name, bases, namespace)
        return cls

    def __init__(cls, name, bases, namespace, **kwargs):
        print(f"__init__: initializing class {name}")
        super().__init__(name, bases, namespace)

class MyClass(metaclass=Meta):
    pass

# Output:
# __prepare__: preparing namespace for MyClass
# __new__: creating class MyClass
# __init__: initializing class MyClass
```

### `__new__` vs `__init__` at Class Creation

- `type.__new__(mcs, name, bases, namespace)` — **creates and returns** the class object (`cls`). This is where you can modify the namespace before the class exists.
- `type.__init__(cls, name, bases, namespace)` — **initializes** the already-created class object. Less powerful — class already exists.

```python
class UpperAttrMeta(type):
    def __new__(mcs, name, bases, namespace):
        # Transform all non-dunder attributes to uppercase:
        upper_namespace = {
            k.upper() if not k.startswith('__') else k: v
            for k, v in namespace.items()
        }
        return super().__new__(mcs, name, bases, upper_namespace)

class MyConfig(metaclass=UpperAttrMeta):
    timeout = 30
    retries = 3
    debug = False

print(MyConfig.TIMEOUT)  # 30
print(MyConfig.RETRIES)  # 3
print(hasattr(MyConfig, 'timeout'))  # False — transformed to TIMEOUT
```

### Practical Metaclass Uses

**1. Class registration (plugin systems):**
```python
class PluginMeta(type):
    registry: dict = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if bases:  # don't register the base class itself
            mcs.registry[name] = cls
        return cls

class BasePlugin(metaclass=PluginMeta): pass

class AuthPlugin(BasePlugin): pass
class LogPlugin(BasePlugin): pass

print(PluginMeta.registry)
# {'AuthPlugin': <class '__main__.AuthPlugin'>, 'LogPlugin': <class '__main__.LogPlugin'>}
```

**2. Enforcing interface completeness:**
```python
class AbstractMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        required = getattr(cls, '_required_methods', [])
        if bases:  # skip the abstract base itself
            missing = [m for m in required if m not in namespace]
            if missing:
                raise TypeError(
                    f"{name} must implement: {missing}"
                )
        return cls

class Service(metaclass=AbstractMeta):
    _required_methods = ['start', 'stop', 'health_check']

class GoodService(Service):
    def start(self): pass
    def stop(self): pass
    def health_check(self): return True

class BadService(Service):    # TypeError at class definition time
    def start(self): pass
    # missing stop and health_check
```

### `__init_subclass__` — The Modern Alternative

For most metaclass use cases, `__init_subclass__` (Python 3.6+) is simpler and avoids metaclass conflicts:

```python
class Base:
    def __init_subclass__(cls, required: list[str] | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if required:
            missing = [m for m in required if m not in cls.__dict__]
            if missing:
                raise TypeError(f"{cls.__name__} must implement: {missing}")

class Service(Base): pass

class GoodService(Service, required=['start', 'stop']):
    def start(self): pass
    def stop(self): pass

class BadService(Service, required=['start', 'stop']):
    def start(self): pass
    # TypeError: BadService must implement: ['stop']
```

`__init_subclass__` is called on the **parent class** when a subclass is created, with the subclass as `cls`. It's cleaner than a metaclass for single-inheritance hierarchies.

### When to Use Metaclass vs `__init_subclass__` vs Class Decorator

| Need | Preferred Tool |
|------|---------------|
| Modify subclass after creation | `__init_subclass__` |
| Class registration | `__init_subclass__` |
| Modify namespace BEFORE class creation | Metaclass `__prepare__` |
| Change how the class object is created | Metaclass `__new__` |
| Multiple inheritance safe | `__init_subclass__` |
| One-off class modification | Class decorator |
| ABCs | `abc.ABCMeta` (a metaclass) |

---

## Interview Questions

### Q1: What is a metaclass and when would you actually use one in production?

**Model answer:**
A metaclass is the class of a class — it controls how class objects are created, just as a class controls how instances are created. Every class in Python is an instance of `type` (or a custom metaclass).

Real production uses (rare, but legitimate):
1. **ORM field registration** — Django's `ModelBase` metaclass reads `Field` instances from the class body and registers them.
2. **Ordered attribute tracking** — `__prepare__` returns an `OrderedDict`-like namespace to preserve definition order (used by `enum.EnumMeta`, `struct`-like libraries).
3. **Interface enforcement at class definition time** — catch missing abstract methods when the class is defined, not at instantiation.
4. **Operator overloading on the class itself** — e.g., `MyClass | OtherClass` (union type syntax is implemented via `type.__or__`).

For most use cases (subclass hooks, registration), `__init_subclass__` is preferred because it's simpler and avoids metaclass conflicts when multiple libraries are combined.

### Q2: What's the difference between `type.__new__` and `type.__init__` during class creation?

**Model answer:**
Both `__new__` and `__init__` are called during class creation, but at different points:

- `type.__new__(mcs, name, bases, namespace)` — **creates the class object**. Returns the new class. You can modify `namespace` here before the class object exists, or return a completely different object.
- `type.__init__(cls, name, bases, namespace)` — **initializes the class object** that `__new__` already created. `cls` is the class. You can add attributes to the class, but you cannot change its bases or fundamental structure.

```python
class Meta(type):
    def __new__(mcs, name, bases, namespace):
        # Intercept before class creation:
        namespace['_created_by'] = 'Meta'
        cls = super().__new__(mcs, name, bases, namespace)
        return cls

    def __init__(cls, name, bases, namespace):
        # Class already exists; can add to it:
        cls._meta_initialized = True
        super().__init__(name, bases, namespace)
```

**Key difference:** `__new__` can prevent class creation (by returning a non-class or raising `TypeError`). `__init__` cannot prevent it — the class already exists. Use `__new__` when you need to transform the namespace or bases; use `__init__` for post-creation setup.

### Q3: Explain `__prepare__` and when you would override it.

**Model answer:**
`type.__prepare__(mcs, name, bases, **kwargs)` is called before the class body is executed. It returns the namespace object (dict-like) that the class body statements populate.

Override it when you need:
1. **Ordered attribute collection** — return an `OrderedDict` (though regular dict is ordered in Python 3.7+, so this is now less needed).
2. **Attribute interception during class definition** — return a custom dict-like that reacts to attribute setting:

```python
class TrackingDict(dict):
    def __init__(self):
        super().__init__()
        self.definition_order = []

    def __setitem__(self, key, value):
        if not key.startswith('__'):
            self.definition_order.append(key)
        super().__setitem__(key, value)

class OrderedMeta(type):
    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        return TrackingDict()

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, dict(namespace))
        cls._order = namespace.definition_order
        return cls

class MyRecord(metaclass=OrderedMeta):
    name: str = ""
    age: int = 0
    email: str = ""

print(MyRecord._order)  # ['name', 'age', 'email'] — definition order preserved
```

`enum.EnumMeta` uses `__prepare__` to return a special namespace that prevents duplicate member names.

### Q4: How do metaclass conflicts arise and how are they resolved?

**Model answer:**
A metaclass conflict occurs when a class tries to inherit from bases with incompatible metaclasses:

```python
class MetaA(type): pass
class MetaB(type): pass

class A(metaclass=MetaA): pass
class B(metaclass=MetaB): pass

class C(A, B): pass
# TypeError: metaclass conflict: the metaclass of a derived class must be
# a (non-strict) subclass of the metaclasses of all its bases
```

Python requires that the most-derived metaclass (in MRO terms) is used. If two metaclasses are unrelated, Python can't pick one.

**Resolution:** Create a combined metaclass that inherits from both:

```python
class MetaC(MetaA, MetaB): pass  # inherits from both

class C(A, B, metaclass=MetaC): pass  # explicit combined metaclass
```

In practice, metaclass conflicts most commonly arise when combining libraries that each define their own metaclass (e.g., combining Django models with a custom ABC-based metaclass). The fix is creating a diamond metaclass that inherits from all conflicting metaclasses and from `ABCMeta`:

```python
from abc import ABCMeta

class CombinedMeta(MyCustomMeta, ABCMeta): pass
```

### Q5: What is the difference between a metaclass and a class decorator? When would you choose each?

**Model answer:**
Both can transform a class, but they operate at different points and have different capabilities:

**Class decorator:** Applied AFTER the class is fully created. Receives the complete class object. Can add/modify attributes and methods. Cannot change bases, metaclass, or intercept namespace population.

```python
@auto_repr
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
# auto_repr runs after Point is created — adds __repr__
```

**Metaclass:** Intercepts the class creation process. Can see and modify the namespace BEFORE the class exists. Can change how the class object is built. Inherited by subclasses (class decorators are not).

```python
class Meta(type):
    def __new__(mcs, name, bases, namespace):
        # Runs for MyClass AND every subclass of MyClass
        ...

class MyClass(metaclass=Meta): pass
class SubClass(MyClass): pass  # Meta.__new__ called again for SubClass
```

**Rule of thumb:**
- Use a **class decorator** for one-off modifications that don't need to propagate to subclasses.
- Use **`__init_subclass__`** for subclass hooks (simpler than metaclass in most cases).
- Use a **metaclass** when you need `__prepare__` (namespace interception), or when the behavior must propagate to all descendants AND `__init_subclass__` is insufficient.

---

## Gotcha Follow-ups

**"Can a metaclass define `__call__` to intercept instance creation?"**
Yes — `type.__call__(cls, *args, **kwargs)` is how `MyClass(...)` works. The class itself is called, which triggers `type.__call__`, which calls `cls.__new__` then `cls.__init__`. A metaclass can override `__call__` to intercept instance creation:

```python
class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Service(metaclass=SingletonMeta):
    pass

a = Service()
b = Service()
print(a is b)  # True — same instance
```

**"What does `type(type)` return?"**
`type`. The `type` metaclass is its own metaclass — `type` is an instance of itself. This is a fundamental bootstrapping circularity in Python's object model: `type` is a class (instance of `type`), `object` is a class (instance of `type`), and `type` is a subclass of `object`. The C implementation resolves this by initializing `type` and `object` together at startup.

---

## Under the Hood

Class creation is in `Objects/typeobject.c`, function `type_new()`. The sequence:
1. `type.__prepare__()` → get namespace dict.
2. Class body executed in that namespace via `EXEC_EVAL`.
3. `type.__new__(mcs, name, bases, namespace)` → allocates `PyTypeObject` struct.
4. `type.__init__(cls, name, bases, namespace)` → finalizes (sets `tp_dict`, `tp_bases`, calls `PyType_Ready()`).
5. `PyType_Ready()` fills in inherited methods, creates `tp_mro`, sets up slot function pointers.

`__init_subclass__` is called inside `type.__init__` after the class is fully initialized but before `type.__init__` returns. It's implemented as `type.__init_subclass__(cls)` on the base class, called with the new subclass as `cls`.
