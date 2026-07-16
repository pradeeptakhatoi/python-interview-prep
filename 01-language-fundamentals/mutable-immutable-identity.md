# Mutable vs Immutable Types, Identity vs Equality

## Concept

Every Python object has three properties: **identity** (`id()`), **type** (`type()`), and **value**. Mutability determines whether the value can change after creation. Identity is fixed for the lifetime of an object. These three form the bedrock of Python semantics.

### Immutable Types

`int`, `float`, `complex`, `bool`, `str`, `bytes`, `tuple`, `frozenset`, `NoneType`

Immutable objects cannot be modified in-place. Any "modification" produces a new object:

```python
x = "hello"
print(id(x))       # e.g. 140234567890

x += " world"      # creates a NEW str object; binds x to it
print(id(x))       # different id — different object

# Tuples are immutable containers:
t = (1, 2, [3, 4])  # tuple is immutable; the list inside is NOT
t[2].append(5)       # legal — modifies the list, not the tuple
print(t)             # (1, 2, [3, 4, 5])
# t[0] = 99         # TypeError — tuple element assignment not supported
```

### Mutable Types

`list`, `dict`, `set`, `bytearray`, user-defined class instances (by default)

```python
a = [1, 2, 3]
b = a               # b is the SAME object as a (aliasing, not copying)
b.append(4)
print(a)            # [1, 2, 3, 4] — a reflects the change

# Shallow vs deep copy:
import copy
c = a.copy()        # or list(a) or a[:]
c.append(99)
print(a)            # [1, 2, 3, 4] — a unchanged; c is a separate object

d = [[1, 2], [3, 4]]
e = d.copy()         # shallow copy — inner lists are STILL shared
e[0].append(99)
print(d[0])          # [1, 2, 99] — d is affected!

f = copy.deepcopy(d) # deep copy — fully independent
f[0].append(0)
print(d[0])          # [1, 2, 99] — d unaffected
```

### `is` vs `==`

- `is` — identity comparison: `id(a) == id(b)`
- `==` — equality comparison: calls `a.__eq__(b)`

```python
a = [1, 2, 3]
b = [1, 2, 3]
print(a == b)   # True — same value
print(a is b)   # False — different objects

c = a
print(a is c)   # True — same object (aliasing)

# NEVER use 'is' for value comparison of non-singletons:
x = 1000
y = 1000
print(x == y)   # True — always correct
print(x is y)   # False in general (may be True due to interning — unreliable)

# CORRECT uses of 'is':
print(x is None)    # correct — None is a singleton
print(x is True)    # correct — True/False are singletons
print(x is NotImplemented)  # correct — singleton
```

### Mutability and Hashability

Only hashable (immutable, or implementing `__hash__`) objects can be dict keys or set members:

```python
# Hashable:
d = {1: "int", "key": "str", (1, 2): "tuple", frozenset({1}): "frozenset"}

# NOT hashable — TypeError:
try:
    d[[1, 2]] = "list"        # TypeError: unhashable type: 'list'
except TypeError as e:
    print(e)

# Tuple is hashable ONLY if all elements are hashable:
hash((1, 2, 3))       # OK
hash((1, [2, 3]))     # TypeError — contains a list
```

### Object Interning

CPython interns small integers (-5 to 256) and identifier-like strings. This makes `is` return `True` for these values — but that is an implementation detail, not a guarantee:

```python
import sys

# Small int cache:
a = 42
b = 42
print(a is b)     # True — same cached object

a = 1000
b = 1000
print(a is b)     # False — new allocation each time

# String interning:
s1 = "hello"
s2 = "hello"
print(s1 is s2)   # True — auto-interned (identifier-like)

s3 = "hello world"
s4 = "hello world"
print(s3 is s4)   # Undefined — may or may not be True; never rely on this
```

---

## Interview Questions

### Q1: Explain why `x = x + [1]` and `x += [1]` behave differently for lists.

**Model answer:**
`x = x + [1]` creates a new list (concatenation always allocates), then rebinds `x` to it. `x += [1]` calls `list.__iadd__([1])`, which extends the existing list in-place and returns `self`. The binding stays on the same object.

```python
a = [1, 2]
b = a
a = a + [3]   # new object
print(b)      # [1, 2] — b still points to original

a = [1, 2]
b = a
a += [3]      # in-place extend
print(b)      # [1, 2, 3] — b sees the change because it's the same object
```

This matters in class attributes, function arguments, and any aliasing scenario. For immutable types (`str`, `int`, `tuple`), `+=` and `+` are always equivalent — both produce a new object.

```python
# Tuple gotcha:
t = (1, 2)
id_before = id(t)
t += (3,)
print(id(t) == id_before)  # False — new tuple; += on immutable = new object
```

### Q2: What does `id()` actually return, and when can two objects have the same `id`?

**Model answer:**
`id(obj)` returns the memory address of `obj` in CPython. It is guaranteed unique only while the object is alive. Two objects can have the same `id` if the first was garbage collected before the second was created:

```python
class Temp:
    pass

a = Temp()
print(id(a))   # e.g. 140234

del a          # refcount → 0; deallocated immediately in CPython
b = Temp()
print(id(b))   # may be identical to a's id — same memory reused!

# This is why storing id() values for later comparison is dangerous:
saved = id(Temp())   # Temp() created, id saved, then IMMEDIATELY collected
c = Temp()           # may reuse same address
print(saved == id(c))  # True — but different logical objects!
```

`is` is safe because it uses `id()` at the moment of comparison, when both objects are alive. Storing `id()` values for deferred comparison is not safe.

### Q3: Why can a mutable object inside an immutable container be modified?

**Model answer:**
Immutability means the container's structure cannot change — you cannot add, remove, or rebind the references it holds. But the referenced objects themselves can be mutable:

```python
t = (1, [2, 3])
# t[0] = 99    # TypeError — can't change what the tuple references
t[1].append(4) # OK — modifies the list object; the tuple still references the same list

# The tuple's "value" (its sequence of references) is immutable.
# The list that one of those references points to is mutable.
# hash(t) raises TypeError because t contains an unhashable list.
```

This distinction is why `tuple` is conditionally hashable: `hash((1, 2))` works, `hash((1, [2]))` raises `TypeError`. The hashing check recurses into elements.

### Q4: What's the difference between `copy.copy()` and `copy.deepcopy()`? When does shallow copy fail?

**Model answer:**
`copy.copy()` creates a new container with the same references to the same inner objects. `copy.deepcopy()` recursively copies all objects, creating fully independent clones.

Shallow copy fails when:
1. Inner mutable objects are shared and later modified.
2. You're building a tree/graph structure and need independent nodes.

```python
import copy

original = {"data": [1, 2, 3], "count": 0}
shallow = copy.copy(original)
deep = copy.deepcopy(original)

original["data"].append(99)
original["count"] += 1

print(shallow["data"])  # [1, 2, 3, 99] — shares the list
print(shallow["count"]) # 0 — int is immutable; rebinding doesn't affect shallow copy
print(deep["data"])     # [1, 2, 3] — fully independent
```

`deepcopy` handles cycles (an object referencing itself) by tracking already-copied objects in a memo dict.

### Q5: How does Python's assignment model differ from C's? What is "pass by assignment"?

**Model answer:**
Python uses **pass by assignment** (sometimes called "pass by object reference"). There are no pointers, no pass-by-value, no pass-by-reference in the C sense. A variable is a name that binds to an object.

When you pass an argument:
- The function parameter binds to the **same object** as the caller's variable.
- If the function **mutates** the object, the caller sees the change (same object).
- If the function **rebinds** the parameter (e.g., `param = new_value`), the caller's binding is unaffected.

```python
def mutate(lst):
    lst.append(99)     # mutates the object — caller sees this

def rebind(lst):
    lst = [1, 2, 3]   # rebinds local name — caller does NOT see this

original = [0]
mutate(original)
print(original)        # [0, 99] — mutated

rebind(original)
print(original)        # [0, 99] — unchanged; rebind only affected local name
```

This is why mutable default arguments are a notorious trap — the default object is shared across all calls.

---

## Gotcha Follow-ups

**"Is `None` always a singleton? Can you create another `None`?"**
`None` is the sole instance of `NoneType`. You cannot instantiate `NoneType` directly (`NoneType()` raises `TypeError`). Every `None` value in Python IS the same object. `x is None` is always safe and is the idiomatic check (not `x == None`).

**"What happens when you hash a custom class instance?"**
By default, `object.__hash__` returns `id(obj) // 16` (implementation detail). If you override `__eq__` without overriding `__hash__`, Python sets `__hash__ = None`, making instances unhashable (raises `TypeError`). This enforces the contract: equal objects must have equal hashes.

```python
class Bad:
    def __eq__(self, other):
        return True
    # __hash__ is implicitly None — unhashable!

b = Bad()
hash(b)     # TypeError: unhashable type: 'Bad'
{b: 1}      # TypeError
```

---

## Under the Hood

Python variables are entries in a namespace dict (module-level: `globals()`, function-level: `locals()` / `localsplus` array, class-level: `__dict__`). Assignment compiles to `STORE_NAME` (module), `STORE_FAST` (function locals), or `STORE_GLOBAL`. There is no "variable box" in memory — only the object itself, and a name that points to it. The `id()` value for CPython is `(Py_uintptr_t)obj` — literally the C pointer value cast to a Python integer.
