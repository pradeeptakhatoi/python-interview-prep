# Multiprocessing: Process Spawning and Shared Memory

## Concept

`multiprocessing` bypasses the GIL by using separate OS processes. Each process has its own Python interpreter, GIL, and memory space. This provides true CPU parallelism at the cost of inter-process communication (IPC) overhead.

### Process Start Methods

The start method determines how a child process is created:

| Method | OS | How | GIL State | Implications |
|--------|----|-----|-----------|--------------|
| `fork` | Unix only | `os.fork()` — copy parent | Fresh | Fast; inherits all state (file descriptors, locks); unsafe with threads |
| `spawn` | All | New interpreter, imports `__main__` | Fresh | Safe but slow; serializes args via pickle |
| `forkserver` | Unix | Fork a clean server process, server forks children | Fresh | Safer than fork with threads; avoids inheriting locks |

```python
import multiprocessing as mp

# Check and set start method:
print(mp.get_start_method())  # 'fork' on Linux, 'spawn' on Windows/macOS 3.8+

mp.set_start_method('spawn', force=True)  # must be called in if __name__ == '__main__'

# Or use context:
ctx = mp.get_context('spawn')
p = ctx.Process(target=some_func, args=(arg1,))
```

**The `fork` danger:** If threads are running in the parent process at fork time, the child gets a copy of the address space with those threads' state — but the threads themselves don't transfer. Mutexes held by those threads are locked in the child forever, causing deadlocks. This is the #1 source of mysterious hangs when mixing `threading` and `multiprocessing` with `fork`.

**macOS changed default to `spawn` in Python 3.8** to fix Objective-C runtime issues with `fork`. This is why code that worked on Linux breaks on Mac — pickling requirements change.

### Pickling Overhead

With `spawn` and `forkserver`, all arguments to `Process` and `Pool.map` are serialized via `pickle`. This has major implications:

```python
import multiprocessing as mp
import pickle

def worker(data):
    return sum(data)

# This works:
p = mp.Process(target=worker, args=([1, 2, 3],))

# These DON'T work (not picklable):
# - Lambda functions
# - Local functions (in some contexts)
# - Open file handles
# - Database connections
# - Threading locks

try:
    p = mp.Process(target=lambda: None)  # Works on fork, fails on spawn
    p.start()
except AttributeError:
    print("lambdas can't be pickled for spawn")

# Measure pickling overhead:
data = list(range(10_000_000))
import timeit
t = timeit.timeit(lambda: pickle.dumps(data), number=1)
print(f"Pickle 10M ints: {t:.3f}s, {len(pickle.dumps(data))/1e6:.1f} MB")
```

### Shared Memory

#### `Value` and `Array` — ctypes-backed shared memory

```python
import multiprocessing as mp
import ctypes

def increment_counter(counter, n):
    for _ in range(n):
        with counter.get_lock():   # must lock — not atomic
            counter.value += 1

if __name__ == '__main__':
    counter = mp.Value(ctypes.c_int, 0)  # shared int, initialized to 0
    n_procs = 4
    n_iters = 100_000

    procs = [mp.Process(target=increment_counter, args=(counter, n_iters))
             for _ in range(n_procs)]
    for p in procs: p.start()
    for p in procs: p.join()

    print(counter.value)  # 400000 — correct with locking
```

#### `shared_memory` Module (Python 3.8+) — True Shared Memory Blocks

```python
from multiprocessing import shared_memory
import numpy as np

# Create a shared memory block:
shm = shared_memory.SharedMemory(create=True, size=10 * 1024 * 1024)  # 10 MB

# Use it as a NumPy array (zero-copy!):
arr = np.ndarray((1024, 1024), dtype=np.float32, buffer=shm.buf)
arr[:] = 0.0  # initialize

# In worker processes: attach to the same block by name
def worker(shm_name, shape):
    shm = shared_memory.SharedMemory(name=shm_name)
    arr = np.ndarray(shape, dtype=np.float32, buffer=shm.buf)
    arr[0, 0] = 42.0  # modifies shared memory
    shm.close()

import multiprocessing as mp
p = mp.Process(target=worker, args=(shm.name, (1024, 1024)))
p.start()
p.join()

print(arr[0, 0])  # 42.0 — modified by worker process

shm.close()
shm.unlink()  # destroy the shared memory block
```

`SharedMemory` is a true POSIX shared memory segment — no pickling, zero-copy between processes. Essential for large data (images, arrays, matrices) passed to worker processes.

#### `Manager` — Proxy-based Shared Objects

```python
from multiprocessing import Manager

with Manager() as manager:
    d = manager.dict()     # proxy to a shared dict
    lst = manager.list()   # proxy to a shared list

    def worker(d, lst, i):
        d[i] = i * 2
        lst.append(i)

    procs = [mp.Process(target=worker, args=(d, lst, i)) for i in range(5)]
    for p in procs: p.start()
    for p in procs: p.join()

    print(dict(d))   # {0: 0, 1: 2, 2: 4, 3: 6, 4: 8}
    print(list(lst)) # [0, 1, 2, 3, 4] (order may vary)
```

`Manager` creates a server process that owns the objects. Workers communicate via IPC. This is much slower than `shared_memory` but supports arbitrary Python objects. Use only when you need shared Python data structures and performance is not critical.

---

## Interview Questions

### Q1: Why is `fork` dangerous in a multi-threaded Python program?

**Model answer:**  
`fork()` creates a copy of the parent process's address space but only copies the calling thread — all other threads are gone in the child. This leaves the child in a potentially inconsistent state:

1. **Locked mutexes** — if another thread held a lock at fork time, that lock is locked in the child forever. The thread that would release it doesn't exist. Any code in the child that tries to acquire this lock deadlocks.
2. **Partially-initialized state** — thread-local state, open database connection pools, logging handlers, and other thread-specific resources are copied but may be in mid-operation.
3. **CPython internal locks** — the GIL, import lock, and memory allocator locks may be held. In CPython 3.12, the `_PyRuntime` structure contains many such locks.

The safe options:
- Use `spawn` (all modern macOS/Windows default).
- Use `fork` only from a single-threaded state (before any threads start).
- Use `forkserver` which forks from a clean single-threaded server.

`os.register_at_fork(before=..., after_in_parent=..., after_in_child=...)` allows reinitializing state post-fork for libraries that must support fork.

### Q2: What's the overhead model for `Pool.map()` vs. serial execution?

**Model answer:**  
`Pool.map(func, iterable)` with `spawn` involves:

1. **Startup cost** — spawning `n` processes, each loading Python, importing your modules (typically 0.1–0.5s per process).
2. **Serialization** — pickling each argument and result. For large data, this can dominate.
3. **IPC** — sending pickled data through a pipe.
4. **Deserialization** — unpickling in the worker.
5. **Execution** — actual computation.
6. **Result IPC** — reverse path for results.

Rule of thumb:
```
use multiprocessing if: compute_time >> (pickle_time + ipc_time + startup_time)
```

```python
import multiprocessing as mp
import pickle
import time

def compute(x):
    # Simulate CPU work
    return sum(i*i for i in range(x))

data = list(range(1, 1001))

# Estimate pickle overhead:
pickled = pickle.dumps(data)
t_pickle = timeit.timeit(lambda: pickle.dumps(data), number=100) / 100

# If t_pickle > total_compute_time / n_workers, multiprocessing won't help

with mp.Pool(4) as pool:
    start = time.perf_counter()
    results = pool.map(compute, data)
    elapsed = time.perf_counter() - start
```

For tasks under ~1ms each, the IPC overhead dominates. Use `chunksize` parameter to amortize:
```python
pool.map(func, data, chunksize=100)  # send 100 items per IPC message
```

### Q3: When would you use `shared_memory` over `Manager`? What are the tradeoffs?

**Model answer:**  

| Aspect | `shared_memory` | `Manager` |
|--------|-----------------|-----------|
| Latency | Direct memory access | IPC round-trip per operation |
| Data types | Raw bytes (use struct/numpy) | Any picklable Python object |
| Synchronization | Manual (locks/events) | Internal (via server) |
| Use case | Large arrays, performance-critical | Shared dicts/lists, coordination |
| Overhead | ~nanoseconds per access | ~microseconds per operation |

**Use `shared_memory` when:**
- Sharing large NumPy arrays between processes (zero-copy is essential).
- Latency matters (each access should be memory-speed, not IPC-speed).
- You control synchronization explicitly (e.g., process 0 writes, signals process 1 to read).

**Use `Manager` when:**
- You need to share Python dicts/lists/queues without implementing serialization.
- The data access is infrequent relative to computation.
- Simplicity matters more than performance.

### Q4: How do you handle exceptions in child processes with `Pool.map()`?

**Model answer:**  
Exceptions in worker processes are pickled and re-raised in the parent:

```python
import multiprocessing as mp

def risky_compute(x):
    if x == 5:
        raise ValueError(f"Bad input: {x}")
    return x * 2

if __name__ == '__main__':
    with mp.Pool(4) as pool:
        try:
            results = pool.map(risky_compute, range(10))
        except ValueError as e:
            print(f"Worker raised: {e}")  # re-raised in parent
```

**Limitation:** Only the first exception is raised; other worker exceptions are silently dropped if `map()` fails fast.

For collecting all exceptions:
```python
async_results = [pool.apply_async(risky_compute, (i,)) for i in range(10)]
results = []
errors = []
for ar in async_results:
    try:
        results.append(ar.get(timeout=5))
    except Exception as e:
        errors.append(e)
```

**Unpicklable exceptions** are a subtle problem: if your custom exception can't be pickled (e.g., holds a reference to a database connection), the worker crashes with a different error than expected. Design exceptions to be picklable (stick to basic Python types in `__init__`).

### Q5: What is `multiprocessing.Queue` vs. `queue.Queue`?

**Model answer:**  

| | `queue.Queue` | `multiprocessing.Queue` |
|--|--------------|------------------------|
| Scope | Within one process, between threads | Across processes |
| Implementation | Deque + condition variable | Pipe + thread + semaphore |
| Performance | Fast (shared memory) | Slower (IPC + pickle) |
| Blocking | `get(timeout=...)` | Same API, but across IPC |

`multiprocessing.Queue` internally uses a pipe and a background feeder thread that serializes items via pickle. For high-throughput inter-process messaging, `multiprocessing.Pipe` is lower overhead (direct, no feeder thread), and `shared_memory` is fastest.

```python
import multiprocessing as mp

def producer(q):
    for i in range(5):
        q.put(i)
    q.put(None)  # sentinel

def consumer(q):
    while True:
        item = q.get()
        if item is None:
            break
        print(f"Got: {item}")

if __name__ == '__main__':
    q = mp.Queue()
    p = mp.Process(target=producer, args=(q,))
    c = mp.Process(target=consumer, args=(q,))
    p.start(); c.start()
    p.join(); c.join()
```

---

## Gotcha Follow-ups

**"Why must `multiprocessing` code be inside `if __name__ == '__main__'`?"**  
With `spawn`, the child process imports `__main__` to get the worker function. Without the guard, it would re-execute the `mp.Process(...)` and `p.start()` calls, spawning a grandchild process — causing infinite process spawning (process bomb). The guard ensures setup code only runs in the original parent.

**"Can you use `asyncio` with `multiprocessing`?"**  
Yes, via `loop.run_in_executor(executor, func, *args)` with a `ProcessPoolExecutor`. The function must be picklable (no lambdas, closures with non-picklable state). The event loop submits work to the pool and awaits completion non-blockingly. This is the correct pattern for CPU-bound work in an async context — avoids blocking the event loop.

---

## Under the Hood

`multiprocessing.Process.start()` with `spawn`:
1. Pickles the `Process` object (target, args, kwargs, daemon flag) to a file descriptor.
2. Calls `subprocess.Popen(['python', '-c', 'from multiprocessing.spawn import freeze_support; ...'])`.
3. The child reads the pickled `Process` object, unpickles it, and calls `target(*args, **kwargs)`.

`shared_memory.SharedMemory` wraps `shm_open()` / `mmap()` on POSIX and `CreateFileMapping()` on Windows. The memory segment has a name that can be shared between processes. The `buf` attribute is a `memoryview` over the raw memory.
