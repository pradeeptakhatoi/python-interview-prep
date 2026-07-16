# Context Managers and ExitStack

## Concept

Context managers formalize the acquire/release pattern for resources. `with` guarantees cleanup even under exceptions — but the protocol has subtleties around exception suppression, re-entrance, and composing multiple resources dynamically.

### The Protocol: `__enter__` and `__exit__`

```python
class ManagedResource:
    def __enter__(self):
        self.acquire()
        return self   # what `as target` binds to

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        # Return True to SUPPRESS the exception; False/None to propagate
        return False

with ManagedResource() as res:
    res.do_work()
# release() called whether or not do_work() raised
```

`__exit__` is called with:
- `(None, None, None)` — no exception.
- `(type, value, traceback)` — an exception was active.

Returning a truthy value suppresses the exception; the `with` block exits normally.

### `@contextmanager` — Generator-Based Context Manager

```python
from contextlib import contextmanager
import time

@contextmanager
def timer(label: str):
    start = time.perf_counter()
    try:
        yield   # control transfers to the `with` body
    finally:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed*1000:.2f}ms")

with timer("my operation"):
    # do work
    time.sleep(0.1)
# Prints: my operation: 100.3ms

# With a yielded value (the 'as' target):
@contextmanager
def managed_temp_file(suffix: str = '.tmp'):
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        os.close(fd)
        yield path
    finally:
        if os.path.exists(path):
            os.unlink(path)

with managed_temp_file('.json') as path:
    with open(path, 'w') as f:
        f.write('{}')
# File deleted after block
```

**How `@contextmanager` works internally:**

The generator is advanced to `yield` on `__enter__`. On `__exit__`:
- No exception: advance past `yield` via `.send(None)`, expect `StopIteration`.
- Exception: `.throw(exc_type, exc_val, exc_tb)` into the generator at the `yield`.
- If the generator re-raises or doesn't suppress, `__exit__` propagates.
- If the generator swallows it (returns without re-raising), `__exit__` returns True.

### Exception Handling in Context Managers

```python
from contextlib import contextmanager

@contextmanager
def suppress_and_log(*exc_types):
    try:
        yield
    except exc_types as e:
        print(f"Suppressed: {e}")
        # falls through: exception is swallowed, __exit__ returns True

with suppress_and_log(ValueError, TypeError):
    raise ValueError("expected error")
# Prints: Suppressed: expected error
# Continues normally

# Built-in: contextlib.suppress
from contextlib import suppress

with suppress(FileNotFoundError):
    os.remove("/tmp/nonexistent")  # silently ignored
```

### `contextlib.ExitStack` — Dynamic Context Managers

`ExitStack` composes a variable number of context managers at runtime:

```python
from contextlib import ExitStack

def process_files(paths: list[str]) -> None:
    with ExitStack() as stack:
        # Open all files, each registered with the stack:
        files = [stack.enter_context(open(p)) for p in paths]
        # If opening any file fails, previously opened files are closed
        for f in files:
            process(f.read())
    # All files closed here, in LIFO order

# Dynamic cleanup callbacks:
with ExitStack() as stack:
    conn = stack.enter_context(get_db_connection())
    stack.callback(log_connection_closed, conn.id)  # callback on exit
    stack.callback(metrics.record_db_session)       # called before log_connection_closed

# Conditional resource registration:
with ExitStack() as stack:
    if use_cache:
        cache = stack.enter_context(CacheConnection())
    else:
        cache = NullCache()
    process(cache)

# ExitStack.pop_all() — transfer ownership:
def build_stack() -> ExitStack:
    with ExitStack() as stack:
        stack.enter_context(resource_a())
        stack.enter_context(resource_b())
        return stack.pop_all()   # caller now owns cleanup responsibility

with build_stack():
    do_work()
```

### Async Context Managers

```python
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_connection(dsn: str):
    conn = await create_connection(dsn)
    try:
        yield conn
    finally:
        await conn.close()

async def main():
    async with managed_connection("postgres://...") as conn:
        await conn.execute("SELECT 1")

# Protocol:
class AsyncResource:
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        return False
```

### Reentrant Context Managers

Some context managers can be entered multiple times (e.g., `threading.RLock`). `contextlib.nullcontext` is a reentrant no-op:

```python
from contextlib import nullcontext

def process(data, lock=None):
    cm = lock if lock is not None else nullcontext()
    with cm:
        modify(data)

# Without nullcontext: you'd need `if lock: with lock: ...` which is ugly
```

---

## Interview Questions

### Q1: What does `__exit__` returning `True` mean? Give a case where you'd want it.

**Model answer:**
Returning `True` from `__exit__` **suppresses** the exception — the `with` block exits normally as if no exception occurred. The caller sees no exception.

Use case: a retry context manager that absorbs transient errors and retries internally:

```python
from contextlib import contextmanager
import time

@contextmanager
def retry_on(exc_type, attempts=3, delay=1.0):
    for attempt in range(attempts):
        try:
            yield
            return   # success — exit the generator normally
        except exc_type:
            if attempt == attempts - 1:
                raise   # last attempt — don't suppress
            time.sleep(delay)
```

Another use case: `contextlib.suppress`:
```python
class suppress:
    def __init__(self, *exceptions):
        self._exceptions = exceptions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return exc_type is not None and issubclass(exc_type, self._exceptions)
        # Returns True (suppress) if exception matches; False (propagate) otherwise
```

### Q2: Why does `@contextmanager` require a `try/finally` around `yield`?

**Model answer:**
Without `try/finally`, an exception inside the `with` block would propagate from `yield` and exit the generator — the cleanup code after `yield` would never run:

```python
@contextmanager
def bad_manager():
    resource = acquire()
    yield resource
    resource.release()   # NEVER RUNS if 'with' body raises!

@contextmanager
def good_manager():
    resource = acquire()
    try:
        yield resource
    finally:
        resource.release()   # ALWAYS runs, even if 'with' body raises
```

The `@contextmanager` decorator throws the exception into the generator at the `yield` point via `generator.throw(exc_type, exc_val, exc_tb)`. Without `try/finally`, the exception propagates upward and the generator terminates without running cleanup.

### Q3: How does `ExitStack` handle exceptions from multiple context managers?

**Model answer:**
`ExitStack` calls `__exit__` on each registered context manager in LIFO (reverse) order. If an `__exit__` call raises or returns False and an exception is active, the exception propagates. If multiple `__exit__` calls fail, only the last one is raised (prior exceptions are chained as `__context__`):

```python
from contextlib import ExitStack

class Exploder:
    def __init__(self, name): self.name = name
    def __enter__(self): return self
    def __exit__(self, *args):
        raise RuntimeError(f"{self.name} cleanup failed")

with ExitStack() as stack:
    stack.enter_context(Exploder("first"))
    stack.enter_context(Exploder("second"))
    # 'second' cleanup runs first (LIFO) — raises RuntimeError("second cleanup failed")
    # 'first' cleanup runs next — raises RuntimeError("first cleanup failed")
    # Final: RuntimeError("first cleanup failed") with __context__ = RuntimeError("second...")
```

This ensures ALL cleanup code runs even if some cleanup code fails. `contextlib.AsyncExitStack` provides the same for async context managers.

### Q4: What is the difference between `contextmanager` and implementing `__enter__`/`__exit__` directly?

**Model answer:**

| Feature | `@contextmanager` | `__enter__`/`__exit__` class |
|---------|------------------|------------------------------|
| Code style | Linear, sequential | Split setup/teardown |
| Exception inspection | Via `except` in generator | Via `exc_type, exc_val, exc_tb` params |
| Reuse | One-shot | Reentrant if designed for it |
| Multiple yield | Not allowed | N/A |
| Performance | Slightly slower (generator overhead) | Slightly faster |
| Readability | Better for simple cases | Better for complex cases |

Use `@contextmanager` for simple acquire/release patterns where the code flows linearly. Use a class when: the context manager is reentrant, has complex state, needs `__repr__` for debugging, or needs to be subclassed.

```python
# Class style is clearer when setup and teardown involve different state:
class DatabaseTransaction:
    def __init__(self, conn):
        self.conn = conn
        self.savepoint = None

    def __enter__(self):
        self.savepoint = self.conn.savepoint()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.conn.rollback_to(self.savepoint)
        else:
            self.conn.release_savepoint(self.savepoint)
        return False   # don't suppress exceptions
```

### Q5: How do you implement a context manager that can be used both synchronously and asynchronously?

**Model answer:**
Implement both `__enter__`/`__exit__` AND `__aenter__`/`__aexit__`:

```python
class Connection:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None

    def _do_connect(self): ...    # sync connection
    async def _do_async_connect(self): ...  # async connection

    def __enter__(self):
        self._conn = self._do_connect()
        return self

    def __exit__(self, *args):
        if self._conn:
            self._conn.close()
        return False

    async def __aenter__(self):
        self._conn = await self._do_async_connect()
        return self

    async def __aexit__(self, *args):
        if self._conn:
            await self._conn.aclose()
        return False

# Sync:
with Connection("postgres://...") as conn:
    conn.execute("SELECT 1")

# Async:
async with Connection("postgres://...") as conn:
    await conn.aexecute("SELECT 1")
```

`contextlib.AbstractContextManager` and `contextlib.AbstractAsyncContextManager` provide default implementations that raise `NotImplementedError` — useful as mixins.

---

## Gotcha Follow-ups

**"Can you `yield` multiple times in a `@contextmanager`?"**
No — `@contextmanager` raises `RuntimeError` if the generator yields more than once. Each call to the decorated function must yield exactly once. If you need to `yield` multiple values from a context manager, use a different pattern (return an iterator, or yield a helper object with methods).

**"What happens if `__exit__` itself raises an exception?"**
The new exception replaces the original. The original exception is attached as `__context__` on the new exception. This is why cleanup code should be robust: a cleanup exception that hides the original is hard to debug. Best practice: wrap cleanup in `try/except` and log (don't re-raise) if cleanup fails.

---

## Under the Hood

`with` compiles to `BEFORE_WITH` + `WITH_EXCEPT_START` + `WITH_EXCEPT_STOP` opcodes (Python 3.11+). `BEFORE_WITH` calls `__enter__` and pushes the cleanup frame. `WITH_EXCEPT_START` calls `__exit__` with exception info. The generator-based `@contextmanager` is implemented in `Lib/contextlib.py` using `_GeneratorContextManager`, which calls `gen.send(None)` for `__enter__` and `gen.throw(...)` / `gen.send(None)` for `__exit__`.
