# contextvars: Async-Safe Request State

## Concept

`contextvars` (Python 3.7+, PEP 567) provides context-local storage that works correctly with `asyncio`, threads, and `concurrent.futures`. It replaces `threading.local()` for async code, where thread-local storage is shared across coroutines on the same thread.

### Why `threading.local()` Fails in Async Code

```python
import threading, asyncio

request_id = threading.local()

async def handler(rid: str):
    request_id.value = rid         # set on the thread-local
    await asyncio.sleep(0)         # yield control — another coroutine runs on SAME thread
    print(request_id.value)        # may see a DIFFERENT coroutine's value!

async def main():
    await asyncio.gather(
        handler("req-1"),
        handler("req-2"),
        handler("req-3"),
    )
    # Output is unpredictable — all three share the same thread-local!

asyncio.run(main())
```

Multiple coroutines interleave on a single thread. Thread-local storage is shared across all coroutines running on that thread.

### `ContextVar` — The Correct Solution

```python
from contextvars import ContextVar, copy_context

request_id: ContextVar[str] = ContextVar('request_id', default='<none>')

async def handler(rid: str):
    token = request_id.set(rid)     # set for this coroutine's context
    try:
        await asyncio.sleep(0)      # safe — context is per-coroutine
        print(request_id.get())     # always the value this coroutine set
    finally:
        request_id.reset(token)     # restore previous value

async def main():
    await asyncio.gather(
        handler("req-1"),
        handler("req-2"),
        handler("req-3"),
    )
    # Prints req-1, req-2, req-3 in some order, each correctly isolated
```

### How `contextvars` Works

Each `asyncio.Task` carries a copy of the context at the moment it was created. When the task runs, it uses its own context snapshot. Setting a `ContextVar` within a task only affects that task's context.

```python
from contextvars import ContextVar, copy_context, Context

var: ContextVar[int] = ContextVar('var', default=0)
var.set(10)

# copy_context() snapshots current context:
ctx: Context = copy_context()

var.set(99)   # change in current context

# Run in the snapshot:
def read_var():
    return var.get()

result = ctx.run(read_var)   # runs in the copied context where var=10
print(result)     # 10 — not 99
print(var.get())  # 99 — current context unchanged by ctx.run()
```

### Token: Reversible Set

`ContextVar.set()` returns a `Token` that can reset the variable to its previous state:

```python
var: ContextVar[str] = ContextVar('var', default='default')

token1 = var.set('first')
print(var.get())   # 'first'

token2 = var.set('second')
print(var.get())   # 'second'

var.reset(token2)
print(var.get())   # 'first' — restored to value before token2

var.reset(token1)
print(var.get())   # 'default' — restored to value before token1
```

**Important:** tokens must be reset in LIFO order — they track the previous value, not a global history.

### Practical Pattern: Request Context Middleware

```python
from contextvars import ContextVar
from dataclasses import dataclass, field
import uuid

@dataclass
class RequestContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int | None = None
    trace_spans: list = field(default_factory=list)

_request_context: ContextVar[RequestContext] = ContextVar('request_context')

def get_context() -> RequestContext:
    return _request_context.get()

# ASGI/FastAPI middleware:
async def request_context_middleware(request, call_next):
    ctx = RequestContext(
        request_id=request.headers.get('X-Request-ID', str(uuid.uuid4()))
    )
    token = _request_context.set(ctx)
    try:
        response = await call_next(request)
        return response
    finally:
        _request_context.reset(token)

# Anywhere in the request lifecycle:
async def some_service():
    ctx = get_context()
    logger.info("Processing", extra={"request_id": ctx.request_id})
```

### Context Propagation in `asyncio.create_task`

```python
import asyncio
from contextvars import ContextVar

tenant_id: ContextVar[str] = ContextVar('tenant_id')

async def background_job():
    # Inherits the context from where create_task was called:
    print(f"Background: tenant={tenant_id.get()}")

async def main():
    tenant_id.set("acme-corp")
    task = asyncio.create_task(background_job())   # copies current context
    tenant_id.set("other-corp")   # change in main — doesn't affect task
    await task
    # Background: tenant=acme-corp  (inherited from set() before create_task)

asyncio.run(main())
```

### Using `contextvars` with `ThreadPoolExecutor`

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

tenant_id: ContextVar[str] = ContextVar('tenant_id')

async def async_main():
    tenant_id.set("acme")

    loop = asyncio.get_event_loop()
    ctx = copy_context()   # snapshot before submitting to thread pool

    def blocking_work():
        # context NOT automatically propagated to threads:
        return tenant_id.get()   # raises LookupError without ctx.run()

    def blocking_work_with_ctx():
        return ctx.run(lambda: tenant_id.get())   # correct!

    result = await loop.run_in_executor(None, blocking_work_with_ctx)
    print(result)   # "acme"
```

---

## Interview Questions

### Q1: Why doesn't `threading.local()` work in asyncio, and what's the correct replacement?

**Model answer:**
`threading.local()` creates per-thread storage. In asyncio, all coroutines run on the same event loop thread (single-threaded by default). Multiple coroutines interleave their execution on that thread, so they all share the same `threading.local()` value:

```
Thread 1: coroutine A sets request_id = "A"
         coroutine A awaits → yields control
Thread 1: coroutine B sets request_id = "B"
         coroutine B awaits → yields control  
Thread 1: coroutine A resumes → reads request_id → gets "B" ← WRONG!
```

`ContextVar` is the solution because each `asyncio.Task` has its own copy of the context. Setting a `ContextVar` inside a coroutine only affects that coroutine's task context, not other tasks:

```python
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar('request_id')

async def handler(rid: str):
    request_id.set(rid)         # sets only in this task's context
    await asyncio.sleep(0)      # other tasks run but don't see our value
    assert request_id.get() == rid  # always True
```

### Q2: How does context propagation work when creating async tasks?

**Model answer:**
When `asyncio.create_task(coro)` is called, it snapshots the **current context** via `copy_context()` and attaches it to the new task. The task then runs within this copied context. Subsequent changes to the parent's context don't affect the task, and vice versa:

```python
from contextvars import ContextVar
import asyncio

user: ContextVar[str] = ContextVar('user')

async def child():
    await asyncio.sleep(0.01)
    print(f"child sees: {user.get()}")   # sees 'alice' — from task creation time

async def parent():
    user.set('alice')
    task = asyncio.create_task(child())  # snapshot: user='alice'
    user.set('bob')                       # change parent context
    print(f"parent sees: {user.get()}")  # 'bob'
    await task
    # child sees: alice — not affected by parent's change to 'bob'

asyncio.run(parent())
```

This is the correct behavior for request-scoped data: a task inherits the context of its creator (e.g., the request that spawned it) and isolation is maintained.

### Q3: What is `ContextVar.reset(token)` and why is it important?

**Model answer:**
`set()` returns a `Token` representing the previous value. `reset(token)` restores the variable to that previous value. This is crucial for:

1. **Middleware patterns:** set context at request start, reset at end — even if an exception occurs.
2. **Nested context managers:** avoid leaking context changes to callers.
3. **Testing:** restore clean state after each test.

```python
from contextvars import ContextVar
from contextlib import contextmanager

user_id: ContextVar[int | None] = ContextVar('user_id', default=None)

@contextmanager
def as_user(uid: int):
    token = user_id.set(uid)
    try:
        yield
    finally:
        user_id.reset(token)   # always restore, even on exception

with as_user(42):
    assert user_id.get() == 42
    with as_user(99):
        assert user_id.get() == 99
    assert user_id.get() == 42   # restored

assert user_id.get() is None   # fully restored
```

**Do not** call `reset()` out of order — it raises `ValueError: <Token var=... at ...> was created by a different ContextVar` or corrupts the context if you reset a token from a different variable.

### Q4: How do you pass context from an async environment to a thread pool?

**Model answer:**
Thread pool executors do NOT automatically propagate `ContextVar` context. You must explicitly copy and run within the snapshot:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context

request_id: ContextVar[str] = ContextVar('request_id')

async def process_async():
    request_id.set("REQ-123")

    # WRONG: context not propagated to thread
    def blocking_bad():
        return request_id.get()   # LookupError!

    # CORRECT: snapshot context and run within it
    ctx = copy_context()
    def blocking_good():
        return ctx.run(request_id.get)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, blocking_good)

    print(result)   # "REQ-123"
```

Note: `asyncio.to_thread()` (Python 3.9+) automatically propagates the current context to the thread — use it instead of `run_in_executor` when possible:

```python
result = await asyncio.to_thread(blocking_function)
# asyncio.to_thread copies context automatically
```

### Q5: How does `ContextVar` interact with `concurrent.futures.ProcessPoolExecutor`?

**Model answer:**
Processes don't share memory — `ContextVar` values must be serialized (pickled) and sent to the worker process. The worker process has its own independent context.

`ProcessPoolExecutor` spawns new processes: the `ContextVar` is not automatically available. You must pass values explicitly through function arguments:

```python
from concurrent.futures import ProcessPoolExecutor
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar('request_id')

def worker(rid: str, data: list) -> int:
    # Can't access ContextVar from parent — must receive as argument
    # Optionally: set it in the child if worker code uses ContextVar internally
    token = request_id.set(rid)
    try:
        return sum(data)
    finally:
        request_id.reset(token)

async def main():
    request_id.set("REQ-456")
    rid = request_id.get()   # get the value to pass explicitly

    with ProcessPoolExecutor() as pool:
        future = pool.submit(worker, rid, [1, 2, 3])
        result = future.result()
```

---

## Gotcha Follow-ups

**"Is `ContextVar.get()` thread-safe?"**
Yes. `ContextVar` operations are thread-safe. Each thread has its own context (just as each task does). Changes in one thread don't affect others. The thread-level isolation is the same as `threading.local()` — but additionally, each `asyncio.Task` within a thread has its own context.

**"What happens to ContextVar when `asyncio.run()` returns?"**
`asyncio.run()` creates a new event loop and a new context for the top-level coroutine. When it returns, the event loop and its context are destroyed. ContextVar values set inside `asyncio.run()` are not visible outside. Each `asyncio.run()` call gets a fresh context.

---

## Under the Hood

`ContextVar` is implemented in `Python/context.c` (`_PyContext`, `_PyContextVar`). Each thread and each asyncio `Task` has a `PyContext*` pointer — a copy-on-write immutable mapping from `ContextVar` objects to their values. `ContextVar.set()` creates a new context object (via `_PyContext_CopyCurrent()` if modified, otherwise same pointer) with the new binding. `copy_context()` returns a shallow copy. The copy-on-write mechanism means copying is O(1) until a write occurs. Tasks hold their context reference in `Task._context`.
