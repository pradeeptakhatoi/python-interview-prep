# Weak References

## Concept

A **weak reference** is a reference to an object that does not increment the object's `ob_refcnt`. If the only remaining references to an object are weak references, the object is garbage collected and the weak references become invalid (return `None` when dereferenced).

The `weakref` module provides:
- `weakref.ref(obj, callback=None)` — creates a weak reference; call the result to dereference
- `weakref.proxy(obj)` — a proxy that behaves like the object (transparent, raises `ReferenceError` when dead)
- `weakref.WeakValueDictionary` — a dict that doesn't keep its values alive
- `weakref.WeakKeyDictionary` — a dict that doesn't keep its keys alive
- `weakref.WeakSet` — a set that doesn't keep its members alive

```python
import weakref
import gc

class Expensive:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"Expensive({self.name!r})"

obj = Expensive("resource")
ref = weakref.ref(obj)

print(ref())       # Expensive('resource') — dereferences the weak ref
print(ref() is obj)  # True

del obj
gc.collect()       # ensure cleanup (in case of GC delay)
print(ref())       # None — object was collected
```

### Callbacks

```python
def on_finalized(ref):
    print(f"Object at {ref} was garbage collected")

obj = Expensive("tracked")
ref = weakref.ref(obj, on_finalized)
del obj  # triggers: "Object at <weakref at 0x...> was garbage collected"
```

The callback receives the (now-dead) weak reference object, not the original object (which is gone). Do not try to dereference it inside the callback.

### WeakValueDictionary — The Cache Pattern

```python
import weakref

class Cache:
    def __init__(self):
        self._store = weakref.WeakValueDictionary()

    def get(self, key, factory):
        obj = self._store.get(key)
        if obj is None:
            obj = factory(key)
            self._store[key] = obj
        return obj

cache = Cache()
r1 = cache.get("alpha", Expensive)
r2 = cache.get("alpha", Expensive)
print(r1 is r2)   # True — same object returned from cache

del r1, r2        # all strong refs gone; cache entry auto-removed
print(dict(cache._store))  # {} — WeakValueDict auto-cleaned
```

This is the correct pattern for implementing a **memoization cache that doesn't prevent GC**. `functools.lru_cache` holds strong references and can retain objects indefinitely.

### What Objects Can Be Weakly Referenced?

Not all objects support weak references. The type must allocate `tp_weaklistoffset` in its C struct:

```python
import weakref

# Support weak refs:
weakref.ref([])          # list ✓
weakref.ref({})          # dict ✓
weakref.ref(set())       # set ✓

class MyClass: pass
weakref.ref(MyClass())   # user-defined classes ✓

# Do NOT support weak refs:
try:
    weakref.ref(42)      # TypeError
except TypeError as e:
    print(e)  # cannot create weak reference to 'int' object

try:
    weakref.ref("hello") # TypeError
except TypeError as e:
    print(e)

# Enable weak refs in custom classes with __slots__:
class WithSlots:
    __slots__ = ('x', '__weakref__')  # must explicitly include __weakref__
    def __init__(self, x):
        self.x = x

weakref.ref(WithSlots(1))  # works because __weakref__ slot is present
```

### Observer Pattern Without Memory Leaks

```python
import weakref
from typing import Callable

class EventEmitter:
    def __init__(self):
        self._listeners: list[weakref.ref] = []

    def subscribe(self, callback: Callable):
        self._listeners.append(weakref.ref(callback))

    def emit(self, event):
        alive = []
        for ref in self._listeners:
            cb = ref()
            if cb is not None:
                cb(event)
                alive.append(ref)
        self._listeners = alive  # prune dead refs

emitter = EventEmitter()

class Handler:
    def __call__(self, event):
        print(f"Handling: {event}")

h = Handler()
emitter.subscribe(h)
emitter.emit("click")   # "Handling: click"

del h                   # handler GC'd
emitter.emit("click")   # nothing — dead ref pruned silently
```

---

## Interview Questions

### Q1: When should you use `weakref.ref` vs `weakref.proxy`?

**Model answer:**  
- `weakref.ref` — when you need to explicitly check liveness before use (`ref()` returns `None` if dead). Prefer this when the check is important for correctness (caches, event listeners).
- `weakref.proxy` — when you want transparent access to the object but can tolerate a `ReferenceError` if the object is collected. Useful for "best-effort" delegation where the object is expected to outlive the proxy.

```python
proxy = weakref.proxy(obj)
del obj
try:
    print(proxy.name)  # ReferenceError: weakly-referenced object no longer exists
except ReferenceError:
    pass
```

`weakref.ref` is safer for production code because it forces explicit liveness checking.

### Q2: Why doesn't `weakref.ref` work on built-in scalars like `int` and `str`?

**Model answer:**  
Supporting weak references requires a slot in the C struct for a weakref list pointer (`tp_weaklistoffset`). CPython's built-in scalars were not designed with this slot because:

1. They are heavily interned/cached (small ints, interned strings) — weak refs to cached objects would never die.
2. The overhead of maintaining a weakref list in every int/str/bytes object would be prohibitive given how many exist.

User-defined classes get `tp_weaklistoffset` automatically (via `__weakref__` in `__dict__`). Classes using `__slots__` must explicitly include `'__weakref__'` in the slots list.

### Q3: What's the difference between `WeakValueDictionary` and `WeakKeyDictionary`? Give a real use case for each.

**Model answer:**  

**`WeakValueDictionary`** — keys are strong, values are weak. The entry is removed when the value is garbage collected.  
*Use case:* Object cache keyed by a stable identifier (ID, name). Objects are evicted from cache when no other code holds a reference.

**`WeakKeyDictionary`** — keys are weak, values are strong. The entry is removed when the key is garbage collected.  
*Use case:* Per-object metadata that should not prevent the object from being collected. A classic example is an attribute store for external types you don't own:

```python
import weakref

_metadata = weakref.WeakKeyDictionary()

def set_metadata(obj, key, value):
    if obj not in _metadata:
        _metadata[obj] = {}
    _metadata[obj][key] = value

def get_metadata(obj, key):
    return _metadata.get(obj, {}).get(key)

class External: pass

e = External()
set_metadata(e, "tag", "important")
print(get_metadata(e, "tag"))  # "important"
del e  # metadata entry auto-removed — no leak
```

### Q4: Can weakrefs prevent the cyclic GC from running? What's the interaction?

**Model answer:**  
Weak references do NOT increment refcounts, so they do not contribute to cycles and do not prevent collection. The cyclic GC ignores weak references when computing reachability.

However, there's a subtle ordering: during a GC collection, weakref callbacks are called BEFORE `__del__` finalizers. This allows cache invalidation code in weakref callbacks to run cleanly before any finalizer code.

```python
import weakref, gc

class Obj:
    def __del__(self):
        print("__del__ called")

def callback(ref):
    print("weakref callback called")

o = Obj()
r = weakref.ref(o, callback)
# Create a cycle that includes o:
o.self_ref = o

del o
gc.collect()
# Output order:
# weakref callback called
# __del__ called
```

### Q5: How do you implement a thread-safe weak-value cache?

**Model answer:**  
`WeakValueDictionary` itself is not thread-safe — concurrent reads and writes can corrupt internal state. Wrap with a lock:

```python
import weakref
import threading

class ThreadSafeWeakCache:
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            return self._cache.get(key)

    def set(self, key, value):
        with self._lock:
            self._cache[key] = value

    def get_or_create(self, key, factory):
        with self._lock:
            obj = self._cache.get(key)
            if obj is None:
                obj = factory(key)
                self._cache[key] = obj
            return obj
```

Note: `WeakValueDictionary.__getitem__` involves two separate operations internally (lookup + dereference), so even read operations need locking in concurrent code.

---

## Gotcha Follow-ups

**"What happens if an object's `__del__` holds a strong reference to itself?"**  
If `__del__` stores `self` somewhere (object resurrection), the weak reference callback has already been called with a dead-looking reference. After resurrection, the object is alive again, but any `weakref.ref` to it is permanently dead — resurrection does not revive weak references. This is a subtle bug pattern.

**"Can you weakly reference a bound method?"**  
Not directly — bound methods are ephemeral objects created fresh on each attribute access. `weakref.ref(obj.method)` will immediately return a dead reference because the bound method object has no other references:

```python
import weakref

class Foo:
    def bar(self): pass

f = Foo()
ref = weakref.ref(f.bar)  # bound method is created and immediately dropped
print(ref())              # None — already collected!

# Solution: use WeakMethod from weakref module (Python 3.4+)
ref = weakref.WeakMethod(f.bar)
print(ref())              # <bound method Foo.bar of <Foo...>> — alive while f is alive
```

---

## Under the Hood

Weak references are implemented in `Objects/weakrefobject.c`. Each object with `tp_weaklistoffset` maintains a linked list of `PyWeakReference` objects pointing to it. When `_Py_Dealloc` is called, before the object is freed, `PyObject_ClearWeakRefs` nulls out all weak references pointing to it and fires any callbacks. This nulling happens before `tp_finalize` (`__del__`) is called, which is why weakref callbacks always run before `__del__`.
