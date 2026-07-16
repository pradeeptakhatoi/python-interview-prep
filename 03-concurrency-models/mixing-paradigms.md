# Mixing Paradigms: Sync ↔ Async Interop

## Concept

Real production systems often need to bridge synchronous and asynchronous code — running blocking code from an async context, or calling async code from a synchronous one. Each crossing point has specific patterns and pitfalls.

### Running Sync Code from Asyncio (run_in_executor)

The standard pattern for calling blocking I/O or CPU-bound sync code from a coroutine:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time

def blocking_io(url: str) -> str:
    """Synchronous, blocking HTTP call (e.g., using requests)."""
    import urllib.request
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.read().decode()

def cpu_heavy(n: int) -> int:
    return sum(i * i for i in range(n))

async def main():
    loop = asyncio.get_running_loop()

    # ThreadPoolExecutor for blocking I/O (GIL released during syscall):
    with ThreadPoolExecutor(max_workers=20) as thread_pool:
        result = await loop.run_in_executor(
            thread_pool, blocking_io, "http://example.com"
        )

    # ProcessPoolExecutor for CPU-bound work (bypasses GIL):
    with ProcessPoolExecutor(max_workers=4) as proc_pool:
        result = await loop.run_in_executor(proc_pool, cpu_heavy, 10_000_000)

    # Default executor (None) — ThreadPoolExecutor created by the loop:
    result = await loop.run_in_executor(None, blocking_io, "http://example.com")

asyncio.run(main())
```

**Passing multiple arguments:**
```python
# run_in_executor only accepts fn + *args; use functools.partial for keyword args:
import functools

def connect(host, port, timeout=30):
    ...

await loop.run_in_executor(
    None,
    functools.partial(connect, "localhost", 5432, timeout=10)
)
```

### Running Async Code from Sync Code

**From a sync context with no running event loop:**
```python
import asyncio

async def fetch_data():
    await asyncio.sleep(0.1)
    return {"result": 42}

# asyncio.run() creates a new loop, runs until complete, closes it:
result = asyncio.run(fetch_data())
print(result)  # {'result': 42}

# asyncio.run() CANNOT be called if an event loop is already running
```

**From sync code inside a running event loop (e.g., a sync method called from async):**
```python
# BAD — this deadlocks:
def sync_method_called_from_async():
    result = asyncio.run(some_coroutine())  # RuntimeError: loop already running

# SOLUTION 1: Use nest_asyncio (not for production):
import nest_asyncio
nest_asyncio.apply()
result = asyncio.run(some_coroutine())  # now works, but brittle

# SOLUTION 2: Don't mix — propagate async upward
# If sync_method needs to be called from async, make it async too

# SOLUTION 3: asyncio.get_event_loop().run_until_complete() — deprecated, error-prone

# SOLUTION 4: Use a separate thread with its own event loop:
import threading

def run_async_in_thread(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

result = run_async_in_thread(some_coroutine())
```

### Thread-Safety of asyncio Primitives

**asyncio primitives are NOT thread-safe.** They are designed for single-threaded event loop use. Calling `asyncio.Queue.put_nowait()` from a different thread can corrupt internal state.

```python
import asyncio
import threading

queue = None
loop = None

async def consumer():
    while True:
        item = await queue.get()
        print(f"Got: {item}")

def producer_thread():
    # WRONG — calling asyncio methods from a different thread:
    # queue.put_nowait("item")  # NOT thread-safe

    # CORRECT — use loop.call_soon_threadsafe():
    loop.call_soon_threadsafe(queue.put_nowait, "item")

    # For coroutines from another thread:
    future = asyncio.run_coroutine_threadsafe(some_coroutine(), loop)
    result = future.result(timeout=5)  # blocks calling thread until done

async def main():
    global queue, loop
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    asyncio.create_task(consumer())

    t = threading.Thread(target=producer_thread)
    t.start()
    await asyncio.sleep(1)

asyncio.run(main())
```

**Thread-safe asyncio bridge methods:**

| Method | Use Case |
|--------|----------|
| `loop.call_soon_threadsafe(callback, *args)` | Schedule a sync callback on the event loop from another thread |
| `asyncio.run_coroutine_threadsafe(coro, loop)` | Schedule a coroutine from another thread; returns a `concurrent.futures.Future` |
| `Future.set_result()` from thread | Only via `loop.call_soon_threadsafe(future.set_result, value)` |

### asyncio + threading: The Right Architecture

```python
import asyncio
import threading
from concurrent.futures import Future as ThreadFuture

class AsyncBridge:
    """Runs an asyncio event loop in a background thread, callable from sync code."""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def run(self, coro):
        """Submit a coroutine and block until it completes."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def submit(self, coro):
        """Submit a coroutine and return a concurrent.futures.Future."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def shutdown(self):
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()
        self._loop.close()

bridge = AsyncBridge()

async def async_fetch(url):
    await asyncio.sleep(0.1)
    return f"data from {url}"

# Call async code from sync context:
result = bridge.run(async_fetch("http://api.example.com"))
print(result)

bridge.shutdown()
```

---

## Interview Questions

### Q1: What's wrong with calling `asyncio.run()` from inside a running event loop?

**Model answer:**  
`asyncio.run()` calls `loop.run_until_complete()` which blocks the calling thread until the coroutine finishes. If you're already inside a running event loop (i.e., your sync code was called from an async context), this means:

1. The outer `run_until_complete()` call is blocking the thread.
2. Your inner `asyncio.run()` tries to start or run another loop in the same thread.
3. This either raises `RuntimeError: This event loop is already running` (Python 3.10+) or creates a deadlock.

The correct fix is to propagate `async` up the call stack. If a sync method needs to do async work, make it async. If it absolutely cannot be made async (legacy API boundary), use `asyncio.run_coroutine_threadsafe()` with a loop running in a separate thread.

### Q2: How do you safely call a coroutine from a non-async callback in an asyncio program?

**Model answer:**  
Non-async callbacks (like `add_done_callback`, GUI callbacks, signal handlers) cannot use `await`. The correct approach:

```python
import asyncio

def sync_callback(some_arg):
    # Cannot await here. Schedule on the event loop:
    loop = asyncio.get_event_loop()  # if we have the loop reference
    asyncio.ensure_future(my_coroutine(some_arg), loop=loop)
    # or:
    loop.create_task(my_coroutine(some_arg))

# From ANOTHER thread:
def thread_callback(some_arg):
    asyncio.run_coroutine_threadsafe(my_coroutine(some_arg), event_loop)
```

**Caution with `ensure_future` / `create_task`:** The created task runs concurrently. If the callback is in a tight loop, you can flood the event loop with tasks. Always include backpressure (semaphore, bounded queue) when scheduling tasks from callbacks.

### Q3: What is `loop.call_soon_threadsafe` and why does it exist?

**Model answer:**  
The asyncio event loop is not thread-safe. Its internal ready queue (`_ready`) can be corrupted if two threads write to it concurrently. `call_soon_threadsafe` is the exception:

1. It acquires an internal lock before appending the callback to `_ready`.
2. It then writes a byte to a self-pipe (or calls `IOCP` event on Windows) to wake the event loop if it's sleeping in `select()`.

This is the ONLY safe way to enqueue work on an asyncio event loop from another thread. `queue.put_nowait()` is NOT safe from threads; `loop.call_soon_threadsafe(queue.put_nowait, item)` IS safe.

```python
# Pattern: producer thread feeding an asyncio consumer
async def consumer(q: asyncio.Queue):
    async for item in async_items(q):
        process(item)

def producer_thread(loop, q):
    for item in generate_items():
        loop.call_soon_threadsafe(q.put_nowait, item)
    loop.call_soon_threadsafe(q.put_nowait, None)  # sentinel
```

### Q4: How do you integrate a legacy blocking library (e.g., `requests`) into an async codebase?

**Model answer:**  
Three tiers of increasing correctness:

**Tier 1 — Thread pool (simplest, good enough for most cases):**
```python
import asyncio
import requests
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=20)

async def async_get(url: str) -> dict:
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        _executor, requests.get, url
    )
    response.raise_for_status()
    return response.json()
```

**Tier 2 — Async-native library (best performance, requires rewrite):**
```python
import aiohttp

async def async_get_native(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

**Tier 3 — Dedicated sync-to-async bridge thread (when executor not applicable):**  
For stateful libraries that maintain thread-local connections (some ORMs, some DB drivers), run them in a dedicated single thread with its own event loop, bridge via `asyncio.run_coroutine_threadsafe`.

**Guidance:** Start with tier 1 (thread pool). Move to tier 2 (native async library) when performance profiling shows thread overhead is a bottleneck.

### Q5: Are `asyncio.Lock`, `asyncio.Queue`, etc. usable across threads?

**Model answer:**  
No — all asyncio synchronization primitives (`Lock`, `Event`, `Semaphore`, `Queue`, `Condition`) are designed for use within a single event loop thread. Using them from multiple OS threads without `call_soon_threadsafe` is a data race.

Specifically:
- `asyncio.Lock.acquire()` returns a coroutine that must be awaited — it can only be awaited from within the event loop thread.
- `asyncio.Queue.put_nowait()` is not protected by a thread lock — calling it from another thread is a race condition.

For multi-threaded async interaction:
- Use `loop.call_soon_threadsafe()` or `asyncio.run_coroutine_threadsafe()` to marshal calls onto the event loop thread.
- Use `threading.Queue` to pass data between threads; have the event loop consume from it via `run_in_executor`.
- Use `asyncio.Queue` only within the event loop thread.

---

## Gotcha Follow-ups

**"What happens to asyncio tasks if the event loop is closed while they're still running?"**  
Closing the loop cancels all pending tasks that haven't completed. If tasks have `__aexit__` cleanup (`async with` blocks), those cleanups may not run because cancellation requires the loop to be running to propagate the `CancelledError`. `asyncio.run()` handles this correctly by cancelling pending tasks and running the loop briefly to allow their cleanup before closing. Raw `loop.close()` does not.

**"Can you use `contextvars.ContextVar` across asyncio tasks safely?"**  
Yes — this is one of `ContextVar`'s key design goals. Each `asyncio.Task` gets a **copy** of the current context at creation time (via `copy_context()`). Changes in one task don't affect another task's context, and they don't affect the parent that created them. This is the correct mechanism for per-request state (user ID, trace ID) in async web frameworks — NOT `threading.local()`.

---

## Under the Hood

`asyncio.run_coroutine_threadsafe` implementation:
1. Creates a `concurrent.futures.Future` (thread-safe, unlike `asyncio.Future`).
2. Calls `loop.call_soon_threadsafe(ensure_future, coro, loop=loop)` — schedules `ensure_future` on the loop thread.
3. When `ensure_future` runs (in the loop thread), it creates an `asyncio.Task` and chains it to the `concurrent.futures.Future` via done callbacks.
4. The calling thread blocks on `cf_future.result()`, which uses `threading.Condition.wait()`.

`call_soon_threadsafe` uses a Unix self-pipe trick: the loop is usually blocked in `select()` waiting for I/O. `call_soon_threadsafe` writes one byte to a write-end file descriptor that the loop monitors. This byte wakes the `select()` call, the loop reads and discards the byte, then processes the queued callback.
