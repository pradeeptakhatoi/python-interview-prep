# sys.settrace and sys.setprofile: How Debuggers and Coverage Tools Work

## Concept

`sys.settrace` and `sys.setprofile` are the hooks that make Python's debugger (pdb), coverage tool (coverage.py), and profilers (cProfile) work. They install callback functions that CPython calls at specific execution events. Understanding them is essential for building observability tools and understanding their performance impact.

### `sys.settrace` — Line-Level Tracing

```python
import sys

def my_trace(frame, event, arg):
    """
    Called at every:
    - 'call'    : function entry (arg=None)
    - 'line'    : before each line executes (arg=None)
    - 'return'  : function exit (arg=return value)
    - 'exception': unhandled exception (arg=(exc_type, exc_value, traceback))
    """
    code = frame.f_code
    filename = code.co_filename
    lineno = frame.f_lineno
    funcname = code.co_name

    print(f"[{event:10s}] {funcname}:{lineno}")

    # Return the trace function for line/return events in THIS frame.
    # Return None to stop tracing this frame.
    return my_trace

sys.settrace(my_trace)

def sample():
    x = 1      # 'line' event
    y = x + 1  # 'line' event
    return y   # 'line' + 'return' events

sample()
sys.settrace(None)   # remove tracing
```

### Per-Frame Trace Function

```python
import sys

def outer_trace(frame, event, arg):
    """Trace function for module level / outer calls."""
    if event == 'call':
        funcname = frame.f_code.co_name
        if funcname == 'interesting_function':
            # Install a per-frame tracer for THIS function only:
            return inner_trace
    return None   # don't trace other functions

def inner_trace(frame, event, arg):
    """Trace function installed for interesting_function's frame."""
    if event == 'line':
        print(f"  executing line {frame.f_lineno}")
    elif event == 'return':
        print(f"  returning: {arg}")
    return inner_trace   # keep tracing this frame

sys.settrace(outer_trace)

def boring():
    x = 1   # not traced

def interesting_function():
    a = 1   # traced: "executing line N"
    b = 2   # traced
    return a + b   # traced: "returning: 3"

boring()
interesting_function()

sys.settrace(None)
```

### Building a Simple Code Coverage Tool

```python
import sys
from collections import defaultdict

class CoverageTracer:
    """Tracks which lines of which files are executed."""

    def __init__(self):
        self.covered: dict[str, set[int]] = defaultdict(set)

    def trace_calls(self, frame, event, arg):
        if event == 'call':
            return self.trace_lines   # install line tracer for this frame
        return None

    def trace_lines(self, frame, event, arg):
        if event == 'line':
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            self.covered[filename].add(lineno)
        return self.trace_lines

    def __enter__(self):
        sys.settrace(self.trace_calls)
        return self

    def __exit__(self, *args):
        sys.settrace(None)

    def report(self) -> dict[str, float]:
        """Coverage percentage per file."""
        # Real coverage.py also tracks which lines are executable (via ast/compile)
        return {
            filename: len(lines)
            for filename, lines in self.covered.items()
        }

with CoverageTracer() as tracer:
    def example():
        x = 1
        if x > 0:
            return "positive"
        return "non-positive"   # never executed

    example()

print(tracer.report())
```

### `sys.setprofile` — Function-Level Profiling

```python
import sys
import time
from collections import defaultdict

def my_profile(frame, event, arg):
    """
    Called at:
    - 'call'     : Python function entry
    - 'return'   : Python function exit
    - 'c_call'   : C function entry (arg=C function object)
    - 'c_return' : C function exit
    - 'c_exception': C function raised exception
    
    NOTE: 'line' events are NOT fired for sys.setprofile.
    """
    funcname = frame.f_code.co_name
    print(f"[{event:12}] {funcname}")

sys.setprofile(my_profile)

def a():
    len([1, 2, 3])   # c_call / c_return for len()
    return 1

a()
sys.setprofile(None)

# Output:
# [call        ] a
# [c_call      ] a    (arg=<built-in function len>)
# [c_return    ] a
# [return      ] a
```

### Building a Simple Call Profiler

```python
import sys
import time
from collections import defaultdict
from contextlib import contextmanager

class SimpleProfiler:
    def __init__(self):
        self._call_counts: dict[str, int] = defaultdict(int)
        self._total_time: dict[str, float] = defaultdict(float)
        self._call_stack: list[tuple[str, float]] = []

    def profile(self, frame, event, arg):
        if event in ('call', 'c_call'):
            name = (frame.f_code.co_qualname if event == 'call'
                    else getattr(arg, '__name__', str(arg)))
            self._call_stack.append((name, time.perf_counter()))

        elif event in ('return', 'c_return', 'c_exception'):
            if self._call_stack:
                name, start = self._call_stack.pop()
                elapsed = time.perf_counter() - start
                self._call_counts[name] += 1
                self._total_time[name] += elapsed

    @contextmanager
    def __call__(self):
        sys.setprofile(self.profile)
        try:
            yield self
        finally:
            sys.setprofile(None)

    def report(self, top_n: int = 10):
        sorted_by_time = sorted(
            self._total_time.items(), key=lambda kv: kv[1], reverse=True
        )
        print(f"{'Function':<40} {'Calls':>8} {'Total(s)':>10}")
        print("-" * 60)
        for name, total in sorted_by_time[:top_n]:
            calls = self._call_counts[name]
            print(f"{name:<40} {calls:>8} {total:>10.4f}")

profiler = SimpleProfiler()
with profiler():
    import json
    data = [{"key": i, "value": i * 2} for i in range(1000)]
    json.dumps(data)

profiler.report()
```

### Performance Impact of Tracing

```python
import sys, timeit

def work():
    total = 0
    for i in range(1000):
        total += i
    return total

# Baseline (no tracing):
t_baseline = timeit.timeit(work, number=100)

# With settrace:
def noop_trace(frame, event, arg):
    return noop_trace

sys.settrace(noop_trace)
t_traced = timeit.timeit(work, number=100)
sys.settrace(None)

print(f"No trace:  {t_baseline:.3f}s")
print(f"Traced:    {t_traced:.3f}s")
print(f"Overhead:  {t_traced / t_baseline:.1f}x")
# Typically 3-10x slower with settrace (per-line callback overhead)

# sys.setprofile is cheaper (~2x overhead) — only fires on call/return
# py-spy (sampling profiler) has <1% overhead — no callbacks, reads from memory
```

---

## Interview Questions

### Q1: How does `coverage.py` use `sys.settrace` to track which lines are executed?

**Model answer:**
`coverage.py` installs a trace function via `sys.settrace`. On `call` events, it installs a per-frame line tracer. On `line` events, it records `(filename, lineno)` in a dictionary.

Key implementation details:
1. **Compile-time line analysis:** `coverage.py` also compiles the source and uses the `dis` module to identify which lines are "executable" (have bytecode). This separates blank lines, comments, and pass-only blocks from lines that can be "missed."
2. **Branch coverage:** tracks `(from_lineno, to_lineno)` pairs for conditional jumps by detecting `JUMP_*` opcodes via the `.pyc` line table.
3. **`.coverage` data file:** records coverage data in an SQLite database.
4. **C extension integration:** `coverage.py` uses a C extension (`_coverage.c`) for the actual trace hook to minimize per-line overhead.

```python
# Simplified coverage.py trace:
class CoverageHook:
    def __init__(self):
        self.lines = defaultdict(set)

    def __call__(self, frame, event, arg):
        if event == 'call':
            return self  # trace this frame
        if event == 'line':
            self.lines[frame.f_code.co_filename].add(frame.f_lineno)
        return self

hook = CoverageHook()
sys.settrace(hook)
# ... run code ...
sys.settrace(None)
```

### Q2: How does pdb (the Python debugger) use `sys.settrace` to implement breakpoints and stepping?

**Model answer:**
pdb installs a trace function and uses it to:
- **Breakpoints:** record `(filename, lineno)` pairs. On `line` events, check if the current `(filename, lineno)` is in the breakpoint set; if so, pause and enter interactive mode.
- **Stepping (n/s):** on `return` from the current function or on the next `line` event in the current frame, pause.
- **Step-into (s):** on the next `call` event, pause.
- **Continue (c):** resume without pausing until the next breakpoint.

```python
import sys
import bdb   # base debugger class

# pdb inherits from bdb.Bdb which manages the settrace hook:
class SimplePdb(bdb.Bdb):
    def user_line(self, frame):
        """Called on each line when we should pause."""
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        print(f"Stopped at {filename}:{lineno}")
        cmd = input("(debug) > ")
        if cmd == 'p':
            print(eval(input("Eval: "), frame.f_globals, frame.f_locals))
        # real pdb has a full command parser here

# The key trace function (simplified from bdb):
def bdb_trace(frame, event, arg):
    if event == 'line':
        if is_breakpoint(frame.f_code.co_filename, frame.f_lineno):
            pause_execution(frame)   # drop into interactive mode
    return bdb_trace
```

### Q3: What's the performance difference between `sys.settrace` and `sys.setprofile`, and why does py-spy not use either?

**Model answer:**

| | `sys.settrace` | `sys.setprofile` | py-spy |
|-|---------------|-----------------|--------|
| Fires on | every line | call/return only | never (sampling) |
| Overhead | 3-10x slowdown | ~2x slowdown | <1% |
| Accuracy | 100% (deterministic) | 100% (deterministic) | statistical |
| Production-safe | No | Borderline | Yes |

`sys.settrace` fires on EVERY line, making it expensive — each callback invocation involves Python object creation, dict lookups, and the Python function call overhead. For a function with 100 lines called 1000 times, that's 100,000 trace callbacks.

`sys.setprofile` only fires on function entry/exit — cheaper, but no line-level information.

**py-spy** is a sampling profiler: it reads the target Python process's memory via OS APIs (`ptrace` on Linux, `task_for_pid` on macOS). At configurable intervals (~200Hz), it reads `PyThreadState->frame` to find the current frame stack — without ANY cooperation from the Python interpreter. No callback overhead, no modified Python code, no `sys.settrace`. The trade-off: it misses fast functions (called and returned between two sample points) and has ~0.5% statistical error.

### Q4: Can you use `sys.settrace` to modify the behavior of running code?

**Model answer:**
Yes — with care. The trace function can modify `frame.f_locals` (then force it back to the C array via `ctypes`), raise exceptions at arbitrary points, or redirect execution by modifying `frame.f_lineno` (pdb uses this for jump/next commands):

```python
import sys, ctypes

def mutating_trace(frame, event, arg):
    if event == 'line' and frame.f_code.co_name == 'target':
        # Modify a local variable mid-execution:
        frame.f_locals['x'] = 99
        ctypes.pythonapi.PyFrame_LocalsToFast(
            ctypes.py_object(frame), ctypes.c_int(0)
        )
    return mutating_trace

sys.settrace(mutating_trace)

def target():
    x = 1      # x will be set to 99 by tracer before x+1 executes
    return x + 1

print(target())   # 100, not 2!

sys.settrace(None)
```

This is how debuggers implement variable modification mid-execution. The `frame.f_lineno` trick is used for `jump` in pdb:

```python
# In pdb's 'jump' command:
frame.f_lineno = target_line   # redirect execution to a different line
```

### Q5: How does the `@profile` decorator from memory_profiler work compared to `sys.settrace`?

**Model answer:**
`memory_profiler`'s `@profile` uses `sys.settrace` with additional calls to `tracemalloc` (or `/proc/self/status` on Linux) to read memory usage on each line:

```python
# Simplified memory_profiler approach:
import sys, tracemalloc

class MemoryLineProfiler:
    def __init__(self, func):
        self.func = func
        self.line_memory: dict[int, float] = {}

    def trace(self, frame, event, arg):
        if event == 'line' and frame.f_code == self.func.__code__:
            snapshot = tracemalloc.take_snapshot()
            stats = snapshot.statistics('lineno')
            total = sum(s.size for s in stats if s.traceback[0].lineno == frame.f_lineno)
            self.line_memory[frame.f_lineno] = total / 1024 / 1024  # MiB
        return self.trace

    def __call__(self, *args, **kwargs):
        tracemalloc.start()
        old_trace = sys.gettrace()
        sys.settrace(self.trace)
        result = self.func(*args, **kwargs)
        sys.settrace(old_trace)
        tracemalloc.stop()
        return result

@MemoryLineProfiler
def memory_heavy():
    data = [0] * 1_000_000   # large allocation
    result = sum(data)
    del data
    return result

memory_heavy()
```

The real `memory_profiler` reads `/proc/self/status` (Linux) or `psutil` (cross-platform) for RSS (resident set size) — the actual physical memory used, not just Python allocations.

---

## Gotcha Follow-ups

**"Does `sys.settrace` work with C extensions?"**
`sys.settrace` only fires for Python bytecodes. Calls into C extensions trigger `c_call`/`c_return` events in `sys.setprofile`, but NOT `line` events in `sys.settrace`. This is why coverage.py cannot measure coverage inside C extensions and why profilers show C functions as single opaque entries.

**"What happens if the trace function itself raises an exception?"**
The exception is silently ignored and the trace function is disabled (set to `None`). This is intentional — a crashing trace function shouldn't crash the program. To debug a trace function: test it separately, add `try/except` with logging inside, or run with `python -X dev` for more verbose error reporting.

---

## Under the Hood

`sys.settrace` stores the trace function in `PyThreadState->c_tracefunc` (C function pointer) and `PyThreadState->c_traceobj` (the Python callable). The eval loop (`Python/ceval.c`) checks `tstate->c_tracefunc != NULL` and calls it at designated events. In Python 3.12+, the check is via `tstate->tracing` and `tstate->monitoring_version` — a versioned system that allows multiple trace subscribers (PEP 669, `sys.monitoring`). `sys.monitoring` (Python 3.12+) is a more efficient replacement for `sys.settrace` — it allows selective registration for specific events (CALL, LINE, RETURN, EXCEPTION) on specific code objects, reducing overhead for tools that only need a subset of events. `coverage.py` migrated to `sys.monitoring` in recent versions for the performance improvement.
