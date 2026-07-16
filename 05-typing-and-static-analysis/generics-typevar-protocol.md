# Generics, TypeVar, and Protocol

## Concept

Python's type system (PEP 484+) allows expressing relationships between types without sacrificing runtime flexibility. Staff-level candidates understand not just the syntax but when each construct is appropriate and what guarantees it provides.

### `TypeVar`: Parameterized Functions

`TypeVar` creates a type variable — a placeholder that a type checker fills in per call site:

```python
from typing import TypeVar

T = TypeVar('T')

def identity(x: T) -> T:
    return x

result: int = identity(42)       # T bound to int at this call site
result: str = identity("hello")  # T bound to str at this call site
```

**Constrained TypeVar:** restrict which types are valid:

```python
from typing import TypeVar

Numeric = TypeVar('Numeric', int, float, complex)

def add(a: Numeric, b: Numeric) -> Numeric:
    return a + b

add(1, 2)          # OK — int
add(1.0, 2.0)      # OK — float
add(1, 2.0)        # Error — a is int, b is float; must be the SAME type
add("a", "b")      # Error — str not in constraint
```

**Bounded TypeVar:** require the type to be a subclass of a bound:

```python
from typing import TypeVar

class Comparable:
    def __lt__(self, other): ...

C = TypeVar('C', bound='Comparable')

def minimum(lst: list[C]) -> C:
    return min(lst)   # works because C is guaranteed to support comparison
```

### `Generic`: Generic Classes

```python
from typing import Generic, TypeVar

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()

    def peek(self) -> T:
        return self._items[-1]

stack: Stack[int] = Stack()
stack.push(1)
stack.push(2)
val: int = stack.pop()   # type checker knows this is int

class Pair(Generic[K, V]):
    def __init__(self, key: K, value: V):
        self.key = key
        self.value = value

    def swap(self) -> 'Pair[V, K]':
        return Pair(self.value, self.key)
```

### `Protocol`: Structural Subtyping (Python 3.8+)

`Protocol` defines a structural interface — any object that has the required methods/attributes satisfies the protocol, without explicit registration:

```python
from typing import Protocol, runtime_checkable

class Drawable(Protocol):
    def draw(self) -> None: ...

    @property
    def color(self) -> str: ...

# These classes DON'T inherit from Drawable — they just have the right shape:
class Circle:
    color = "red"
    def draw(self) -> None:
        print(f"Circle ({self.color})")

class Square:
    color = "blue"
    def draw(self) -> None:
        print(f"Square ({self.color})")

def render(shape: Drawable) -> None:
    shape.draw()   # type checker: shape must have draw() and color

render(Circle())   # OK — Circle has draw() and color
render(Square())   # OK — Square has draw() and color
render(42)         # Type error — int has neither
```

**`@runtime_checkable`:** enables `isinstance()` checks (limited — only checks method presence, not signatures):

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Sized(Protocol):
    def __len__(self) -> int: ...

print(isinstance([1, 2, 3], Sized))   # True — list has __len__
print(isinstance(42, Sized))          # False — int has no __len__
print(isinstance("hello", Sized))     # True — str has __len__
```

### `@overload`: Multiple Signatures

`@overload` lets you declare multiple type signatures for a function, narrowing the return type based on input:

```python
from typing import overload

@overload
def parse(value: str) -> int: ...

@overload
def parse(value: bytes) -> str: ...

@overload
def parse(value: int) -> float: ...

def parse(value: str | bytes | int) -> int | str | float:
    if isinstance(value, str):
        return int(value)
    elif isinstance(value, bytes):
        return value.decode()
    else:
        return float(value)

x: int = parse("42")       # type checker knows return is int
y: str = parse(b"hello")   # type checker knows return is str
```

### Python 3.12+ `type` Syntax

Python 3.12 (PEP 695) adds explicit type parameter syntax:

```python
# Old way:
from typing import TypeVar, Generic
T = TypeVar('T')

class Stack(Generic[T]):
    ...

# New way (Python 3.12+):
class Stack[T]:
    def push(self, item: T) -> None: ...
    def pop(self) -> T: ...

def minimum[C: Comparable](lst: list[C]) -> C:
    return min(lst)

type Alias[T] = list[T] | set[T]   # type alias with type parameter
```

### `ParamSpec` and `Concatenate` (Python 3.10+)

For decorators that preserve the original function's parameter types:

```python
from typing import ParamSpec, Callable, TypeVar
import functools

P = ParamSpec('P')
R = TypeVar('R')

def timer(func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        import time
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__}: {time.perf_counter() - start:.3f}s")
        return result
    return wrapper

@timer
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"

# Type checker preserves: greet(name: str, greeting: str = "Hello") -> str
greet("Alice")           # OK
greet("Alice", "Hi")     # OK
greet(123)               # Type error — name must be str
```

---

## Interview Questions

### Q1: What's the difference between `TypeVar` with constraints vs `TypeVar` with a bound?

**Model answer:**
Both restrict which types are valid, but differently:

**Constrained TypeVar** (`TypeVar('T', A, B, C)`): the type must be EXACTLY one of the listed types (no subclasses). Each call site binds T to exactly one constraint:
```python
T = TypeVar('T', int, float)

def double(x: T) -> T: return x * 2

double(1)     # T = int, returns int
double(1.0)   # T = float, returns float
double(True)  # T = int (bool is subclass of int, but promoted to int)
```

**Bounded TypeVar** (`TypeVar('T', bound=Base)`): the type must be `Base` or any subclass. Preserves the concrete subtype:
```python
class Animal:
    def speak(self): ...

class Dog(Animal):
    def fetch(self): ...

A = TypeVar('A', bound=Animal)

def make_speak(animal: A) -> A:
    animal.speak()
    return animal

dog: Dog = make_speak(Dog())   # returns Dog, not Animal — bound preserves subtype
```

Use **constraints** when you have a fixed set of supported types with no inheritance relationship. Use **bound** when you want to require certain methods (polymorphism) while preserving the concrete type.

### Q2: When would you use a `Protocol` instead of an ABC?

**Model answer:**
Use `Protocol` for structural typing (duck typing with type checking); use `ABC` for nominal typing (explicit registration required).

**Protocol wins when:**
1. You can't or don't want to change the existing class (third-party code, stdlib types).
2. The interface is small (1-3 methods).
3. You want duck-typing semantics with type safety.

```python
from typing import Protocol

class Closeable(Protocol):
    def close(self) -> None: ...

def cleanup(resource: Closeable) -> None:
    resource.close()

# Works with socket, file, psycopg2.connection, httpx.Client, etc.
# None of these inherit from Closeable — they just have .close()
```

**ABC wins when:**
1. You want to enforce implementation at class definition time (raises `TypeError` on instantiation if abstract methods missing).
2. You need `isinstance()` checks (ABCs with `__subclasshook__` are more powerful).
3. You want mixin methods provided for free (`Sequence.index()`, `Mapping.keys()`).

```python
from abc import ABC, abstractmethod

class DataStore(ABC):
    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def write(self, key: str, data: bytes) -> None: ...

    def exists(self, key: str) -> bool:    # mixin method — free!
        try:
            self.read(key)
            return True
        except KeyError:
            return False

class SQLiteStore(DataStore):
    def read(self, key): ...
    def write(self, key, data): ...
    # exists() provided by ABC
```

### Q3: What is `@overload` for, and what does it NOT do?

**Model answer:**
`@overload` is purely a **type-checking hint** — it does not change runtime behavior. You must still write the actual implementation (the final undecorated definition), and that implementation handles all cases:

```python
from typing import overload

@overload
def stringify(x: int) -> str: ...
@overload
def stringify(x: list[int]) -> list[str]: ...

def stringify(x):           # actual implementation — no type annotations
    if isinstance(x, int):
        return str(x)
    return [str(i) for i in x]
```

The overloaded signatures tell the type checker which output type to infer for each input type. At runtime, there's only one function.

`@overload` does NOT:
- Change the runtime function called.
- Dispatch to different implementations.
- Add runtime type checking.

For runtime dispatch on type: use `functools.singledispatch`.

### Q4: Explain `Generic` vs inheriting from a concrete parameterized type.

**Model answer:**
`Generic[T]` is a base class that signals "this class has a type parameter T." Inheriting from a concrete parameterized type fixes the type parameter for that class:

```python
from typing import Generic, TypeVar, List

T = TypeVar('T')

class MyList(Generic[T]):          # T is free — caller specifies it
    def __init__(self) -> None:
        self._data: list[T] = []

class IntList(list[int]):          # T fixed to int — always a list of ints
    def sum(self) -> int:
        return sum(self)

# Using Generic[T]:
ints: MyList[int] = MyList()       # caller fixes T
strs: MyList[str] = MyList()       # different T per instance

# Using concrete inheritance:
il = IntList([1, 2, 3])
il.sum()   # 6
```

Inherit from `Generic[T]` when building a generic container. Inherit from `list[int]` (concrete) when building a specialized, fixed-type container.

### Q5: What is `Self` type and when do you need it?

**Model answer:**
`Self` (from `typing`, Python 3.11+, or `typing_extensions`) refers to the current class's type, including subclasses. It's essential for methods that return `self` or a new instance of the same type:

```python
from typing import Self   # Python 3.11+

class Builder:
    def __init__(self) -> None:
        self._config: dict = {}

    def set(self, key: str, value: str) -> Self:  # NOT 'Builder' — see below
        self._config[key] = value
        return self

class SpecialBuilder(Builder):
    def special_method(self) -> None: ...

b: SpecialBuilder = SpecialBuilder().set("x", "1")  # returns SpecialBuilder, not Builder
b.special_method()   # type checker knows b is SpecialBuilder
```

If you wrote `-> Builder` instead of `-> Self`, the type checker would infer `SpecialBuilder().set(...)` as `Builder`, losing the subtype. `Self` preserves it.

Also needed for classmethods that create instances:
```python
class Config:
    @classmethod
    def from_dict(cls, data: dict) -> Self:
        obj = cls()
        obj.__dict__.update(data)
        return obj
```

---

## Gotcha Follow-ups

**"What does `TypeVar('T')` with the same name `T` but created twice mean for type checking?"**
Each `TypeVar(...)` call creates a distinct type variable, even if the name is the same string. Two `T = TypeVar('T')` at module level in the same module are the same variable (it's just a name binding). But `TypeVar('T')` in two different modules are different type variables — they're identified by their object identity, not their name string. The string is just for error messages.

**"Can a `Protocol` method have a default implementation?"**
Yes. Protocol methods with bodies are still structural — the class doesn't NEED to override them (the Protocol's default runs). But most Protocols have `...` (ellipsis) bodies, indicating the body doesn't matter for structural checking. A Protocol with a real body is more like an ABC mixin.

---

## Under the Hood

`TypeVar` is implemented in `Lib/typing.py` as a class. At runtime, `TypeVar` objects are plain Python objects — they carry no runtime enforcement. Type checkers (mypy, pyright) use them during static analysis; at runtime, `list[int]` creates a `types.GenericAlias` and `Generic[T]` creates `typing._GenericAlias`, both of which are transparent at runtime.

`Protocol` (PEP 544) uses `__protocol_attrs__` at the class level to track required attributes. `runtime_checkable` protocols implement `__instancecheck__` via `_ProtocolMeta.__instancecheck__` — it only checks for the presence of methods (using `hasattr`), not their signatures.
