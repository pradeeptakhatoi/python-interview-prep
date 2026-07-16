# Descriptors: __get__, __set__, __delete__, Data vs Non-data

## Concept

The **descriptor protocol** is the mechanism behind Python's `property`, `classmethod`, `staticmethod`, bound methods, and `__slots__`. Any object that defines `__get__`, `__set__`, or `__delete__` is a descriptor. Understanding descriptors is essential to understanding how Python's attribute access actually works.

### The Descriptor Protocol

```python
class Descriptor:
    def __get__(self, obj, objtype=None):
        """Called when the attribute is accessed: obj.attr"""
        # obj is None when accessed on the class itself (e.g. MyClass.attr)
        ...

    def __set__(self, obj, value):
        """Called when the attribute is assigned: obj.attr = value"""
        ...

    def __delete__(self, obj):
        """Called when the attribute is deleted: del obj.attr"""
        ...
```

A descriptor is placed in a **class** (not an instance). When accessed via an instance, the descriptor protocol intercepts the attribute lookup.

### Data vs Non-data Descriptors

| Type | Has `__get__` | Has `__set__` or `__delete__` | Priority |
|------|--------------|-------------------------------|----------|
| Non-data descriptor | ✓ | ✗ | Lower — instance `__dict__` wins |
| Data descriptor | ✓ | ✓ | Higher — descriptor wins over instance `__dict__` |

```python
class NonDataDescriptor:
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return 42

class DataDescriptor:
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get('_x', 0)

    def __set__(self, obj, value):
        obj.__dict__['_x'] = value   # store in instance __dict__ under different name

class MyClass:
    non_data = NonDataDescriptor()
    data_attr = DataDescriptor()

obj = MyClass()
print(obj.non_data)      # 42 — descriptor __get__ called

# Override non-data descriptor via instance __dict__:
obj.__dict__['non_data'] = 999
print(obj.non_data)      # 999 — instance __dict__ takes priority

# Data descriptor cannot be overridden by instance __dict__:
obj.__dict__['data_attr'] = 999   # stored, but never seen via attribute access
print(obj.data_attr)               # 0 — descriptor __get__ called, ignores __dict__
```

### `__set_name__` — Descriptor Self-Naming

Python 3.6+ calls `descriptor.__set_name__(owner_class, attr_name)` when the class body is processed. This lets descriptors know their own name without being told explicitly:

```python
class Validated:
    def __set_name__(self, owner, name):
        self._name = name
        self._private = f'_{name}'

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self._private, None)

    def __set__(self, obj, value):
        if not isinstance(value, (int, float)):
            raise TypeError(f"{self._name} must be numeric")
        setattr(obj, self._private, value)

class Config:
    timeout = Validated()   # __set_name__ called with name='timeout'
    retries = Validated()   # __set_name__ called with name='retries'

c = Config()
c.timeout = 30
c.retries = 3
print(c.timeout, c.retries)  # 30 3
c.timeout = "fast"           # TypeError: timeout must be numeric
```

### How `property` Is Built on Descriptors

`property` is simply a data descriptor implemented in C:

```python
# Pure Python equivalent of property:
class property_py:
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.__doc__ = doc or (fget.__doc__ if fget else None)

    def __set_name__(self, owner, name):
        self.__name__ = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError(f"unreadable attribute '{self.__name__}'")
        return self.fget(obj)

    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError(f"can't set attribute '{self.__name__}'")
        self.fset(obj, value)

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError(f"can't delete attribute '{self.__name__}'")
        self.fdel(obj)

    def getter(self, fget): return type(self)(fget, self.fset, self.fdel, self.__doc__)
    def setter(self, fset): return type(self)(self.fget, fset, self.fdel, self.__doc__)
    def deleter(self, fdel): return type(self)(self.fget, self.fset, fdel, self.__doc__)
```

This is why `@property` is a data descriptor — it defines both `__get__` and `__set__` (even if `fset` is `None`, the `__set__` raises `AttributeError`). That's how read-only properties prevent assignment via instance `__dict__` shadowing.

### How Methods Are Descriptors

Functions are non-data descriptors. `function.__get__(obj, objtype)` returns a **bound method**:

```python
class Dog:
    def bark(self):
        return "Woof!"

dog = Dog()

# Attribute access calls function.__get__:
print(type(Dog.bark))    # <class 'function'>
print(type(dog.bark))    # <class 'method'>  — bound method

# Equivalent to:
bound_method = Dog.bark.__get__(dog, Dog)
print(bound_method())    # "Woof!"
```

Each `dog.bark` access creates a new bound method object (in CPython, cached in 3.8+ via inline caches). The bound method holds a reference to both the function and `dog` (the "instance").

### Descriptor Lookup Order

When `obj.attr` is evaluated, CPython does (simplified):

```
1. type(obj).__mro__ → find attr in class hierarchy
2. If found and it's a DATA DESCRIPTOR → call descriptor.__get__(obj, type(obj))
3. If NOT a data descriptor (or not found in class): check obj.__dict__['attr']
4. If found in __dict__: return that value
5. If found in class and is a NON-DATA DESCRIPTOR: call descriptor.__get__(obj, type(obj))
6. If found in class (plain class attr): return it
7. Raise AttributeError
```

---

## Interview Questions

### Q1: Explain the difference between data and non-data descriptors with a concrete example of why it matters.

**Model answer:**
A data descriptor defines `__set__` (and/or `__delete__`) in addition to `__get__`. It takes priority over the instance's `__dict__`. A non-data descriptor only defines `__get__`; the instance `__dict__` shadows it.

This distinction is critical for `property`:
```python
class Circle:
    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, value):
        if value < 0:
            raise ValueError("negative radius")
        self._radius = value

c = Circle()
c.radius = 5
# If property were non-data: c.__dict__['radius'] = 5 would shadow the property
# next access would return 5 from __dict__, bypassing validation completely.
# But property IS a data descriptor — __set__ intercepts the assignment.

c.__dict__['radius'] = -99   # silently stored in __dict__
print(c.radius)               # still calls property __get__ → returns self._radius
                              # the __dict__ value is NEVER seen
```

Non-data descriptors (like plain functions/methods) are intentionally shadowed by instance `__dict__` — this is how `obj.method = lambda: ...` can override a method on a specific instance.

### Q2: How does `__set_name__` solve the problem of descriptor self-discovery?

**Model answer:**
Before `__set_name__` (Python 3.6), a descriptor had no way to know what name it was assigned to in the class, leading to this pattern:

```python
# Old, fragile pattern — name repeated twice:
class MyModel:
    name = Validated(name='name')        # must pass name explicitly
    email = Validated(name='email')      # error-prone: easy to mistype
```

With `__set_name__` (called by `type.__init_subclass__` / `type.__new__` during class creation):

```python
class MyModel:
    name = Validated()    # __set_name__(MyModel, 'name') called automatically
    email = Validated()   # __set_name__(MyModel, 'email') called automatically
```

The descriptor knows its own name without redundant argument passing. This is how `dataclasses` and `attrs` work internally to know field names.

### Q3: How would you implement a lazy-loading descriptor?

**Model answer:**
A lazy-loading descriptor computes a value on first access and caches it in the instance `__dict__`. It should be a **non-data descriptor** so the cached value in `__dict__` takes priority on subsequent accesses:

```python
import functools

class lazy_property:
    """Non-data descriptor: compute once, cache in instance __dict__."""

    def __init__(self, func):
        self.func = func
        self.__doc__ = func.__doc__
        # __set_name__ called at class creation:

    def __set_name__(self, owner, name):
        self.__name__ = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self   # class-level access returns descriptor itself
        # Compute and store in instance __dict__:
        value = self.func(obj)
        obj.__dict__[self.__name__] = value   # shadows this non-data descriptor
        return value
    # NO __set__ — makes this a non-data descriptor so __dict__ wins on next access

class Database:
    def __init__(self, dsn):
        self.dsn = dsn

    @lazy_property
    def connection(self):
        """Expensive: only created when first accessed."""
        print(f"Creating connection to {self.dsn}")
        return f"conn:{self.dsn}"

db = Database("postgres://localhost/mydb")
print(db.connection)   # "Creating connection..." then value
print(db.connection)   # No print — reads from __dict__ directly
```

`functools.cached_property` in the stdlib does exactly this. Note that `cached_property` is NOT thread-safe without a lock — if two threads call it simultaneously on the same instance, the factory may run twice.

### Q4: Why are functions descriptors, and what does `function.__get__` return?

**Model answer:**
Functions implement `__get__`, making them non-data descriptors. When accessed on an instance, `function.__get__(instance, owner_class)` returns a **bound method** object that wraps the function and the instance together.

```python
class Greeter:
    def hello(self, name):
        return f"Hello, {name}!"

g = Greeter()

# Class-level access: function itself
print(Greeter.hello)          # <function Greeter.hello at 0x...>
print(type(Greeter.hello))    # <class 'function'>

# Instance-level access: triggers __get__ → bound method
print(g.hello)                # <bound method Greeter.hello of <Greeter...>>
print(type(g.hello))          # <class 'method'>

# Manually invoke the descriptor protocol:
bound = Greeter.hello.__get__(g, Greeter)
print(bound("Alice"))         # "Hello, Alice!" — same as g.hello("Alice")
```

The bound method stores `__func__` (the original function) and `__self__` (the instance). Calling `bound(*args)` calls `__func__(__self__, *args)`. This is how `self` is automatically passed — it's not magic; it's the descriptor protocol.

### Q5: What is `__delete__` used for in practice?

**Model answer:**
`__delete__` is called when `del obj.attr` is executed on a descriptor. Use cases:

1. **Properties with deletion semantics:**
```python
class CachedResult:
    def __set_name__(self, owner, name):
        self._name = name
        self._private = f'_{name}_cached'

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if not hasattr(obj, self._private):
            raise AttributeError(f"{self._name} not computed yet")
        return getattr(obj, self._private)

    def __set__(self, obj, value):
        setattr(obj, self._private, value)

    def __delete__(self, obj):
        # del obj.result → invalidates cache
        if hasattr(obj, self._private):
            delattr(obj, self._private)
        print(f"{self._name} cache cleared")

class Processor:
    result = CachedResult()

p = Processor()
p.result = 42
print(p.result)   # 42
del p.result      # "result cache cleared"
p.result          # AttributeError: result not computed yet
```

2. **Resource cleanup descriptors** — `del connection` triggers network disconnection.

3. **Read-only properties** — `__delete__` raises `AttributeError` to prevent deletion.

---

## Gotcha Follow-ups

**"Can a descriptor be defined on an instance rather than a class?"**
No. Descriptors only work when defined in the *class* (or its MRO). Descriptors stored in the *instance* `__dict__` are never invoked — they're just plain object values. The descriptor protocol is triggered by the `type(obj).__mro__` lookup, not by the instance dict lookup.

```python
class D:
    def __get__(self, obj, objtype=None):
        return 42

obj = object.__new__(object)
obj.__dict__ = {'x': D()}   # won't work — can't set __dict__ on object
# Even if you could: obj.x would return the D() instance, not 42
```

**"What's the difference between `property` and a plain data descriptor for performance?"**
`property` is implemented in C — its `__get__`/`__set__`/`__delete__` calls are essentially C function calls. A pure Python data descriptor adds a Python function call overhead per attribute access. For hot paths (e.g., accessing an attribute in a tight loop 1M times), a `__slots__`-based attribute or a C-level `property` is significantly faster than a pure Python descriptor.

---

## Under the Hood

The descriptor protocol is implemented in `Objects/object.c`, specifically `_PyObject_GenericGetAttrWithDict()`. The priority lookup (data descriptor → instance dict → non-data descriptor) is coded in this function. When `LOAD_ATTR` is executed by the bytecode evaluator, it calls this function (or a specialized version after adaptive interpreter warmup: `LOAD_ATTR_INSTANCE_VALUE`, `LOAD_ATTR_SLOT`).

`classmethod` and `staticmethod` are descriptor classes in C (`Objects/funcobject.c`). `classmethod.__get__` returns a bound method with the class (not instance) as the first argument. `staticmethod.__get__` returns the raw function.
