# Coroutine Internals: Generators to async/await

## Concept

Python's `async`/`await` is built directly on top of generators. Understanding how generators work at the protocol level explains how coroutines work, what `send()` and `throw()` do, and why cancellation in asyncio propagates the way it does.

### Generator Protocol

```python
def counter(start=0):
    value = start
    while True:
        received = yield value   # yield suspends AND can receive a value
        if received is not None:
            value = received
        else:
            value += 1

gen = counter(10)

print(next(gen))       # 10 — primes the generator (advances to first yield)
print(next(gen))       # 11 — resumes with implicit send(None)
print(gen.send(100))   # 100 — sends 100 as the result of yield; received = 100
print(gen.send(None))  # 101 — normal increment
gen.throw(ValueError, "stop")  # throws exception at the current yield point
gen.close()            # throws GeneratorExit
```

**The three suspension/resumption operations:**
- `next(gen)` ≡ `gen.send(None)` — resume, yield's expression evaluates to `None`
- `gen.send(value)` — resume, yield's expression evaluates to `value`
- `gen.throw(ExcType, value, tb)` — throw an exception at the current yield point
- `gen.close()` — throw `GeneratorExit` (generator should not yield again)

### `yield from` — The Bridge

`yield from iterable` delegates to another generator or iterable, transparently forwarding `send()` and `throw()` calls:

```python
def inner():
    x = yield 1
    print(f"inner received: {x}")
    return "inner result"

def outer():
    result = yield from inner()   # delegates to inner, forwards send/throw
    print(f"inner returned: {result}")
    yield 2

gen = outer()
print(next(gen))       # 1 — from inner's yield
print(gen.send(42))    # "inner received: 42", "inner returned: inner result", then 2
```

`yield from` enables coroutine chaining. When `inner()` returns, the return value becomes the result of `yield from inner()` in `outer`. This is the mechanism that `asyncio` uses to chain coroutines through `await`.

### How `async def` / `await` Maps to Generators

`async def` + `await` is syntactic sugar over `yield from`:

```python
# These are conceptually equivalent (simplified):

# Generator-based coroutine (pre-3.5 asyncio pattern):
@asyncio.coroutine
def old_style():
    result = yield from asyncio.sleep(1)
    return result

# async/await (post-3.5):
async def new_style():
    result = await asyncio.sleep(1)  # await ≡ yield from (for awaitable objects)
    return result
```

Under the hood:
- `async def` creates a coroutine object with `CO_COROUTINE` flag (not `CO_GENERATOR`).
- `await expr` calls `expr.__await__()` to get an iterator, then does `yield from` on it.
- `asyncio.Task.__step()` drives the coroutine via `coro.send(None)` and `coro.throw(exc)`.

### `send()` / `throw()` / `close()` Internals

```python
import asyncio
import sys

async def example():
    try:
        value = await some_future
    except asyncio.CancelledError:
        print("Cancelled! Cleaning up...")
        raise  # must re-raise

# When task.cancel() is called:
# 1. task.cancel() sets a cancellation flag
# 2. At the next iteration, asyncio calls coro.throw(CancelledError)
# 3. The CancelledError is thrown at the current await point
# 4. Propagates up through yield from chains to the coroutine's try/except

# Manual demonstration:
async def waiter():
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        print("Got CancelledError via throw()")
        raise

async def main():
    task = asyncio.create_task(waiter())
    await asyncio.sleep(0)  # let waiter start
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Task cancelled")

asyncio.run(main())
```

### StopIteration vs StopAsyncIteration

```python
# Regular generator — signals completion via StopIteration:
def gen():
    yield 1
    # implicit: raise StopIteration (or "return" becomes StopIteration(return_value))

g = gen()
next(g)  # 1
next(g)  # raises StopIteration

# Async iterator — signals completion via StopAsyncIteration:
class AsyncRange:
    def __init__(self, n):
        self.n = n
        self.current = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.current >= self.n:
            raise StopAsyncIteration  # NOT StopIteration
        self.current += 1
        return self.current

# PEP 479 (Python 3.7+): StopIteration raised inside a coroutine/generator
# is CONVERTED to RuntimeError to prevent accidental silent termination
async def bad_coroutine():
    raise StopIteration("oops")  # RuntimeError: StopIteration raised in coroutine
```

### Generator Frame Suspension

```python
import sys

def inspect_generator():
    gen = (i for i in range(3))
    
    next(gen)
    frame = gen.gi_frame
    print(f"Generator suspended at line: {frame.f_lineno}")
    print(f"Generator locals: {frame.f_locals}")
    print(f"gi_suspended: {gen.gi_suspended}")  # Python 3.12+
    
    next(gen)
    print(f"After second next, frame: {gen.gi_frame}")  # still active
    
    list(gen)  # exhaust
    print(f"Exhausted, frame: {gen.gi_frame}")  # None — frame released

inspect_generator()
```

---

## Interview Questions

### Q1: Explain the relationship between Python generators and async/await at the protocol level.

**Model answer:**  
`async def` / `await` is syntactic sugar over the generator protocol, with a few key differences:

| | Generator (`def` + `yield`) | Coroutine (`async def` + `await`) |
|-|------------------------------|----------------------------------|
| Flag | `CO_GENERATOR` | `CO_COROUTINE` |
| Advance | `next(g)` or `g.send(None)` | `coro.send(None)` via Task |
| Delegate | `yield from iterable` | `await awaitable` (calls `__await__()`) |
| Exception | `g.throw(exc)` | `task.cancel()` → `coro.throw(CancelledError)` |
| Completion | `StopIteration(value)` | `StopIteration(value)` (caught by Task) |

The asyncio `Task` is essentially a driver loop that:
1. Calls `coro.send(None)` to advance the coroutine.
2. The coroutine `yield`s a Future (via `await future`'s `__await__` → `yield self`).
3. Task registers itself as a done callback on the Future.
4. When the Future resolves, Task calls `coro.send(result)`.
5. If the Future raised, Task calls `coro.throw(exc)`.
6. When `StopIteration` is raised, the coroutine is done; Task sets its own result.

`await` compiles to `GET_AWAITABLE` + `SEND` opcodes (3.12+), which implement `yield from` semantics but with additional checks (the object must have `__await__`, and that must return an iterator with `CO_ITERABLE_COROUTINE` flag or similar).

### Q2: What happens if a generator's `close()` is not called? Is it a resource leak?

**Model answer:**  
If a generator object is garbage collected without being closed, Python calls `close()` automatically via the generator's `tp_finalize`. `close()` throws `GeneratorExit` into the generator, allowing it to clean up `try/finally` blocks.

```python
def with_cleanup():
    try:
        while True:
            yield
    finally:
        print("Cleaned up!")

gen = with_cleanup()
next(gen)
del gen   # triggers tp_finalize → gen.close() → "Cleaned up!" printed
```

**However:** In CPython with reference counting, `del gen` immediately calls `tp_finalize` (synchronous). In other runtimes (PyPy) or with reference cycles, cleanup may be delayed until GC. Code relying on generator cleanup for resource management is fragile.

**Best practice:** Explicitly close generators when done with them:
```python
gen = my_generator()
try:
    for item in gen:
        process(item)
finally:
    gen.close()  # explicit cleanup

# Or use contextlib.closing:
from contextlib import closing
with closing(my_generator()) as gen:
    for item in gen:
        process(item)
```

### Q3: What is `PEP 479` and why does it matter?

**Model answer:**  
**PEP 479** (Python 3.7+, was `__future__` in 3.5-3.6) changed how `StopIteration` behaves inside generators and coroutines.

**Before PEP 479:** If `StopIteration` was raised inside a generator (accidentally or intentionally), it would silently terminate the generator:
```python
def gen(it):
    for x in it:
        next(it)  # accidentally exhausts iterator: StopIteration silently ends gen
        yield x
```

This caused extremely hard-to-debug bugs where exceptions were accidentally swallowed.

**After PEP 479:** `StopIteration` raised inside a generator is converted to `RuntimeError: generator raised StopIteration`. This makes the bug visible instead of silently incorrect.

For coroutines, `StopAsyncIteration` raised inside an `async for` loop's `__anext__` is the correct way to signal async iteration end. `StopIteration` inside a coroutine raises `RuntimeError`.

**Interview significance:** Shows understanding of how the generator protocol interacts with exception handling and why Python's async model requires `StopAsyncIteration` instead of `StopIteration`.

### Q4: What does `gen.throw()` do and how is it used in asyncio cancellation?

**Model answer:**  
`gen.throw(ExcType, value=None, traceback=None)` throws an exception into the generator at its current suspension point (the `yield` expression). If the generator catches it and yields again, `throw()` returns the yielded value. If the exception propagates out of the generator, `throw()` re-raises it.

In asyncio:
1. `task.cancel()` sets `_must_cancel = True` on the Task.
2. At the next `__step()` call, Task calls `coro.throw(CancelledError())`.
3. `CancelledError` is thrown at the current `await` point in the coroutine.
4. If the coroutine has a `try/except CancelledError`, it can run cleanup.
5. The coroutine MUST re-raise `CancelledError` — swallowing it makes cancellation invisible and breaks structured concurrency.

```python
import asyncio

async def careful():
    async with some_async_resource() as r:
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            await r.flush()    # cleanup before cancellation
            raise              # MUST re-raise

# asyncio.shield() prevents throw() from reaching the inner coroutine:
async def protected():
    try:
        result = await asyncio.shield(careful())
    except asyncio.CancelledError:
        # careful() was NOT cancelled; only the shield wrapper was
        pass
```

### Q5: How do async generators work? What protocol do they implement?

**Model answer:**  
Async generators combine `async def` with `yield`. They implement `__aiter__` and `__anext__` automatically:

```python
async def async_range(n: int):
    for i in range(n):
        await asyncio.sleep(0)  # can await inside
        yield i                  # AND yield

async def main():
    async for value in async_range(5):
        print(value)

# What it compiles to protocol-wise:
class _AsyncRange:
    def __init__(self, n):
        self._n = n
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= self._n:
            raise StopAsyncIteration
        await asyncio.sleep(0)
        result = self._i
        self._i += 1
        return result
```

Key differences from regular generators:
- `yield` in an `async def` creates an async generator (not a coroutine).
- You cannot `await` an async generator directly — use `async for`.
- Closing an async generator calls `aclose()`, which throws `GeneratorExit` asynchronously.
- Finalization: `sys.set_asyncgen_hooks()` lets the event loop manage async generator cleanup.

```python
# Async generator with cleanup:
async def resource_generator():
    resource = acquire()
    try:
        for item in resource.items():
            await asyncio.sleep(0)
            yield item
    finally:
        await resource.aclose()  # async cleanup on .aclose() call
```

---

## Gotcha Follow-ups

**"What happens if you raise `StopIteration` inside a `try/finally` block in a generator?"**  
In Python 3.7+ (PEP 479), `StopIteration` inside a generator is converted to `RuntimeError`. This `RuntimeError` propagates normally — the `finally` block runs (as always with exceptions), and then the `RuntimeError` propagates out. The generator terminates with an exception. This is usually a bug: something called `next()` on an iterator and got a `StopIteration`, which escaped into the generator body.

**"Can you use `send()` on the first call to a generator?"**  
Only `send(None)` is valid as the first call (equivalent to `next()`). `send(non_None_value)` on an un-started generator raises `TypeError: can't send non-None value to a just-started generator`. This is because there's no `yield` expression that has suspended to receive the value — the generator hasn't run at all yet. The standard pattern for generators that need to receive an initial value is to call `next(gen)` once to prime it (advance to the first `yield`), then use `send()`.

---

## Under the Hood

Generator objects are `PyGenObject` in `Objects/genobject.c`. Key fields:
- `gi_frame` — the suspended `_PyInterpreterFrame`
- `gi_code` — the code object
- `gi_yieldfrom` — the object currently delegated to via `yield from` (non-NULL when inside `yield from`)

`gen.send(value)` calls `_gen_send_ex()`:
1. If `gi_frame` is NULL: generator is exhausted, raise `StopIteration`.
2. If generator is already running (recursive `next()`): raise `ValueError`.
3. Sets `gi_frame.localsplus[-1]` (the pending value slot) to `value`.
4. Calls `_PyEval_EvalFrameDefault(frame)`.
5. When the frame yields, the yielded value is returned.
6. When the frame returns (coroutine completes), `StopIteration(return_value)` is raised.

Coroutines (`PyCoroObject`) and async generators (`PyAsyncGenObject`) share the same underlying structure via a common header.
