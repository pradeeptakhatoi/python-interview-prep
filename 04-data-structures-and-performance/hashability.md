# Hashability: __hash__/__eq__ Contracts

## Concept

An object is **hashable** if it has a stable `__hash__` return value and can be compared with `__eq__`. Hashable objects can be dict keys or set members. Python enforces this via two rules:
1. Objects that compare equal must have equal hashes.
2. If `__eq__` is defined, `__hash__` must also be defined (or set to `None` to make the class unhashable).

```python
# Built-in types:
hash(42)           # 42 (int hashes to itself for small values)
hash("hello")      # varies (randomized per process in Python 3.3+)
hash((1, 2, 3))    # stable (tuple of hashables)
hash([1, 2, 3])    # TypeError: unhashable type: 'list'
hash({1: 2})       # TypeError: unhashable type: 'dict'
hash({1, 2})       # TypeError: unhashable type: 'set'
hash(frozenset({1, 2}))    # OK
```

### The Hash/Eq Contract

```
Equal objects must have equal hashes:
    a == b  →  hash(a) == hash(b)

Unequal hashes guarantee inequality:
    hash(a) != hash(b)  →  a != b

BUT: equal hashes do NOT imply equality (collision):
    hash(a) == hash(b)  does NOT mean a == b
```

This is why dict/set lookup requires BOTH a hash match AND an equality check.

### What Happens When You Define Only `__eq__`

```python
class BadPoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    # __hash__ NOT defined → Python sets __hash__ = None automatically

p = BadPoint(1, 2)
hash(p)           # TypeError: unhashable type: 'BadPoint'
{p: "value"}      # TypeError
{p}               # TypeError
```

Python sets `__hash__ = None` automatically when `__eq__` is defined without `__hash__`. This prevents violations of the hash/eq contract.

### Implementing `__hash__` Correctly

```python
class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        # Include exactly the same fields used in __eq__
        # tuple hashing is efficient and handles composition well
        return hash((self.x, self.y))

p1 = Point(1.0, 2.0)
p2 = Point(1.0, 2.0)

print(p1 == p2)                    # True
print(hash(p1) == hash(p2))        # True
print({p1: "origin", p2: "same"})  # {Point(1.0, 2.0): 'same'} — same key!

s = {p1, p2}
print(len(s))                      # 1 — they're the same element
```

### `__hash__` for Mutable Objects

Mutable objects that support `__hash__` create a dangerous situation — if you mutate an object that's already in a set or dict, its hash changes but the object is at the wrong bucket:

```python
class MutablePoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))

p = MutablePoint(1, 2)
s = {p}                  # stored at bucket for hash((1,2))

p.x = 99                 # mutate — hash is now hash((99,2))

print(p in s)            # False! object is at bucket (1,2) but now hashes to (99,2)
print(list(s)[0] in s)   # also False! dict is in inconsistent state

# The correct approach: make hashable objects immutable, or use id()-based hash
```

**Rule:** Only hash on fields that are immutable or that you commit to never changing.

### Hash Collision Behavior

```python
class ConstHash:
    def __init__(self, v):
        self.v = v

    def __hash__(self):
        return 42  # catastrophic — all instances collide

    def __eq__(self, other):
        return self.v == other.v

# Lookup degrades to O(n) when all keys collide
d = {ConstHash(i): i for i in range(1000)}
# Every insert probes all previous entries: O(n²) construction
```

### `hash()` for Built-in Types

```python
# Integers: hash(n) == n for small n; special case for -1 (becomes -2)
print(hash(-1))    # -2 (Python maps -1 to -2 to avoid C's -1 error sentinel)
print(hash(0))     # 0
print(hash(1))     # 1

# Floats: equal values have equal hashes even across types
print(hash(1.0))   # 1 (same as hash(1))
print(hash(1.5))   # 1152921504606846977 (not human-readable)

# Cross-type equality must have cross-type hash equality:
print(1 == 1.0)         # True
print(hash(1) == hash(1.0))  # True — law enforced

# Complex numbers:
print(hash(1+0j))  # 1 (same as hash(1) and hash(1.0))

# Strings: randomized per process (PYTHONHASHSEED)
print(hash("hello"))   # different each run
```

### `sys.hash_info` — Understanding the Hash System

```python
import sys

print(sys.hash_info)
# sys.hash_info(width=64, modulus=2305843009213693951, inf=314159,
#               nan=0, imag=1000003, algorithm='siphash24', hash_bits=64,
#               seed_bits=128, cutoff=0)
```

- `modulus` is a Mersenne prime (2^61 - 1). Hashes are computed modulo this.
- `algorithm` is SipHash-1-3 or SipHash-2-4 (randomized, keyed hash for str/bytes).
- Integer hash: `hash(n) = n % modulus` (for large ints).
- Float hash: defined by the numeric hash protocol to ensure cross-type consistency.

---

## Interview Questions

### Q1: Explain the hash/equality contract. What happens if you violate it?

**Model answer:**
The contract: objects that compare equal (`a == b`) must produce the same hash value (`hash(a) == hash(b)`).

If violated, dict and set operations produce wrong results — items are lost, lookups fail, or duplicates appear:

```python
class Broken:
    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        return True   # every instance equals every other

    def __hash__(self):
        return id(self)   # every instance has different hash

a = Broken(1)
b = Broken(2)
print(a == b)     # True (says so)
print(hash(a) == hash(b))  # False (different IDs!)

s = {a, b}
print(len(s))     # 2 — but a == b, so it should be 1!
print(a in s)     # True (because a is in s)
print(b in s)     # True (because b is in s)
# But logically both are equal to each other — inconsistent behavior
```

The CPython lookup algorithm: first check if `hash(lookup_key) == hash(stored_key)`, then check `lookup_key == stored_key`. If hashes differ, the equality check is SKIPPED (they can't be equal with different hashes, by contract). Violating the contract bypasses the equality check at the wrong time.

### Q2: Why does Python automatically set `__hash__ = None` when you define `__eq__`?

**Model answer:**
This is enforcement of the hash/eq contract. If you override `__eq__` but keep the inherited `object.__hash__` (which returns `id(self) // 16`), you'd get:

```python
class BadPair:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    # Without Python's automatic hash-None: __hash__ = object.__hash__

p1 = BadPair(1, 2)
p2 = BadPair(1, 2)

print(p1 == p2)          # True (our __eq__ says so)
print(hash(p1) == hash(p2))  # False! (id-based, different objects)
# The contract is violated — equal objects have different hashes
# p1 and p2 would be treated as different dict keys, breaking dedup
```

Python prevents this silently broken state by making the class unhashable when `__eq__` is defined. You must explicitly implement `__hash__` if you want hashability.

To inherit the parent's `__hash__` intentionally (unusual):
```python
class MyClass(Parent):
    def __eq__(self, other): ...
    __hash__ = Parent.__hash__   # explicitly opt in
```

### Q3: How does Python hash `float` values to ensure `hash(1) == hash(1.0)`?

**Model answer:**
Python enforces that numerically equal values have the same hash, even across types (`int`, `float`, `complex`, `Decimal`, `Fraction`). This is the **numeric hash protocol**.

For floats, the hash is computed based on the rational representation of the float:
- `1.0` is exactly `1/1`, so `hash(1.0)` uses the same formula as `hash(1)` → both return `1`.
- `0.5` is `1/2`, hashed as `pow(2, -1, M)` where M is the Mersenne prime modulus.

```python
from fractions import Fraction
from decimal import Decimal

print(hash(1) == hash(1.0) == hash(Fraction(1)) == hash(Decimal('1')))  # True
print(hash(0.5) == hash(Fraction(1, 2)))   # True

# Why this matters for dict:
d = {1: "int_key"}
print(d[1.0])    # "int_key" — 1.0 finds the same bucket as 1
print(d[1+0j])   # "int_key" — complex 1+0j also equals 1
```

The implication: you can't have `1` and `1.0` as separate keys in the same dict. They ARE the same key.

### Q4: What is `__hash__` for a class that inherits from a hashable parent?

**Model answer:**
Inheritance behavior for `__hash__`:
1. If you don't override `__eq__` or `__hash__`: inherit both (stays hashable with `object.__hash__`).
2. If you override `__eq__` only: `__hash__` is set to `None` → unhashable.
3. If you override both `__eq__` and `__hash__`: works as expected.
4. If you override only `__hash__`: allowed (unusual) — inherits `__eq__` from parent.

```python
class Base:
    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        return self.v == other.v

    def __hash__(self):
        return hash(self.v)

class Child(Base):
    def __init__(self, v, extra):
        super().__init__(v)
        self.extra = extra

    # Does NOT override __eq__ or __hash__ — inherits both
    # But: two Childs with same v but different extra ARE equal!
    # This is a semantic problem — you should override both:

    def __eq__(self, other):
        return isinstance(other, Child) and self.v == other.v and self.extra == other.extra

    def __hash__(self):
        return hash((self.v, self.extra))
```

**Rule:** whenever you override `__eq__`, always explicitly override `__hash__` to use the same fields.

### Q5: How do you make a mutable class conditionally hashable?

**Model answer:**
There are two approaches:

**1. Freeze-on-hash:** hash based on current state, but prohibit mutation after first hash:
```python
class FrozenAfterHash:
    def __init__(self, data: list):
        self._data = list(data)
        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(tuple(self._data))
        return self._hash

    def mutate(self, val):
        if self._hash is not None:
            raise RuntimeError("Cannot mutate: object has been hashed")
        self._data.append(val)
```

**2. Use `id()` as hash (object identity semantics):**
```python
class IdentityHashable:
    """Hashable by identity — two distinct instances are never equal."""

    def __eq__(self, other):
        return self is other    # identity equality

    def __hash__(self):
        return id(self)

# This is exactly what object.__hash__ and object.__eq__ do by default.
# Explicitly re-implement if parent's __eq__ was overridden.
```

The `id()`-based approach is suitable when you want to put mutable objects in sets (e.g., set of active connections), but equality means "same object" not "same data."

---

## Gotcha Follow-ups

**"What is `hash(-1)` in Python and why?"**
`hash(-1)` returns `-2`. CPython uses `-1` as a C-level error sentinel in hash functions (C functions return -1 to signal an error). The Python-level hash protocol remaps `-1` to `-2` to avoid confusion with the error sentinel. This is an implementation detail but a common interview trap.

```python
print(hash(-1))     # -2
print(hash(-2))     # -2 (these two hash to the same value!)
print(-1 == -2)     # False — hash collision, but not equal
```

**"Can a class be both mutable and stored in a set?"**
Yes, if you use identity-based hashing (or freeze-after-hash). The stdlib's `weakref.WeakSet` stores objects that the user could mutate. The set's integrity relies on the object NOT mutating in a way that changes its hash. If it does, the set is in an inconsistent state.

---

## Under the Hood

Hash computation: `Objects/object.c`, `PyObject_Hash()`. For integers: `Objects/longobject.c`, `long_hash()` — uses the Mersenne prime modulus. For strings: `Objects/unicodeobject.c`, `unicode_hash()` — SipHash-1-3 with a per-process random seed (initialized from OS entropy at startup).

`__hash__ = None` mechanism: in `type_new()` (`Objects/typeobject.c`), if the new class defines `__eq__` and inherits `__hash__` from a class where `__hash__` was not overridden from `object.__hash__`, the new class's `tp_hash` is set to `PyObject_HashNotImplemented`, and `__hash__` is set to `None` in the class dict. This causes `TypeError: unhashable type` on `hash()` calls.
