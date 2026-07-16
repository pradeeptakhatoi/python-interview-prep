# Profiling: cProfile, py-spy, Flame Graphs

## Concept

Profiling identifies where time is spent. The choice of profiler depends on the environment: deterministic profiling (cProfile) for development, sampling profiling (py-spy) for production without stopping the process.

### `cProfile` — Deterministic Profiling

```python
import cProfile
import pstats
from io import StringIO

def slow_function():
    return sum(i**2 for i in range(100_000))

# Method 1: context manager
with cProfile.Profile() as pr:
    slow_function()

stats = pstats.Stats(pr, stream=StringIO())
stats.sort_stats('cumulative')
stats.print_stats(20)   # top 20 functions by cumulative time

# Method 2: command line
# python -m cProfile -s cumtime my_script.py

# Method 3: save and analyze later
cProfile.run('slow_function()', '/tmp/profile.out')
# Analysis:
import pstats
p = pstats.Stats('/tmp/profile.out')
p.sort_stats('tottime')   # by time spent in function itself (not children)
p.print_stats(10)
p.print_callers(5)        # who called the expensive functions
p.print_callees(5)        # what each function called
```

**cProfile output columns:**

| Column | Meaning |
|--------|---------|
| `ncalls` | Number of calls |
| `tottime` | Time spent in function only (not sub-calls) |
| `percall` | tottime / ncalls |
| `cumtime` | Total time including sub-calls |
| `percall` | cumtime / ncalls |
| `filename:lineno(function)` | Location |

### `py-spy` — Sampling Profiler (Production-Safe)

```bash
# Install:
pip install py-spy

# Profile a running process by PID (no code changes needed):
py-spy top --pid 12345

# Record a flame graph:
py-spy record -o profile.svg --pid 12345 --duration 30

# Profile a new process:
py-spy record -o profile.svg -- python my_script.py

# Dump current stack traces (like jstack for Java):
py-spy dump --pid 12345
```

py-spy works by reading the process's memory and walking the Python call stack — no interpreter hooks, no performance overhead (< 1% CPU), no code changes. Safe for production.

### Flame Graphs

A flame graph visualizes call stacks over time:
- X-axis: time (wider = more time spent).
- Y-axis: call depth (callers at bottom, callees above).
- Width of each bar: percentage of samples where that function appeared.

```python
# Generate from cProfile with snakeviz:
pip install snakeviz
cProfile.run('main()', 'profile.out')
# snakeviz profile.out  ← opens browser with interactive icicle chart

# Or use pyinstrument for a cleaner text-based summary:
pip install pyinstrument
pyinstrument my_script.py

# In code:
from pyinstrument import Profiler

profiler = Profiler()
with profiler:
    slow_function()

profiler.print()   # human-readable summary
profiler.open_in_browser()   # interactive HTML flame graph
```

### `tracemalloc` — Memory Profiling

```python
import tracemalloc

tracemalloc.start()

# ... run code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
# output: /path/to/file.py:42: size=1024 KiB, count=512, average=2048 B

# Comparing snapshots (finding leaks):
tracemalloc.start()
snapshot1 = tracemalloc.take_snapshot()

run_potentially_leaky_code()

snapshot2 = tracemalloc.take_snapshot()
top_stats = snapshot2.compare_to(snapshot1, 'lineno')
for stat in top_stats[:10]:
    print(stat)
# +500 KiB at file.py:99  ← grew between snapshots
```

### `memory_profiler` — Line-by-Line Memory

```python
from memory_profiler import profile

@profile
def process_large_file(path: str):
    with open(path) as f:
        data = f.read()           # Line 5: +50 MB
    lines = data.split('\n')      # Line 6: +100 MB (another copy)
    del data                      # Line 7: -50 MB
    result = [l.upper() for l in lines]  # Line 8: +100 MB
    return result

# Run: python -m memory_profiler my_script.py
# Output shows MiB usage increment per line
```

---

## Interview Questions

### Q1: What's the difference between `tottime` and `cumtime` in cProfile output? Which one do you use to find bottlenecks?

**Model answer:**
`tottime` (total time): time spent in the function itself, excluding time spent in function calls it makes. This tells you how expensive the function's own code is.

`cumtime` (cumulative time): time spent in the function AND all functions it calls. This tells you the total cost of calling this function from a profiling perspective.

**To find bottlenecks:**
- Sort by `cumtime` first: find the expensive call chains. A function at the top might be `main()` — not useful. Follow the chain down to find where time concentrates.
- Sort by `tottime`: find functions that are expensive in themselves (not just because they call expensive things). These are often the actual optimization targets.

```python
# Example: sorted by cumtime
# main() cumtime=10s tottime=0.01s → calls into expensive code
# compute() cumtime=9.5s tottime=9.5s → THE bottleneck (tottime ≈ cumtime)

# Check ncalls too: a function called 1M times with 0.001s tottime = 1000s total
```

High `ncalls` × small `tottime` often indicates a function that should be cached or its call frequency reduced.

### Q2: When would you use py-spy over cProfile?

**Model answer:**

| Scenario | Tool |
|----------|------|
| Development, detailed call graph needed | cProfile |
| Production service under live load | py-spy |
| C extension overhead | py-spy (cProfile misses C time) |
| Can't modify code | py-spy (attach to running process) |
| Async code profiling | pyinstrument (async-aware) |
| Memory profiling | tracemalloc |

**py-spy advantages:**
- **Zero code changes:** attach to any running Python process by PID.
- **Zero overhead:** sampling profiler reads process memory — no hooks.
- **C extension visibility:** shows time in C code that cProfile misses (native frames).
- **Production safe:** can run against live services without restart.

**cProfile advantages:**
- **Exact call counts:** deterministic, every call counted.
- **Precise timing per function:** not statistical.
- **Built into stdlib:** no installation needed.

For a performance regression in CI: use `cProfile` in a benchmark test. For a slow production service you can't restart: `py-spy top --pid $(pgrep -f myservice)`.

### Q3: How do you profile asyncio code, where cProfile shows misleading results?

**Model answer:**
cProfile shows misleading results for async code because it measures wall-clock time across all coroutines, not the actual execution time of each coroutine. `await asyncio.sleep(1)` in one coroutine counts as 1 second of `cumtime` for that coroutine even though no CPU work happened.

Better tools:

**pyinstrument** is async-aware — it correctly handles `await` boundaries:
```python
from pyinstrument import Profiler

async def main():
    profiler = Profiler(async_mode='enabled')
    with profiler:
        await my_async_code()
    profiler.print()
```

**yappi** (Yet Another Python Profiler) supports coroutine-aware profiling:
```python
import yappi
import asyncio

yappi.set_clock_type("cpu")  # CPU time, not wall time
yappi.start()

asyncio.run(main())

yappi.get_func_stats().print_all()
yappi.get_thread_stats().print_all()
```

For production: py-spy handles async code correctly (it walks the actual Python frame stack, which correctly shows the active coroutine).

### Q4: You find that `str.join()` appears at the top of your profile. What does this indicate?

**Model answer:**
`str.join()` at the top indicates string concatenation in a loop — one of the most common Python performance antipatterns. Instead of accumulating strings with `+` or `+=` (which creates a new string object each time), the solution is collecting parts in a list and joining once:

```python
# Bad: O(n²) due to repeated string creation
def build_bad(parts: list[str]) -> str:
    result = ""
    for part in parts:
        result += part   # new string allocated each iteration!
    return result

# Good: O(n)
def build_good(parts: list[str]) -> str:
    return "".join(parts)   # single allocation

# If parts aren't all strings yet:
def build_mixed(items) -> str:
    return "".join(str(item) for item in items)
```

If `str.join()` itself appears at the top with high `tottime` and the input list is very large, the issue might be the size of data, not the pattern. Profile the list construction code too.

### Q5: What's the right approach for profiling a long-running service that intermittently becomes slow?

**Model answer:**
For intermittent slowness in a long-running service:

1. **Continuous lightweight profiling:** py-spy with `--duration` sampling during slow periods:
```bash
# When you notice high latency:
py-spy record -o /tmp/profile-$(date +%s).svg --pid $(pgrep -f myservice) --duration 60
```

2. **Built-in metrics with `cProfile` on demand:** expose a signal handler that enables/disables profiling:
```python
import cProfile, signal, pstats

_profiler = None

def toggle_profiling(signum, frame):
    global _profiler
    if _profiler is None:
        _profiler = cProfile.Profile()
        _profiler.enable()
    else:
        _profiler.disable()
        _profiler.print_stats(sort='cumtime')
        _profiler = None

signal.signal(signal.SIGUSR1, toggle_profiling)
# Usage: kill -USR1 <pid>  to start/stop
```

3. **Distributed tracing:** for service-level latency, OpenTelemetry traces show which operations are slow (DB queries, external calls, serialization). This catches systemic issues cProfile can't see.

4. **Hypothesis:** look at garbage collection pauses, memory pressure, lock contention. Use `gc.callbacks` or `gc.set_debug(gc.DEBUG_STATS)` to detect GC pauses.

---

## Gotcha Follow-ups

**"Does cProfile add overhead that changes the behavior being measured?"**
Yes — cProfile adds a hook to every function call (deterministic profiling). This can make tight loops appear slower than they are, and can mask the true bottleneck if the profiling overhead is significant relative to the function's work. For micro-benchmarks, use `timeit`. For macro profiling, cProfile overhead is usually acceptable (~10-30%).

**"How do you profile a C extension?"**
cProfile only sees Python-level calls — time spent inside C extension code appears as `tottime` of the calling Python function, not attributed to C code. To profile C extension time: use py-spy (reads native frames), Valgrind/perf on Linux, or Instruments on macOS. For Cython extensions: enable line tracing with `cython: linetrace=True` directive and use cProfile.

---

## Under the Hood

cProfile is implemented as a C extension (`_lsprof.c`). It uses `sys.setprofile()` under the hood — a per-thread callback called on every `call`, `return`, and `exception` event. The callback increments counters in a hash table keyed on (caller, callee) pairs. The overhead of the per-call hook is why cProfile is deterministic but expensive. py-spy uses `ptrace` (Linux) or `task_for_pid` (macOS) to read the target process's memory and find the `PyThreadState`, then walks `frame->f_back` linked list to reconstruct the call stack. Each sample is taken at ~200Hz (configurable).
