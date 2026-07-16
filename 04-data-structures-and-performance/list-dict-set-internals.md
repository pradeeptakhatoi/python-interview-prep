# CPython list, dict, set Internals

## Concept

Understanding how CPython implements `list`, `dict`, and `set` at the memory level enables you to predict performance, avoid surprises, and make informed architectural choices. These are not abstract data types — they have concrete implementations with real trade-offs.

### `list` Internals: Dynamic Array with Over-Allocation

A CPython list is a `PyListObject` containing:
- `ob_item`: a C array of `PyObject*` pointers.
- `ob_size`: current number of elements.
- `allocated`: allocated slots (always ≥ `ob_size`).

```python
import sys

lst = []
print(sys.getsizeof(lst))   # 56 bytes (header only, no storage)

lst.append(1)
print(sys.getsizeof(lst))   # 88 bytes — 4 slots allocated

lst.extend(range(3))        # now 4 elements
print(sys.getsizeof(lst))   # 88 bytes — still within the 4 allocated slots

lst.append(5)               # 5th element, triggers realloc
print(sys.getsizeof(lst))   # 120 bytes — now 8 slots
```

**Over-allocation formula** (from `listobject.c`):
```
new_allocated = (new_size + new_size // 8 + 6) & ~3
```
- For small lists: grows roughly by 4 → 8 → 16 → 25 → ...
- Amortized O(1) append. Each element "pays" for the extra allocations.

**Key operations:**
```python
lst = list(range(1000))

# O(1): random access by index
lst[500]        # array pointer arithmetic: ob_item[500]

# O(1) amortized: append to end
lst.append(x)

# O(n): insert at arbitrary position
lst.insert(0, x)    # shifts all elements right — avoid in hot loops

# O(n): delete from middle
del lst[0]          # shifts all elements left

# O(1): pop from end
lst.pop()

# O(k): pop from arbitrary position
lst.pop(0)          # O(n) — shifts elements
```

### `dict` Internals: Open-Addressing Hash Table (Python 3.6+)

CPython dicts use **open addressing** with a separate "indices" array. Since Python 3.7, insertion order is guaranteed (and since 3.6, as a CPython implementation detail).

Internal structure:
- `ma_keys`: a `PyDictKeysObject` containing:
  - `dk_indices`: compact array of indices (size = power of 2, at least 8).
  - `dk_entries`: dense array of `(hash, key, value)` triples.
- `ma_values`: either `NULL` (combined dict) or pointer to separate values array.

```python
import sys

d = {}
print(sys.getsizeof(d))    # 64 bytes — empty dict

d['a'] = 1
print(sys.getsizeof(d))    # 232 bytes — initial allocation (8 slots)
```

**Lookup algorithm:**
1. Compute `hash(key)`.
2. Index into `dk_indices` at position `hash % dk_size`.
3. If empty: key not found.
4. If occupied: compare key hashes, then keys with `==`.
5. If collision: probe (`hash + 1`, `hash + 5`, exponential probing) until empty slot or match.

```python
# Hash collision demo:
class BadHash:
    def __init__(self, v): self.v = v
    def __hash__(self): return 42   # all instances collide!
    def __eq__(self, o): return self.v == o.v

d = {BadHash(i): i for i in range(10)}
# Performance degrades to O(n) on lookup — every probe chain is length n
```

**Load factor and resizing:**
- Dict resizes (doubles) when load exceeds 2/3 capacity.
- Resize triggers rehash of all existing entries.

**Compact dict optimization:**
- Keys stored in insertion order in `dk_entries`.
- `dk_indices` maps hash slots → `dk_entries` indices.
- Memory: `dict` of N items uses `O(N)` memory, not `O(capacity)`.

### `set` / `frozenset` Internals: Open-Addressing Hash Table

Sets use a similar hash table but store only keys (no values). The internal structure is `PySetObject` with a fixed-size initial table (8 slots) and the same open-addressing probing.

```python
import sys

s = set()
print(sys.getsizeof(s))    # 216 bytes (initial 8-slot table, always allocated)

# Comparison: same cardinality
print(sys.getsizeof({i: None for i in range(8)}))  # more than set
print(sys.getsizeof(set(range(8))))                 # less — no value storage
```

**Set operations and complexity:**

| Operation | Average | Worst (all collide) |
|-----------|---------|---------------------|
| `x in s` | O(1) | O(n) |
| `s.add(x)` | O(1) | O(n) |
| `s.remove(x)` | O(1) | O(n) |
| `s \| t` (union) | O(len(s)+len(t)) | O(n²) |
| `s & t` (intersection) | O(min(len(s),len(t))) | — |
| `s - t` (difference) | O(len(s)) | — |
| `s == t` | O(len(s)) | — |

---

## Interview Questions

### Q1: Why is `list.append()` O(1) amortized but not O(1) worst-case?

**Model answer:**
`list.append()` uses **over-allocation** — when the backing C array is full, it allocates a new array roughly 1.125× the current size and copies all elements. The copy is O(n) for that single call. But spread over all the O(n) appends that fill the list, the total copy work is O(n), so each append costs O(1) amortized.

```python
import sys

lst = []
prev_alloc = 0
for i in range(20):
    lst.append(i)
    curr = sys.getsizeof(lst)
    if curr != prev_alloc:
        print(f"len={len(lst)}: getsizeof={curr} (realloc)")
        prev_alloc = curr
    else:
        print(f"len={len(lst)}: getsizeof={curr}")
```

Output shows reallocs at lengths 5, 9, 17, 26... — not every append.

The amortized argument: if the list doubles each time (simplified), the total copy work for N appends is N/2 + N/4 + ... = N. Divide by N appends: O(1) amortized.

### Q2: Why did Python 3.7 guarantee dict insertion order? What changed internally?

**Model answer:**
Before Python 3.6, dicts used a simple open-addressing hash table where entries were stored at arbitrary positions determined by hash values — no inherent ordering.

Python 3.6 (CPython) introduced the **compact dict** design by Raymond Hettinger:
- Separate `dk_indices` (sparse, maps hash slots to entry positions) from `dk_entries` (dense, entries stored in insertion order).
- The dense `dk_entries` array preserves insertion order naturally — each new entry goes to the next available slot in the dense array.

This was an implementation detail in 3.6. Python 3.7 made it a **language guarantee** across all implementations.

Benefit: dict became 20-25% smaller in memory and faster to iterate, because iteration scans the dense `dk_entries` (no skipping empty slots), not the sparse index table.

### Q3: What's the difference between using a `set` and a `dict` as a lookup structure?

**Model answer:**
Functionally: `x in s` (set) vs `x in d` (dict) are both O(1) average. For membership testing, `set` is the right tool — it stores only keys, using roughly half the memory of a `dict` with the same keys (no value storage, no separate values array).

```python
import sys

keys = list(range(1000))
d = {k: None for k in keys}   # dict used as set
s = set(keys)

print(sys.getsizeof(d))   # 36968 bytes
print(sys.getsizeof(s))   # 32984 bytes — smaller

# In practice, the values array cost is minimal but visible
# More importantly: semantic clarity — use set for membership, dict for mapping
```

When you actually need associated values (counts, metadata), use `dict`. For pure membership testing, `set` is correct semantically and slightly more memory efficient.

### Q4: How do hash collisions affect dict/set performance in practice? When does it become a concern?

**Model answer:**
Hash collisions degrade lookup from O(1) to O(k) where k is the collision chain length. In the worst case (all keys hash to the same slot), it's O(n). CPython's probing is `(5 * hash + 1 + perturb)` (not simple linear), which distributes collisions well for typical data.

**Realistic concern 1: DoS via hash collision.** Identical-hash keys in a dict cause O(n²) insertion. CPython 3.3+ uses **hash randomization** (`PYTHONHASHSEED`) for `str`, `bytes`, `datetime` to prevent externally-controlled hash flooding. (Integers and tuples of integers use deterministic hashes.)

```python
import os
os.environ['PYTHONHASHSEED'] = '0'   # reproducible (for testing only)
# In production: PYTHONHASHSEED is random by default
```

**Realistic concern 2: Custom `__hash__` returning a constant.** Avoid this. Even returning `id(self)` is better than `return 42`.

**Realistic concern 3: Float keys.** `1.0 == 1` is `True` and `hash(1.0) == hash(1)`, so they're the same key in a dict:
```python
d = {1: "int", 1.0: "float"}
print(d)    # {1: 'float'} — 1.0 replaced 1's value (same key)
```

### Q5: What is the memory layout difference between a list of integers and a numpy array of integers?

**Model answer:**
This comes up when discussing when to use standard Python data structures vs specialized ones.

A Python `list` of integers:
- `PyListObject`: 56-byte header + array of `PyObject*` pointers (8 bytes each on 64-bit).
- Each integer is a separate heap-allocated `PyLongObject` (28+ bytes for small ints, but cached for -5 to 256).
- Total: 56 + 8N + heap objects. Pointers are NOT contiguous in memory (except for cached ints).

A numpy `ndarray` of `int64`:
- One contiguous C array of 8-byte integers.
- Total: ~96-byte header + 8N bytes. Cache-friendly — sequential memory access.

```python
import sys
import numpy as np

N = 1000
lst = list(range(N))
arr = np.arange(N, dtype=np.int64)

# List: sys.getsizeof only counts the list header + pointers, not the int objects!
print(sys.getsizeof(lst))           # ~8056 bytes (header + 1000 pointers)
print(sys.getsizeof(lst[0]) * N)    # ~28000 bytes for int objects (not counted above)

print(arr.nbytes)                    # 8000 bytes — just the data
print(sys.getsizeof(arr))           # 8096 bytes (header + data, all in one allocation)
```

For numeric arrays, numpy is ~3-5× more memory-efficient and dramatically faster for vectorized operations due to SIMD optimization and cache locality.

---

## Gotcha Follow-ups

**"If dict preserves insertion order, can you use it as an ordered set?"**
You can use `dict.fromkeys(iterable)` or `{k: None for k in iterable}` to preserve order and deduplicate. But `collections.OrderedDict` (pre-3.7) and `dict` are not `set` — they don't support set operations (`|`, `&`, `-`). For an ordered unique collection with set operations, you'd need a third-party library or a custom class.

**"Does `list.sort()` modify the list in-place? What about `sorted()`?"**
`list.sort()` sorts in-place and returns `None` — a common trap (`result = lst.sort()` gives you `None`). `sorted()` returns a new list. Both use **Timsort** (O(n log n) worst-case, O(n) on nearly-sorted data), implemented in C.

---

## Under the Hood

`list`: `Objects/listobject.c` → `list_resize()` implements the over-allocation. Growth: `new_allocated = (new_size + (new_size >> 3) + 6) & ~3`.

`dict`: `Objects/dictobject.c` → `PyDictObject`. The compact dict design introduced in 3.6: `dk_indices` is an 8/16/32/64-bit integer array (type chosen based on table size), `dk_entries` is a dense `PyDictKeyEntry` array. Split dict optimization (3.3+): instances of the same class share a common `dk_keys` object but have separate `ma_values` arrays, reducing memory when many instances share the same key set.

`set`: `Objects/setobject.c` → `PySetObject`. Small sets (≤ 4 elements) use a fixed inline table; larger sets use a heap-allocated one. Probing: `j = (5*j + 1 + perturb) % mask`.
