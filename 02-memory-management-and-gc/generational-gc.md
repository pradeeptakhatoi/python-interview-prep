# Generational Garbage Collector

## Concept

CPython's cyclic garbage collector (the `gc` module) exists solely to collect **reference cycles** — groups of objects that reference each other but are unreachable from any root. Reference counting handles everything else.

### Three Generations

The collector partitions objects into three generations based on survival time:

| Generation | Index | Threshold (default) | Purpose |
|------------|-------|---------------------|---------|
| Young | 0 | 700 allocations | Newly created objects |
| Middle | 1 | 10 gen-0 collections | Survivors of one gen-0 sweep |
| Old | 2 | 10 gen-1 collections | Long-lived objects |

Objects are promoted to the next generation each time they survive a collection. The rationale is the **generational hypothesis**: most objects die young (temporaries, locals). Collecting gen-0 frequently and gen-2 rarely amortizes the cost of scanning long-lived objects.

```python
import gc

print(gc.get_threshold())  # (700, 10, 10) by default
print(gc.get_count())      # (current_gen0, gen1, gen2) allocation counts

gc.set_threshold(1000, 15, 15)  # tune for long-lived object-heavy workloads
```

### How a Collection Works

1. **Mark unreachable:** For each object in the target generation, the GC decrements a copy of `ob_refcnt` by the count of internal references (those from objects in the same generation). Objects whose copy reaches 0 have no external references — they are unreachable.
2. **Finalizers:** Objects with `__del__` are moved to `gc.garbage` (pre-PEP 442) or scheduled for finalization in safe order (post-PEP 442).
3. **Sweep:** Unreachable objects are deallocated.

The key insight: subtracting internal-reference counts from `ob_refcnt` reveals which objects are held only by the cycle itself.

```python
import gc

class Node:
    def __init__(self, name):
        self.name = name
        self.next = None

a = Node("a")
b = Node("b")
a.next = b
b.next = a   # cycle

del a, b     # external refs gone; refcounts are 1 (each held by the other)
             # NOT freed by reference counting

collected = gc.collect()  # forces gen-0/1/2 sweep
print(f"Collected {collected} objects")  # 2
```

### Tracking Container Objects

The GC only tracks **container objects** — those that can hold references to other objects. Scalars (`int`, `float`, `str`, `bytes`) are never tracked. You can check:

```python
import gc
print(gc.is_tracked([]))      # True  — list is a container
print(gc.is_tracked({}))      # True
print(gc.is_tracked(42))      # False — int is scalar
print(gc.is_tracked("hello")) # False

# After a list contains only scalars, CPython 3.x may untrack it:
lst = [1, 2, 3]
print(gc.is_tracked(lst))     # False in CPython 3.x — untracked optimization
lst.append([])
print(gc.is_tracked(lst))     # True — now contains a container
```

---

## Interview Questions

### Q1: When does the cyclic GC run, and can you control it?

**Model answer:**  
The GC runs automatically when the allocation count for a generation exceeds its threshold. `gc.get_count()` returns the current counts; `gc.get_threshold()` shows the thresholds.

You can:
- **Trigger manually:** `gc.collect(generation=2)` collects that generation and all younger ones.
- **Disable:** `gc.disable()` — useful in benchmarks or when you know your code has no cycles (web request handlers often do this per-request).
- **Tune thresholds:** `gc.set_threshold(n0, n1, n2)`. Increase gen-0 threshold for allocation-heavy code to reduce GC frequency at the cost of holding cycles longer.

```python
import gc

gc.disable()  # disable automatic collection
# ... allocation-heavy section ...
gc.collect()  # manual collection
gc.enable()
```

### Q2: What is `gc.garbage` and when does it get populated?

**Model answer:**  
`gc.garbage` is a list of objects the GC found to be unreachable but could **not** safely free. Objects land here when:

1. They define `__del__` AND are part of a reference cycle — pre-Python 3.4 (pre-PEP 442). The GC couldn't determine a safe finalization order.
2. Code explicitly appends to `gc.garbage` (unusual).

Post-PEP 442 (Python 3.4+), objects with `__del__` in cycles ARE collected — `gc.garbage` is populated only if the GC cannot determine a safe ordering even with PEP 442 rules, which is rare.

**Monitoring in production:**

```python
import gc
import logging

gc.collect()
if gc.garbage:
    logging.warning("Uncollectable objects: %d", len(gc.garbage))
    # Inspect and clear:
    gc.garbage.clear()
```

### Q3: How does generation promotion work, and why does it matter?

**Model answer:**  
On each gen-0 collection, objects that survive are moved to gen-1. After `n1` gen-0 collections (default 10), gen-1 is collected — survivors move to gen-2. After `n2` gen-1 collections, gen-2 is collected.

This matters because:
- **Long-lived objects (gen-2) are scanned rarely** — a web server's cached config dict isn't scanned on every gen-0 sweep.
- **High allocation rate in gen-0 doesn't slow down gen-2 scans.**
- **Tuning gen-0 threshold** can help in high-allocation, low-cycle workloads: raising it from 700 to 5000 means gen-0 collects 7x less often.

Instagram famously disabled the GC entirely after moving to a copy-on-write fork model (via `gc.freeze()` in Python 3.7+, which moves all current objects to a "permanent" gen-2 pool that is never collected again).

### Q4: What is `gc.freeze()` and why did Instagram use it?

**Model answer:**  
`gc.freeze()` (Python 3.7+) moves all currently tracked objects to a frozen generation that the GC never collects. Frozen objects are still tracked for cycle detection purposes of non-frozen objects, but are never swept.

Instagram's use case: they have a Python master process that loads all app code once, then `fork()`s thousands of worker processes. Without `gc.freeze()`:
- Each worker's GC sees all the pre-fork objects as gen-2 candidates.
- After fork, the kernel uses copy-on-write (COW) for memory pages. The GC traversing gen-2 objects caused writes to `ob_refcnt` fields, dirtying COW pages and destroying the memory savings of forking.

With `gc.freeze()` before forking: pre-fork objects are frozen, GC never touches them in workers, COW pages stay shared.

```python
import gc
gc.disable()
# ... load all modules, warm caches ...
gc.freeze()     # freeze everything loaded so far
# fork() here — workers inherit frozen objects without GC dirtying them
```

### Q5: Explain the difference between `gc.collect()` with no argument vs. `gc.collect(0)`.

**Model answer:**  
- `gc.collect()` or `gc.collect(2)` — collects generation 2 and all younger generations (full collection).
- `gc.collect(0)` — collects only generation 0.
- `gc.collect(1)` — collects generation 1 and generation 0.

In all cases, the return value is the number of **unreachable objects** found (not necessarily freed — some may have `__del__` methods). A full collection (`gc.collect(2)`) also updates the generation counts.

---

## Gotcha Follow-ups

**"Can you make the GC miss a cycle?"**  
Yes — by overriding `__del__` in a way that creates new external references during finalization (object resurrection). Also, C extension types that don't implement `tp_traverse` properly will have their cycles missed entirely because the GC can't walk their internal references.

**"What's the overhead of the GC on a typical web application?"**  
It depends heavily on object lifetime and cycle rate. A common production pattern is to call `gc.collect()` only between requests (not during), or to use `gc.disable()` + periodic manual collection. The GC's overhead is roughly proportional to the number of live tracked objects, so applications with many long-lived containers pay the most.

---

## Under the Hood

The GC maintains a doubly-linked list of tracked objects (the "generation list"). Each tracked object has a `PyGC_Head` prepended to it in memory:

```c
/* Modules/gcmodule.c */
typedef struct {
    uintptr_t _gc_next;   /* forward link */
    uintptr_t _gc_prev;   /* backward link + refcount copy flags */
} PyGC_Head;
```

During `collect()`, the GC walks this list, performs the refcount subtraction (using `tp_traverse` to find internal refs), marks unreachable objects, and calls `tp_finalize` (Python's `__del__`) on them before deallocation.
