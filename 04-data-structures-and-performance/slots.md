# __slots__: Memory Savings and Tradeoffs

## Concept

By default, Python instances store attributes in a `__dict__` — a per-instance dictionary. `__slots__` replaces this dictionary with a fixed-size array of slots (C-level `PyMemberDef` structs), eliminating `__dict__` (and `__weakref__` by default).

```python
import sys

class WithDict:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class WithSlots:
    __slots__ = ('x', 'y')

    def __init__(self, x, y):
        self.x = x
        self.y = y

a = WithDict(1, 2)
b = WithSlots(1, 2)

print(sys.getsizeof(a))           # 48 bytes (instance header)
print(sys.getsizeof(a.__dict__))  # 232 bytes (initial dict allocation)
print(sys.getsizeof(b))           # 56 bytes (48 + 2 slots × 8 bytes each)
# No __dict__ on b: 56 bytes total vs 280 bytes total — 5× reduction
```

### How `__slots__` Works Internally

When Python processes a `class` with `__slots__`:
1. For each slot name, a **data descriptor** (`member_descriptor`) is added to the class dict.
2. The descriptor reads from / writes to a fixed position in the instance's memory (an offset into the `PyObject` struct).
3. The instance's `tp_basicsize` is increased to accommodate the slots.
4. `__dict__` is NOT created per-instance (unless you explicitly add `'__dict__'` to `__slots__`).

```python
class Point:
    __slots__ = ('x', 'y')

print(type(Point.x))     # <class 'member_descriptor'>
print(Point.x.__get__)   # <slot wrapper '__get__' of 'member_descriptor' objects>

p = Point()
p.x = 10
print(p.x)               # 10
p.z = 5                  # AttributeError — no __dict__, can't set undefined attrs
```

### Memory Savings: Real Numbers

```python
import sys
import tracemalloc

tracemalloc.start()

N = 100_000

class NodeDict:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

class NodeSlots:
    __slots__ = ('val', 'left', 'right')

    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

snapshot_before = tracemalloc.take_snapshot()

nodes_dict = [NodeDict(i) for i in range(N)]
snap_dict = tracemalloc.take_snapshot()

nodes_dict = None  # release
nodes_slots = [NodeSlots(i) for i in range(N)]
snap_slots = tracemalloc.take_snapshot()

# NodeDict: ~48 bytes per instance + ~232 bytes dict = ~280 bytes each = ~28 MB for 100K
# NodeSlots: ~72 bytes per instance (48 header + 3×8 slots) = ~7.2 MB for 100K
```

Typical savings:
- **Simple data class (3-5 attrs):** 3-5× memory reduction.
- **Cached property / lazy attrs pattern:** breaks without `'__dict__'` in slots.

### Inheritance Implications

`__slots__` only saves memory if **all classes in the MRO** define `__slots__`. If any class (including the implicit `object`) provides `__dict__`, instances will have one:

```python
class Base:
    __slots__ = ('x',)

class Child(Base):
    # No __slots__ defined — Python adds __dict__ automatically!
    pass

c = Child()
c.x = 1       # uses Base's slot
c.y = 2       # stored in Child's __dict__
print(hasattr(c, '__dict__'))   # True — inheritance broke slots savings

class GoodChild(Base):
    __slots__ = ('y',)    # declares its own slots too

gc = GoodChild()
print(hasattr(gc, '__dict__'))  # False — no __dict__ at any level
```

### `__weakref__` and `__slots__`

By default, `__slots__` removes `__weakref__` support. If you need weak references to instances:

```python
class Cacheable:
    __slots__ = ('data', '__weakref__')   # explicitly add __weakref__

    def __init__(self, data):
        self.data = data

import weakref
c = Cacheable("hello")
ref = weakref.ref(c)   # works — __weakref__ slot exists
```

### Multiple Inheritance Complications

Multiple inheritance with `__slots__` requires all bases to have non-overlapping slots. If two bases define the same slot name, Python raises `TypeError`:

```python
class A:
    __slots__ = ('x', 'y')

class B:
    __slots__ = ('y', 'z')    # 'y' overlaps with A

class C(A, B): pass
# TypeError: multiple bases have instance lay-out conflict
# (both define 'y' but at different C-level offsets)

# Fix: only put shared attrs in one base, or use a common ancestor
class A:
    __slots__ = ('x',)

class B:
    __slots__ = ('z',)

class C(A, B):
    __slots__ = ('y',)    # no conflicts

c = C()
c.x = 1; c.y = 2; c.z = 3   # all work
```

### When NOT to Use `__slots__`

1. **Dynamic attributes:** If code does `setattr(obj, computed_name, value)`, slots break it (unless `'__dict__'` is in slots).
2. **Pickling:** Requires extra `__getstate__`/`__setstate__` if using slots without `__dict__`.
3. **Multiple inheritance:** Conflicts when combined with other slotted classes.
4. **Dataclasses:** `@dataclass` supports `__slots__=True` (Python 3.10+) cleanly.

```python
from dataclasses import dataclass

@dataclass(slots=True)   # Python 3.10+ — creates a new class with __slots__
class Config:
    host: str
    port: int
    timeout: float = 30.0

c = Config("localhost", 5432)
print(hasattr(c, '__dict__'))  # False
print(sys.getsizeof(c))        # compact, no __dict__
```

---

## Interview Questions

### Q1: What exactly does `__slots__` do? How does it save memory?

**Model answer:**
By default, every Python instance has a `__dict__` — a dictionary that maps attribute names to values. Even a fresh empty instance with no attributes carries a 232-byte dictionary allocation (initial hash table).

`__slots__` replaces this per-instance dict with fixed-size C-level slots. Each slot is a `PyObject*` pointer (8 bytes on 64-bit) at a known offset within the instance's memory. The descriptor machinery (`member_descriptor`) reads/writes these directly.

Memory impact for a class with 3 attributes:
- Without slots: 48 bytes (instance header) + 232 bytes (`__dict__`) = ~280 bytes.
- With slots: 48 + 24 = 72 bytes — nearly 4× smaller.

At 1 million instances (think parsed log entries, graph nodes), this is the difference between 280 MB and 72 MB.

### Q2: Why does inheriting from a slotted class without declaring `__slots__` in the subclass break the memory savings?

**Model answer:**
When a subclass doesn't declare `__slots__`, Python adds `__dict__` to the subclass automatically (to preserve normal Python behavior). Instances of the subclass then have BOTH the parent's slots AND a `__dict__`.

```python
class Efficient:
    __slots__ = ('x', 'y')

class Wasteful(Efficient):
    pass  # no __slots__ — Wasteful instances have slots + __dict__

w = Wasteful()
w.x = 1        # uses Efficient's slot
w.z = 99       # stored in __dict__
print(hasattr(w, '__dict__'))  # True — slots savings are gone
print(sys.getsizeof(w))        # back to large size
```

The fix is to explicitly declare `__slots__` in every class in the hierarchy. The subclass can add NEW slot names; it doesn't need to repeat the parent's.

### Q3: How do `__slots__` interact with `__dict__` — can you have both?

**Model answer:**
Yes — add `'__dict__'` to `__slots__` explicitly:

```python
class Hybrid:
    __slots__ = ('x', 'y', '__dict__')

    def __init__(self):
        self.x = 10
        self.y = 20

h = Hybrid()
h.x = 1        # uses slot
h.z = 99       # stored in __dict__ — dynamic attrs work
print(h.__dict__)  # {'z': 99}
```

Use case: you have a handful of attributes that are always present (put in `__slots__` for speed) and want to allow arbitrary additional attributes (put `__dict__` in slots). The hot-path attributes get C-level slot access; occasional dynamic attrs go to the dict.

This is also needed to make descriptors like `functools.cached_property` work (they store results in the instance `__dict__`).

### Q4: Can `__slots__` affect pickling? How do you fix it?

**Model answer:**
Python's default pickle protocol relies on `__dict__` for state. With `__slots__` only (no `__dict__`), `pickle` doesn't know how to get and set the state:

```python
import pickle

class Point:
    __slots__ = ('x', 'y')

    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
data = pickle.dumps(p)   # raises: TypeError for older protocols, or works but may miss slots
p2 = pickle.loads(data)
print(p2.x, p2.y)        # may fail or give wrong results depending on protocol
```

Fix: implement `__getstate__` and `__setstate__`:
```python
class Point:
    __slots__ = ('x', 'y')

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __getstate__(self):
        return {'x': self.x, 'y': self.y}

    def __setstate__(self, state):
        self.x = state['x']
        self.y = state['y']

p = Point(3, 4)
data = pickle.dumps(p)
p2 = pickle.loads(data)
print(p2.x, p2.y)   # 3 4 — works correctly
```

Note: Python 3.11+ handles slots correctly in pickle protocol 5, but explicit `__getstate__`/`__setstate__` is safest for compatibility.

### Q5: What is the performance difference for attribute access with vs without `__slots__`?

**Model answer:**
With `__slots__`, attribute access compiles to a C-level offset read/write — equivalent to `*(PyObject**)(obj + offset)`. This is faster than dict lookup (hash compute + probe + dict read).

```python
import timeit

class WithDict:
    def __init__(self): self.x = 42

class WithSlots:
    __slots__ = ('x',)
    def __init__(self): self.x = 42

a = WithDict()
b = WithSlots()

t_dict  = timeit.timeit('a.x', globals={'a': a}, number=10_000_000)
t_slots = timeit.timeit('b.x', globals={'b': b}, number=10_000_000)

print(f"dict:  {t_dict:.3f}s")
print(f"slots: {t_slots:.3f}s")
# slots is typically 20-40% faster for attribute access in CPython
```

The speedup is more significant for write (`obj.x = val`) than read, because write with `__dict__` may trigger dict resize. With the specializing adaptive interpreter (3.11+), `LOAD_ATTR` can specialize to `LOAD_ATTR_SLOT` — a near-zero-overhead path.

---

## Gotcha Follow-ups

**"Can you add new attributes to a class that uses `__slots__` after it's defined?"**
You can add class-level attributes (methods, class variables), but NOT new instance-level slot names after class creation — `__slots__` becomes the class's `tp_members` at class creation time, which is immutable. You'd need to create a new subclass.

**"What happens to `__slots__` in abstract base classes?"**
ABCs can use `__slots__`, but if a concrete subclass doesn't also declare `__slots__`, the savings are lost. This is a common oversight when mixing ABCs with slotted concrete classes. As a rule, if you want slots to work through a hierarchy, declare `__slots__ = ()` (empty tuple) in abstract intermediary classes — this signals "I don't add any instance vars, but I am part of a slotted hierarchy."

---

## Under the Hood

`__slots__` processing is in `Objects/typeobject.c`, `type_new()`. For each name in `__slots__`:
1. A `PyMemberDef` is created with type `T_OBJECT_EX` and an offset computed from the current `tp_basicsize`.
2. A `member_descriptor` object wrapping this `PyMemberDef` is stored in the class's `tp_dict`.
3. `tp_basicsize` is incremented by `sizeof(PyObject*)`.
4. The resulting descriptor is a data descriptor (has both `__get__` and `__set__`) — so it takes priority over any instance `__dict__` (but `__dict__` doesn't exist without slots `'__dict__'`).
