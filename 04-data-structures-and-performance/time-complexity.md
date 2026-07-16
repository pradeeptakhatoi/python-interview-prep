# Time Complexity of Common Operations

## Concept

Knowing Big-O complexity is table stakes. What separates Staff/Architect candidates is understanding *why* — which CPython implementation choice drives each complexity class — and *when the constant matters* enough to change the structure.

### Complete Complexity Reference

#### `list`

| Operation | Complexity | Why |
|-----------|-----------|-----|
| `lst[i]` | O(1) | Array indexing: `ob_item + i` |
| `len(lst)` | O(1) | `ob_size` field read |
| `lst.append(x)` | O(1) amortized | Amortized over reallocations |
| `lst.pop()` | O(1) | Decrement `ob_size` |
| `lst.pop(i)` | O(n) | Shift elements left |
| `lst.insert(i, x)` | O(n) | Shift elements right |
| `lst[i] = x` | O(1) | Array write |
| `x in lst` | O(n) | Linear scan |
| `lst.index(x)` | O(n) | Linear scan |
| `lst.remove(x)` | O(n) | Linear scan + O(n) shift |
| `lst.sort()` | O(n log n) | Timsort |
| `sorted(lst)` | O(n log n) | Timsort, creates new list |
| `lst.copy()` | O(n) | Copies all pointers |
| `lst + lst2` | O(n+m) | New list, copy both |
| `lst.extend(it)` | O(k) | k = len(iterable) |
| `lst.reverse()` | O(n) | In-place swap |
| `min(lst)` / `max(lst)` | O(n) | Linear scan |
| `lst.count(x)` | O(n) | Linear scan |
| `del lst[i]` | O(n) | Shift left |
| `del lst[i:j]` | O(n) | Compact + shift |
| `lst[i:j]` | O(k) | k = j-i, new list |

```python
import timeit

# list.insert(0, ...) vs deque.appendleft() — the canonical example:
from collections import deque

N = 10_000

# O(N) per insert — avoid in hot loops
t1 = timeit.timeit(
    setup='lst = list(range(1000))',
    stmt='lst.insert(0, 0)',
    number=N
)

# O(1) per appendleft — correct structure
t2 = timeit.timeit(
    setup='from collections import deque; d = deque(range(1000))',
    stmt='d.appendleft(0)',
    number=N
)

print(f"list.insert(0): {t1*1000:.1f}ms total")
print(f"deque.appendleft: {t2*1000:.1f}ms total")
# list.insert is ~100x slower for large lists
```

#### `dict`

| Operation | Complexity | Why |
|-----------|-----------|-----|
| `d[k]` | O(1) avg | Hash table lookup |
| `d[k] = v` | O(1) avg | Hash table insert |
| `k in d` | O(1) avg | Hash table lookup |
| `del d[k]` | O(1) avg | Mark slot deleted |
| `len(d)` | O(1) | `ma_used` field |
| `d.get(k, def)` | O(1) avg | Hash table lookup |
| `d.keys()` / `.values()` / `.items()` | O(1) | Returns a view |
| Iterating view | O(n) | Scans dense entries array |
| `dict(other_dict)` | O(n) | Copies n entries |
| `d.update(other)` | O(n) | n = len(other) |
| `{**d, **e}` | O(n+m) | Merge |
| `d.pop(k)` | O(1) avg | Hash lookup + mark deleted |
| `d.setdefault(k, v)` | O(1) avg | Hash lookup + optional insert |

#### `set` / `frozenset`

| Operation | Complexity | Why |
|-----------|-----------|-----|
| `x in s` | O(1) avg | Hash lookup |
| `s.add(x)` | O(1) avg | Hash insert |
| `s.remove(x)` | O(1) avg | Hash lookup + mark deleted |
| `s.discard(x)` | O(1) avg | Hash lookup (no KeyError) |
| `s \| t` | O(n+m) | Iterate and insert all |
| `s & t` | O(min(n,m)) | Iterate smaller, probe larger |
| `s - t` | O(n) | Iterate s, test t |
| `s ^ t` | O(n+m) | Symmetric difference |
| `s <= t` (subset) | O(n) | Test every s element in t |
| `s == t` | O(n) | Subset check both ways |

#### `deque` (from `collections`)

| Operation | Complexity | Why |
|-----------|-----------|-----|
| `d.appendleft(x)` | O(1) | Doubly-linked blocks |
| `d.append(x)` | O(1) | Doubly-linked blocks |
| `d.popleft()` | O(1) | Head pointer update |
| `d.pop()` | O(1) | Tail pointer update |
| `d[0]` / `d[-1]` | O(1) | Direct head/tail access |
| `d[i]` | O(n) | Traverse linked blocks |
| `x in d` | O(n) | Linear scan |
| `len(d)` | O(1) | Maintained counter |

#### `heapq` (min-heap)

| Operation | Complexity | Why |
|-----------|-----------|-----|
| `heappush(h, x)` | O(log n) | Sift up |
| `heappop(h)` | O(log n) | Sift down |
| `heapify(lst)` | O(n) | Bottom-up heapify |
| `heappushpop(h, x)` | O(log n) | Push then pop (more efficient than separate) |
| `h[0]` | O(1) | Min element (heap property) |

#### `bisect` (sorted list)

| Operation | Complexity | Why |
|-----------|-----------|-----|
| `bisect_left(lst, x)` | O(log n) | Binary search |
| `insort_left(lst, x)` | O(n) | Binary search + O(n) insert |

```python
import heapq, bisect

# heapq example: k smallest in stream
def k_smallest(stream, k):
    heap = []
    for item in stream:
        if len(heap) < k:
            heapq.heappush(heap, item)
        elif item < heap[0]:
            heapq.heapreplace(heap, item)
    return sorted(heap)

# bisect example: maintaining sorted order
import bisect

def add_sorted(lst, x):
    pos = bisect.bisect_left(lst, x)  # O(log n)
    lst.insert(pos, x)                # O(n) — bisect doesn't help insertion!
    return lst

# For log-n insertion AND lookup, use sortedcontainers.SortedList (3rd party)
```

---

## Interview Questions

### Q1: Why is `list.insert(0, x)` O(n)? What should you use instead for queue-like access?

**Model answer:**
`list.insert(0, x)` inserts at position 0, shifting all existing elements one position right — a `memmove` of N pointers. That's O(n).

`collections.deque` is implemented as a doubly-linked list of fixed-size blocks (64 items per block in CPython). Appending to either end only updates the head or tail pointer: O(1).

```python
from collections import deque

d = deque(maxlen=1000)  # optionally bounded — O(1) circular buffer behavior
d.appendleft(1)         # O(1)
d.appendleft(2)         # O(1)
d.pop()                 # O(1) — FIFO: append one end, pop the other

# WRONG: deque[i] for arbitrary i is O(n) — iterate the linked blocks
# RIGHT: use deque only for head/tail access
```

Rule: use `list` when you need random access by index; use `deque` when you need O(1) head/tail operations.

### Q2: Why is `x in dict` O(1) but `x in list` O(n)?

**Model answer:**
`list` stores values in an array with no structure for lookups — finding `x` requires scanning every element until a match is found: O(n).

`dict` uses a hash table. Finding `x`:
1. Compute `hash(x)`: O(1) (for most types).
2. Index into hash table at `hash(x) % table_size`: O(1).
3. Compare keys: O(1) average (assuming few collisions).

The price: every key in a `dict` must be hashable. You can't use `list` or `dict` as dict keys.

```python
# Practical: membership testing in a large collection
large_list = list(range(10_000))
large_set = set(range(10_000))

import timeit
t_list = timeit.timeit('9999 in large_list', globals={'large_list': large_list}, number=10000)
t_set = timeit.timeit('9999 in large_set', globals={'large_set': large_set}, number=10000)
print(f"list: {t_list:.4f}s, set: {t_set:.6f}s")
# set is ~100-1000x faster for large collections
```

### Q3: What is the time complexity of `set.union(s2)` vs `s1 | s2`? Are they the same?

**Model answer:**
Both produce the same result with the same complexity — O(n+m). But they differ in input type flexibility:

```python
s1 = {1, 2, 3}
s2 = [4, 5, 6]     # not a set

print(s1 | s2)                  # TypeError — `|` requires set on RHS (Python 3.8 behavior)
# In Python 3.9+, this raises TypeError: unsupported operand type(s) for |: 'set' and 'list'

print(s1.union(s2))             # {1, 2, 3, 4, 5, 6} — union() accepts any iterable
```

`s1 | s2` uses `set.__or__`, requiring another set (or set-like type) on the right side.
`s1.union(*others)` accepts any iterable (including lists, generators, tuples).

For multiple sets: `s1 | s2 | s3` is O(n+m) + O(n+m+p) — two passes. `s1.union(s2, s3)` can be smarter internally (single pass over combined iterables).

### Q4: When would you choose `bisect` over a `set` for sorted-order maintenance?

**Model answer:**
`set` gives O(1) membership testing but provides no ordering — you can't find the k-th smallest element or elements in a range without sorting first.

`bisect` on a sorted `list` gives:
- O(log n) positional queries: "where does x fit?"
- O(1) range queries by index: `lst[3:7]`
- O(log n) search: `bisect_left(lst, x)` finds the insertion point.

But insertion remains O(n) (shift elements). Use cases where bisect wins:
1. You have infrequent insertions but frequent range queries.
2. You need the k-th smallest element directly: `lst[k]`.
3. You need sorted iteration (sets iterate in arbitrary order).

```python
import bisect

schedule = []  # sorted list of (timestamp, task)

def add_task(ts, task):
    bisect.insort(schedule, (ts, task))   # O(n) but simple

def tasks_before(ts):
    pos = bisect.bisect_right(schedule, (ts, ''))
    return schedule[:pos]   # O(k) copy, O(log n) for boundary

# For production: use sortedcontainers.SortedList for O(log n) insert AND range query
```

### Q5: Explain the complexity of `dict.update(other)` and when it triggers a resize.

**Model answer:**
`dict.update(other)` iterates over `other` (O(m) for m items) and inserts each into `self` (O(1) average per insert). Total: O(m).

Resize is triggered when the load factor exceeds 2/3 — i.e., when `len(d) > (2/3) * table_size`. After resize, the table doubles and all entries are rehashed: O(n) for the resize operation. But across all insertions, this is amortized O(1) per insert.

If you're initializing a dict from a large `other`, prefer:
```python
d = dict(other)         # single allocation, no incremental resizing
# vs
d = {}
d.update(other)         # may resize multiple times if growing from empty
```

Or use `|=` (Python 3.9+):
```python
d |= other              # equivalent to d.update(other)
merged = d1 | d2        # new dict — O(n+m)
```

---

## Gotcha Follow-ups

**"Is `list.sort()` stable? Does it matter?"**
Yes — Timsort is stable (equal elements maintain their relative order). This matters when sorting by one key then another:
```python
records = [('b', 2), ('a', 1), ('b', 1)]
records.sort(key=lambda x: x[1])  # sort by second element
# [('a', 1), ('b', 1), ('b', 2)] — 'b' pairs in original relative order
# Stable sort enables "sort by multiple keys" via successive single-key sorts
```

**"What's the complexity of `len()` for all these structures?"**
O(1) for `list`, `dict`, `set`, `deque`, `bytearray`, `str`, `bytes`, `tuple`. All maintain a cached length counter — no counting required. This is not true of all data structures; a linked list without a length field would be O(n).

---

## Under the Hood

Timsort (`Objects/listobject.c`): a hybrid stable sort combining natural runs (already-sorted sequences) and binary insertion sort for small runs, with merge of run pairs. Designed for real-world data that is often partially sorted. Python's `list.sort()` and `sorted()` both use Timsort. Java's `Arrays.sort` for objects uses a similar algorithm.

`dict` resize (`Objects/dictobject.c`): `dict_resize()` creates a new `dk_indices` with 4× the old size (not 2× — avoids immediate re-resize), then calls `insertdict()` for every existing entry. The density of the old table ≥ 1/2 before resize; after resize, it's ≤ 1/4.
