# Coroutine Internals: Generators to async/await

## Concept

Python's `async`/`await` is syntactic sugar over generators. Understanding the full chain — generator protocol → coroutine protocol → asyncio's event loop driving coroutines — is essential for diagnosing async bugs and understanding performance characteristics.

### Generators: The Foundation

```python
def gen():
    print("Before first yield")
    value = yield 1           # yields 1 to caller; receives sent value
    print(f"Received: {value}")
    yield 2

g = gen()

# Generators are lazy — nothing runs until next():
result = next(g)              # "Before first yield" printed
print(result)                 # 1

result = g.send("hello")      # resumes after yield; value="hello"
print(result)                 # "Received: hello" printed; 2 returned

try:
    next(g)                   # StopIteration — generator exhausted
except StopIteration:
    pass

# Generator protocol:
# g.__next__() == next(g) — resumes from last yield, sends None
# g.send(value) — resumes, sends value into the yield expression
# g.throw(exc) — resumes, raises exc at the yield point
# g.close() — sends GeneratorExit to the generator
```

### Generator State Machine

```python
import inspect

def stateful():
    x = yield "first"
    y = yield "second"
    return x + y

g = stateful()
print(inspect.getgeneratorstate(g))   # GEN_CREATED

next(g)
print(inspect.getgeneratorstate(g))   # GEN_SUSPENDED

g.send(10)
print(inspect.getgeneratorstate(g))   # GEN_SUSPENDED

try:
    g.send(20)
except StopIteration as e:
    print(e.value)                     # 30 (return value)
    print(inspect.getgeneratorstate(g))  # GEN_CLOSED
```

### `yield from` — Generator Delegation

```python
def inner():
    yield 1
    yield 2
    return "inner done"  # return value goes to yield from expression

def outer():
    result = yield from inner()   # transparently delegates
    print(f"inner returned: {result}")
    yield 3

list(outer())   # [1, 2, 3] — inner done printed

# yield from also forwards send() and throw():
def passthrough():
    return (yield from subgenerator())

# yield from is the mechanism that makes coroutine chaining work
```

### Coroutines: `async def` + `await`

```python
import asyncio

# async def creates a coroutine function; calling it returns a coroutine OBJECT
async def my_coro():
    print("start")
    await asyncio.sleep(0.1)   # suspends this coroutine, lets others run
    print("end")

# Coroutine is NOT started by calling it:
coro = my_coro()    # returns coroutine object, nothing printed yet
print(type(coro))   # <class 'coroutine'>

# Drive it with asyncio:
asyncio.run(coro)   # "start" then "end"

# Under the hood: await foo ≡ yield from foo.__await__()
# asyncio.sleep returns an object with __await__ that yields a Future
```

### The Awaitable Protocol

```python
# An awaitable is anything with __await__() returning an iterator
# The iterator yields Futures or None to the event loop

import asyncio
import inspect

class Sleep:
    """Custom awaitable — equivalent to asyncio.sleep."""

    def __init__(self, delay: float):
        self.delay = delay

    def __await__(self):
        # Yield a Future to the event loop; resume when Future is done
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        loop.call_later(self.delay, future.set_result, None)
        yield future   # event loop receives this Future and waits on it

async def main():
    print("before sleep")
    await Sleep(0.1)   # uses our custom awaitable
    print("after sleep")

asyncio.run(main())

# asyncio.Future is the core: it's what gets yielded up to the event loop.
# The event loop's .run_forever() loop:
# 1. Calls next() on the coroutine
# 2. Receives a Future
# 3. Registers the Future with the selector (epoll/select)
# 4. When FD becomes ready, calls Future.set_result()
# 5. Future.set_result() schedules the coroutine's .send(result) via callbacks
```

### Frame Objects and Coroutine Suspension

```python
import asyncio

async def suspended_coro():
    # Inspect ourselves while suspended
    import sys
    frame = sys._current_frames()
    await asyncio.sleep(0)   # yield to event loop

async def main():
    coro = suspended_coro()
    task = asyncio.ensure_future(coro)

    # Before running: coroutine has a frame in GEN_CREATED state
    print(coro.cr_frame)        # frame object
    print(coro.cr_running)      # False (not currently executing)
    print(coro.cr_await)        # None (not awaiting anything yet)

    await asyncio.sleep(0)      # let suspended_coro start

    # Now it's suspended at await asyncio.sleep(0):
    print(task.get_coro().cr_await)  # asyncio.Task awaiting sleep

# Stack tracing:
async def trace_stack():
    import traceback
    await asyncio.sleep(0)
    # traceback.print_stack() shows: trace_stack → event loop → ...

asyncio.run(main())
```

### Generator-Based Coroutines (Historical — Python 3.4-3.10)

```python
# The original coroutine syntax (still valid but deprecated):
import asyncio

@asyncio.coroutine
def old_coro():
    yield from asyncio.sleep(0.1)
    return "done"

# Modern equivalent:
async def modern_coro():
    await asyncio.sleep(0.1)
    return "done"

# async def is compiled with CO_COROUTINE flag
# @asyncio.coroutine sets CO_ITERABLE_COROUTINE via types.coroutine()
```

---

## Interview Questions

### Q1: How does Python implement `async`/`await` under the hood — what is the relationship to generators?

**Model answer:**
`async def` creates a coroutine function. Calling it returns a coroutine object — essentially a generator with `CO_COROUTINE` flag set in `co_flags`. `await expr` compiles to `GET_AWAITABLE` + `SEND` + `YIELD_VALUE` opcodes — equivalent to `yield from expr.__await__()`.

The execution model:
1. The event loop calls `coroutine.send(None)` to start or resume a coroutine.
2. The coroutine runs until it hits `await`, which eventually yields a `Future` object to the event loop.
3. The event loop registers a callback on the `Future`.
4. When the Future resolves (I/O ready, timer fired, etc.), the event loop calls `coroutine.send(result)`.
5. The coroutine resumes from the `await` point with `result` as the value.

```python
# Equivalent desugaring:
async def f():
    x = await g()

# Approximately equivalent to:
def f():
    x = yield from g().__await__()

# The event loop is a standard Python generator driver:
def run(coro):
    result = None
    try:
        future = coro.send(result)
        # ... register future with selector ...
        # ... when future resolves, loop back and send result ...
    except StopIteration as e:
        return e.value   # coroutine returned
```

### Q2: What is an awaitable and how do you create a custom one?

**Model answer:**
An awaitable is any object with `__await__()` returning an iterator. The iterator yields control to the event loop (by yielding `Future` objects or `None`) and receives results via `send()`.

Three standard awaitables:
1. **Coroutine objects** (from `async def`)
2. **`asyncio.Future`** objects
3. **`asyncio.Task`** (wraps a coroutine, drives it, acts as Future)

Custom awaitable:

```python
class Awaitable:
    def __init__(self, result_value):
        self._result = result_value

    def __await__(self):
        # A "trivial" awaitable that doesn't suspend:
        return iter([])    # empty iterator — no suspension
        yield   # unreachable — makes this a generator (required for yield-based protocol)
        return self._result   # StopIteration.value

# Or using asyncio.Future for actual suspension:
class DelayedResult:
    def __init__(self, value, delay):
        self.value = value
        self.delay = delay

    def __await__(self):
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        loop.call_later(self.delay, future.set_result, self.value)
        result = yield future   # suspend; receive result when future resolves
        return result

async def main():
    result = await DelayedResult("hello", 0.1)
    print(result)   # "hello" after 0.1 seconds
```

### Q3: What is `asyncio.Task` and how does it drive a coroutine?

**Model answer:**
`asyncio.Task` is a thin wrapper around a coroutine that implements the `Future` protocol. It drives the coroutine by chaining callbacks:

1. At creation, `Task.__step()` is scheduled immediately via `loop.call_soon()`.
2. `__step()` calls `coro.send(None)` or `coro.send(result)`.
3. If the coroutine yields a `Future`, `Task` adds itself as a done callback on that `Future` via `future.add_done_callback(self.__step)`.
4. When the `Future` resolves, `__step()` is called again with the result.
5. If `coro.send()` raises `StopIteration`, the coroutine is done — `Task.set_result()` is called.

```python
# Simplified Task implementation:
class SimpleTask:
    def __init__(self, coro, loop):
        self._coro = coro
        self._loop = loop
        self._result = None
        self._done = False
        self._callbacks = []
        loop.call_soon(self.__step)

    def __step(self, exc=None):
        try:
            if exc:
                future = self._coro.throw(type(exc), exc)
            else:
                future = self._coro.send(self._result)
            future.add_done_callback(self.__wakeup)
        except StopIteration as e:
            self._result = e.value
            self._done = True
            for cb in self._callbacks:
                cb(self)

    def __wakeup(self, future):
        try:
            self._result = future.result()
        except Exception as exc:
            self.__step(exc=exc)
        else:
            self.__step()
```

### Q4: What's the difference between `asyncio.gather`, `asyncio.create_task`, and `asyncio.wait`?

**Model answer:**

```python
import asyncio

async def work(n):
    await asyncio.sleep(n)
    return n

# asyncio.gather: run coroutines concurrently, return results in ORDER
results = await asyncio.gather(work(1), work(2), work(3))
print(results)   # [1, 2, 3] — same order as input, not completion order

# asyncio.create_task: schedule coroutine immediately, return Task
# Tasks run concurrently without needing to await them:
t1 = asyncio.create_task(work(1))
t2 = asyncio.create_task(work(2))
r1 = await t1
r2 = await t2

# asyncio.wait: wait for a set of tasks, with timeout and return conditions
done, pending = await asyncio.wait(
    [asyncio.create_task(work(1)), asyncio.create_task(work(5))],
    timeout=2.0,
    return_when=asyncio.FIRST_COMPLETED,
)
for task in done:
    print(task.result())   # only the 1-second task completed
for task in pending:
    task.cancel()

# asyncio.TaskGroup (Python 3.11+): structured concurrency with error propagation
async with asyncio.TaskGroup() as tg:
    t1 = tg.create_task(work(1))
    t2 = tg.create_task(work(2))
# All tasks complete here; exceptions from any task cancel all others
```

Key difference: `gather` is for "I need all results"; `wait` is for "I need some results or timeout"; `TaskGroup` is for structured concurrency with proper cancellation.

### Q5: How does `async for` and `async with` work under the hood?

**Model answer:**

```python
# async for requires __aiter__() and __anext__()
class AsyncRange:
    def __init__(self, n):
        self.n = n
        self.i = 0

    def __aiter__(self):
        return self   # async iterators are their own async iterables

    async def __anext__(self):
        if self.i >= self.n:
            raise StopAsyncIteration   # signals end of async iteration
        await asyncio.sleep(0)        # simulate async work
        val = self.i
        self.i += 1
        return val

async def consume():
    async for val in AsyncRange(3):
        print(val)   # 0, 1, 2

# Desugared:
async def consume_desugared():
    it = AsyncRange(3).__aiter__()
    while True:
        try:
            val = await it.__anext__()
            print(val)
        except StopAsyncIteration:
            break

# async with requires __aenter__() and __aexit__()
class AsyncResource:
    async def __aenter__(self):
        print("acquiring resource")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        print("releasing resource")
        return False   # don't suppress exceptions

async def use_resource():
    async with AsyncResource() as r:
        print("using resource")

# Desugared:
async def use_resource_desugared():
    mgr = AsyncResource()
    resource = await mgr.__aenter__()
    try:
        print("using resource")
    except BaseException as exc:
        if not await mgr.__aexit__(type(exc), exc, exc.__traceback__):
            raise
    else:
        await mgr.__aexit__(None, None, None)
```

---

## Gotcha Follow-ups

**"Why does `asyncio.run(coro)` fail if called from inside a running event loop?"**
`asyncio.run()` creates a NEW event loop and runs it to completion. If called inside a running event loop (e.g., in Jupyter, or in an async function), it raises `RuntimeError: This event loop is already running`. Solution: use `await coro` directly, or `asyncio.create_task(coro)`, or use `nest_asyncio.apply()` in Jupyter. In libraries that must work in both sync and async contexts, expose both `sync_fn()` and `async_fn()` versions.

**"What happens if you forget `await` on a coroutine?"**
The coroutine object is created but never driven — it's immediately garbage-collected. Python 3.8+ emits `RuntimeWarning: coroutine 'X' was never awaited`. The async function appears to run but does nothing. This is one of the most common bugs in async Python code. Solution: always `await` coroutines, or explicitly `asyncio.create_task()` them (and keep a reference to the task to prevent premature GC).

---

## Under the Hood

Coroutine objects are `PyCoroObject` (`Include/cpython/genobject.h`), sharing the same structure as `PyGenObject` (generators) and `PyAsyncGenObject` (async generators). The `CO_COROUTINE` flag in `co_flags` is what distinguishes a coroutine code object from a generator. `await` compiles to `GET_AWAITABLE` (calls `__await__()` and verifies the result is a generator/coroutine) followed by `SEND` (like `yield from` — drives the sub-iterator until StopIteration). The event loop (`asyncio/base_events.py: BaseEventLoop._run_once()`) uses `selectors.select()` on a timeout equal to the next scheduled callback, then processes all ready callbacks. `asyncio.Future` (`asyncio/futures.py`) uses `__await__` returning `self` — when `yield self` is received by the event loop (via `Task.__step`), the Task adds a done callback.
