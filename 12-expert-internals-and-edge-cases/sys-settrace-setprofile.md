# sys.settrace and sys.setprofile: How Debuggers and Coverage Tools Work

## Concept

Python provides two hooks that allow arbitrary code to be called as the interpreter executes Python code. These are the foundation for debuggers (`pdb`), coverage tools (`coverage.py`), profilers, and tracing frameworks.

### `sys.settrace` — Per-Line Execution Hook

`sys.settrace(tracefunc)` installs a trace function called for every:
- `call` event — function is called
- `line` event — interpreter is about to execute a line
- `return` event — function is about to return
- `exception` event — an exception has occurred

```python
import sys

call_count = {}
line_count = {}

def tracer(frame, event, arg):
    """Called for every call/line/return/exception event."""
    code = frame.f_code
    func_name = code.co_name
    filename = code.co_filename
    lineno = frame.f_lineno

    if event == 'call':
        call_count[func_name] = call_count.get(func_name, 0) + 1
        return tracer  # MUST return a trace function to trace inside this function
                       # Return None to stop tracing inside this function

    elif event == 'line':
        key = (filename, lineno)
        line_count[key] = line_count.get(key, 0) + 1
        return tracer

    elif event == 'return':
        pass  # arg is the return value

    elif event == 'exception':
        exc_type, exc_value, exc_traceback = arg

    return tracer

def target_function():
    x = 1
    y = x + 1
    return y

sys.settrace(tracer)
result = target_function()
sys.settrace(None)  # disable tracing

print("Function calls:", call_count)
print("Lines executed:", line_count)
```

**Critical:** The trace function for the `call` event must return a callable to trace INSIDE that function. Returning `None` means that specific function call won't be traced (optimization).

### `sys.setprofile` — Call/Return Hook (Profiling)

`sys.setprofile(profilefunc)` is similar but only fires on:
- `call` — function called
- `return` — function returning
- `c_call` — C function about to be called
- `c_return` — C function returning
- `c_exception` — C function raised an exception

Does NOT fire for `line` events — much lower overhead than `settrace`.

```python
import sys
import time

_call_times = {}
_call_stack = []

def profiler(frame, event, arg):
    func_name = f"{frame.f_code.co_filename}:{frame.f_code.co_name}"

    if event == 'call':
        _call_stack.append((func_name, time.perf_counter_ns()))

    elif event == 'return':
        if _call_stack and _call_stack[-1][0] == func_name:
            name, start = _call_stack.pop()
            elapsed = time.perf_counter_ns() - start
            _call_times[name] = _call_times.get(name, 0) + elapsed

sys.setprofile(profiler)
# ... code to profile ...
sys.setprofile(None)

for func, ns in sorted(_call_times.items(), key=lambda x: -x[1])[:10]:
    print(f"{func}: {ns/1e6:.2f}ms")
```

### How `coverage.py` Works

`coverage.py` uses `sys.settrace` to track which lines are executed:

```python
import sys

class CoverageCollector:
    def __init__(self):
        self.executed_lines = {}  # {filename: {lineno, ...}}

    def trace(self, frame, event, arg):
        if event == 'line':
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            if filename not in self.executed_lines:
                self.executed_lines[filename] = set()
            self.executed_lines[filename].add(lineno)
        return self.trace  # return self to continue tracing

    def start(self):
        sys.settrace(self.trace)

    def stop(self):
        sys.settrace(None)
        # Also need to reset per-thread: threading.settrace(None)

collector = CoverageCollector()
collector.start()

# Code under measurement:
def add(a, b):
    return a + b  # this line gets marked as covered when called

result = add(1, 2)

collector.stop()
print(collector.executed_lines)
```

**Why `coverage.py` is slow:** The `line` event fires for EVERY line executed. For tight loops, this is called millions of times. `coverage.py` adds ~3-10x overhead to well-optimized code.

### How `pdb` Works

`pdb` (Python Debugger) uses `sys.settrace` to pause execution at breakpoints:

```python
import sys

class SimpleDebugger:
    def __init__(self):
        self.breakpoints = set()

    def set_breakpoint(self, filename, lineno):
        self.breakpoints.add((filename, lineno))

    def trace(self, frame, event, arg):
        if event == 'line':
            key = (frame.f_code.co_filename, frame.f_lineno)
            if key in self.breakpoints:
                self.pause(frame)
        return self.trace

    def pause(self, frame):
        print(f"\nBreakpoint hit at {frame.f_code.co_filename}:{frame.f_lineno}")
        print(f"Locals: {frame.f_locals}")
        cmd = input("(n)ext, (c)ontinue, (q)uit: ")
        if cmd == 'q':
            sys.settrace(None)

    def run(self, code_str):
        sys.settrace(self.trace)
        exec(code_str)
        sys.settrace(None)
```

`pdb.set_trace()` calls `sys.settrace` and then raises an exception that the trace function catches to pause at the current line. Newer Python (`breakpoint()` built-in, Python 3.7+) calls `sys.breakpointhook()` which defaults to `pdb.set_trace()` but can be overridden.

### Thread-Local Tracing

Each thread has its own trace function. `sys.settrace` only sets it for the calling thread. To trace all threads:

```python
import sys
import threading

def trace_func(frame, event, arg):
    ...

sys.settrace(trace_func)         # current thread
threading.settrace(trace_func)   # future threads
```

`sys.gettrace()` returns the current thread's trace function.

### Python 3.12 `sys.monitoring` — The Modern API

Python 3.12 added `sys.monitoring` (PEP 669) as a more efficient replacement for `sys.settrace`:

```python
import sys

TOOL_ID = 1  # your tool's ID (1-5 for user tools)

def line_handler(code, line_number):
    print(f"Line {line_number} in {code.co_name}")

sys.monitoring.use_tool_id(TOOL_ID, "my_tracer")
sys.monitoring.register_callback(TOOL_ID, sys.monitoring.events.LINE, line_handler)
sys.monitoring.set_events(TOOL_ID, sys.monitoring.events.LINE)

def my_function():
    x = 1
    y = x + 1
    return y

my_function()  # triggers line_handler for each line

sys.monitoring.set_events(TOOL_ID, 0)  # disable
sys.monitoring.free_tool_id(TOOL_ID)
```

`sys.monitoring` is significantly faster than `sys.settrace` because:
1. It uses specialized bytecode (`INSTRUMENTED_*` opcodes) instead of checking a hook at every opcode.
2. Events can be selectively enabled per-code-object.
3. No per-event Python function call overhead when events are disabled.

---

## Interview Questions

### Q1: How does `sys.settrace` impose overhead, and why does `coverage.py` slow down code so much?

**Model answer:**  
`sys.settrace` installs a per-thread trace function that the bytecode evaluator calls at every `line`, `call`, and `return` event. For `line` events:

1. At every `LINE` bytecode (`RESUME` in 3.11+), the evaluator checks if a trace function is set.
2. If yes, it calls it — a full Python function call with frame object creation.
3. The trace function executes its Python body.
4. Control returns to the evaluator.

This overhead applies to every single line of Python code. For a tight loop running 10M iterations, that's 10M Python function calls just for coverage tracking. Coverage.py adds:
- ~3x overhead for I/O-bound code (I/O dominates, trace overhead amortizes)
- ~5-10x overhead for CPU-bound pure Python (every line tracked)

**Why line events are so expensive:** The frame object must be fully initialized (or at least partially), and each trace call must navigate the Python/C boundary.

**Coverage.py's optimizations:**
- Uses C extension (`_coverage_tracer`) for the trace function instead of Python.
- Skips files matching excludes.
- In Python 3.12+, uses `sys.monitoring` instead of `sys.settrace` for much lower overhead.

### Q2: Implement a minimal function call logger using `sys.settrace`.

**Model answer:**  
```python
import sys
from contextlib import contextmanager

class CallLogger:
    def __init__(self):
        self.calls = []
        self._depth = 0

    def trace(self, frame, event, arg):
        code = frame.f_code
        name = f"{code.co_filename}:{code.co_name}"

        if event == 'call':
            self._depth += 1
            self.calls.append({
                'type': 'call',
                'depth': self._depth,
                'function': name,
                'line': frame.f_lineno,
                'args': frame.f_locals.copy()  # snapshot locals at call time
            })
            return self.trace  # continue tracing inside this function

        elif event == 'return':
            self.calls.append({
                'type': 'return',
                'depth': self._depth,
                'function': name,
                'value': repr(arg)[:50]  # truncate large return values
            })
            self._depth -= 1

        return self.trace

@contextmanager
def trace_calls():
    logger = CallLogger()
    sys.settrace(logger.trace)
    try:
        yield logger
    finally:
        sys.settrace(None)

def add(a, b):
    return a + b

def compute():
    return add(1, 2) + add(3, 4)

with trace_calls() as logger:
    result = compute()

for call in logger.calls:
    indent = "  " * call['depth']
    print(f"{indent}{call['type']}: {call['function']}")
```

### Q3: What's the difference between `sys.settrace` and `sys.setprofile`? When would you use each?

**Model answer:**  

| | `sys.settrace` | `sys.setprofile` |
|-|----------------|-----------------|
| Events | call, line, return, exception | call, return, c_call, c_return, c_exception |
| Overhead | High (every line) | Low (only call/return) |
| C extensions | Only Python-level | Also C functions |
| Use cases | Debuggers, coverage | Profilers |

**Use `sys.settrace` when:** You need per-line granularity — debugging (need to know WHAT line was executed), coverage analysis (which lines ran), or step-through debuggers.

**Use `sys.setprofile` when:** You only need call/return information — profiling function call counts and durations. Much lower overhead. Can also detect C extension calls (C functions are opaque to `settrace`).

For production-grade profilers: use neither (both are too slow). Use `py-spy` (sampling via OS signals, no Python-level hooks) or `sys.monitoring` (Python 3.12+ specialized opcodes with much lower overhead).

### Q4: How does `breakpoint()` work and how do you override it?

**Model answer:**  
`breakpoint()` (Python 3.7+) calls `sys.breakpointhook()`. By default, this is `pdb.set_trace()`. It's overridable:

```python
import sys

def my_debugger(*args, **kwargs):
    """Custom breakpoint hook."""
    import ipdb  # IPython debugger
    ipdb.set_trace()

sys.breakpointhook = my_debugger

# Or via environment variable (affects all Python processes):
# PYTHONBREAKPOINT=ipdb.set_trace

# Disable breakpoints entirely:
# PYTHONBREAKPOINT=0
```

This allows teams to configure their preferred debugger without changing code. CI/CD pipelines can set `PYTHONBREAKPOINT=0` to prevent any `breakpoint()` calls in production from dropping into a debugger.

`pdb.set_trace()` implementation:
1. Gets the caller's frame via `sys._getframe(1)`.
2. Creates a `Pdb` instance.
3. Calls `pdb.set_trace(frame)` which calls `sys.settrace(pdb.trace_dispatch)`.
4. `pdb.trace_dispatch` intercepts `line` events and handles the debugger REPL.

### Q5: What is `sys.monitoring` and how does it improve on `sys.settrace`?

**Model answer:**  
`sys.monitoring` (PEP 669, Python 3.12) replaces `sys.settrace` for tools. Key improvements:

1. **Specialized bytecodes:** When monitoring is enabled for an event type, the JIT/interpreter patches bytecode with `INSTRUMENTED_*` variants (e.g., `INSTRUMENTED_LINE` instead of `RESUME`). When disabled, original bytecodes are restored. No overhead when not monitoring.

2. **Per-code-object events:** Enable line monitoring only for specific files/functions, not globally.

3. **Multiple tools:** Up to 6 tools can be active simultaneously (e.g., coverage + debugger + profiler), each with its own event set.

4. **No call overhead for disabled events:** `sys.settrace` with `None` trace returned from `call` still pays the cost of checking the trace function. `sys.monitoring` truly eliminates overhead for disabled events via bytecode patching.

```python
import sys

sys.monitoring.use_tool_id(1, "line_tracer")
sys.monitoring.register_callback(
    1,
    sys.monitoring.events.LINE,
    lambda code, lineno: print(f"Line {lineno}")
)
# Enable only for specific code object:
import types
code = my_function.__code__
sys.monitoring.set_local_events(1, code, sys.monitoring.events.LINE)
```

---

## Gotcha Follow-ups

**"Can `sys.settrace` trace C extension code?"**  
Only at the call/return boundary. `sys.settrace`'s `c_call` and `c_return` events track entry/exit of C functions. But inside a C function, there are no `line` events — C code runs without Python frame overhead. `sys.setprofile` explicitly adds `c_call`/`c_return`/`c_exception` events for this reason.

**"What happens if a trace function itself raises an exception?"**  
The exception from the trace function is silently swallowed and tracing is disabled. This is intentional — a buggy tracer shouldn't crash the traced program. `sys.gettrace()` will return `None` after this happens. This makes debugger errors extremely confusing to diagnose; trace functions should catch all exceptions internally.

---

## Under the Hood

`sys.settrace` stores the trace function in `_Py_TraceFunc` and `_Py_ProfileFunc` on the thread state (`PyThreadState`). The evaluator loop checks `tstate->c_tracefunc` at each `RESUME` (or `LINE` event position). In Python 3.12+, `sys.monitoring` patches bytecode in-place (the `co_code` bytes of the code object are modified to use `INSTRUMENTED_*` variants). This patching is done per-code-object and is atomic with respect to the GIL (or uses per-object locks in free-threaded builds).
