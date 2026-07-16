# Abstract Base Classes vs Protocols vs Duck Typing

## Concept

Python offers three mechanisms for defining interfaces and checking type compatibility. Choosing the right one is an architectural decision with real impact on coupling, flexibility, and IDE/type-checker support.

### Duck Typing (Implicit Interface)

No explicit interface declaration. If an object has the required methods, it works.

```python
def process(item):
    item.start()   # relies on duck typing — any object with .start() works
    data = item.read()
    item.close()
    return data

class File:
    def start(self): ...
    def read(self): ...
    def close(self): ...

class Socket:
    def start(self): ...
    def read(self): ...
    def close(self): ...

process(File())    # works
process(Socket())  # works
# No type annotation, no explicit interface — pure duck typing
```

**Pros:** Maximum flexibility. No coupling between caller and callees.  
**Cons:** No IDE support, no static analysis, runtime-only errors, no explicit contract.

### Abstract Base Classes (ABCs) — Nominal Typing

`abc.ABC` + `@abstractmethod` creates an explicit interface that must be inherited:

```python
from abc import ABC, abstractmethod
from typing import Any

class Processable(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def read(self) -> bytes: ...

    @abstractmethod
    def close(self) -> None: ...

    @classmethod
    def __subclasshook__(cls, C):
        """Optional: allow implicit registration via duck typing check."""
        if cls is Processable:
            # Duck-type check: does C have all required methods?
            return all(
                any(method in B.__dict__ for B in C.__mro__)
                for method in ('start', 'read', 'close')
            )
        return NotImplemented

class File(Processable):
    def start(self) -> None: pass
    def read(self) -> bytes: return b""
    def close(self) -> None: pass

# Attempting to instantiate an ABC without all abstract methods:
class Incomplete(Processable):
    def start(self) -> None: pass
    # Missing read() and close()

Incomplete()  # TypeError: Can't instantiate abstract class Incomplete
              # with abstract methods close, read

# Virtual subclasses (register without inheriting):
class Legacy:  # doesn't inherit Processable
    def start(self): pass
    def read(self): return b""
    def close(self): pass

Processable.register(Legacy)
print(isinstance(Legacy(), Processable))  # True — registered
print(issubclass(Legacy, Processable))    # True
```

### Protocols (Structural Typing — PEP 544, Python 3.8+)

`typing.Protocol` defines an interface that any class with the right structure satisfies — no inheritance or registration needed:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Processable(Protocol):
    def start(self) -> None: ...
    def read(self) -> bytes: ...
    def close(self) -> None: ...

class File:  # NO inheritance from Processable
    def start(self) -> None: pass
    def read(self) -> bytes: return b""
    def close(self) -> None: pass

class Socket:
    def start(self) -> None: pass
    def read(self) -> bytes: return b""
    def close(self) -> None: pass

def process(item: Processable) -> bytes:  # type-checked against Protocol
    item.start()
    data = item.read()
    item.close()
    return data

process(File())     # ✓ mypy/pyright: structurally compatible
process(Socket())   # ✓ mypy/pyright: structurally compatible

# Runtime check (only with @runtime_checkable):
print(isinstance(File(), Processable))  # True
print(isinstance(42, Processable))      # False

# Without @runtime_checkable, isinstance raises TypeError
```

### Key Comparison

| Aspect | Duck Typing | ABC | Protocol |
|--------|------------|-----|---------|
| Explicit contract | None | Yes (inheritance) | Yes (structural) |
| Type checker support | Minimal | Good | Excellent |
| `isinstance()` | Not applicable | Yes | Yes (with @runtime_checkable) |
| Coupling | None | Tight (must inherit) | Loose (structural match) |
| Third-party class support | Yes (implicit) | Via `.register()` | Yes (no action needed) |
| Error detection | Runtime | Instantiation time | Static analysis |
| Use in stdlib | `collections.abc` | Widely | New (3.8+) |

### Collections ABCs and Protocol

The `collections.abc` module provides ABCs for built-in protocols:

```python
from collections.abc import Sequence, Mapping, Iterable, Iterator, Callable

# Check if an object implements the sequence protocol:
print(isinstance([1, 2, 3], Sequence))  # True — list has __getitem__, __len__
print(isinstance("hello", Sequence))    # True
print(isinstance({}, Sequence))         # False — dict is a Mapping, not Sequence

# Implementing a custom Sequence:
class Fibonacci(Sequence):
    def __init__(self, n):
        self._data = self._compute(n)

    def _compute(self, n):
        a, b = 0, 1
        result = []
        for _ in range(n):
            result.append(a)
            a, b = b, a + b
        return result

    def __getitem__(self, idx):  # abstract — must implement
        return self._data[idx]

    def __len__(self):           # abstract — must implement
        return len(self._data)
    # Mixin methods (count, index, __contains__, __iter__, __reversed__)
    # provided for free by Sequence ABC
```

---

## Interview Questions

### Q1: When would you use Protocol over ABC at a Staff/Architect level?

**Model answer:**  
**Use Protocol when:**
- Integrating with third-party classes you don't control (they can't inherit your ABC).
- The interface is defined by behavior, not lineage — structural typing is more natural.
- You want maximum flexibility: any class with the right methods works, even existing ones.
- Building library code that should be easy to mock/stub in tests without inheriting base classes.

**Use ABC when:**
- You want instantiation-time enforcement of interface completeness (ABC raises `TypeError` immediately; Protocol only catches violations with a static type checker).
- You provide mixin behavior via concrete methods in the ABC (see `collections.abc.Sequence` providing `count`, `index` for free).
- You need `isinstance()` checks in library code that must work without `@runtime_checkable` overhead.
- The class hierarchy IS the domain model — e.g., `BaseException` hierarchy where lineage is semantically meaningful.

**General principle for libraries:** Prefer Protocol for input parameters (maximally flexible for callers). Use ABC for output types or when you need to provide shared implementation.

### Q2: What is `__subclasshook__` and why does `collections.abc.Iterable` use it?

**Model answer:**  
`__subclasshook__` is a classmethod on an ABC that's called by `isinstance()` and `issubclass()` before checking the class registry. If it returns `True` or `False`, that's used. If it returns `NotImplemented`, normal ABC checks proceed.

`collections.abc.Iterable.__subclasshook__`:
```python
@classmethod
def __subclasshook__(cls, C):
    if cls is Iterable:
        return _check_methods(C, "__iter__")
    return NotImplemented
```

This means any class with `__iter__` is considered an `Iterable`, even without inheriting from it:
```python
from collections.abc import Iterable

class MyContainer:
    def __iter__(self):
        return iter([1, 2, 3])

print(isinstance(MyContainer(), Iterable))  # True — via __subclasshook__
print(issubclass(MyContainer, Iterable))    # True
```

This is how duck typing and ABCs are reconciled in the stdlib. The ABC defines the structural check; `__subclasshook__` makes it automatic. Without `__subclasshook__`, you'd need `Iterable.register(MyContainer)` explicitly.

### Q3: What's the performance difference between Protocol structural checks and ABC isinstance checks?

**Model answer:**  
`isinstance()` with a `@runtime_checkable` Protocol is **slower** than with an ABC:

- **ABC:** Looks up `type(obj).__mro__` and checks if the ABC is in it, or if the type was registered. Both are O(1) amortized (class identity checks, dict lookups). 
- **Protocol with `@runtime_checkable`:** Iterates through all methods defined in the Protocol and checks that `obj` has them. O(m) where m is the number of methods in the Protocol.

```python
import timeit
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

class ABCInterface(ABC):
    @abstractmethod
    def method(self): ...

@runtime_checkable
class ProtoInterface(Protocol):
    def method(self): ...

class Impl(ABCInterface):
    def method(self): pass

obj = Impl()
print(timeit.timeit(lambda: isinstance(obj, ABCInterface), number=1_000_000))
print(timeit.timeit(lambda: isinstance(obj, ProtoInterface), number=1_000_000))
# Protocol isinstance is typically 3-10x slower
```

**Practical advice:** Don't use `isinstance(obj, Protocol)` in hot paths. Use it for validation at system boundaries (e.g., validating input to a public API). In static type-checking contexts (function signatures), Protocol has zero runtime cost — the check is purely at analysis time.

### Q4: How do Protocols handle generic types (e.g., `Comparable`, `Sortable`)?

**Model answer:**  
```python
from typing import Protocol, TypeVar

T = TypeVar('T')

class Comparable(Protocol[T]):
    def __lt__(self, other: T) -> bool: ...
    def __eq__(self, other: object) -> bool: ...

class Sortable(Protocol):
    def __lt__(self: T, other: T) -> bool: ...

def sort_items(items: list[Comparable]) -> list[Comparable]:
    return sorted(items)

# Works with any class implementing __lt__ and __eq__:
@dataclass
class Point:
    x: float
    y: float
    def __lt__(self, other: 'Point') -> bool:
        return (self.x, self.y) < (other.x, other.y)

sort_items([Point(1, 2), Point(0, 3)])  # type-checks correctly
```

`Self` type (Python 3.11+) in Protocols:
```python
from typing import Protocol, Self

class Addable(Protocol):
    def __add__(self, other: Self) -> Self: ...
    # Self means "the same concrete type as the implementing class"

class Vector:
    def __add__(self, other: 'Vector') -> 'Vector': ...
    # Vector satisfies Addable[Vector]
```

### Q5: When does ABC's mixin inheritance provide real value over Protocols?

**Model answer:**  
ABCs can provide **concrete mixin methods** that implementing classes get for free. This is the primary advantage over Protocols (which only define the interface, no implementation):

```python
from abc import ABC, abstractmethod
from typing import Iterator

class Sequence(ABC):
    @abstractmethod
    def __getitem__(self, index): ...  # must implement

    @abstractmethod
    def __len__(self) -> int: ...       # must implement

    # Mixin methods — provided by ABC, don't need to implement:
    def __contains__(self, value) -> bool:
        for item in self:
            if item == value:
                return True
        return False

    def __iter__(self) -> Iterator:
        i = 0
        while True:
            try:
                yield self[i]
            except IndexError:
                return
            i += 1

    def __reversed__(self) -> Iterator:
        for i in reversed(range(len(self))):
            yield self[i]

    def index(self, value, start=0, stop=None) -> int:
        ...  # implementation using __getitem__ and __len__

    def count(self, value) -> int:
        return sum(1 for item in self if item == value)
```

By implementing just `__getitem__` and `__len__`, you get `in`, `for`, `reversed()`, `.index()`, `.count()` for free. This is why `collections.abc.Sequence` is worth inheriting for custom sequence types. Protocol can't provide this — it's structural only.

---

## Gotcha Follow-ups

**"Can a class satisfy a Protocol's structural check while still being semantically incompatible?"**  
Yes — structural typing checks method names and signatures, not behavior. A class with `def read(self) -> bytes` satisfies the `Readable` Protocol even if `read()` always returns corrupt data or raises unexpectedly. Protocols define the interface contract but cannot enforce behavioral correctness. This is why Protocols are best for technical interoperability (does it have these methods?) while ABCs with documentation and tests are better for enforcing semantic contracts.

**"What's the `__protocol_attrs__` attribute on a Protocol?"**  
In Python 3.12+, `Protocol.__protocol_attrs__` is a frozenset of the names of methods/attributes that define the protocol (excluding inherited ones from `Protocol` itself and `object`). This is used by `isinstance()` checks with `@runtime_checkable` to know which attributes to check. Before 3.12, this was computed ad hoc and was slower.

---

## Under the Hood

ABCs are implemented in `Lib/abc.py` (Python-level metaclass `ABCMeta`) backed by `_abc` (C module in Python 3.4+). The `ABCMeta.__instancecheck__` and `__subclasscheck__` methods implement the registry and `__subclasshook__` logic. The ABC registry is stored as a `WeakSet` in `ABCMeta.__subclasses__` — instances are automatically removed when classes are GC'd.

`typing.Protocol`'s runtime checking is in `typing.py`. The `@runtime_checkable` decorator sets a `_is_runtime_protocol` flag. `Protocol.__instancecheck__` then iterates `__protocol_attrs__` and calls `hasattr(obj, attr)` for each. This is why Protocol isinstance is slower than ABC isinstance — it's O(n_methods) vs O(1) for ABCs.
