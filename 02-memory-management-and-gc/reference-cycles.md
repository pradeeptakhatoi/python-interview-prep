# Reference Cycles

## Concept

A reference cycle exists when a group of objects form a chain of references that leads back to the first object. No object in the cycle can ever reach a refcount of 0 through reference counting alone, even if the entire group is unreachable from the program's root set.

### Common Cycle Patterns

```python
# Pattern 1: Direct self-reference
x = []
x.append(x)         # x -> x

# Pattern 2: Two-object cycle
a, b = {}, {}
a['b'] = b
b['a'] = a          # a -> b -> a

# Pattern 3: Parent-child back-reference (very common in tree structures)
class Node:
    def __init__(self, val, parent=None):
        self.val = val
        self.parent = parent
        self.children = []

root = Node(1)
child = Node(2, parent=root)
root.children.append(child)  # root -> child -> root (via parent)

# Pattern 4: Closures capturing their enclosing scope
def make_cycle():
    def inner():
        return inner  # inner references itself
    return inner

cycle_fn = make_cycle()  # closure cycle
```

### Why Cycles Are Not Freed by Refcounting

```python
import sys
import gc

gc.disable()  # prevent the GC from cleaning up our demonstration

a = []
b = [a]
a.append(b)  # cycle: a -> b -> a

print(sys.getrefcount(a))  # 3: 'a' name, b[0], getrefcount arg
print(sys.getrefcount(b))  # 3: 'b' name, a[0], getrefcount arg

del a, del b  # remove external names
# Both refcounts drop to 1 (still held by the other object in the cycle)
# tp_dealloc is never called — memory is leaked until GC runs

gc.enable()
collected = gc.collect()
print(f"GC collected {collected} objects")  # 2
```

### `__del__` and Cycles (Pre- vs. Post-PEP 442)

**Pre-Python 3.4 (before PEP 442):**  
Objects with `__del__` methods in a reference cycle could NEVER be collected by the cyclic GC. They landed in `gc.garbage` as "uncollectable" objects, causing memory leaks.

**Post-Python 3.4 (PEP 442 — Safe object finalization):**  
The GC now calls `tp_finalize` (which invokes `__del__`) on unreachable objects BEFORE they are unlinked from the cycle. This allows finalizers to run safely. The GC checks if finalizers "resurrected" the object (created a new external reference) and handles that case.

```python
import gc

class Cyclic:
    def __init__(self, name):
        self.name = name
        self.other = None

    def __del__(self):
        print(f"__del__ called on {self.name}")

gc.disable()
x = Cyclic("x")
y = Cyclic("y")
x.other = y
y.other = x  # cycle with __del__

del x, y

gc.enable()
gc.collect()
# Post-PEP 442: prints "__del__ called on ..." for both
# Pre-PEP 442: they would land in gc.garbage instead
```

---

## Interview Questions

### Q1: How does CPython's cyclic GC detect that objects in a cycle are unreachable?

**Model answer:**  
The GC uses a "copy refcount" trick:

1. For each object in the target generation, it walks the object's internal references via `tp_traverse`, decrementing a **copy** of `ob_refcnt` (not the real count) for each internal reference found.
2. After this pass, objects whose copy reaches 0 are referenced only by other objects in the same generation — no external references exist. They are provisionally marked "unreachable."
3. Objects still reachable from provisionally-unreachable ones (via `tp_traverse`) are moved back to "reachable."
4. The remaining unreachable objects form the cycle; they are finalized and deallocated.

This algorithm is O(n) in the number of tracked objects in the generation.

### Q2: What is object resurrection and why is it dangerous?

**Model answer:**  
Object resurrection occurs when `__del__` (or `tp_finalize`) creates a new external reference to the object being finalized:

```python
registry = []

class ResurrectionDemo:
    def __del__(self):
        registry.append(self)  # self is now referenced again — resurrected!
        print("Resurrected!")

obj = ResurrectionDemo()
del obj
# __del__ runs, appends to registry — obj is now alive again
# __del__ will NOT be called again when registry releases it
```

Why dangerous:
1. The object is now in an inconsistent state — it may hold resources that were already partially cleaned up.
2. `__del__` is guaranteed to run at most once per object lifetime; a resurrected object that is later freed will NOT have `__del__` called again.
3. In pre-3.4 code, resurrection in cycle scenarios prevented collection entirely.

### Q3: How do you break cycles intentionally in production code?

**Model answer:**  
Three approaches:

**1. Weak references for back-references:**
```python
import weakref

class Node:
    def __init__(self, val, parent=None):
        self.val = val
        self._parent = weakref.ref(parent) if parent else None
        self.children = []

    @property
    def parent(self):
        return self._parent() if self._parent else None
```

**2. Explicit nulling in a `close()` method:**
```python
class Resource:
    def __init__(self, owner):
        self.owner = owner  # creates cycle if owner holds self

    def close(self):
        self.owner = None  # break the cycle explicitly
```

**3. Use `__slots__` with `weakref.ref` to reduce accidental cycles.**

For tree structures (ASTs, DOM nodes, linked lists), the parent back-reference is the most common source of cycles. Using `weakref.ref` for the parent pointer is the idiomatic solution.

### Q4: Can you write a cycle detector in pure Python?

**Model answer:**  
```python
import gc

def find_cycles():
    """Return groups of objects forming reference cycles."""
    gc.collect()  # ensure gc.garbage is populated for truly uncollectable ones
    
    # For collectable cycles, we can detect them by looking at objects
    # the GC is tracking that refer to each other.
    # This is a simplified approach using gc.get_objects():
    
    objects = gc.get_objects()
    id_to_obj = {id(o): o for o in objects}
    
    cycles = []
    visited = set()
    
    def find_cycle_from(obj, path, path_ids):
        obj_id = id(obj)
        if obj_id in path_ids:
            # Found a cycle
            cycle_start = path.index(obj)
            cycles.append(path[cycle_start:])
            return
        if obj_id in visited:
            return
        
        path.append(obj)
        path_ids.add(obj_id)
        
        for ref in gc.get_referents(obj):
            if id(ref) in id_to_obj:
                find_cycle_from(ref, path, path_ids)
        
        path.pop()
        path_ids.discard(obj_id)
        visited.add(obj_id)
    
    for obj in objects:
        find_cycle_from(obj, [], set())
    
    return cycles
```

Note: `gc.get_objects()` returns all tracked objects. `gc.get_referents(obj)` walks `tp_traverse`, the same function the GC uses internally.

### Q5: What types of objects are immune to reference cycles in CPython?

**Model answer:**  
Only **container** objects can participate in cycles — objects that can hold references to other Python objects. Non-container types cannot:

```python
import gc
# These are NEVER tracked by the GC:
gc.is_tracked(42)       # False — int
gc.is_tracked(3.14)     # False — float
gc.is_tracked("hello")  # False — str
gc.is_tracked(b"data")  # False — bytes
gc.is_tracked(True)     # False — bool

# These ARE tracked:
gc.is_tracked([])       # True
gc.is_tracked({})       # True
gc.is_tracked(set())    # True
gc.is_tracked(object()) # True (has __dict__ potentially)
```

CPython also untracks lists/tuples that contain only non-container items as an optimization. This is why cycles between pure scalar containers are still possible at the Python level but the GC would track the container (list/dict) wrapping them.

---

## Gotcha Follow-ups

**"Show me a cycle that involves a class itself."**
```python
import gc, sys

class Meta(type):
    pass

class MyClass(metaclass=Meta):
    pass

# MyClass.__class__ is Meta
# Meta.__instancecheck__ involves MyClass
# Class objects routinely have cycles; gc handles them
```

**"If I call `gc.disable()` in production, what am I risking?"**  
Any code that creates reference cycles will leak memory indefinitely until `gc.collect()` is called explicitly. Modern web frameworks (Flask, Django views) and async frameworks (asyncio tasks that hold closures) can easily create cycles. Disabling the GC requires that you either: (a) have zero cycles in your object graph, or (b) call `gc.collect()` manually at safe points (e.g., end of each request). Instagram could do this because they analyzed their object graph; most teams cannot make that guarantee.

---

## Under the Hood

The cycle detection algorithm is in `Modules/gcmodule.c`, function `collect()`. The critical step is `subtract_refs()` which calls `tp_traverse` on each object in the generation, decrementing a shadow refcount field. Objects whose shadow count reaches zero are added to the "unreachable" list. A second pass (`move_legacy_finalizers()`) separates objects with `__del__` for safe finalization ordering (PEP 442).
