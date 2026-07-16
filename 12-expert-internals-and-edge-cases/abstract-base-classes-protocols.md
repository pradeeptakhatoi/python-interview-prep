# Abstract Base Classes vs Protocols vs Duck Typing

## Concept

Python provides three distinct mechanisms for expressing interface contracts, each with different trade-offs around coupling, runtime checkability, and static analysis support. Understanding when to use each is a Staff/Architect-level skill.

### Duck Typing — The Default

```python
# No formal interface — just call the method and handle AttributeError:
def process(obj):
    """Works with anything that has a .read() method."""
    return obj.read()

# EAFP (Easier to Ask Forgiveness than Permission):
def send(obj):
    try:
        data = obj.read()
    except AttributeError:
        raise TypeError(f"{type(obj).__name__} must have a read() method")

# LBYL (Look Before You Leap):
def send_lbyl(obj):
    if not hasattr(obj, 'read'):
        raise TypeError(f"{type(obj).__name__} must have a read() method")
    return obj.read()
```

### ABCs — Nominal Typing with Runtime Enforcement

```python
from abc import ABC, abstractmethod

class Serializer(ABC):
    @abstractmethod
    def serialize(self, obj) -> bytes: ...

    @abstractmethod
    def deserialize(self, data: bytes): ...

    def round_trip(self, obj):
        """Concrete method using the abstract interface."""
        return self.deserialize(self.serialize(obj))

class JSONSerializer(Serializer):
    def serialize(self, obj) -> bytes:
        import json
        return json.dumps(obj).encode()

    def deserialize(self, data: bytes):
        import json
        return json.loads(data)

# Concrete methods are inherited:
s = JSONSerializer()
assert s.round_trip({"key": "value"}) == {"key": "value"}

# Cannot instantiate with missing abstract methods:
class Incomplete(Serializer):
    def serialize(self, obj) -> bytes:
        return b""
    # Missing deserialize

try:
    Incomplete()   # TypeError: Can't instantiate abstract class
except TypeError as e:
    print(e)

# ABC isinstance — nominal:
print(isinstance(s, Serializer))  # True (subclass)
print(isinstance({"key": 1}, Serializer))  # False (no inheritance)
```

### Virtual Subclasses — ABCs with `__subclasshook__`

```python
from abc import ABC, abstractmethod

class Readable(ABC):
    @abstractmethod
    def read(self) -> bytes: ...

    @classmethod
    def __subclasshook__(cls, C):
        """Structural check: any class with .read() counts."""
        if cls is Readable:
            if any("read" in B.__dict__ for B in C.__mro__):
                return True  # virtual subclass — no inheritance required
        return NotImplemented

class FileStream:
    """Has .read() but doesn't inherit Readable."""
    def read(self) -> bytes:
        return b"data"

print(isinstance(FileStream(), Readable))   # True — via __subclasshook__
print(issubclass(FileStream, Readable))     # True

# Manual virtual subclass registration:
class OldStyleReader:
    def read(self):
        return b""

Readable.register(OldStyleReader)   # explicitly declare compatibility
print(isinstance(OldStyleReader(), Readable))  # True
```

### Protocols — Structural Typing Without Inheritance

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Drawable(Protocol):
    def draw(self) -> None: ...
    def resize(self, factor: float) -> None: ...

class Circle:
    """No Drawable inheritance — but satisfies the protocol structurally."""
    def draw(self) -> None:
        print("Drawing circle")

    def resize(self, factor: float) -> None:
        self.radius *= factor

class Square:
    def draw(self) -> None:
        print("Drawing square")

    def resize(self, factor: float) -> None:
        self.side *= factor

def render_all(shapes: list[Drawable]) -> None:
    for shape in shapes:
        shape.draw()

# Works with any class that has draw() and resize():
render_all([Circle(), Square()])

# Runtime check (only checks method presence, not signatures):
print(isinstance(Circle(), Drawable))   # True
print(isinstance("not a shape", Drawable))  # False

# Static check: mypy/pyright verify the full signature at call sites
```

### Comparison: ABC vs Protocol

```python
from abc import ABC, abstractmethod
from typing import Protocol

# ABC approach: requires inheritance
class Repository(ABC):
    @abstractmethod
    def get(self, id: int): ...
    @abstractmethod
    def save(self, entity) -> None: ...

class PostgresRepo(Repository):   # MUST inherit
    def get(self, id: int): ...
    def save(self, entity) -> None: ...

# Protocol approach: structural — no inheritance required
class Repository(Protocol):
    def get(self, id: int): ...
    def save(self, entity) -> None: ...

class PostgresRepo:   # no inheritance needed
    def get(self, id: int): ...
    def save(self, entity) -> None: ...

# Practical choice matrix:
# - Third-party class you don't control → Protocol (can't make it inherit)
# - Your own class hierarchy → ABC (enforces implementation, provides concrete methods)
# - Plugin interface → entry_points + Protocol (ABC if you ship a base class)
# - Want default method implementations → ABC (Protocol has no default impls)
```

### `collections.abc` — Built-in ABCs

```python
from collections.abc import (
    Sequence,      # __getitem__ + __len__ → free: __contains__, __iter__, __reversed__, index, count
    MutableSequence,  # + __setitem__, __delitem__, insert → free: append, clear, reverse, extend, pop, remove, __iadd__
    Mapping,       # __getitem__ + __len__ + __iter__ → free: __contains__, keys, items, values, get, __eq__
    MutableMapping,   # + __setitem__, __delitem__ → free: pop, popitem, clear, update, setdefault
    Iterable,      # __iter__
    Iterator,      # __iter__ + __next__
    Callable,      # __call__
    Sized,         # __len__
)

class SortedList(MutableSequence):
    """Implements 5 methods, gets 12 free."""
    def __init__(self):
        self._data = []

    def __getitem__(self, idx):
        return self._data[idx]

    def __setitem__(self, idx, val):
        self._data[idx] = val
        self._data.sort()

    def __delitem__(self, idx):
        del self._data[idx]

    def __len__(self):
        return len(self._data)

    def insert(self, idx, val):
        self._data.insert(idx, val)
        self._data.sort()

sl = SortedList()
sl.append(3)
sl.append(1)
sl.append(2)
print(list(sl))  # [1, 2, 3] — sorted; append/extend/pop all work free
```

---

## Interview Questions

### Q1: When would you choose an ABC over a Protocol for a public API?

**Model answer:**
ABCs when:
1. **You provide concrete default implementations** that subclasses inherit. `collections.abc.MutableSequence` gives `append`, `extend`, `pop`, etc. for free — implementing only 5 abstract methods.
2. **You want to prevent instantiation of incomplete implementations** — `abstractmethod` raises `TypeError` at instantiation if any abstract method is missing.
3. **You ship a base class to subclass** — SDK users inherit `MyBasePlugin` to get free functionality and be automatically compatible.
4. **You use `register()` for virtual subclasses** — explicitly marking third-party classes as compatible without modifying them.

Protocols when:
1. **You don't control the implementing class** — can't require it to inherit anything.
2. **You want zero coupling** — the Protocol lives in your library; implementors don't need to import it.
3. **Structural typing is enough** — any object with the right shape works.
4. **Static analysis is the primary enforcement** — mypy/pyright check Protocol compliance without runtime overhead.

### Q2: What does `collections.abc.MutableSequence` give you for free when you implement 5 abstract methods?

**Model answer:**
`MutableSequence` requires `__getitem__`, `__setitem__`, `__delitem__`, `__len__`, `insert`. In return, it provides mixin implementations of:
- `append(v)` → `insert(len(self), v)`
- `clear()` → `del self[i]` for all i
- `reverse()` → in-place reversal using `__getitem__`/`__setitem__`
- `extend(other)` → `append()` for each
- `pop(idx=-1)` → get + delete
- `remove(v)` → find + delete
- `__iadd__(other)` → extend
- `__contains__(v)` → linear scan via `__getitem__`
- `__iter__()` → index-based iteration
- `__reversed__()` → reverse index-based iteration
- `index(v)` → linear scan
- `count(v)` → linear scan

This is the power of the ABC pattern for data structures: implement the minimal primitives, get the full standard interface.

### Q3: How does `__subclasshook__` make an ABC behave structurally like a Protocol?

**Model answer:**
`__subclasshook__(cls, C)` is called by `isinstance()` and `issubclass()` BEFORE checking the MRO. If it returns `True`, the class is treated as a virtual subclass — without inheritance or `register()`.

```python
from abc import ABC

class Closeable(ABC):
    @classmethod
    def __subclasshook__(cls, C):
        if cls is Closeable:
            # Check if any class in C's MRO defines 'close':
            if any("close" in B.__dict__ for B in C.__mro__):
                return True
        return NotImplemented   # fall back to normal MRO check

class FileWrapper:
    def close(self):
        ...

print(isinstance(FileWrapper(), Closeable))  # True — via __subclasshook__
print(isinstance(open("/dev/null"), Closeable))  # True — io.IOBase has close()
```

This is how `collections.abc.Iterable` works: any class with `__iter__` is an `Iterable` without inheriting it. The difference from Protocol: it's an ABC runtime check, still uses `isinstance()`, but is opt-in per ABC (not automatic structural typing like Protocol).

### Q4: What's the performance difference between `isinstance(obj, SomeABC)` and `isinstance(obj, SomeProtocol)`?

**Model answer:**
ABC `isinstance`: O(depth of MRO) — fast MRO lookup or O(1) via `_abc_registry` cache (C implementation in `Modules/_abc.c`). After the first check for a given type, the result is cached in `_abc_cache` or `_abc_negative_cache`.

`@runtime_checkable` Protocol `isinstance`: O(m) where m = number of protocol methods — `hasattr()` check for each method. No caching. For a Protocol with 10 methods, it's 10 attribute lookups on every `isinstance()` call.

```python
import timeit
from typing import Protocol, runtime_checkable
from collections.abc import Iterable

@runtime_checkable
class MyProtocol(Protocol):
    def method_a(self) -> None: ...
    def method_b(self) -> int: ...
    def method_c(self) -> str: ...

class ConcreteClass:
    def method_a(self): pass
    def method_b(self): return 0
    def method_c(self): return ""

obj = ConcreteClass()
lst = [1, 2, 3]

# ABC (collections.abc): fast after first check
t1 = timeit.timeit(lambda: isinstance(lst, Iterable), number=100_000)

# Protocol: O(m) every time
t2 = timeit.timeit(lambda: isinstance(obj, MyProtocol), number=100_000)

print(f"ABC: {t1:.4f}s")       # ~0.005s
print(f"Protocol: {t2:.4f}s")  # ~0.020s — 4x slower per check
```

For hot paths: check once, cache the result. Or use ABC if the overhead matters.

### Q5: How do you create a class that passes `isinstance()` checks for multiple ABCs without inheriting from all of them?

**Model answer:**
Use `register()` for each ABC, or implement `__subclasshook__` in a custom metaclass, or provide the required methods (for structural ABCs like `Iterable`):

```python
from collections.abc import Sized, Iterable, Container

class VirtualCollection:
    """Passes ABC checks without explicit inheritance."""
    def __len__(self): return 0
    def __iter__(self): return iter([])
    def __contains__(self, x): return False

obj = VirtualCollection()

# These ABCs use __subclasshook__ to check for the relevant dunders:
print(isinstance(obj, Sized))      # True — has __len__
print(isinstance(obj, Iterable))   # True — has __iter__
print(isinstance(obj, Container))  # True — has __contains__

# For ABCs without __subclasshook__, use register():
from collections.abc import Mapping

class ConfigProxy:
    """Acts like a Mapping but has a custom __init__."""
    def __getitem__(self, key): ...
    def __len__(self): return 0
    def __iter__(self): return iter([])

Mapping.register(ConfigProxy)
print(isinstance(ConfigProxy(), Mapping))  # True

# Caveat: register() does NOT verify the implementation
# Missing __getitem__ would still register successfully — silent bug!
```

---

## Gotcha Follow-ups

**"Can a Protocol have non-method attributes?"**
Yes — Protocol can specify class variables and instance attributes:
```python
class HasName(Protocol):
    name: str       # instance attribute — checked structurally
    MAX: ClassVar[int]  # class variable

class Foo:
    name = "foo"     # satisfies the protocol
    MAX = 100
```
However, `@runtime_checkable` only checks for methods (callable attributes via `hasattr`), not data attributes. Type checkers (mypy/pyright) do check attribute presence statically.

**"Does `ABC.register()` make `issubclass()` return True?"**
Yes — both `isinstance()` and `issubclass()` are affected by `register()`. But `__mro__` of the registered class is NOT modified — it doesn't appear as an ancestor in the MRO. This is "virtual" subclassing: the class knows it satisfies the contract, but the hierarchy is unchanged.

---

## Under the Hood

The ABC mechanism (`Modules/_abc.c`, `Lib/abc.py`): `ABCMeta.__instancecheck__` calls `__subclasshook__` first, then checks `_abc_cache` (positive hits) and `_abc_negative_cache` (negative hits). Cache entries are `weakref`s — cleared when the class is GC'd. `abstractmethod` sets `__isabstractmethod__ = True` on the function; `ABCMeta.__new__` collects all methods with this flag into `__abstractmethods__` on the class. `object.__new__` checks `cls.__abstractmethods__` and raises `TypeError` if non-empty. Protocol (`typing.py: Protocol`): `@runtime_checkable` installs a custom `__instancecheck__` that uses `hasattr()` for each name in `Protocol.__protocol_attrs__`.
