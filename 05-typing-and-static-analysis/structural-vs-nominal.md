# Structural vs Nominal Typing

## Concept

**Nominal typing:** a type is identified by its name. To be a subtype, you must explicitly declare inheritance (`class Dog(Animal)`). Used by Java, C#, traditional OOP.

**Structural typing:** a type is identified by its structure (what methods/attributes it has). Any object with the right methods is a valid subtype. Used by Go interfaces, TypeScript, and Python's `Protocol`.

Python supports both.

### Nominal Typing: ABCs and Class Inheritance

```python
from abc import ABC, abstractmethod

class Serializable(ABC):
    @abstractmethod
    def serialize(self) -> bytes: ...

    @abstractmethod
    def deserialize(self, data: bytes) -> None: ...

class JSONDoc(Serializable):   # explicit inheritance — nominal subtype
    def serialize(self) -> bytes:
        import json
        return json.dumps(self.__dict__).encode()

    def deserialize(self, data: bytes) -> None:
        self.__dict__.update(json.loads(data))

# Checking nominal subtype:
print(issubclass(JSONDoc, Serializable))   # True
print(isinstance(JSONDoc(), Serializable)) # True

class CSVDoc:                  # NO inheritance — NOT a nominal subtype
    def serialize(self) -> bytes: ...
    def deserialize(self, data: bytes) -> None: ...

print(issubclass(CSVDoc, Serializable))    # False — even though it has the methods!
```

### Structural Typing: Protocol

```python
from typing import Protocol

class Serializable(Protocol):    # structural — no inheritance needed
    def serialize(self) -> bytes: ...
    def deserialize(self, data: bytes) -> None: ...

class JSONDoc:                   # no explicit declaration
    def serialize(self) -> bytes: ...
    def deserialize(self, data: bytes) -> None: ...

class CSVDoc:
    def serialize(self) -> bytes: ...
    def deserialize(self, data: bytes) -> None: ...

def save(doc: Serializable) -> None:   # type checker: requires the protocol shape
    db.write(doc.serialize())

save(JSONDoc())   # OK — structurally compatible
save(CSVDoc())    # OK — structurally compatible
save(object())    # Type Error — no serialize/deserialize
```

### `isinstance()` with Protocols vs ABCs

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Drawable(Protocol):
    def draw(self) -> None: ...

class Circle:
    def draw(self) -> None: print("Circle")

class Square:
    def draw(self) -> None: print("Square")

print(isinstance(Circle(), Drawable))  # True — has draw()
print(isinstance(Square(), Drawable))  # True — has draw()
print(isinstance("hello", Drawable))   # False — no draw()

# Limitation: Protocol isinstance only checks METHOD PRESENCE, not signature:
class Fake:
    def draw(self) -> str: return "wrong return type"

print(isinstance(Fake(), Drawable))   # True! — method exists; signature not checked at runtime
```

ABC `isinstance` checks nominal registration (or `__subclasshook__`):
```python
from abc import ABC, abstractmethod
from collections.abc import Iterable

print(isinstance([1, 2], Iterable))   # True — list is registered with Iterable ABC
print(isinstance(42, Iterable))       # False

class MyIterable:
    def __iter__(self): return iter([])

print(isinstance(MyIterable(), Iterable))  # True — __subclasshook__ checks for __iter__
```

### When Protocol Beats ABC

1. **Third-party code you can't modify:** you can't add `class ThirdParty(MyABC)` to code you don't own, but `Protocol` works structurally.

2. **Simpler code:** no registry, no explicit inheritance chain.

3. **Testing:** mock objects that implement just the required methods pass structural checks without explicit inheritance.

```python
from typing import Protocol
from unittest.mock import MagicMock

class DatabaseProtocol(Protocol):
    def query(self, sql: str) -> list[dict]: ...
    def execute(self, sql: str) -> int: ...

def process(db: DatabaseProtocol) -> int:
    rows = db.query("SELECT * FROM users")
    return db.execute(f"UPDATE ...")

# In tests: MagicMock automatically has all methods — passes Protocol checks
mock_db = MagicMock(spec=DatabaseProtocol)
process(mock_db)   # works structurally
```

### When ABC Beats Protocol

1. **Mixin methods for free:** ABC provides concrete methods that subclasses inherit.
2. **Enforcement at class definition:** `TypeError` when abstract methods not implemented.
3. **Complex `isinstance` checks with `__subclasshook__`.** 

```python
from abc import ABC, abstractmethod
from collections.abc import Sequence

# Sequence ABC provides count(), index() for free — you just implement __getitem__ and __len__:
class MyList(Sequence):
    def __init__(self, data):
        self._data = list(data)

    def __getitem__(self, i):
        return self._data[i]

    def __len__(self):
        return len(self._data)

ml = MyList([3, 1, 2, 1])
print(ml.count(1))   # 2 — free from Sequence ABC
print(ml.index(2))   # 2 — free from Sequence ABC
```

### Combining Both: `register()` for Virtual Subclasses

ABCs support "virtual subclasses" — register without inheritance:

```python
from abc import ABC, abstractmethod

class Serializable(ABC):
    @abstractmethod
    def serialize(self) -> bytes: ...

class ExternalLibClass:   # third-party, can't modify
    def serialize(self) -> bytes:
        return b"external"

# Register as a virtual subclass:
Serializable.register(ExternalLibClass)

print(isinstance(ExternalLibClass(), Serializable))   # True
print(issubclass(ExternalLibClass, Serializable))     # True
# But: ExternalLibClass.serialize() is NOT checked — registration is trust-based
```

This bridges structural and nominal: you declare "this class satisfies the ABC" without modifying the class.

---

## Interview Questions

### Q1: What is the fundamental difference between `Protocol` and `ABC` from a type theory perspective?

**Model answer:**
`ABC` implements **nominal subtyping**: `B` is a subtype of `A` if `B` is declared to inherit from `A`. Structural compatibility is irrelevant — only the declared hierarchy matters.

`Protocol` implements **structural subtyping**: `B` is a subtype of `A` if `B` has at least the methods and attributes that `A` specifies, regardless of inheritance.

```python
# Nominal: explicit declaration required
from abc import ABC, abstractmethod

class HasArea(ABC):
    @abstractmethod
    def area(self) -> float: ...

class Square(HasArea):   # must declare — without this, isinstance fails
    def area(self) -> float: return 4.0

class Triangle:          # has area() but not a nominal subtype
    def area(self) -> float: return 3.0

print(isinstance(Square(), HasArea))    # True
print(isinstance(Triangle(), HasArea))  # False — missing declaration

# Structural: shape determines membership
from typing import Protocol

class HasAreaProto(Protocol):
    def area(self) -> float: ...

print(isinstance(Square(), HasAreaProto))    # True (with @runtime_checkable)
print(isinstance(Triangle(), HasAreaProto))  # True — has the method, structurally compatible
```

The type theory terms: nominal is "explicit subtype relation," structural is "behavioral equivalence / duck typing formalized."

### Q2: When would you choose `Protocol` over inheritance to express an interface in a library's public API?

**Model answer:**
Prefer `Protocol` in a library API when:

1. **Callers shouldn't be forced to import your base class.** Inheritance creates tight coupling — callers must `from mylib import MyBase`. Protocol is zero-coupling: callers just implement the right methods.

2. **You want to accept existing types from the stdlib or third parties.** `list`, `dict`, `socket.socket`, `io.IOBase` — none inherit from your ABC, but they might satisfy your Protocol.

3. **You want testability by default.** Any mock or stub satisfies the Protocol without explicit setup.

```python
# Library defines:
from typing import Protocol

class Store(Protocol):
    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes) -> None: ...

def cache_result(store: Store, key: str, compute: callable) -> bytes:
    cached = store.get(key)
    if cached is None:
        cached = compute()
        store.set(key, cached)
    return cached

# Users can provide: Redis client, dict-wrapper, filesystem store, mock — anything with get/set
```

Use ABC when:
- You provide mixin functionality (free method implementations).
- You need `__init_subclass__` hooks for registration.
- You need `isinstance()` to work deeply (virtual subclass registration).

### Q3: What are the performance implications of `isinstance()` checks with Protocol vs ABC?

**Model answer:**
`isinstance()` with ABC: O(1) — checks `tp_mro` C array for the ABC, or checks `_abc_registry` set (for virtual subclasses). The ABC is stored in the class's MRO or in the registered set; lookup is a pointer comparison or hash table lookup.

`isinstance()` with `@runtime_checkable` Protocol: O(m) where m is the number of protocol methods — for each required method, `hasattr(obj, method_name)` is called. This is significantly slower and scales with protocol size.

```python
import timeit
from abc import ABC
from typing import Protocol, runtime_checkable

class MyABC(ABC):
    def method(self): ...

class MyProto(Protocol):
    def method(self): ...

MyProto = runtime_checkable(MyProto)

class Impl(MyABC):
    def method(self): pass

inst = Impl()

t_abc = timeit.timeit(lambda: isinstance(inst, MyABC), number=1_000_000)
t_proto = timeit.timeit(lambda: isinstance(inst, MyProto), number=1_000_000)
print(f"ABC: {t_abc:.3f}s  Protocol: {t_proto:.3f}s")
# Protocol is typically 3-10x slower for isinstance checks
```

**Recommendation:** Use `Protocol` for static type checking (no runtime cost). Use ABC for runtime `isinstance` checks that are performance-sensitive. If you need both: define an ABC and optionally make it compatible with the Protocol structurally.

### Q4: How do you type a function that works with any file-like object (structural typing)?

**Model answer:**
The stdlib provides `typing.IO`, `typing.TextIO`, `typing.BinaryIO` for file-like objects. For custom protocols:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ReadableStream(Protocol):
    def read(self, n: int = -1) -> bytes: ...
    def readable(self) -> bool: ...

@runtime_checkable
class WriteableStream(Protocol):
    def write(self, data: bytes) -> int: ...
    def writable(self) -> bool: ...

def copy_stream(src: ReadableStream, dst: WriteableStream, chunk_size: int = 8192) -> int:
    total = 0
    while True:
        chunk = src.read(chunk_size)
        if not chunk:
            break
        total += dst.write(chunk)
    return total

# Works with:
import io
copy_stream(io.BytesIO(b"hello"), io.BytesIO())    # in-memory
# open('in.bin', 'rb'), open('out.bin', 'wb')       # files
# socket.makefile('rb'), socket.makefile('wb')       # sockets
# gzip.open('f.gz', 'rb'), io.BytesIO()             # gzip → memory
# All satisfy ReadableStream/WriteableStream structurally
```

This is the canonical use case for structural typing — the stdlib IO types don't share a single inheritance chain, but they share a common structure.

### Q5: What is `__subclasshook__` and how does it blur the line between structural and nominal?

**Model answer:**
`__subclasshook__` is a classmethod on an ABC that lets you define CUSTOM logic for `isinstance()` checks — returning `True` or `False` to override the default MRO/registry check:

```python
from abc import ABCMeta, abstractmethod

class Iterable(metaclass=ABCMeta):
    @abstractmethod
    def __iter__(self): ...

    @classmethod
    def __subclasshook__(cls, subclass):
        if cls is Iterable:
            # Structural check: does the class have __iter__?
            if any('__iter__' in B.__dict__ for B in subclass.__mro__):
                return True
        return NotImplemented

# All classes with __iter__ are virtual subclasses of Iterable:
class MyList:
    def __iter__(self):
        return iter([])

print(isinstance(MyList(), Iterable))   # True — via __subclasshook__
print(issubclass(MyList, Iterable))     # True — without explicit registration
```

This is exactly how `collections.abc.Iterable`, `collections.abc.Mapping`, etc. work — they use `__subclasshook__` for structural duck-typing while still being ABCs. It bridges nominal and structural: the check is structural (look for `__iter__`), but the class is an ABC with mixin methods.

---

## Gotcha Follow-ups

**"Does Protocol support multiple structural requirements (AND vs OR)?"**
`Protocol` is always AND — the object must have ALL specified methods. For OR semantics, use `Union[Protocol1, Protocol2]`, but this is rarely what you want. More often, define a more permissive single Protocol with only the minimal methods you actually use.

**"If `JSONDoc` satisfies `SerializableProto` structurally, does that make it a subclass?"**
At the static type-checking level, yes — the type checker treats it as compatible. At runtime, `issubclass(JSONDoc, SerializableProto)` returns `False` unless `@runtime_checkable` is used and then it only checks method presence via `isinstance()`. `issubclass()` with Protocols raises `TypeError` unless the Protocol is `@runtime_checkable`.

---

## Under the Hood

`Protocol` (`Lib/typing.py`): `_ProtocolMeta` stores `__protocol_attrs__` — the set of method names that form the protocol. For `@runtime_checkable`, `__instancecheck__` iterates `__protocol_attrs__` and calls `hasattr(instance, attr_name)`. This is why it's O(m) and why it misses signature mismatches.

ABC (`Lib/abc.py` + `Modules/_abc.c`): `ABCMeta` maintains a `_abc_registry` (set of explicitly registered classes) and `_abc_cache`/`_abc_negative_cache` (sets caching positive and negative `isinstance` results). The C implementation (`_abc_subclasscheck`) checks these caches first (O(1)), then falls back to `__subclasshook__`, then MRO traversal.
