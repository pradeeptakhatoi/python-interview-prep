# concurrent.futures: ThreadPoolExecutor vs ProcessPoolExecutor

## Concept

`concurrent.futures` provides a high-level, unified interface for both thread-based and process-based concurrency. It abstracts away the mechanics of pool management and result collection, offering `Future` objects for pending results.

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import time

def task(n):
    time.sleep(0.1)
    return n * n
```

### ThreadPoolExecutor

Runs callables in a pool of threads within the same process. Subject to the GIL for CPU-bound Python code; ideal for I/O-bound work.

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=10) as executor:
    # submit() — non-blocking, returns a Future
    future = executor.submit(task, 5)
    print(future.result())  # blocks until done; returns 25

    # map() — like built-in map, but concurrent; preserves order
    results = list(executor.map(task, range(10)))
    print(results)  # [0, 1, 4, 9, ..., 81]

    # map() with timeout:
    try:
        results = list(executor.map(task, range(10), timeout=0.5))
    except TimeoutError:
        print("Some tasks timed out")
```

**Thread count guidance:**
- I/O-bound: `min(32, os.cpu_count() + 4)` (Python 3.8+ default for `ThreadPoolExecutor`)
- Don't use more threads than concurrent I/O connections you actually need
- More threads ≠ more throughput; each thread has stack overhead (~8MB on Linux)

### ProcessPoolExecutor

Runs callables in a pool of separate processes. True CPU parallelism; each worker has its own GIL.

```python
from concurrent.futures import ProcessPoolExecutor
import os

def cpu_bound(n):
    return sum(i * i for i in range(n))

if __name__ == '__main__':  # required for spawn start method
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = [executor.submit(cpu_bound, 10_000_000) for _ in range(4)]
        for future in as_completed(futures):
            print(future.result())
```

### `as_completed` vs `executor.map`

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

def fetch(url):
    time.sleep(random.uniform(0.1, 0.5))  # simulate variable latency
    return f"response from {url}"

urls = [f"http://api.example.com/{i}" for i in range(10)]

# map(): preserves order; waits for each in sequence if iterating
with ThreadPoolExecutor(max_workers=5) as executor:
    for result in executor.map(fetch, urls):  # yields in submission order
        print(result)                          # waits for url[0] even if url[5] finished first

# as_completed(): yields results as they arrive (out of order, faster first response)
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch, url): url for url in urls}
    for future in as_completed(futures):
        url = futures[future]
        try:
            result = future.result()
            print(f"{url}: {result}")
        except Exception as e:
            print(f"{url}: failed with {e}")
```

**Rule:** Use `map()` when order matters or when processing results in a pipeline. Use `as_completed()` when you want to process results as soon as they're ready (e.g., streaming updates to a UI, early exit on first success).

### Future API

```python
from concurrent.futures import ThreadPoolExecutor
import threading

with ThreadPoolExecutor(max_workers=2) as executor:
    f = executor.submit(task, 10)

    # Inspect state:
    print(f.running())    # True if executing
    print(f.done())       # True if complete (success or exception)
    print(f.cancelled())  # True if successfully cancelled

    # Callbacks (called in the thread that completed the future, or immediately if already done):
    f.add_done_callback(lambda fut: print(f"Done: {fut.result()}"))

    # Blocking get with timeout:
    try:
        result = f.result(timeout=1.0)
    except TimeoutError:
        print("Timed out")
    except Exception as e:
        print(f"Task raised: {e}")  # re-raises exception from worker

    # Cancel (only works if task hasn't started yet):
    f2 = executor.submit(task, 99)
    cancelled = f2.cancel()  # may return False if already running
```

### Executor Shutdown

```python
executor = ThreadPoolExecutor(max_workers=4)
futures = [executor.submit(task, i) for i in range(20)]

# shutdown(wait=True) — wait for all running tasks to complete (default)
# shutdown(wait=False) — return immediately; running tasks still finish
# shutdown(cancel_futures=True) — cancel queued (not-yet-started) tasks (Python 3.9+)
executor.shutdown(wait=True, cancel_futures=False)
```

The context manager (`with` block) calls `shutdown(wait=True)` on exit. This is the correct pattern — always use the context manager.

---

## Interview Questions

### Q1: When would you choose `ThreadPoolExecutor` over `asyncio`, and vice versa?

**Model answer:**  

**Use `ThreadPoolExecutor` when:**
- Calling blocking APIs that you can't make async (legacy DB drivers, `requests`, subprocess).
- Integrating with existing blocking code in a non-async codebase.
- The number of concurrent tasks is bounded and relatively small (hundreds, not thousands).
- Code simplicity matters more than peak throughput.

**Use `asyncio` when:**
- You control the I/O stack end-to-end (can use `aiohttp`, `asyncpg`, etc.).
- You need tens of thousands of concurrent connections (threads have ~8MB stack overhead each; coroutines are ~1KB).
- You need fine-grained control over scheduling, cancellation, and timeouts.
- Latency and throughput matter at scale.

Conceptually: threads give you concurrency via preemptive scheduling (OS manages switching). asyncio gives you concurrency via cooperative scheduling (you explicitly yield at `await` points). The overhead per concurrent unit: thread (~8MB stack) vs coroutine (~1KB frame + task overhead).

### Q2: What happens to exceptions in a `ProcessPoolExecutor` worker?

**Model answer:**  
Exceptions in worker processes are pickled and transmitted back to the parent via IPC. When you call `future.result()`, the exception is re-raised in the calling thread.

```python
from concurrent.futures import ProcessPoolExecutor

def bad_worker():
    raise RuntimeError("something went wrong")

with ProcessPoolExecutor() as executor:
    f = executor.submit(bad_worker)
    try:
        f.result()  # raises RuntimeError("something went wrong")
    except RuntimeError as e:
        print(f"Caught: {e}")
```

**Caveats:**
1. The exception must be picklable. Custom exceptions that hold non-picklable objects (file handles, locks) will cause a `PicklingError` instead of the original exception.
2. `BrokenProcessPool` is raised if a worker process crashes (e.g., segfault, `os.kill`). This is unrecoverable; create a new `ProcessPoolExecutor`.
3. `executor.map()` raises the first exception and silently drops results for remaining items.

### Q3: How do you implement a timeout that cancels actual work, not just unblocks the caller?

**Model answer:**  
`future.result(timeout=N)` raises `TimeoutError` but does NOT cancel the worker thread — it continues running. For threads, you cannot forcibly stop them in Python. For processes, you can kill the worker process.

**Approach for threads:** Use a flag or `threading.Event` to signal the worker to stop gracefully.

```python
import threading
from concurrent.futures import ThreadPoolExecutor

def cancellable_task(stop_event: threading.Event, data):
    for i, chunk in enumerate(data):
        if stop_event.is_set():
            return None  # early exit
        process_chunk(chunk)
    return "done"

stop_event = threading.Event()
with ThreadPoolExecutor() as executor:
    f = executor.submit(cancellable_task, stop_event, large_data)
    try:
        result = f.result(timeout=5.0)
    except TimeoutError:
        stop_event.set()  # signal worker to stop
        result = None
```

**Approach for processes:** Kill the process via `os.kill()` or use `multiprocessing.Process` directly instead of `ProcessPoolExecutor`.

### Q4: What is `initializer` in `ThreadPoolExecutor` and when is it useful?

**Model answer:**  
Both `ThreadPoolExecutor(initializer=fn, initargs=...)` and `ProcessPoolExecutor` accept an `initializer` function that runs once in each worker thread/process at startup. Use cases:

1. **Database connection per thread/process:**
```python
import threading
from concurrent.futures import ThreadPoolExecutor

_local = threading.local()

def init_db():
    _local.conn = create_db_connection()  # one connection per thread

def query(sql):
    return _local.conn.execute(sql).fetchall()

with ThreadPoolExecutor(max_workers=5, initializer=init_db) as executor:
    results = list(executor.map(query, sql_statements))
```

2. **Loading a large model once per process (ML inference):**
```python
model = None

def init_model():
    global model
    model = load_large_ml_model()  # loaded once; not passed via pickle each call

def predict(data):
    return model.predict(data)

with ProcessPoolExecutor(max_workers=4, initializer=init_model) as executor:
    results = list(executor.map(predict, batch_data))
```

### Q5: How does `executor.map()` handle the case where one task takes much longer than others?

**Model answer:**  
`executor.map()` submits all tasks immediately and iterates results in **submission order**. If task 0 takes 10 seconds and tasks 1-9 take 0.1 seconds each, iterating `executor.map()` will block at the first result for 10 seconds even though tasks 1-9 are long done.

```python
# map() blocks at slow tasks:
with ThreadPoolExecutor(max_workers=4) as executor:
    results_iter = executor.map(task, items)  # all submitted immediately
    for result in results_iter:               # blocks on each in order
        process(result)
    # If item[0] is slow, items[1..] sit in memory waiting

# as_completed() processes results as they arrive:
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(task, item): item for item in items}
    for future in as_completed(futures):      # faster results come first
        process(future.result())
```

For pipelines processing results immediately, `as_completed()` is almost always better for latency. `map()` is better for batch collection where you need the results in order for the next processing step.

---

## Gotcha Follow-ups

**"What happens if you submit work to an executor after calling `shutdown()`?"**  
`RuntimeError: cannot schedule new futures after shutdown` — the executor rejects new submissions. This is why the `with` block pattern is important: it calls `shutdown()` on exit, after which the executor object should not be used.

**"Is there a way to limit the number of queued (not yet executing) tasks in `ThreadPoolExecutor`?"**  
No — by default, `ThreadPoolExecutor` has an unbounded internal queue. If you submit 1M tasks to a 4-thread pool, 1M `Future` objects sit in memory. For backpressure, use `asyncio.Semaphore` (in async code) or a `threading.Semaphore` that you acquire before submitting and release in the done callback (for thread pools):

```python
sem = threading.Semaphore(100)  # max 100 queued tasks

def submit_with_backpressure(executor, fn, *args):
    sem.acquire()
    f = executor.submit(fn, *args)
    f.add_done_callback(lambda _: sem.release())
    return f
```

---

## Under the Hood

`ThreadPoolExecutor` maintains an internal `SimpleQueue` (`_work_queue`) of `_WorkItem` objects. Worker threads loop on `queue.get()` and execute items. The queue is unbounded by default. `ProcessPoolExecutor` uses a more complex mechanism: a `multiprocessing.Queue` for call items and a result queue, managed by `_process_worker` and `_result_handler` threads.

`Future.result()` internally calls `self._condition.wait(timeout)` — a `threading.Condition` wait. When the worker completes, it calls `future.set_result()` (or `set_exception()`), which notifies the condition and calls done callbacks.
