# Benchmarking Correctly with timeit

## Concept

Microbenchmarking is deceptively easy to get wrong. Python's JIT-less interpreter, GC, OS scheduling, and the specializing adaptive interpreter (3.11+) all affect timing. Correct benchmarking requires understanding these factors.

### `timeit` — The Right Tool for Microbenchmarks

```python
import timeit

# Basic usage:
t = timeit.timeit(
    stmt='result = [x**2 for x in range(1000)]',
    number=10_000   # run 10,000 times, report total
)
print(f"Total: {t:.3f}s, Per call: {t/10000*1e6:.1f}µs")

# With setup code (run once, not timed):
t = timeit.timeit(
    stmt='d[1000]',
    setup='d = {i: i for i in range(2000)}',
    number=1_000_000
)

# Using globals (access current namespace):
data = list(range(10_000))
t = timeit.timeit(lambda: sum(data), number=10_000)
# Lambda avoids setup string; globals are captured automatically

# timeit.repeat for getting stable measurements:
results = timeit.repeat(
    stmt='sorted(data)',
    setup='import random; data = random.sample(range(10000), 1000)',
    repeat=7,         # 7 independent runs
    number=1000       # 1000 iterations per run
)
print(f"min={min(results):.3f}s, mean={sum(results)/len(results):.3f}s")
# Use min, not mean — min is the least-noise measurement
```

### Why Use `min()`, Not `mean()`

```python
import timeit

# The minimum time represents the "true" cost — OS noise only adds time, never removes it.
# High values = OS interrupt, GC pause, context switch.
# Mean includes noise; min excludes it.

results = timeit.repeat('sum(range(1000))', repeat=10, number=10_000)
print(f"min={min(results):.4f}s")   # use this
print(f"mean={sum(results)/len(results):.4f}s")   # less reliable
print(f"max={max(results):.4f}s")   # highest noise, ignore
```

### Common Benchmarking Mistakes

```python
# MISTAKE 1: Not warming up the specializing adaptive interpreter (3.11+)
# After ~8 executions, CPython specializes bytecode (BINARY_OP_ADD_INT, etc.)
# First runs are unspecialized; later runs are faster.

def benchmark_correctly():
    # Warmup:
    for _ in range(100):
        target_function()
    # Measure:
    return timeit.timeit(target_function, number=10_000)

# MISTAKE 2: Measuring something that gets optimized away
def broken_bench():
    # The constant expression may be constant-folded at compile time!
    t = timeit.timeit('x = 2 + 2', number=1_000_000)   # measures almost nothing

# MISTAKE 3: GC interference
import gc

# Option 1: disable GC during benchmark
t = timeit.timeit('expensive()', setup='gc.disable(); expensive = lambda: None',
                  number=10_000)
gc.enable()

# Option 2: force GC before measuring
gc.collect()
t = timeit.timeit(stmt, number=10_000)

# MISTAKE 4: Timing the wrong thing (including setup in stmt):
# Bad:
t = timeit.timeit('data = list(range(1000)); sorted(data)', number=10_000)  # includes list creation
# Good:
t = timeit.timeit('sorted(data)', setup='data = list(range(1000))', number=10_000)

# MISTAKE 5: Not accounting for I/O in "computational" benchmarks
# sys.stdout.write in a loop looks fast until you measure without it
```

### `pytest-benchmark` — Integration with Test Suite

```python
# pip install pytest-benchmark

def test_sum_performance(benchmark):
    """Benchmark integrated with pytest — fails if threshold exceeded."""
    data = list(range(10_000))
    result = benchmark(sum, data)
    assert result == sum(range(10_000))

# More control:
def test_sorting(benchmark):
    import random
    data = random.sample(range(10_000), 1_000)

    @benchmark
    def run():
        sorted(data)

# Compare implementations:
@pytest.mark.parametrize("fn", [sorted, my_sort], ids=["stdlib", "custom"])
def test_sort_comparison(benchmark, fn):
    data = list(range(1000, 0, -1))
    benchmark(fn, data)

# Run: pytest --benchmark-sort=mean --benchmark-histogram
# Produces comparison table and histogram
```

### `memory_profiler` for Memory Benchmarks

```python
from memory_profiler import memory_usage
import time

def my_function():
    data = [i for i in range(1_000_000)]
    return sum(data)

# Measure peak memory usage:
mem = memory_usage(my_function, interval=0.01, timeout=10)
print(f"Peak memory: {max(mem):.1f} MiB")
print(f"Memory delta: {max(mem) - min(mem):.1f} MiB")
```

### Comparing Implementations Fairly

```python
import timeit
import statistics

def compare(*implementations, setup="", n=10_000, repeat=5):
    """Compare multiple implementations on the same workload."""
    results = {}
    for impl in implementations:
        times = timeit.repeat(impl, setup=setup, number=n, repeat=repeat)
        results[impl.__name__ if callable(impl) else str(impl)] = {
            'min': min(times),
            'mean': statistics.mean(times),
            'stdev': statistics.stdev(times),
        }

    baseline = min(v['min'] for v in results.values())
    for name, r in sorted(results.items(), key=lambda x: x[1]['min']):
        speedup = r['min'] / baseline
        print(f"{name:30s} min={r['min']*1000:.2f}ms  ×{speedup:.1f}x")

compare(
    'sorted(data)',
    '[x for x in data if True]',  # comparison example
    setup='data = list(range(1000, 0, -1))',
)
```

---

## Interview Questions

### Q1: Why does `timeit` disable garbage collection by default, and when should you re-enable it?

**Model answer:**
`timeit.timeit()` calls `gc.disable()` before measuring to prevent GC pauses from adding noise to timing measurements. GC pauses in Python are stop-the-world — they can add milliseconds to what should be microsecond operations.

When you should re-enable GC in benchmarks:
1. **Your code creates many objects and benefits from incremental GC:** the no-GC benchmark would show unrealistically low memory pressure.
2. **Benchmarking memory-allocation-heavy code:** disabling GC causes objects to accumulate, increasing memory usage and eventually causing a GC pause in the last iteration (worst case timing).
3. **Realistic production simulation:** production runs with GC enabled; benchmarks should too for comparable numbers.

```python
# Include GC overhead in benchmark:
timeit.timeit(
    stmt='[User(i) for i in range(1000)]',
    setup='gc.enable(); gc.collect(); from myapp import User',
    number=1000
)
```

For most benchmarks: disable GC (default) and measure the code's computation cost. For memory-allocation-heavy code: enable GC and measure realistic throughput.

### Q2: What is the "specializing adaptive interpreter" (PEP 659) effect on benchmarks and how do you account for it?

**Model answer:**
CPython 3.11+ specializes bytecode after ~8 executions. A function's `BINARY_OP` may become `BINARY_OP_ADD_INT` after warmup — significantly faster. Early benchmark iterations run the unspecialized version; later ones run the specialized version.

```python
import timeit

def add_ints(a, b):
    return a + b

# First 8 calls: BINARY_OP (general)
# Calls 9+: BINARY_OP_ADD_INT (specialized for int)

# Wrong: measuring before specialization
t1 = timeit.timeit(lambda: add_ints(1, 2), number=5)

# Right: warm up first
for _ in range(100):  # trigger specialization
    add_ints(1, 2)

t2 = timeit.timeit(lambda: add_ints(1, 2), number=10_000)

# t2 is the realistic steady-state performance; t1 includes startup cost
```

In practice: `timeit.timeit(number=10_000)` automatically handles this — 10,000 runs means specialization happens after the first handful, and the measurement is dominated by the specialized version. The issue is only with very small `number` values.

### Q3: How do you benchmark code that has I/O or network calls?

**Model answer:**
Don't use `timeit` for I/O benchmarks — it doesn't handle async, can't control external resources, and measures wall-clock time mixed with wait time.

For I/O benchmarks, use explicit timing with proper setup:

```python
import time
import statistics

def benchmark_with_io(func, n=100):
    """Benchmark I/O-bound code with proper warmup and measurement."""
    # Warmup: fill caches, establish connections
    for _ in range(5):
        func()

    # Measure:
    times = []
    for _ in range(n):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)

    return {
        'p50': statistics.median(times),
        'p95': sorted(times)[int(n * 0.95)],
        'p99': sorted(times)[int(n * 0.99)],
        'mean': statistics.mean(times),
    }

# For HTTP benchmarks: use tools like wrk, vegeta, or locust
# For DB benchmarks: use realistic query patterns with actual data volumes
# For async code: use asyncio.gather + time measurement

async def benchmark_async(coro_factory, n=100):
    times = []
    for _ in range(n):
        start = time.perf_counter()
        await coro_factory()
        times.append(time.perf_counter() - start)
    return statistics.median(times)
```

For realistic throughput: measure requests-per-second, not individual call latency — they answer different questions.

### Q4: What's the difference between wall-clock time and CPU time, and when does it matter for Python benchmarks?

**Model answer:**
- **Wall-clock time** (`time.perf_counter()`): elapsed real time — includes waiting for I/O, OS scheduler, sleep.
- **CPU time** (`time.process_time()`): time the process actually used the CPU — excludes sleep and I/O wait.

For pure CPU-bound benchmarks: both are similar (no I/O wait). Use `time.perf_counter()` for its higher resolution.

For I/O-bound code: wall-clock and CPU time diverge dramatically:
```python
import time

start_wall = time.perf_counter()
start_cpu = time.process_time()

import time as t
t.sleep(1)   # 1 second of waiting

wall = time.perf_counter() - start_wall
cpu = time.process_time() - start_cpu

print(f"wall={wall:.3f}s, cpu={cpu:.6f}s")
# wall=1.001s, cpu=0.000052s
# Sleep uses no CPU — only wall time increases
```

When comparing algorithms: CPU time is more meaningful (removes OS scheduling noise). When measuring user-perceived latency (web request): wall-clock time is what users experience.

### Q5: How do you prevent benchmark results from being compiled away (dead code elimination)?

**Model answer:**
Python's compiler does limited constant folding, but interpreted execution rarely eliminates work entirely. The bigger risk is **the result not being used**, which can look like a fast result but is actually the interpreter skipping computation:

```python
# Problematic: the list comprehension is computed but immediately discarded
timeit.timeit('[x**2 for x in range(1000)]', number=10_000)
# Python executes the comprehension but discards the result
# This IS measuring the computation cost, but if the compiler folds constants:
timeit.timeit('2 + 2', number=1_000_000)   # peephole optimizer replaces with 4

# To ensure computation happens:
timeit.timeit(
    stmt='result = [x**2 for x in data]; len(result)',  # force use
    setup='data = list(range(1000))',
    number=10_000
)

# Better pattern: use variables from setup (not constants):
timeit.timeit(
    stmt='sorted(data)',   # data from setup — not a constant
    setup='data = list(range(1000, 0, -1))',
    number=10_000
)

# With lambdas and mutable state:
import random
data = [random.random() for _ in range(1000)]
t = timeit.timeit(lambda: sorted(data), number=10_000)
# sorted() returns a new list each time — definitely computed
```

---

## Gotcha Follow-ups

**"Is `time.time()` appropriate for benchmarking?"**
No — `time.time()` has platform-dependent resolution (often 10-15ms on Windows) and can jump backward (NTP adjustments). Use `time.perf_counter()` (high-resolution monotonic wall clock) or `time.process_time()` (CPU time). Never `time.time()` for benchmarks.

**"Should you benchmark in debug mode or optimized mode?"**
Always benchmark as close to production as possible: same Python version, same `PYTHONHASHSEED`, same environment variables, same hardware architecture. Debug builds (`./python_d`, `PYTHONDEBUG=1`) are 2-5× slower and give misleading results.

---

## Under the Hood

`timeit.timeit()` creates a `Timer` object with a compiled code template that loops `number` times around the statement. The template is `for _i in itertools.repeat(None, {number}): {stmt}` — compiled to bytecode using `compile()`. This avoids per-iteration overhead from Python's `for` loop. `time.perf_counter()` maps to `clock_gettime(CLOCK_MONOTONIC_RAW)` on Linux, `QueryPerformanceCounter` on Windows — both sub-microsecond resolution.
