# Function Calls: Frame Objects and Stack Frames

## Concept

Every function call in CPython creates a `PyFrameObject` — a data structure holding the local variables, value stack, bytecode pointer, and enclosing scope information. Understanding frame objects explains the call stack, how introspection works, and why Python function calls are relatively expensive compared to C.

### Frame Objects

```python
import sys
import inspect

def inner(x):
    # Access the current frame:
    frame = sys._getframe()                # current frame
    caller_frame = sys._getframe(1)        # caller's frame

    print(f"Current function: {frame.f_code.co_name}")   # 'inner'
    print(f"Caller function: {caller_frame.f_code.co_name}")

    print(f"Local variables: {frame.f_locals}")    # {'x': 42}
    print(f"File: {frame.f_code.co_filename}")
    print(f"Line: {frame.f_lineno}")

    # Walk the call stack:
    frame_iter = frame
    while frame_iter:
        print(f"  {frame_iter.f_code.co_name}:{frame_iter.f_lineno}")
        frame_iter = frame_iter.f_back   # parent frame

def outer():
    inner(42)

outer()

# Modern API:
for frame_info in inspect.stack():
    print(f"{frame_info.function}:{frame_info.lineno} in {frame_info.filename}")
```

### Frame Object Attributes

```python
import sys

def demo(a, b, c=3, *args, **kwargs):
    frame = sys._getframe()

    print(frame.f_code)          # code object
    print(frame.f_locals)        # dict of local vars (snapshot)
    print(frame.f_globals)       # module globals dict (live reference)
    print(frame.f_builtins)      # builtins dict
    print(frame.f_back)          # parent frame
    print(frame.f_lineno)        # current line number
    print(frame.f_lasti)         # index of last bytecode instruction

    # f_locals is a SNAPSHOT — writing to it doesn't change actual locals
    # (for optimized functions with LOAD_FAST — locals live in C arrays)
    frame.f_locals['a'] = 999    # has no effect in optimized frames!
    print(a)   # still original value

    # ctypes can force-write local variables (CPython internals hack):
    import ctypes
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(0))

demo(1, 2)
```

### Call Stack Introspection

```python
import traceback
import sys

def a():
    b()

def b():
    c()

def c():
    # Full traceback as string:
    tb = ''.join(traceback.format_stack())

    # As structured data:
    for frame, lineno in traceback.walk_stack(None):
        print(f"{frame.f_code.co_name}:{lineno}")

    # Extract call chain:
    chain = []
    frame = sys._getframe()
    while frame:
        chain.append((frame.f_code.co_name, frame.f_lineno))
        frame = frame.f_back
    return chain

a()
```

### Frame Object Lifecycle and Memory

```python
import gc
import sys

def memory_demo():
    frame = sys._getframe()
    ref_count = sys.getrefcount(frame)
    print(f"Frame refcount: {ref_count}")   # at least 2 (frame var + getrefcount arg)

    # Frames are reference-counted:
    # - The running thread holds a reference to the current frame
    # - f_back chains hold references (child → parent)
    # - Tracing/debugging tools may hold additional references

# Reference cycles via frames:
def cycle_demo():
    frame = sys._getframe()
    d = {'frame': frame}   # dict holds frame; frame.f_locals holds dict
    # frame → f_locals → d → frame — reference cycle!
    # CPython's cyclic GC handles this

# Python 3.11+: frames are allocated on the C stack (not heap) for common cases:
# - "inline frames" for simple function calls
# - Heap allocation only when frame is retained (debugging, tracing)
```

### Argument Passing: Positional, Keyword, *args, **kwargs

```python
import dis

def f(a, b, c=3, *args, d=10, **kwargs):
    pass

# See how call sites compile:
def caller():
    f(1, 2, c=4, *[5, 6], d=20, **{'extra': 7})

dis.dis(caller)
# LOAD_GLOBAL   f
# BUILD_LIST    [5, 6] → CALL_INTRINSIC_1 (list_to_tuple)
# Various LOAD_CONSTs, BUILD_MAP, etc.
# CALL_FUNCTION_EX  (with extra args + kwargs)

# Python 3.11+ calling conventions:
# CALL replaces CALL_FUNCTION, CALL_FUNCTION_KW, CALL_METHOD
# KW_NAMES: for keyword-only calls — pre-packaged keyword names tuple

# inspect.signature: introspect function signature at runtime
import inspect

sig = inspect.signature(f)
for name, param in sig.parameters.items():
    print(f"{name}: kind={param.kind.name}, default={param.default}")
```

### `inspect.currentframe()` vs `sys._getframe()`

```python
import inspect, sys

def compare():
    f1 = inspect.currentframe()   # high-level, None if no C stack support
    f2 = sys._getframe()          # low-level, CPython-specific

    # Both return the same frame object:
    print(f1 is f2)   # True

    # inspect.currentframe() is more portable (returns None in Jython)
    # sys._getframe(n) takes a depth argument — skips n levels up

    # Preferred for production: inspect.stack() with limit:
    for fi in inspect.stack(context=1):
        print(fi.function)   # context=1: only 1 source line per frame (faster)

compare()
```

---

## Interview Questions

### Q1: What is a frame object and what does it contain?

**Model answer:**
A `PyFrameObject` (exposed as `frame` in Python) is the runtime execution context for a single function call. It's created when a function is called and destroyed (or GC'd) when the function returns.

Contents:
- `f_code`: the `code` object being executed
- `f_locals`: dict of local variables (snapshot for optimized frames)
- `f_globals`: module's global namespace dict
- `f_builtins`: builtins namespace
- `f_back`: the calling frame (parent)
- `f_lineno`: current source line being executed
- `f_lasti`: last bytecode instruction index
- Value stack: array of `PyObject*` for intermediate computation results

In Python 3.11+: frames can be "lightweight" — allocated on the C eval loop stack instead of the heap, making function calls significantly cheaper. The frame is only promoted to a heap-allocated object when `sys._getframe()`, `inspect.currentframe()`, or a tracer captures it.

### Q2: Why is `frame.f_locals` a snapshot rather than a live view of locals?

**Model answer:**
For optimized functions (those with `CO_OPTIMIZED` flag, i.e., most functions), local variables are stored in a C array (`localsplus` in `PyFrameObject`) indexed by position — this is what `LOAD_FAST`/`STORE_FAST` use. There's no Python dict.

`frame.f_locals` is computed on demand by `PyFrame_FastToLocalsWithError()` which copies the C array values into a dict snapshot. Writing to this dict doesn't update the C array — changes are lost.

```python
import sys, ctypes

def demonstrate():
    x = 1
    frame = sys._getframe()

    frame.f_locals['x'] = 999   # modifies the dict snapshot, not the C array
    print(x)   # still 1!

    # Force the dict back into the C array (CPython internal hack):
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(0))
    print(x)   # 999 — now updated

# This is why debuggers (pdb) can't easily modify local variables mid-execution.
# The `locals()` built-in has the same limitation.
```

### Q3: How do Python function calls differ in cost from C function calls?

**Model answer:**
A C function call: push arguments on the stack, jump to the function's address — a few nanoseconds.

A CPython function call:
1. Look up the function object (LOAD_GLOBAL or LOAD_FAST)
2. Push arguments onto the value stack
3. Allocate a `PyFrameObject` (heap allocation — Python 3.10 and earlier, often on heap in 3.11+)
4. Set up `f_locals`, `f_globals`, `f_back`
5. Set up the value stack for the new frame
6. Enter the eval loop for the new frame
7. On return: restore the parent frame, decrement refcounts

Total overhead: ~100-1000ns per call (vs ~1ns for a C call). This is why tight Python loops with many small function calls can be slow, and why `list(map(fn, data))` can be faster than an explicit `for` loop (reduces Python-level function calls for simple transforms).

```python
import timeit

def identity(x):
    return x

# Function call overhead:
t = timeit.timeit(lambda: identity(42), number=1_000_000)
print(f"Python call: {t:.3f}s / 1M calls = {t*1000:.1f}ms/1M")

# vs no call:
x = 42
t = timeit.timeit(lambda: x + 0, number=1_000_000)
print(f"No call:     {t:.3f}s / 1M calls = {t*1000:.1f}ms/1M")
```

Python 3.11 reduced function call overhead by ~15-20% via specialized call opcodes and frame inlining.

### Q4: How does `inspect.stack()` work and what are the performance implications?

**Model answer:**
`inspect.stack()` calls `sys._getframe()` to get the current frame, then walks `frame.f_back` up to the top of the call stack, collecting `FrameInfo` named tuples.

For each frame, it reads source lines (by calling `linecache.getlines(filename, module_globals)` — which may read from disk or cache). Each frame object accessed by Python code is kept alive as long as the reference exists.

Performance implications:
- **`inspect.stack()` is slow:** it may read source files from disk and processes every frame on the stack.
- **Avoid in hot paths:** never call in a tight loop or critical performance path.
- **Stack depth matters:** `inspect.stack()` walks the ENTIRE stack — a deep recursion stack is expensive to inspect.
- **`context=0` or `context=1`:** use to limit source line reading.

```python
import inspect, timeit

def shallow():
    return inspect.stack(context=0)   # 0 source lines = fastest

def deep():
    return inspect.stack(context=3)   # 3 source lines per frame = slow

# Profiling:
t1 = timeit.timeit(shallow, number=1000)
t2 = timeit.timeit(deep, number=1000)
print(f"context=0: {t1:.3f}s")
print(f"context=3: {t2:.3f}s")
```

### Q5: What's the difference between `f_locals`, `locals()`, and `vars()`?

**Model answer:**
All three give access to a namespace dict, but with subtle differences:

```python
def demo():
    x = 1
    y = 2

    # locals(): built-in, returns a COPY of f_locals snapshot
    l = locals()
    l['z'] = 99    # modifying l does NOT affect actual locals
    print('z' in dir())   # False — z was never a real local

    # frame.f_locals: same snapshot as locals() in the same frame
    import sys
    frame = sys._getframe()
    print(frame.f_locals is locals())   # may be True or False depending on Python version

    # vars(): with no argument, same as locals()
    print(vars() == locals())   # True

# At module level:
x = 1
print(locals() is globals())   # True! At module level, locals = globals
print(vars() is globals())     # True

# vars(obj): returns obj.__dict__
class C:
    def __init__(self):
        self.a = 1
        self.b = 2

c = C()
print(vars(c))           # {'a': 1, 'b': 2} — same as c.__dict__
vars(c)['c'] = 3        # DOES work — modifies __dict__ directly
print(c.c)               # 3 — unlike f_locals, __dict__ is the real store
```

At module or class scope, `locals()` returns the actual namespace dict (live). In a function body, it returns a snapshot (dead copy). This inconsistency is a known Python wart.

---

## Gotcha Follow-ups

**"Does holding a reference to `frame.f_back` cause memory leaks?"**
Yes — frame objects form a reference chain. If you store a frame reference (e.g., in a traceback or exception), the entire call stack up to that point stays in memory. Exception objects attached to locals create a well-known reference cycle: `except Exception as e:` creates `e.__traceback__` which holds the frame, which holds `f_locals`, which may hold the exception itself. Python 3 clears `e` after the `except` block to break this cycle, but you should also `del e` or `e = None` in long-lived exception handling code.

**"Can you modify a running frame's local variables from a debugger?"**
pdb and other debuggers use `sys.settrace` to intercept execution, then modify `frame.f_locals` and call `PyFrame_LocalsToFast()` via ctypes to actually update the C-level local array. This works but is fragile — the specialized adaptive interpreter (Python 3.11+) can specialize LOAD_FAST to not even consult the locals array in some cases.

---

## Under the Hood

`PyFrameObject` (`Include/cpython/frameobject.h`) in Python 3.11+ is split: `_PyInterpreterFrame` (the "inline frame" — lives on the C stack for common cases) and `PyFrameObject` (the "Python frame" — heap-allocated, created lazily when accessed from Python). The eval loop (`Python/ceval.c: _PyEval_EvalFrameDefault()`) manipulates `_PyInterpreterFrame` directly via pointer arithmetic. `sys._getframe()` materializes a `PyFrameObject` from the `_PyInterpreterFrame`. Local variable storage is in `frame->localsplus` — a C array of `PyObject*` pointers (NULL for uninitialized). `LOAD_FAST` is: `owner = frame->localsplus[oparg]; if (owner == NULL) goto unbound_local_error;`.
