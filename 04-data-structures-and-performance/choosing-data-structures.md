# Choosing the Right Data Structure

## Concept

The right data structure is not the one you know — it's the one that matches the access pattern. Staff-level engineers articulate why they chose a structure in terms of asymptotic complexity, constant factors, memory layout, and thread-safety properties.

### Decision Framework

```
What do you need?                   Use
─────────────────────────────────────────────────────────────────
Ordered, random access by index     list
Queue (FIFO), stack (LIFO)          deque
Priority queue / smallest-K         heapq (list)
Sorted container, range queries     sortedcontainers.SortedList
Membership test, deduplication      set / frozenset
Key → value mapping                 dict
Ordered mapping (insertion order)   dict (3.7+) or OrderedDict
Counting occurrences                collections.Counter
Default values                      collections.defaultdict
Immutable mapping                   types.MappingProxyType
Named tuple (readable, fast)        collections.namedtuple / NamedTuple
Typed record (mutability optional)  dataclass / attrs
Compact numeric array               array.array
Sliding window / bounded queue      deque(maxlen=N)
LRU cache with size limit           functools.lru_cache / OrderedDict
Trie / prefix tree                  No stdlib — third party or custom
```

### `array.array`: Typed Compact Arrays

When you have a large homogeneous sequence of primitives (ints, floats), `array.array` is 4-5× more memory efficient than `list`:

```python
import array, sys

lst = list(range(1_000_000))
arr = array.array('l', range(1_000_000))  # 'l': signed long

print(sys.getsizeof(lst))   # ~8056040 bytes — 8MB for pointers alone
                             # + separate int objects on heap
print(arr.buffer_info()[1] * arr.itemsize)  # 8000000 bytes — contiguous int64s

# Supported typecodes:
# 'b': int8, 'B': uint8, 'h': int16, 'H': uint16,
# 'i': int32, 'I': uint32, 'l': int64, 'L': uint64,
# 'f': float32, 'd': float64
```

**Limitations:** No mixed types. Operations on individual elements still box/unbox Python objects. For heavy numeric work, prefer `numpy` which supports SIMD and C-speed vectorization.

### `collections.deque`: Double-Ended Queue

```python
from collections import deque

# Bounded sliding window — O(1) appendleft, automatic popleft on overflow
window = deque(maxlen=5)
for i in range(10):
    window.append(i)
    print(list(window))
# [0] [0,1] [0,1,2] [0,1,2,3] [0,1,2,3,4]
# [1,2,3,4,5] [2,3,4,5,6] ... [5,6,7,8,9]

# Efficient rotation
window.rotate(2)    # O(n) but implemented in C — faster than slicing
print(list(window))

# Use as stack: append/pop from right end, both O(1)
stack = deque()
stack.append(1)
stack.append(2)
stack.pop()         # 2

# Use as queue: append right, popleft — both O(1)
queue = deque()
queue.append(1)
queue.append(2)
queue.popleft()     # 1 — FIFO
```

### `heapq`: Priority Queue

Python's `heapq` module implements a **min-heap** on a regular `list`:

```python
import heapq

# Basic usage
h = [5, 2, 8, 1, 9]
heapq.heapify(h)    # O(n) — in-place, not sorted but heap-ordered
print(h[0])         # 1 — minimum element always at index 0

heapq.heappush(h, 3)
print(heapq.heappop(h))   # 1 — always returns the minimum

# Pattern: task scheduler with priorities
import time

class PriorityTask:
    def __init__(self, priority, task):
        self.priority = priority
        self.task = task

    def __lt__(self, other):
        return self.priority < other.priority

heap = []
heapq.heappush(heap, PriorityTask(3, 'low'))
heapq.heappush(heap, PriorityTask(1, 'urgent'))
heapq.heappush(heap, PriorityTask(2, 'normal'))

while heap:
    t = heapq.heappop(heap)
    print(f"[{t.priority}] {t.task}")
# [1] urgent, [2] normal, [3] low

# k smallest / k largest:
nums = [5, 2, 8, 1, 9, 3]
print(heapq.nsmallest(3, nums))   # [1, 2, 3] — O(n log k)
print(heapq.nlargest(3, nums))    # [9, 8, 5] — O(n log k)

# For k=1: min()/max() is faster than nsmallest/nlargest
# For k≥n/2: sorted()[:k] is faster than heapq
```

### `bisect`: Binary Search on Sorted Lists

```python
import bisect

# Sorted list maintenance
grades = []
scores = [85, 92, 78, 95, 88]
for s in scores:
    bisect.insort(grades, s)   # O(n) insert after O(log n) search
print(grades)  # [78, 85, 88, 92, 95]

# Grade mapping using bisect_left:
boundaries = [60, 70, 80, 90]  # D, C, B, A thresholds
letters = ['F', 'D', 'C', 'B', 'A']

def grade(score):
    i = bisect.bisect_left(boundaries, score)
    return letters[i]

print(grade(75))   # C
print(grade(90))   # A
print(grade(59))   # F

# "Is x in sorted list?" — O(log n) vs O(n) for linear scan:
def contains_sorted(lst, x):
    i = bisect.bisect_left(lst, x)
    return i < len(lst) and lst[i] == x
```

### `collections.Counter`: Efficient Counting

```python
from collections import Counter

# Counting elements
words = ['the', 'cat', 'sat', 'on', 'the', 'mat', 'the']
c = Counter(words)
print(c.most_common(2))   # [('the', 3), ('cat', 1)]

# Arithmetic on counters
c1 = Counter({'a': 3, 'b': 1})
c2 = Counter({'a': 1, 'b': 2, 'c': 5})
print(c1 + c2)    # Counter({'c': 5, 'a': 4, 'b': 3})
print(c1 - c2)    # Counter({'a': 2}) — negative counts dropped
print(c1 & c2)    # Counter({'a': 1, 'b': 1}) — min
print(c1 | c2)    # Counter({'c': 5, 'a': 3, 'b': 2}) — max

# Common use: character frequency for anagram detection
def is_anagram(s1: str, s2: str) -> bool:
    return Counter(s1) == Counter(s2)
```

### `collections.defaultdict`: Zero-Initialization Pattern

```python
from collections import defaultdict

# Group by first letter
words = ['apple', 'banana', 'avocado', 'blueberry', 'cherry']
groups = defaultdict(list)
for word in words:
    groups[word[0]].append(word)
print(dict(groups))
# {'a': ['apple', 'avocado'], 'b': ['banana', 'blueberry'], 'c': ['cherry']}

# Nested defaultdict for 2D grouping
nested = defaultdict(lambda: defaultdict(int))
nested['row1']['col1'] += 1
nested['row1']['col2'] += 5

# Adjacency list for graphs
graph = defaultdict(set)
for u, v in [(1, 2), (1, 3), (2, 3)]:
    graph[u].add(v)
    graph[v].add(u)
```

### OrderedDict vs dict (Python 3.7+)

`dict` preserves insertion order since Python 3.7. Use `OrderedDict` when you need:
- `move_to_end()` — move a key to front or back efficiently.
- LRU cache pattern: `move_to_end(key)` on access, `popitem(last=False)` for eviction.
- `==` comparison that considers ORDER (plain `dict` equality ignores insertion order).

```python
from collections import OrderedDict

lru = OrderedDict()

def cache_access(key, value=None):
    if key in lru:
        lru.move_to_end(key)    # mark as recently used
        return lru[key]
    if value is not None:
        lru[key] = value
        if len(lru) > 100:
            lru.popitem(last=False)  # evict LRU item
    return None
```

---

## Interview Questions

### Q1: When would you use `array.array` instead of `list`? When would you use `numpy`?

**Model answer:**
`array.array` is appropriate when you have a large, homogeneous sequence of primitives (integers or floats) and want compact memory without pulling in a third-party dependency.

Trade-offs:
- `array.array` vs `list`: 4-8× less memory (no boxing/pointer overhead per element). Element-level operations still box/unbox Python objects — no speedup for loops.
- `numpy` vs `array.array`: numpy supports vectorized operations (via SIMD/LAPACK), broadcasting, multi-dimensional arrays, and is 10-100× faster for bulk numeric operations. At the cost of a heavy dependency and a learning curve.

Decision rule:
- Need compact I/O or storage (serializing numeric data): `array.array`.
- Need any computation (sum, mean, filter, transform): `numpy`.
- Need general-purpose mixed data: `list`.

```python
import array, timeit
import numpy as np

data_list = list(range(1_000_000))
data_array = array.array('l', range(1_000_000))
data_numpy = np.arange(1_000_000)

# Summing: list is slowest, numpy fastest
t_list  = timeit.timeit(lambda: sum(data_list), number=100)
t_array = timeit.timeit(lambda: sum(data_array), number=100)
t_numpy = timeit.timeit(lambda: data_numpy.sum(), number=100)
# Approximate: list ~50ms, array.array ~30ms, numpy ~0.5ms per call
```

### Q2: You need a priority queue that supports both push and decrease-key. What are your options in Python?

**Model answer:**
Python's `heapq` doesn't support decrease-key (changing the priority of an existing item). The idiomatic workaround is the **lazy deletion** pattern:

```python
import heapq

class PriorityQueue:
    def __init__(self):
        self._heap = []
        self._entry_finder = {}   # task → entry
        self._REMOVED = object()  # sentinel
        self._counter = 0

    def push(self, task, priority):
        if task in self._entry_finder:
            self._mark_removed(task)
        count = self._counter
        self._counter += 1
        entry = [priority, count, task]
        self._entry_finder[task] = entry
        heapq.heappush(self._heap, entry)

    def _mark_removed(self, task):
        entry = self._entry_finder.pop(task)
        entry[-1] = self._REMOVED   # mark as removed

    def decrease_key(self, task, new_priority):
        self.push(task, new_priority)   # re-insert with new priority

    def pop(self):
        while self._heap:
            priority, count, task = heapq.heappop(self._heap)
            if task is not self._REMOVED:
                del self._entry_finder[task]
                return task, priority
        raise KeyError('pop from empty queue')
```

For production with heavy decrease-key use (Dijkstra's on dense graphs), consider `sortedcontainers.SortedList` for O(log n) removal by value, or a Fibonacci heap (available in third-party libraries) for O(1) amortized decrease-key.

### Q3: When is a `deque` worse than a `list`?

**Model answer:**
`deque` is implemented as a doubly-linked list of fixed-size blocks (64 items per block). This is great for O(1) head/tail operations but terrible for:

1. **Random access:** `d[i]` is O(n) — traverse blocks.
2. **Cache locality for iteration:** blocks may not be contiguous in memory, causing cache misses.
3. **Memory overhead:** each block carries pointer overhead beyond the data.

```python
from collections import deque
import timeit

lst = list(range(10_000))
d = deque(range(10_000))

# Random access: list wins dramatically
t_list = timeit.timeit(lambda: lst[5000], number=1_000_000)
t_deque = timeit.timeit(lambda: d[5000], number=1_000_000)
print(f"list[5000]: {t_list:.3f}s, deque[5000]: {t_deque:.3f}s")
# list is ~5-10x faster for random access
```

Rule: use `deque` only when you access head and/or tail. If you need iteration or random access, use `list`.

### Q4: Why would you use `frozenset` instead of `tuple` as a dict key for a set of items?

**Model answer:**
Both `frozenset` and `tuple` are hashable and can be dict keys. The semantic difference:
- `tuple`: ordered sequence — `(1, 2) != (2, 1)`.
- `frozenset`: unordered collection — `frozenset({1, 2}) == frozenset({2, 1})`.

If the order of the items in your key doesn't matter (e.g., a set of permissions, a set of tags), `frozenset` gives you order-independent equality and hashing:

```python
d = {}

# With tuple: different orderings = different keys
d[('read', 'write')] = 1
d[('write', 'read')] = 2
print(len(d))   # 2 — they're different keys

# With frozenset: order doesn't matter
d2 = {}
d2[frozenset({'read', 'write'})] = 1
d2[frozenset({'write', 'read'})] = 2   # same key!
print(len(d2))  # 1 — only one entry

# Real use case: graph edge (undirected) — frozenset({u, v}) is canonical
edge = frozenset({node_a, node_b})
```

Also: `frozenset` membership test is O(1); finding an item in a tuple is O(n).

### Q5: What's the idiomatic way to implement a sliding window of the last N elements?

**Model answer:**
`deque(maxlen=N)` is purpose-built for this:

```python
from collections import deque

def sliding_window_max(nums: list[int], k: int) -> list[int]:
    """O(n) sliding window max using deque of indices."""
    result = []
    dq = deque()   # stores indices, largest at front

    for i, num in enumerate(nums):
        # Remove elements outside the window
        while dq and dq[0] < i - k + 1:
            dq.popleft()

        # Remove smaller elements from back (they'll never be max)
        while dq and nums[dq[-1]] < num:
            dq.pop()

        dq.append(i)

        if i >= k - 1:
            result.append(nums[dq[0]])

    return result

print(sliding_window_max([1, 3, -1, -3, 5, 3, 6, 7], 3))
# [3, 3, 5, 5, 6, 7]
```

For a simpler "keep last N values" window:
```python
from collections import deque

class MetricsBuffer:
    def __init__(self, window_size: int):
        self._buf = deque(maxlen=window_size)

    def record(self, value: float) -> None:
        self._buf.append(value)

    def average(self) -> float:
        return sum(self._buf) / len(self._buf) if self._buf else 0.0

    def max(self) -> float:
        return max(self._buf) if self._buf else float('-inf')
```

---

## Gotcha Follow-ups

**"Can you use a `dict` as a thread-safe data structure?"**
Individual `dict` operations (get, set, del by key) are effectively atomic in CPython because they hold the GIL during the operation. But compound operations (check-then-act: `if k not in d: d[k] = ...`) are NOT atomic — another thread can insert between the check and the set. Use `dict.setdefault(k, v)` or `threading.Lock` for compound operations. For a thread-safe mapping with full ACID semantics, use `collections.OrderedDict` + `threading.Lock` or `shelve` + `threading.Lock`.

**"What's the difference between `bisect_left` and `bisect_right`?"**
Both find where to insert `x` in a sorted list to maintain sort order. `bisect_left` returns the leftmost position (before equal elements); `bisect_right` returns the rightmost position (after equal elements):
```python
lst = [1, 2, 2, 2, 3]
print(bisect.bisect_left(lst, 2))    # 1 — insert BEFORE existing 2s
print(bisect.bisect_right(lst, 2))   # 4 — insert AFTER existing 2s
```
Use `bisect_left` for "find first occurrence"; `bisect_right` for "find insertion point after all equal items."

---

## Under the Hood

`heapq` (`Lib/heapq.py`): pure Python, with C-accelerated `_heapq` module for CPython. The heap property: `h[k] <= h[2*k+1]` and `h[k] <= h[2*k+2]` for all valid indices. `heappush` sifts up from the tail; `heappop` moves tail to root and sifts down.

`bisect` (`Lib/bisect.py`): also has a C accelerator (`_bisect`). The binary search loop: `lo, hi = 0, len(a)`; `mid = (lo + hi) >> 1`; compare `a[mid]` with `x`; adjust `lo` or `hi`. O(log n) comparisons, but O(n) for `insort` due to the shift.
