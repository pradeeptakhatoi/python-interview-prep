# Variance: Covariance and Contravariance

## Concept

Variance describes how generic type relationships (subtype/supertype) propagate through parameterized types. It answers: if `Dog` is a subtype of `Animal`, is `Container[Dog]` a subtype of `Container[Animal]`?

```
Covariant:     Container[Dog]  IS-A  Container[Animal]   (preserves direction)
Contravariant: Container[Animal] IS-A Container[Dog]      (reverses direction)
Invariant:     neither is a subtype of the other          (no relationship)
```

### Invariant (Default)

By default, `TypeVar` is invariant — `Container[Dog]` and `Container[Animal]` are unrelated, even if `Dog <: Animal`:

```python
from typing import TypeVar, Generic

T = TypeVar('T')   # invariant

class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item
    def get(self) -> T:
        return self.item
    def set(self, item: T) -> None:
        self.item = item

class Animal: pass
class Dog(Animal): pass

box_dog: Box[Dog] = Box(Dog())
box_animal: Box[Animal] = box_dog   # TYPE ERROR — invariant!
```

Why? If `Box[Dog]` were a subtype of `Box[Animal]`, you could do:
```python
box_animal.set(Animal())   # stores an Animal in a Box[Dog]
dog: Dog = box_dog.get()   # retrieves an Animal, but expects Dog — runtime error!
```

`Box` must be invariant because it both reads AND writes.

### Covariant (`covariant=True`)

A type is covariant if it's read-only (produces values). `Container[Dog]` IS a `Container[Animal]` if you can only read from the container:

```python
from typing import TypeVar, Generic

T_co = TypeVar('T_co', covariant=True)

class Readable(Generic[T_co]):
    def __init__(self, item: T_co) -> None:
        self._item = item

    def get(self) -> T_co:   # only read — safe to be covariant
        return self._item

readable_dog: Readable[Dog] = Readable(Dog())
readable_animal: Readable[Animal] = readable_dog   # OK — covariant

# Python built-in covariant types:
# Tuple[int, ...] is covariant — tuples are immutable
# FrozenSet[int] is covariant — frozensets are immutable
# Coroutine is covariant in its return type
```

**`Sequence` is covariant** (read-only view — no append/set):
```python
from typing import Sequence

def process(items: Sequence[Animal]) -> None:
    for item in items:
        item.eat()

dogs: list[Dog] = [Dog(), Dog()]
process(dogs)   # OK — Sequence[Dog] <: Sequence[Animal] (covariant)

# But list itself is invariant:
def bad(animals: list[Animal]) -> None:
    animals.append(Animal())   # would break if called with list[Dog]

bad(dogs)   # TYPE ERROR — list[Dog] is NOT list[Animal]
```

### Contravariant (`contravariant=True`)

A type is contravariant if it only consumes values (write-only). If you can process Animals, you can certainly process Dogs:

```python
from typing import TypeVar, Generic

T_contra = TypeVar('T_contra', contravariant=True)

class Consumer(Generic[T_contra]):
    def consume(self, item: T_contra) -> None:  # only write — safe to be contravariant
        print(f"Consuming {item}")

consumer_animal: Consumer[Animal] = Consumer()
consumer_dog: Consumer[Dog] = consumer_animal   # OK — contravariant

# An Animal consumer CAN consume a Dog (Dog is-a Animal)
# A Dog consumer CANNOT safely consume just any Animal
```

**`Callable` is contravariant in parameters, covariant in return type:**

```python
from typing import Callable

# f accepts Animal → can be used where Dog consumer expected (contravariant params)
def f(a: Animal) -> None: print(a)

def process_dog(callback: Callable[[Dog], None]) -> None:
    callback(Dog())

process_dog(f)   # OK — f accepts Animal (supertype of Dog), which is fine
                 # if we pass a Dog, f can handle it (Animal is a Dog's supertype)

# Return type is covariant:
def factory_dog() -> Dog: return Dog()
factory_animal_needed: Callable[[], Animal] = factory_dog  # OK — Dog IS-A Animal
```

### Variance in Python's `typing` Module

```python
from typing import TypeVar, List, Sequence, MutableSequence, Tuple

# list is invariant (both reads and writes):
T = TypeVar('T')
# list[Dog] is NOT list[Animal] — can't assign

# Sequence is covariant (read-only view):
T_co = TypeVar('T_co', covariant=True)
# Sequence[Dog] IS Sequence[Animal]

# MutableSequence is invariant (has both read and write):
# MutableSequence[Dog] is NOT MutableSequence[Animal]

# Tuple[T, ...] is covariant:
t: tuple[Dog, ...] = (Dog(), Dog())
t_animal: tuple[Animal, ...] = t   # OK — covariant

# Fixed-length tuple: each position is independently covariant
t2: tuple[Dog, int] = (Dog(), 1)
t2_animal: tuple[Animal, int] = t2   # OK
```

---

## Interview Questions

### Q1: Why is `list[Dog]` not a subtype of `list[Animal]` in Python's type system?

**Model answer:**
`list` is mutable — it has both reads (`__getitem__`) and writes (`append`, `__setitem__`). If `list[Dog]` were a subtype of `list[Animal]`, the following would be type-safe but crash at runtime:

```python
dogs: list[Dog] = [Dog()]
animals: list[Animal] = dogs  # pretend this is allowed

animals.append(Cat())   # Cat is an Animal, so list[Animal] accepts it
dog: Dog = dogs[0]      # dogs[0] is actually a Cat — runtime AttributeError!
dog.fetch()             # Dog method, Cat doesn't have it
```

The type system must forbid this. `list` is therefore **invariant** — `list[Dog]` and `list[Animal]` have no subtype relationship.

The fix: use `Sequence[Animal]` as the parameter type when you only read:
```python
def print_names(animals: Sequence[Animal]) -> None:  # read-only
    for a in animals:
        print(a)

print_names([Dog(), Dog()])   # OK — Sequence is covariant
```

### Q2: Explain why `Callable[[Animal], None]` is a subtype of `Callable[[Dog], None]` (contravariance in parameters).

**Model answer:**
If `f: Callable[[Animal], None]` is expected where `Callable[[Dog], None]` is needed, we call `f` with a `Dog`. That's fine — `f` can handle `Dog` because `Dog` is an `Animal`.

```python
class Animal:
    def breathe(self): ...

class Dog(Animal):
    def fetch(self): ...

def handle_animal(a: Animal) -> None:
    a.breathe()   # safe — any Animal can breathe

def handle_dog(d: Dog) -> None:
    d.fetch()     # requires Dog-specific method

# handle_animal can replace handle_dog:
callback: Callable[[Dog], None] = handle_animal  # OK — contravariant
callback(Dog())  # passes a Dog to handle_animal — Dog is-a Animal, safe

# handle_dog CANNOT replace handle_animal:
callback2: Callable[[Animal], None] = handle_dog  # ERROR
callback2(Animal())  # would pass a non-Dog Animal to handle_dog — fetch() would fail
```

**Mnemonic:** Callable parameters are **contra**variant (flip the subtype direction). Return types are **co**variant (same direction). `Callable[[Dog], Animal]` is a subtype of `Callable[[Animal], Dog]`... wait, no: it's a subtype of `Callable[[Animal], Animal]` and `Callable[[Dog], Dog]`. The full rule: `Callable[[P1], R1] <: Callable[[P2], R2]` iff `P2 <: P1` (params reversed) AND `R1 <: R2` (returns same direction).

### Q3: What is `TypeVar(covariant=True)` and when would you define a covariant TypeVar?

**Model answer:**
`covariant=True` on a `TypeVar` signals to the type checker that a generic class using this TypeVar is covariant in it — meaning `Generic[Dog] <: Generic[Animal]` when `Dog <: Animal`.

You'd define a covariant TypeVar when building a **producer** — a container that only yields values and never accepts them:

```python
from typing import TypeVar, Generic, Iterator

T_co = TypeVar('T_co', covariant=True)

class ReadOnlyContainer(Generic[T_co]):
    def __init__(self, items: list) -> None:
        self._items = items

    def get(self, i: int) -> T_co:     # producer — yields T_co
        return self._items[i]

    def __iter__(self) -> Iterator[T_co]:  # producer
        return iter(self._items)

    # NO __setitem__ or similar — no consuming

dogs: ReadOnlyContainer[Dog] = ReadOnlyContainer([Dog(), Dog()])
animals: ReadOnlyContainer[Animal] = dogs   # OK — covariant
```

Type checkers validate the variance declaration — if you add a method that consumes `T_co`, the checker will warn you that the TypeVar can't be covariant.

### Q4: How does variance apply to `Tuple` types?

**Model answer:**
Fixed-length `tuple[A, B, C]` is covariant in each position independently (each position is a separate type parameter, all covariant):

```python
class Animal: pass
class Dog(Animal): pass
class Cat(Animal): pass

t: tuple[Dog, Cat] = (Dog(), Cat())
t_animal: tuple[Animal, Animal] = t   # OK — covariant in both positions
```

Variable-length `tuple[T, ...]` is covariant in `T`:
```python
dogs_var: tuple[Dog, ...] = (Dog(), Dog(), Dog())
animals_var: tuple[Animal, ...] = dogs_var   # OK
```

This makes `tuple` useful as a covariant alternative to `list` when you have a fixed collection you want to pass around without worrying about mutation side-effects:

```python
def process(animals: tuple[Animal, ...]) -> None:
    for a in animals:
        a.eat()

process((Dog(), Dog()))   # OK — tuple[Dog, ...] <: tuple[Animal, ...]
```

### Q5: What is the "Liskov Substitution Principle" and how does it relate to variance?

**Model answer:**
The Liskov Substitution Principle (LSP): if `S` is a subtype of `T`, objects of type `T` may be replaced with objects of type `S` without altering correctness.

In Python typing: variance rules are LSP enforcement. Covariance/contravariance/invariance decisions ensure that substituting a generic subtype doesn't create unsound code.

LSP violation example:
```python
class Animal:
    def eat(self, food: Animal) -> Animal: ...   # signature

class Dog(Animal):
    def eat(self, food: Dog) -> Dog: ...  # narrower input — LSP VIOLATION
    # Caller expects eat(Animal) but gets eat(Dog) — can't pass Cat (an Animal) to Dog.eat
```

Proper LSP-conformant override:
```python
class Dog(Animal):
    def eat(self, food: Animal) -> Dog: ...
    # Input is widened or same (Animal, not Dog) — contravariance
    # Output is narrowed or same (Dog, is-a Animal) — covariance
```

Python's type system enforces this: method parameters should be contravariant (can accept supertype), return types should be covariant (can return subtype). `mypy` will warn on input narrowing in subclasses.

---

## Gotcha Follow-ups

**"Is `dict[str, Dog]` a subtype of `dict[str, Animal]`?"**
No — `dict` is invariant in its value type (you can both read and write values). You can retrieve a Dog (covariant) or insert an Animal (contravariant) — since it must do both, invariance is required. Use `Mapping[str, Animal]` (read-only view) if you only need to read values, as `Mapping` is covariant in its value type.

**"What does `Union[int, str]` mean for variance?"**
`Union` itself is covariant: `Union[Dog, Cat]` is a subtype of `Union[Animal, Animal]` (i.e., `Union[Animal]` = `Animal`) because both `Dog` and `Cat` are `Animal`s. More precisely, `Union[A, B] <: Union[C, D]` if `A <: C` and `B <: D`.

---

## Under the Hood

Variance is entirely a static analysis concept — Python's runtime has no notion of it. The `covariant` and `contravariant` parameters on `TypeVar` just set flags that mypy/pyright read. At runtime, `TypeVar('T', covariant=True)` is just a `TypeVar` instance with `__covariant__ = True`.

mypy checks variance declarations against class usage — if you declare a TypeVar covariant but use it in a write position, it reports an error like "Covariant TypeVar 'T_co' used in contravariant position." This verification happens at type-check time only, never at runtime.
