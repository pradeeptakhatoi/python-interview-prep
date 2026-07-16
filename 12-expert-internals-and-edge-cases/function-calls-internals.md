# Function Calls: Frame Objects and Stack Frames

## Concept

Every Python function call creates a **frame object** (`PyFrameObject`) — a Python-level object that represents one level of the call stack. Understanding frames is essential for comprehending debuggers, profilers, tracebacks, and performance characteristics.

### Frame Objects

```python
import sys
import inspect

def inner():
    frame = sys._getframe()          # current frame
    caller = sys._getframe(1)        # caller's frame
    
    print(f"Current function: {frame.f_code.co_name}")
    print(f"Caller function:  {caller.f_code.co_name}")
    print(f"Current locals:   {frame.f_locals}")
    print(f"Line number:      {frame.f_lineno}")
    print(f"File:             {frame.f_code.co_filename}")

def outer():
    x = 42
    inner()

outer()
# Current function: inner
# Caller function:  outer
# Current locals:   {'frame': ..., 'caller': ...}
# Line number:      ...
```

Frame attributes:
- `f_code` — the code object being executed
- `f_locals` — a dict of local variables (materialized on demand; reading this is expensive)
- `f_globals` — the global namespace dict
- `f_builtins` — the builtins dict
- `f_lineno` — current line number
- `f_back` — the calling frame (linked list of frames = call stack)
- `f_lasti` — index of last bytecode instruction executed

### LOAD_FAST vs LOAD_GLOBAL — Frame-Level Details

```python
import dis

def function_with_locals():
    x = 1         # STORE_FAST — writes to frame->localsplus[0]
    y = x + 1    # LOAD_FAST 0 — reads frame->localsplus[0] (no dict lookup)
    return y

dis.dis(function_with_locals)
# LOAD_FAST is an array index into the frame's locals array — O(1), no hashing
```

The `localsplus` array in a frame is pre-allocated based on `co_nlocals` at compile time. Local variable access is array indexing, not dict lookup. This is why Python functions are faster than expected for local variable access.

**`f_locals` vs `localsplus`:** Reading `frame.f_locals` triggers materialization — CPython copies `localsplus` entries into a dict. Modifying `f_locals` does NOT update the actual locals (localsplus) in running frame. Use `ctypes` or frame-patching to actually change locals at runtime.

### How a Function Call Works (CALL opcode)

```python
import dis

def add(a, b):
    return a + b

def caller():
    return add(1, 2)

dis.dis(caller)
```

Typical output (3.12):
```
RESUME           0
LOAD_GLOBAL      1 (NULL + add)    # loads function object + NULL sentinel
LOAD_CONST       1 (1)
LOAD_CONST       2 (2)
CALL             2                 # 2 positional args
RETURN_VALUE
```

What `CALL` does internally:
1. Pops `n` arguments from the stack.
2. Pops the callable (function object).
3. Checks if it's a Python function (`PyCFunction` vs `PyFunctionObject`).
4. For Python functions: creates a new `PyFrameObject`, sets `f_code`, `f_back`, copies arguments into `localsplus`.
5. Pushes the new frame and enters the eval loop recursively.

### Frame Lifecycle and Python 3.11 Frame Optimization

**Pre-3.11:** Each function call heap-allocated a full `PyFrameObject`. Frequent function calls meant heavy allocator pressure.

**3.11+:** The internal frame representation was split:
- `_PyInterpreterFrame` — a lightweight struct stored on the C stack or in a per-thread frame cache. Not directly accessible as a Python object.
- `PyFrameObject` — the Python-visible frame object. Created lazily only when code accesses `sys._getframe()`, `traceback`, etc.

This change made function calls ~15-20% faster by eliminating the heap allocation for most calls.

```python
# This triggers full frame object creation (slower path):
def with_frame_access():
    f = sys._getframe()   # forces PyFrameObject creation
    return f

# This uses lightweight internal frame only (faster):
def without_frame_access():
    return 42
```

### Generators and Frames

Generators are essentially suspended frames:

```python
def counter(n):
    for i in range(n):
        yield i

gen = counter(3)
print(gen.gi_frame)          # the suspended frame
print(gen.gi_frame.f_locals) # {'n': 3, 'i': 0} after first yield
next(gen)                    # advances frame, updates f_locals
print(gen.gi_frame.f_locals) # {'n': 3, 'i': 1}
```

When a generator yields, `_PyInterpreterFrame` is preserved — the frame is not destroyed, just suspended. `next()` resumes from where `yield` left.

---

## Interview Questions

### Q1: What is `sys._getframe()` and when would you legitimately use it in production code?

**Model answer:**  
`sys._getframe(depth)` returns the frame object `depth` levels up the call stack. The leading underscore signals it's an implementation detail.

**Legitimate production uses:**
1. **Logging with automatic context** — some logging frameworks capture the caller's filename/line:
```python
import sys, logging

def log(msg, level=logging.INFO):
    frame = sys._getframe(1)
    caller_file = frame.f_code.co_filename
    caller_line = frame.f_lineno
    logging.getLogger().log(level, f"[{caller_file}:{caller_line}] {msg}")
```

2. **Dependency injection / auto-wiring** — frameworks inspect the caller's locals to auto-resolve dependencies (Flask-style `g` objects).

3. **Test assertion helpers** — `pytest`'s `assert` rewriting, `unittest.mock.patch` use frame inspection.

**When to avoid:** Anything performance-sensitive. `sys._getframe()` forces frame object creation and is O(depth) to walk. Also, it's fragile across Python implementations (PyPy, Jython may not support it the same way).

### Q2: How does Python implement closures at the frame/cell level?

**Model answer:**  
Closures use **cell objects** — a wrapper around a variable that is shared between the enclosing scope's frame and the inner function's code object.

```python
def outer():
    x = 10  # x is a "cell variable" — stored in a Cell object, not localsplus directly

    def inner():
        return x  # LOAD_DEREF — reads through the cell object

    return inner

import dis
dis.dis(outer)
# MAKE_CELL  0 (x)    — wraps x in a Cell object in outer's frame
# ...
# MAKE_FUNCTION       — creates inner with a reference to the Cell

dis.dis(outer())      # the inner function
# LOAD_DEREF 0 (x)   — dereferences the Cell to get x's value
```

The cell object is the shared reference point. If `outer` modifies `x` after returning `inner` but before `inner` is called, `inner` sees the new value (late binding). The cell ensures that both frames point to the same storage location.

```python
def outer():
    x = 1
    def inner():
        return x
    x = 2     # modifies the cell
    return inner

print(outer()())  # 2 — inner sees the modified cell value
```

### Q3: Why is reading `frame.f_locals` expensive? How do profilers minimize this cost?

**Model answer:**  
`frame.f_locals` is not stored as a dict — locals are in `localsplus`, an array. When you read `f_locals`, CPython calls `PyEval_GetFrameLocals()` which:
1. Allocates a new `dict`.
2. Iterates all `co_varnames` entries.
3. Copies each non-NULL local into the dict.
4. Returns the dict.

This is O(n_locals) per access and always allocates a new dict.

Profilers minimize this by:
1. **Not reading `f_locals` at all** — most profilers only need `f_code`, `f_lineno`, and `f_back`, which are cheap.
2. **Using `sys.setprofile`/`sys.settrace` judiciously** — only hooking on `call`/`return` events, not `line` events.
3. **Sampling instead of tracing** — `py-spy` samples the C-level stack without touching Python frame objects at all.
4. **`ctypes` frame access** — some profilers read `localsplus` directly via ctypes to avoid dict creation.

### Q4: What is `co_stacksize` and why does it matter?

**Model answer:**  
`co_stacksize` is the maximum depth of the value stack that the bytecode needs at any point during execution. It's computed by the compiler's stack depth analyzer and used to pre-allocate the frame's stack space.

```python
def complex():
    return (1 + 2) * (3 + 4)

print(complex.__code__.co_stacksize)  # 3
# Stack needs: push 1, push 2, add (→1), push 3, push 4, add (→1), multiply
# Max depth = 3 items at peak
```

Why it matters:
1. **Memory pre-allocation** — the frame allocates `co_stacksize` slots for the value stack. Overflowing this is prevented by the compiler's analysis.
2. **Safety** — CPython validates that bytecode doesn't overflow `co_stacksize` when loading a `.pyc` file.
3. **Tools** — if you're writing custom bytecode (e.g., in a compiler targeting Python), you must compute `co_stacksize` correctly or the interpreter will raise `SystemError`.

### Q5: How does Python handle tail calls? Does it optimize them?

**Model answer:**  
CPython does **not** optimize tail calls. Every function call, including tail calls, creates a new frame and is pushed onto the call stack. This means recursive Python code can hit `RecursionError` at the default limit of 1000 frames.

```python
import sys
print(sys.getrecursionlimit())  # 1000

def tail_recursive_sum(n, acc=0):
    if n == 0:
        return acc
    return tail_recursive_sum(n - 1, acc + n)  # not optimized

tail_recursive_sum(999)   # OK
tail_recursive_sum(1000)  # RecursionError: maximum recursion depth exceeded
```

Workarounds:
1. **Increase limit:** `sys.setrecursionlimit(10000)` — risky; each frame uses C stack space; OS has limits.
2. **Explicit stack/iteration:** Convert recursion to explicit loop with a stack.
3. **Trampolining:** A technique where recursive functions return thunks (callables) instead of calling directly, and an outer trampoline loop calls them iteratively.

```python
def trampoline(fn, *args):
    result = fn(*args)
    while callable(result):
        result = result()
    return result

def sum_trampoline(n, acc=0):
    if n == 0:
        return acc
    return lambda: sum_trampoline(n - 1, acc + n)  # return thunk

print(trampoline(sum_trampoline, 100_000))  # works; no recursion limit hit
```

---

## Gotcha Follow-ups

**"If I modify `frame.f_locals` inside `sys.settrace`, does the running code see the changes?"**  
No — `f_locals` is a snapshot dict, not live storage. Modifications to it don't affect the actual `localsplus` array. This is a frequent source of confusion when writing debuggers. The `ctypes` hack (`ctypes.pythonapi.PyFrame_LocalsToFast`) can write the dict back into `localsplus`, but it's fragile and implementation-specific. Python 3.13 is adding `FrameLocalsProxy` to make this safer.

**"What's the maximum call stack depth in CPython and what determines it?"**  
`sys.getrecursionlimit()` (default 1000) limits Python frame depth. But the actual limit is the C stack size (OS-determined, typically 8MB). Each Python frame takes C stack space for the eval loop recursion. `sys.setrecursionlimit(10000)` might work or might segfault depending on the frame sizes and OS stack limit. Production code should avoid deep Python recursion entirely.

---

## Under the Hood

`PyFrameObject` (Python-visible) is defined in `Include/cpython/frameobject.h`. The internal `_PyInterpreterFrame` (3.11+) is in `Include/internal/pycore_frame.h`. Key fields:

```c
struct _PyInterpreterFrame {
    PyCodeObject *f_code;
    struct _PyInterpreterFrame *previous;   // f_back equivalent
    PyObject *f_funcobj;
    PyObject *f_globals;
    PyObject *f_builtins;
    PyObject *f_locals;
    PyObject **localsplus;                  // start of locals/stack array
    int f_lasti;
    // ...
};
```

The `localsplus` array holds both locals and the value stack in the same allocation — locals at lower indices, stack growing upward. This was a Python 3.11 optimization; previously they were separate allocations.
