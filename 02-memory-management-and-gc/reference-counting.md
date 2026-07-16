# Reference Counting Internals

## Concept

CPython uses reference counting as its **primary** memory management mechanism. Every Python object has an `ob_refcnt` field (a `Py_ssize_t` in `Include/object.h`). When that count reaches zero, `_Py_Dealloc()` is called immediately and synchronously — no GC pause, no deferred collection.

**`Py_INCREF(op)`** — increments `ob_refcnt`  
**`Py_DECREF(op)`** — decrements; if zero, calls `op->ob_type->tp_dealloc(op)`

Events that increment refcount:
- Object creation (`Py_INCREF` in the allocator)
- Assignment (`x = obj`)
- Passing as a function argument
- Appending to a container (list, dict, etc.)
- Returning from a function

Events that decrement:
- Variable goes out of scope
- `del x`
- Rebinding (`x = other_obj`)
- Removing from a container
- Function frame exits

```python
import sys

x = []
print(sys.getrefcount(x))  # 2: one for x, one for the getrefcount argument

y = x
print(sys.getrefcount(x))  # 3: x, y, getrefcount arg

def holds(obj):
    print(sys.getrefcount(obj))  # +1 for the parameter binding

holds(x)  # prints 4
print(sys.getrefcount(x))  # back to 3
```

**Why `sys.getrefcount` always returns +1:** the temporary reference created by passing the argument to `getrefcount` itself counts.

### RAII-style resource management

Reference counting gives CPython RAII-like deterministic cleanup. A file object closes its file descriptor the instant its refcount hits zero:

```python
def read_file(path):
    f = open(path)
    data = f.read()
    return data
    # f's refcount hits 0 here; file is closed immediately
    # In CPython. In PyPy/Jython this is NOT guaranteed.
```

This is an **implementation detail** of CPython, not a Python language guarantee. Code relying on it is not portable to other runtimes.

---

## Interview Questions

### Q1: What is reference counting and what are its limitations?

**Model answer:**  
CPython tracks the number of references to each object via `ob_refcnt`. When the count reaches zero, the object is deallocated immediately. Advantages: deterministic cleanup, no GC pause for most objects, low overhead for short-lived objects.

Limitations:
1. **Cannot collect reference cycles** — objects that mutually reference each other never reach refcount 0 even when unreachable from the program root. CPython's cyclic garbage collector handles this (see `generational-gc.md`).
2. **`ob_refcnt` is not thread-safe** — incrementing/decrementing is not atomic. The GIL protects it in the standard CPython build; free-threaded builds use biased reference counting instead.
3. **Performance overhead** — every assignment and function call touches `ob_refcnt`. For tight numeric loops this is measurable overhead vs. tracing GCs.

### Q2: How does `del x` actually work? Does it free memory?

**Model answer:**  
`del x` removes the name binding from the current namespace (calls `STORE_NAME` with `DELETE_NAME` opcode, or `DELETE_FAST` for locals). This decrements the object's refcount by 1. If and only if that refcount reaches 0 does `tp_dealloc` run and memory is returned.

```python
x = [1, 2, 3]
y = x          # refcount = 2
del x          # refcount = 1 — list is still alive
print(y)       # [1, 2, 3]
del y          # refcount = 0 — list is deallocated NOW
```

`del` does not guarantee memory is freed — it only reduces refcount. Memory is freed only when refcount hits 0. If the object is in a cycle, the cyclic GC must collect it.

### Q3: Why does CPython's reference counting NOT apply to integers between -5 and 256?

**Model answer:**  
CPython pre-allocates a fixed array of `PyLongObject` instances for integers in the range `[-5, 256]` (the "small int cache"). These objects are never deallocated; their refcount is effectively permanent. This means `sys.getrefcount` on these will show a large number.

```python
import sys
print(sys.getrefcount(0))    # very high — 0 is used everywhere
print(sys.getrefcount(1000)) # typically 3 (creation + getrefcount arg + interning)
```

This is an optimization to avoid millions of tiny allocations. It also means `x is y` is `True` for these integers even across unrelated assignments — which should never be relied upon in production code.

### Q4: Explain the `__del__` finalizer's interaction with reference counting.

**Model answer:**  
`__del__` is called by `tp_dealloc` when an object's refcount reaches 0. It is **not** a destructor in the C++ sense — it's a finalizer that runs just before deallocation. Key subtleties:

1. During `__del__`, the object is still alive (temporarily resurrected). If `__del__` creates a new reference to `self`, the object is resurrected and `__del__` will NOT be called again (pre-Python 3.4 behavior was different and dangerous).
2. Objects with `__del__` that are part of a reference cycle are problematic — prior to PEP 442 (Python 3.4), they could not be collected by the cyclic GC. Post-PEP 442, they can be collected but `__del__` order is not guaranteed.
3. `__del__` is not called for objects that still exist at interpreter shutdown.

```python
class Resource:
    def __del__(self):
        print(f"Cleaning up {self}")
        # Do NOT reference self here in a way that creates a new permanent reference

r = Resource()
del r  # prints "Cleaning up ..." immediately in CPython
```

**Prefer `contextlib.contextmanager` or `__exit__` over `__del__` for deterministic cleanup.**

### Q5: What does `sys.getrefcount` tell you in practice, and when do you use it?

**Model answer:**  
It shows the current reference count of an object, which includes the temporary reference created by the `getrefcount` call itself (always +1 vs. what you'd expect).

Real use cases:
- **Debugging unexpected object retention** — if a `getrefcount` returns a very high number for an object you expected to be short-lived, something is holding a reference.
- **Verifying cleanup logic** — confirming that a cache correctly releases objects.
- **Understanding container overhead** — a list of 1000 elements means 1000 refcount increments.

It's a diagnostic tool, not something to call in production hot paths.

---

## Gotcha Follow-ups

**"If CPython uses reference counting, why does it also have a garbage collector?"**  
Reference counting cannot detect cycles. Two objects pointing at each other never reach refcount 0 even if no external variable references them. CPython's generational cyclic GC (`gc` module) handles exactly this case. You can see it with `gc.collect()` and `gc.garbage`.

**"Is `__del__` called when the interpreter exits?"**  
Not reliably. At interpreter shutdown, objects may be collected in arbitrary order and the global namespace may already be `None`-ified. `__del__` may see module-level names as `None`. This is why `__del__` implementations that rely on global state (loggers, etc.) fail silently at shutdown.

---

## Under the Hood

```c
/* Include/object.h */
#define Py_INCREF(op) \
    do { \
        PyObject *_py_incref_tmp = (PyObject *)(op); \
        ++((_py_incref_tmp)->ob_refcnt); \
    } while (0)

#define Py_DECREF(op)                                   \
    do {                                                \
        PyObject *_py_decref_tmp = (PyObject *)(op);   \
        if (--(_py_decref_tmp->ob_refcnt) == 0)        \
            _Py_Dealloc(_py_decref_tmp);               \
    } while (0)
```

`_Py_Dealloc` calls `op->ob_type->tp_dealloc(op)`, which for most objects frees the memory via `PyObject_Free` after calling any finalizer.

In debug builds (`Py_REF_DEBUG`), CPython also maintains a global refcount total (`_Py_RefTotal`) to detect leaks at interpreter shutdown.
