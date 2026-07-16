# asyncio Internals

## Concept

`asyncio` provides single-threaded cooperative concurrency via an **event loop** that schedules coroutines. Unlike threads (preemptive, GIL-managed), asyncio coroutines voluntarily yield control at `await` expressions, allowing other coroutines to run.

### The Event Loop

The event loop is the scheduler. Its main loop:
1. Run all ready callbacks (coroutines that can proceed, scheduled calls).
2. Poll I/O readiness (via `select`/`epoll`/`kqueue`) for registered file descriptors.
3. Process I/O events — mark associated futures as done, schedule their callbacks.
4. Repeat.

```python
import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# High-level entry point (Python 3.11+):
asyncio.run(main())  # creates a fresh event loop, runs until main() completes, closes loop

# Access the running loop from inside a coroutine:
async def get_loop():
    loop = asyncio.get_running_loop()
    return loop
```

### Coroutine, Task, Future — The Three Abstractions

```python
import asyncio

# 1. Coroutine object — not scheduled; just a generator-like object
async def greet(name):
    await asyncio.sleep(0.1)
    return f"Hello, {name}"

coro = greet("Alice")   # coroutine OBJECT — nothing runs yet
print(type(coro))       # <class 'coroutine'>

# 2. Task — a coroutine scheduled on the event loop; runs concurrently
async def main():
    task = asyncio.create_task(greet("Bob"))  # scheduled immediately
    result = await task                        # wait for completion
    print(result)

# 3. Future — a low-level placeholder for a result that doesn't exist yet
async def future_demo():
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    async def set_result():
        await asyncio.sleep(0.1)
        future.set_result(42)

    asyncio.create_task(set_result())
    result = await future   # waits until future.set_result() is called
    print(result)           # 42

asyncio.run(future_demo())
```

**Hierarchy:** `Task` subclasses `Future`. Both implement `__await__`. A `coroutine` is awaited by wrapping in a `Task` via `create_task()`.

### How `await` Suspends and Resumes

```python
async def slow_io():
    await asyncio.sleep(1)  # suspends this coroutine
    return "done"

# What actually happens:
# 1. asyncio.sleep(1) creates a Future and schedules a callback for 1s later
# 2. The Future's __await__ yields control back to the event loop
# 3. The event loop runs other ready coroutines
# 4. After 1s, the callback fires: future.set_result(None)
# 5. The awaiting coroutine is rescheduled (added to ready queue)
# 6. slow_io() resumes after the await, returns "done"
```

The `await` expression compiles to bytecode that calls `__await__()` on the awaitable, then runs the generator protocol (`send()` / `throw()`) to advance the coroutine. When the inner awaitable yields (suspends), the suspension propagates up the call stack to the event loop's scheduler.

### `asyncio.gather` vs `asyncio.TaskGroup`

```python
import asyncio

async def fetch(url: str) -> str:
    await asyncio.sleep(0.1)
    if "bad" in url:
        raise ValueError(f"Bad URL: {url}")
    return f"data from {url}"

# gather() — all start concurrently; if any raises, gather raises immediately
# (others continue running unless return_exceptions=True)
async def with_gather():
    try:
        results = await asyncio.gather(
            fetch("http://api1.com"),
            fetch("http://api2.com"),
            fetch("http://bad.com"),
            return_exceptions=True  # return exceptions as values, don't raise
        )
        for r in results:
            if isinstance(r, Exception):
                print(f"Error: {r}")
            else:
                print(f"OK: {r}")
    except Exception:
        pass

# TaskGroup (Python 3.11+) — structured concurrency; all tasks in the group
# are cancelled if any raises; waits for all to finish before raising
async def with_task_group():
    try:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(fetch("http://api1.com"))
            t2 = tg.create_task(fetch("http://api2.com"))
            t3 = tg.create_task(fetch("http://bad.com"))
        # If any task raises, ALL tasks are cancelled, then ExceptionGroup is raised
    except* ValueError as eg:
        print(f"Value errors: {eg.exceptions}")

asyncio.run(with_task_group())
```

**`TaskGroup` is the preferred pattern** (Python 3.11+): it enforces structured concurrency — you can't "leak" tasks that outlive their group, and exceptions cancel the group cleanly.

### Cancellation Semantics

```python
import asyncio

async def long_operation():
    try:
        await asyncio.sleep(10)
        return "done"
    except asyncio.CancelledError:
        print("Cancelled! Cleaning up...")
        # Do cleanup here, then:
        raise  # MUST re-raise CancelledError — do not swallow it

async def main():
    task = asyncio.create_task(long_operation())
    await asyncio.sleep(0.5)
    task.cancel()  # sends CancelledError into the task at the next await
    try:
        await task
    except asyncio.CancelledError:
        print("Task was cancelled")

asyncio.run(main())
```

**Cancellation rules:**
1. `task.cancel()` schedules a `CancelledError` to be thrown into the task at its next `await` point.
2. The coroutine MUST re-raise `CancelledError` after cleanup. Swallowing it silently prevents cancellation from propagating.
3. `asyncio.shield(coro)` protects a coroutine from cancellation — cancellation hits the shield, not the inner coroutine.

```python
# Protecting critical cleanup from cancellation:
async def critical_save():
    await asyncio.shield(write_to_db())  # write_to_db won't be cancelled even if task is

# With TaskGroup: cancelling the group cancels all tasks in it
```

---

## Interview Questions

### Q1: Explain what happens at the C level when `await asyncio.sleep(1)` executes.

**Model answer:**  

1. `asyncio.sleep(1)` creates a `TimerHandle` (a delayed callback scheduled via `loop.call_later(1, future.set_result, None)`) and returns a `Future` object whose `__await__` is a generator.

2. The `await` expression calls `future.__await__().__next__()`, which hits a `yield` statement inside the Future's `__await__` implementation. This yields a reference to the Future itself back to the calling coroutine's driver.

3. The calling coroutine's `Task.__step()` receives the yielded Future, registers itself as a callback on that Future (`future.add_done_callback(task.__step)`), and returns control to the event loop.

4. The event loop continues running — polling for I/O, running other ready tasks.

5. After 1 second, the `TimerHandle` fires: `future.set_result(None)` is called, which invokes `task.__step()` as a done callback.

6. `task.__step()` calls `coro.send(None)` on the coroutine, resuming it after the `yield` point inside `Future.__await__`. The coroutine proceeds past `await asyncio.sleep(1)`.

### Q2: What is the difference between `asyncio.gather` and `asyncio.TaskGroup`? When does `gather` leak tasks?

**Model answer:**  

`asyncio.gather()`:
- Schedules all awaitables concurrently.
- If one raises and `return_exceptions=False`, it raises immediately — but the other tasks keep running in the background with no reference to them (they become "detached"). This is the task leak.
- No structured lifetime guarantee.

`asyncio.TaskGroup` (Python 3.11+):
- Implements **structured concurrency** — all tasks in the group are cancelled if any raises.
- `async with` block waits for ALL tasks (including those that finished before the exception) before propagating the exception as `ExceptionGroup`.
- Tasks cannot outlive the group — prevents leaks.

```python
# Leak example with gather:
async def main():
    result = await asyncio.gather(
        fetch("good"),
        fetch("bad"),  # raises immediately
        return_exceptions=False
    )
# The "good" task may still be running! No way to await it now.

# TaskGroup prevents this:
async with asyncio.TaskGroup() as tg:
    t1 = tg.create_task(fetch("good"))
    t2 = tg.create_task(fetch("bad"))
# Both tasks are cancelled and awaited before exiting the with block
```

### Q3: How does `asyncio` handle CPU-bound code? Why does `await` not help?

**Model answer:**  
`asyncio` is single-threaded. If a coroutine executes CPU-bound Python code without an `await` point, it blocks the event loop entirely — no other coroutines run, no I/O is processed.

```python
async def blocking_cpu():
    result = 0
    for i in range(100_000_000):  # blocks event loop for seconds
        result += i
    return result
```

Fix: run CPU-bound code in a thread or process pool via `loop.run_in_executor()`:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

def cpu_work(n):
    return sum(range(n))

async def main():
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, cpu_work, 100_000_000)
    print(result)

asyncio.run(main())
```

`run_in_executor(None, fn, *args)` uses the default `ThreadPoolExecutor` (sufficient for GIL-releasing I/O wrappers; not for pure Python CPU work). Use `ProcessPoolExecutor` for CPU-bound work.

### Q4: What is `asyncio.shield()` and when do you need it?

**Model answer:**  
`asyncio.shield(coro)` wraps a coroutine in a protected Future. If the outer awaiter is cancelled, `CancelledError` is thrown into the shield's wrapper, not into the inner coroutine. The inner coroutine continues running.

```python
async def critical_write(data):
    await db.execute("INSERT INTO ...", data)  # must not be interrupted

async def handler(request):
    try:
        response_data = await process(request)
        # Even if this handler's task is cancelled, the write completes:
        await asyncio.shield(critical_write(response_data))
    except asyncio.CancelledError:
        # Handler was cancelled, but critical_write is still running
        raise
```

**Caution:** `shield` doesn't prevent cancellation; it just redirects it. If you discard the shield's future without awaiting it, the inner task becomes a background task that may raise unhandled exceptions. Always await or handle the shielded future.

### Q5: Explain `async for` and `async with` — what protocols do they use?

**Model answer:**  

**`async with`** uses the async context manager protocol:
- `__aenter__(self)` — coroutine called on entry; must be `async def`
- `__aexit__(self, exc_type, exc_val, tb)` — coroutine called on exit

```python
class AsyncResource:
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

async def use():
    async with AsyncResource() as r:
        await r.do_work()
```

**`async for`** uses the async iterable/iterator protocol:
- `__aiter__(self)` — returns an async iterator (can be synchronous)
- `__anext__(self)` — coroutine that returns next value or raises `StopAsyncIteration`

```python
class AsyncCounter:
    def __init__(self, stop):
        self.current = 0
        self.stop = stop

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.current >= self.stop:
            raise StopAsyncIteration
        self.current += 1
        await asyncio.sleep(0)  # yield control between items
        return self.current

async def main():
    async for n in AsyncCounter(5):
        print(n)  # 1, 2, 3, 4, 5
```

`asyncio.Queue.get()` is a common async iterator source; async generators (`async def` with `yield`) automatically implement this protocol.

---

## Gotcha Follow-ups

**"What happens if you `await` a coroutine from a non-async function?"**  
You can't — `await` is only valid inside `async def`. Calling `asyncio.run(coro)` from sync code creates a new event loop, runs the coroutine to completion, and returns the result. But `asyncio.run()` cannot be called from inside a running event loop. For this case, use `asyncio.get_event_loop().run_until_complete(coro)` (deprecated pattern) or `asyncio.ensure_future()` / `loop.create_task()` if you have access to the loop.

**"Is asyncio truly concurrent? Can two coroutines run at the same time?"**  
No — asyncio is single-threaded. At any instant, only one coroutine is executing. "Concurrency" means coroutines can be in-progress simultaneously (interleaved), but not parallel. Two coroutines can both be waiting for I/O at the same time; while both are suspended, the event loop handles other things. True parallelism requires multiple OS threads or processes.

---

## Under the Hood

The event loop's I/O polling uses `selectors.DefaultSelector`, which maps to `epoll` on Linux, `kqueue` on macOS, and `IOCP` on Windows. A `Task` is a subclass of `Future` that holds a reference to a coroutine object and implements `__step()` — the method that drives the coroutine via `coro.send(value)` or `coro.throw(exc)`. When a coroutine awaits a Future, `Task.__step()` registers itself as a done callback on that Future. When the Future is resolved, the callback schedules `Task.__step()` via `loop.call_soon()`, which adds it to the ready queue.

The bytecode for `await expr` is `GET_AWAITABLE` + `SEND` (in Python 3.12+) or `YIELD_FROM` (older). In 3.12, coroutines got dedicated opcodes (`RESUME`, `SEND`, `YIELD_VALUE`) that are distinct from the generator opcodes, enabling better stack trace display and optimization.
