# Memory Profiling

## Concept

Memory leaks in Python are usually not "leaked memory" in the C sense — they're live Python objects that remain referenced longer than intended. The tools to find them operate at the object level, not the raw memory level.

### Key Tools

| Tool | Type | What It Measures |
|------|------|-----------------|
| `tracemalloc` | stdlib | Per-allocation tracing; pinpoints where memory was allocated |
| `objgraph` | 3rd-party | Object counts, reference chains, what's holding what |
| `gc.get_objects()` | stdlib | All live tracked objects |
| `sys.getsizeof()` | stdlib | Shallow size of one object (not recursive) |
| `memory_profiler` | 3rd-party | Line-by-line RSS growth (process level) |
| `py-spy` | 3rd-party | Sampling profiler; can show memory alongside CPU |

---

### `tracemalloc` — The Right Starting Point

```python
import tracemalloc

tracemalloc.start()

# ... code under investigation ...
result = [dict(x=i, y=i*2) for i in range(100_000)]

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("Top 10 memory allocations:")
for stat in top_stats[:10]:
    print(stat)

tracemalloc.stop()
```

**Comparing two snapshots** (most useful pattern — finds what grew):

```python
import tracemalloc

tracemalloc.start()
snap1 = tracemalloc.take_snapshot()

# ... load more data, handle more requests ...
data = {i: [j for j in range(100)] for i in range(1000)}

snap2 = tracemalloc.take_snapshot()
top_stats = snap2.compare_to(snap1, 'lineno')

print("Memory growth since snap1:")
for stat in top_stats[:5]:
    print(stat)
```

**Filters to exclude noise:**

```python
filters = [
    tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
    tracemalloc.Filter(False, tracemalloc.__file__),
]
snapshot = tracemalloc.take_snapshot().filter_traces(filters)
```

### `objgraph` — Finding What's Holding References

```python
import objgraph

# Show most common object types by count:
objgraph.show_most_common_types(limit=10)

# Find all instances of a type:
leaking_dicts = objgraph.by_type('dict')

# Show what's referencing a specific object (VERY useful for leak debugging):
obj = leaking_dicts[0]
objgraph.show_backrefs(obj, max_depth=3)  # renders a reference graph

# Find objects that appeared since a previous snapshot:
objgraph.show_growth(limit=5)  # call before and after to see growth
```

**Typical leak investigation workflow:**

```python
import gc
import objgraph

gc.collect()
counts_before = objgraph.typestats()

# ... run the operation suspected of leaking ...
process_batch(data)

gc.collect()
counts_after = objgraph.typestats()

# Find what grew:
for type_name, count in sorted(counts_after.items()):
    before = counts_before.get(type_name, 0)
    if count > before + 10:
        print(f"{type_name}: {before} -> {count} (+{count - before})")
```

### `sys.getsizeof` — Shallow vs Deep Size

```python
import sys
from collections import deque

# getsizeof returns SHALLOW size only:
lst = [object() for _ in range(1000)]
print(sys.getsizeof(lst))    # ~8056 bytes — only the list array, not the objects

def deep_sizeof(obj, seen=None):
    """Recursive size including all referenced objects."""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(deep_sizeof(k, seen) + deep_sizeof(v, seen) for k, v in obj.items())
    elif hasattr(obj, '__dict__'):
        size += deep_sizeof(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        size += sum(deep_sizeof(item, seen) for item in obj)
    return size
```

### Diagnosing Leaks in Long-Running Processes

Leaks in web servers / long-running daemons typically look like one of:

1. **Growing `dict` or `list` count** — something is accumulating references without clearing.
2. **Growing closure count** — callbacks or coroutines are being created but not released.
3. **Growing custom object count** — a cache or registry with no eviction.

**Pattern: periodic snapshots with delta reporting**

```python
import gc
import tracemalloc
import logging
from threading import Thread
import time

class MemoryMonitor(Thread):
    def __init__(self, interval=60):
        super().__init__(daemon=True)
        self.interval = interval
        self._last_snapshot = None

    def run(self):
        tracemalloc.start(25)  # 25 frames of traceback
        while True:
            time.sleep(self.interval)
            gc.collect()
            snapshot = tracemalloc.take_snapshot()
            if self._last_snapshot:
                stats = snapshot.compare_to(self._last_snapshot, 'traceback')
                for stat in stats[:3]:
                    if stat.size_diff > 1024 * 100:  # >100KB growth
                        logging.warning("Memory growth: %s", stat)
            self._last_snapshot = snapshot

monitor = MemoryMonitor(interval=60)
monitor.start()
```

---

## Interview Questions

### Q1: What's the difference between `tracemalloc` and `objgraph`? When do you use each?

**Model answer:**  
`tracemalloc` operates at the allocator level — it intercepts every call to Python's memory allocator and records where (file + line) the allocation came from. It tells you WHERE memory was allocated, with precise stack traces. It has low-ish overhead (~10-20% depending on traceback depth) and ships with the stdlib.

`objgraph` operates at the object level — it queries `gc.get_objects()` and analyzes reference graphs. It tells you WHAT types of objects are alive and WHAT is holding references to a specific object. It's invaluable for answering "why hasn't this object been GC'd?" It has essentially no overhead when not actively in use.

Typical workflow:
1. Notice process RSS growing → use `tracemalloc` to identify which code path allocates the most.
2. Identify a specific type growing in count → use `objgraph.show_backrefs()` to find what's holding the reference.

### Q2: How do you find a memory leak in a production Python service without restarting it?

**Model answer:**  
Best approach: build in a debug endpoint that can be triggered on demand.

```python
# In a Flask/aiohttp handler — only enable in non-production or via feature flag:
import gc
import tracemalloc
import objgraph
from io import StringIO

def memory_report():
    gc.collect()
    
    output = StringIO()
    
    # Object type counts
    output.write("=== Top object types ===\n")
    objgraph.show_most_common_types(limit=20, file=output)
    
    # tracemalloc snapshot if running
    if tracemalloc.is_tracing():
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics('lineno')
        output.write("\n=== Top allocations ===\n")
        for stat in stats[:10]:
            output.write(f"{stat}\n")
    
    return output.getvalue()
```

If you can't touch code, attach `py-spy` externally: `py-spy record -p <pid> -o profile.svg` gives a flame graph with memory annotations.

### Q3: What does `sys.getsizeof` miss, and how do you get accurate deep sizes?

**Model answer:**  
`sys.getsizeof` returns the **shallow** size — the size of the Python object struct itself, not including any objects it references. For a list of 1000 objects, it returns the size of the internal array (pointers), not the objects pointed to.

```python
import sys
x = [1] * 1000
print(sys.getsizeof(x))    # ~8056 — the list's pointer array
print(sys.getsizeof(1))    # 28 — a single int
# Actual memory: ~8056 + 28 (shared small int) ≈ 8056 (ints are cached)

y = [object() for _ in range(1000)]
print(sys.getsizeof(y))    # ~8056 — same pointer array
# But each object() costs 56 bytes, so real cost ~8056 + 56000 = 64056
```

For accurate deep sizes, use `pympler.asizeof` (third-party) or implement a recursive traversal with a `seen` set (to handle shared references correctly).

### Q4: How would you diagnose a leak where `gc.collect()` doesn't help?

**Model answer:**  
If `gc.collect()` doesn't free objects, the leak is not a cycle problem — objects are being explicitly referenced somewhere. The investigation path:

1. **`objgraph.show_backrefs(leaking_obj, max_depth=5)`** — renders the reference chain holding the object. Look for caches, module-level globals, class variables.

2. **Common culprits:**
   - `functools.lru_cache` — caches grow without bound on unbounded input
   - Module-level lists/dicts used as registries with no eviction
   - Logging handlers that buffer log records
   - `threading.local()` objects that accumulate data across threads
   - Event listeners that hold strong references to subscribers

3. **`gc.get_referrers(obj)`** — returns all objects that directly reference `obj`. More precise than `objgraph` for a specific object, but slow on large heaps.

```python
import gc
import objgraph

leakers = objgraph.by_type('MyLeakingClass')
if leakers:
    obj = leakers[0]
    referrers = gc.get_referrers(obj)
    print(f"Held by {len(referrers)} objects:")
    for r in referrers:
        print(type(r), repr(r)[:100])
```

### Q5: How does `__slots__` affect memory profiling and actual memory use?

**Model answer:**  
Without `__slots__`, every instance gets a `__dict__` (a Python dict) for attribute storage. A dict object has ~200+ bytes of overhead. For classes with a fixed set of attributes, `__slots__` replaces the dict with a C-level array of slots — one pointer per slot, plus the object header. Savings are typically 40-70% per instance.

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

d = WithDict(1, 2)
s = WithSlots(1, 2)

print(sys.getsizeof(d))            # 48 (object) + 232 (dict) ≈ 280
print(sys.getsizeof(d.__dict__))   # 232
print(sys.getsizeof(s))            # 56 — just the object with 2 slots, no dict

# At 1M instances:
# WithDict: ~280 MB
# WithSlots: ~56 MB (5x smaller)
```

In memory profiling, `__slots__` objects appear smaller in `tracemalloc` and `sys.getsizeof`, and `objgraph` shows far fewer `dict` objects.

---

## Gotcha Follow-ups

**"tracemalloc shows a function is allocating lots of memory, but the memory doesn't show up in objgraph. What's happening?"**  
The objects were allocated AND freed before `objgraph` checked. `tracemalloc` shows cumulative allocations (can be configured); `objgraph` shows live objects. If memory is allocated and released within a tight loop, `tracemalloc` will show a high total but `objgraph` won't show excess live objects. This is peak memory usage, not a leak. Use `tracemalloc.get_traced_memory()` to get current vs. peak.

**"How do you profile memory in asyncio-based code?"**  
The same tools work — `tracemalloc` is async-safe. The tricky part is that coroutine objects themselves have non-trivial size (each `Task` + frame + locals), and tasks that are created but not awaited accumulate. `asyncio.all_tasks()` lets you count live tasks; unexpected growth there indicates task leaks (e.g., fire-and-forget code that creates tasks without holding references and never awaiting them).

---

## Under the Hood

`tracemalloc` hooks into CPython's memory allocator via `PyMemAllocatorEx`. The `start(nframe)` call installs custom `malloc`/`realloc`/`free` hooks that record a stack trace (up to `nframe` frames) for every allocation. The tracing data is stored in a C-level hash table, not Python objects, to avoid recursion and overhead from tracing the tracer itself. At `take_snapshot()`, this table is serialized into Python `Traceback` and `Statistic` objects.
