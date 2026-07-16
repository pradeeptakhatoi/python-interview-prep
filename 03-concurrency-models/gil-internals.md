# GIL Internals

## Concept

The **Global Interpreter Lock (GIL)** is a mutex that protects CPython's internal state — primarily the reference counting machinery (`ob_refcnt`) — from concurrent modification by multiple threads. At any given time, only one thread may execute Python bytecode.

### Why It Exists

CPython's reference counting is not atomic. Without a lock, two threads simultaneously decrementing the same object's `ob_refcnt` would produce a race condition: both read the count as 1, both decrement, both get 0, and both call `tp_dealloc` — double-free. The GIL is the simplest solution.

The GIL also protects:
- The global list of tracked GC objects
- The intern table (`sys.intern`)
- The memory allocator's freelist structures
- Many C extension states that assumed single-threaded access

### Switching Mechanism

**Python ≤ 3.1 (per-opcode switching):** The GIL was released every 100 bytecode instructions (`sys.getcheckinterval()`). This caused high-frequency context switches and poor CPU cache behavior.

**Python ≥ 3.2 (time-based switching, PEP 0311 via Dave Beazley's research):** The GIL is released approximately every **5 milliseconds** (`sys.getswitchinterval()`, default 0.005). A thread that wants the GIL sets a "request" flag; the current holder releases at the next safe point (a `EVAL_BREAKER` check).

```python
import sys

print(sys.getswitchinterval())  # 0.005 (5ms)
sys.setswitchinterval(0.001)    # 1ms — more responsive but higher overhead

# In C extensions: the GIL is released via Py_BEGIN_ALLOW_THREADS
# and reacquired via Py_END_ALLOW_THREADS
```

### What the GIL Does NOT Protect

The GIL does not make Python objects thread-safe at the application level:

```python
import threading

counter = 0  # global shared state

def increment():
    global counter
    for _ in range(100_000):
        counter += 1  # NOT atomic: LOAD_GLOBAL, BINARY_OP, STORE_GLOBAL
                      # GIL can switch between these three opcodes

threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()

print(counter)  # Likely not 400000 — race condition!
```

`counter += 1` compiles to three opcodes. The GIL can switch threads between any of them. Use `threading.Lock` for shared mutable state.

### GIL and I/O-Bound vs. CPU-Bound Work

- **I/O-bound (network, disk, subprocess):** The GIL is released during blocking I/O calls (the C implementation calls `Py_BEGIN_ALLOW_THREADS` before the syscall). Multiple threads can make progress concurrently. `threading` is genuinely useful here.
- **CPU-bound (pure Python computation):** Threads fight over the GIL. Adding more threads makes CPU-bound work slower due to GIL contention. Use `multiprocessing` or release-GIL C extensions (NumPy, etc.).

```python
import threading
import time

def cpu_task():
    total = 0
    for i in range(10_000_000):
        total += i
    return total

# Single-threaded:
start = time.perf_counter()
cpu_task()
cpu_task()
single_time = time.perf_counter() - start

# Multi-threaded (SLOWER due to GIL contention):
start = time.perf_counter()
t1 = threading.Thread(target=cpu_task)
t2 = threading.Thread(target=cpu_task)
t1.start(); t2.start()
t1.join(); t2.join()
multi_time = time.perf_counter() - start

print(f"Single: {single_time:.2f}s, Multi: {multi_time:.2f}s")
# multi_time >= single_time — GIL prevents true parallelism
```

### GIL Contention Visualization

```python
import sys
import threading

def trace_gil(frame, event, arg):
    if event == 'call':
        print(f"[{threading.current_thread().name}] {frame.f_code.co_filename}:{frame.f_lineno}")
    return trace_gil

# Use a sampling profiler like py-spy instead for production GIL analysis:
# py-spy record --gil -p <pid> -o output.svg
```

---

## Interview Questions

### Q1: Why does the GIL make CPU-bound multi-threaded Python slower than single-threaded?

**Model answer:**  
When two CPU-bound threads share a process, each runs Python bytecode and holds the GIL. Thread A runs for 5ms, releases; thread B acquires and runs for 5ms; repeat. The overhead here is:

1. **OS context switching** — switching between threads involves saving and restoring CPU registers, even if only one is doing useful work at a time.
2. **GIL request signaling** — a waiting thread continuously signals "I want the GIL" via the `eval_breaker` mechanism, which the running thread must check at each `EVAL_BREAKER` point.
3. **Cache invalidation** — threads often run on different CPU cores. When thread B acquires the GIL and runs on a different core, the cache lines that thread A warmed are cold.
4. **False parallelism cost** — two threads produce more OS scheduler overhead than one, but no actual parallel execution.

Result: the total work is the same, but with extra overhead from context switching and cache effects.

### Q2: Why doesn't the GIL protect `counter += 1` in a multi-threaded program?

**Model answer:**  
`counter += 1` is not a single atomic operation. The CPython bytecode for it is:

```
LOAD_GLOBAL  counter    # read counter onto stack
LOAD_CONST   1          # push 1
BINARY_OP    +          # add them
STORE_GLOBAL counter    # write result back
```

The GIL can switch threads between any of these opcodes (specifically at the `EVAL_BREAKER` check point). Two threads can both execute `LOAD_GLOBAL counter` and read the same value, then both store incremented values — losing one increment.

The GIL protects individual bytecode opcodes from being interrupted mid-execution (each opcode modifies internal CPython state atomically w.r.t. GIL), but does not make multi-instruction Python operations atomic.

Fix: use `threading.Lock`:
```python
lock = threading.Lock()
def safe_increment():
    global counter
    with lock:
        counter += 1
```

Or use `queue.Queue` (all operations are internally synchronized).

### Q3: How does the GIL interact with C extensions like NumPy?

**Model answer:**  
Well-written C extensions release the GIL during expensive computations that don't touch Python objects:

```c
/* In a C extension: */
Py_BEGIN_ALLOW_THREADS  /* releases GIL */
    do_heavy_matrix_multiply(a, b, out);  /* pure C, no Python objects */
Py_END_ALLOW_THREADS    /* reacquires GIL */
```

Between these macros, the thread does not hold the GIL. Other Python threads can run Python code concurrently. This is how NumPy achieves genuine parallelism in multi-threaded code — BLAS operations run GIL-free.

This means:
- `numpy.dot(a, b)` in a thread pool can genuinely use multiple cores.
- Pure Python loops cannot.

The rule: any C extension doing CPU-heavy work on non-Python data should release the GIL. Extensions that read or write Python objects must hold the GIL.

### Q4: What is the `eval_breaker` and how does GIL handoff actually work?

**Model answer:**  
`eval_breaker` is a flag in `_PyRuntime` (a C-level global) that the bytecode evaluation loop checks at specific points — after certain opcodes and at backward jumps (loop iterations). When set, the interpreter pauses to handle:
- GIL release requests from other threads
- Signal delivery
- Asynchronous exception injection

When thread B wants the GIL (it's been waiting >5ms), it sets `gil_drop_request = 1` in the GIL state struct. Thread A checks `eval_breaker` at the next opportunity, sees the request, and performs the GIL handoff:

1. Thread A releases the GIL (atomically clears the lock).
2. Thread A signals a condition variable.
3. Thread B wakes, acquires the GIL, clears `gil_drop_request`.
4. Thread A waits for the GIL to become available again if it needs to continue.

The 5ms timeout is not enforced by a timer interrupt — it's a soft suggestion. Thread A might not hit an `eval_breaker` check for slightly longer if executing a long opcode.

### Q5: When would you use `threading` despite the GIL?

**Model answer:**  
`threading` is appropriate when work is I/O-bound, not CPU-bound:

1. **Network I/O** — making 100 HTTP requests to external APIs. Each thread blocks in the kernel's `recv()` call with the GIL released, so other threads run.
2. **Database queries** — `psycopg2`/`sqlite3` release the GIL during queries.
3. **File I/O** — disk reads release the GIL.
4. **Subprocess communication** — `subprocess.communicate()` releases the GIL.
5. **Mixed workloads** — a main thread doing Python logic while a background thread handles network polling.

For these cases, `threading.Thread` with a `ThreadPoolExecutor` gives clean concurrency. For CPU-bound work, use `multiprocessing.ProcessPoolExecutor`.

---

## Gotcha Follow-ups

**"Is it possible to have a deadlock involving the GIL?"**  
Yes. If a C extension holds the GIL and tries to acquire a Python-level lock that is held by another thread (which is waiting for the GIL), you have a deadlock. This typically happens in `__del__` finalizers that acquire locks, or in C callbacks invoked from non-Python threads.

**"If I set `sys.setswitchinterval(0)`, what happens?"**  
A switch interval of 0 means the GIL is checked after every single bytecode instruction. This causes extremely high GIL contention overhead and typically makes everything slower. It's used only for testing GIL-related races. The minimum effective interval is bounded by the granularity of the OS timer.

---

## Under the Hood

The GIL implementation is in `Python/ceval_gil.c`. Key structures:
- `_gil_runtime_state` — holds the GIL mutex, condition variable, locked flag, and `switch_number`.
- `eval_breaker` — a flag in `_PyRuntime.ceval` that is checked in the bytecode evaluation loop via `_Py_HandlePending()`.
- The GIL is implemented as a flag protected by a POSIX mutex + condition variable, not as a raw OS mutex, to allow the timed-wait handoff mechanism.

In free-threaded builds (PEP 703), `ceval_gil.c` is replaced with per-thread reference counting and a different locking strategy — see `gil-removal-pep703.md`.
