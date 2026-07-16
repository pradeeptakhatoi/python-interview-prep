# Exception Chaining and Groups

## Concept

Python 3.11 introduced `ExceptionGroup` to handle multiple concurrent errors — essential for `asyncio.TaskGroup` and other concurrent primitives. Exception chaining (`raise X from Y`) preserves causal context across abstraction layers.

### Exception Chaining: `raise X from Y`

```python
# Explicit chaining: "X was caused by Y"
try:
    result = db.query("SELECT ...")
except sqlite3.Error as e:
    raise DatabaseError("query failed") from e   # __cause__ = e, __suppress_context__ = True

# Implicit chaining: exception raised while another is active
try:
    x = {}['missing_key']
except KeyError:
    raise ValueError("bad config")   # __context__ = KeyError, __suppress_context__ = False
    # Display: "During handling of the above exception, another exception occurred"

# Suppress chaining entirely:
try:
    risky()
except SomeError:
    raise CleanError("clean message") from None   # __cause__ = None, __suppress_context__ = True
    # No "caused by" printed — useful when original error is an implementation detail
```

**Reading chained exceptions:**

```python
import traceback

def deep_function():
    try:
        {}['key']
    except KeyError as e:
        raise ValueError("config missing") from e

try:
    deep_function()
except ValueError as e:
    print(e.__cause__)            # KeyError: 'key'
    print(e.__context__)          # KeyError: 'key' (same in this case)
    print(e.__suppress_context__) # True (because we used 'from')
    traceback.print_exc()         # Full chain with "The above exception was the direct cause"
```

### `ExceptionGroup` (Python 3.11+)

`ExceptionGroup` wraps multiple exceptions raised concurrently. The primary source: `asyncio.TaskGroup` raising an `ExceptionGroup` when multiple tasks fail simultaneously.

```python
import asyncio

async def might_fail(n: int) -> int:
    await asyncio.sleep(0.01)
    if n % 2 == 0:
        raise ValueError(f"even number: {n}")
    return n

async def run_all():
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(might_fail(i)) for i in range(5)]
    # If tasks 0, 2, 4 fail: ExceptionGroup("", [ValueError("0"), ValueError("2"), ValueError("4")])

try:
    asyncio.run(run_all())
except ExceptionGroup as eg:
    print(f"Group message: {eg.message}")
    print(f"Exceptions: {eg.exceptions}")
    # eg.exceptions is a tuple of the individual exceptions
```

### `except*` — Handling Parts of an ExceptionGroup

`except*` (Python 3.11+) matches a subset of exceptions within an `ExceptionGroup`, letting unmatched exceptions propagate:

```python
import asyncio

async def task(n: int):
    if n == 1:
        raise ValueError("bad value")
    elif n == 2:
        raise TypeError("wrong type")
    elif n == 3:
        raise RuntimeError("runtime fail")

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            for i in range(1, 4):
                tg.create_task(task(i))
    except* ValueError as eg:
        print(f"Handled ValueError(s): {eg.exceptions}")
        # Logs the ValueError but lets TypeError and RuntimeError propagate
    except* TypeError as eg:
        print(f"Handled TypeError(s): {eg.exceptions}")
    # RuntimeError propagates as an ExceptionGroup([RuntimeError])

asyncio.run(main())
```

Key difference: `except*` always operates on groups. Even if only one exception of the matched type exists, it arrives as an `ExceptionGroup`. The unmatched exceptions form a new `ExceptionGroup` that propagates.

### Creating ExceptionGroups Manually

```python
# Collect errors from a batch operation:
def process_batch(items: list) -> list:
    results = []
    errors = []

    for i, item in enumerate(items):
        try:
            results.append(process_item(item))
        except Exception as e:
            errors.append(ValueError(f"Item {i} failed: {e}"))

    if errors:
        raise ExceptionGroup("batch processing failed", errors)

    return results

# Nested ExceptionGroups:
outer = ExceptionGroup("outer", [
    ValueError("v1"),
    ExceptionGroup("inner", [TypeError("t1"), KeyError("k1")]),
    RuntimeError("r1"),
])

# Flattening and inspecting:
def collect_exceptions(eg: ExceptionGroup, target_type: type) -> list:
    matched, rest = eg.split(target_type)
    results = list(matched.exceptions) if matched else []
    for exc in (rest.exceptions if rest else []):
        if isinstance(exc, ExceptionGroup):
            results.extend(collect_exceptions(exc, target_type))
    return results

print(collect_exceptions(outer, ValueError))   # [ValueError('v1')]
```

### `ExceptionGroup.split()` — Programmatic Filtering

```python
eg = ExceptionGroup("mixed", [
    ValueError("v1"),
    TypeError("t1"),
    ValueError("v2"),
    RuntimeError("r1"),
])

# Split into matched and unmatched:
matched, rest = eg.split(ValueError)
print(matched)   # ExceptionGroup('mixed', [ValueError('v1'), ValueError('v2')])
print(rest)      # ExceptionGroup('mixed', [TypeError('t1'), RuntimeError('r1')])

# split() with a predicate:
big_errors, small_errors = eg.split(lambda e: not isinstance(e, ValueError))
```

---

## Interview Questions

### Q1: What's the difference between `raise X from Y` and `raise X` inside an `except` block?

**Model answer:**
Both create exception chains, but with different semantics:

`raise X` inside `except Y`: implicit chain — `X.__context__ = Y`, `X.__suppress_context__ = False`. Display: "During handling of the above exception, another exception occurred."

`raise X from Y`: explicit chain — `X.__cause__ = Y`, `X.__suppress_context__ = True`. Display: "The above exception was the direct cause of the following exception."

`raise X from None`: explicitly suppresses all chaining. Neither `__cause__` nor `__context__` is shown. Used when you want to hide implementation details:

```python
class UserRepository:
    def get(self, user_id: int):
        try:
            return self._internal_lookup(user_id)
        except _InternalDbError as e:
            # Don't expose internal DB error details to callers
            raise UserNotFoundError(user_id) from None

# Caller sees only UserNotFoundError with no DB internals in traceback
```

`raise X from Y` is the right choice when the chain is genuinely informative (debuggers want it). `from None` is for internal implementation details you explicitly choose not to expose.

### Q2: What is `ExceptionGroup` and why was it added?

**Model answer:**
`ExceptionGroup` (PEP 654, Python 3.11) represents multiple concurrent failures — something that couldn't be expressed with a single exception.

The motivating case is `asyncio.TaskGroup`: if three tasks run concurrently and two raise exceptions, there's no way to represent "both failed" in a single exception without losing one. `ExceptionGroup` holds all of them.

```python
async def main():
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(download("url1"))   # raises ConnectionError
        t2 = tg.create_task(download("url2"))   # succeeds
        t3 = tg.create_task(download("url3"))   # raises TimeoutError
    # Raises: ExceptionGroup("", [ConnectionError("url1"), TimeoutError("url3")])

try:
    asyncio.run(main())
except* ConnectionError as eg:
    for e in eg.exceptions:
        logger.warning("Connection failed: %s", e)
except* TimeoutError as eg:
    for e in eg.exceptions:
        retry(e)
```

Before Python 3.11: you had to choose — raise the first exception, collect errors in a list manually, or use a custom aggregate exception type.

### Q3: How does `except*` differ from `except` for exception groups?

**Model answer:**
`except` matches a single exception type. `except*` matches ALL exceptions of a type within an `ExceptionGroup` and creates a new `ExceptionGroup` for unmatched ones to propagate:

```python
eg = ExceptionGroup("", [ValueError("v"), TypeError("t"), ValueError("v2")])

# Using except*:
try:
    raise eg
except* ValueError as matched:
    print(matched.exceptions)   # (ValueError('v'), ValueError('v2'))
    # TypeError('t') is re-raised as ExceptionGroup("", [TypeError('t')])
```

Key: even if there's only one matched exception, `except*` gives you an `ExceptionGroup`. You always access `eg.exceptions`:

```python
except* ValueError as eg:
    for exc in eg.exceptions:   # always iterate — might be 1 or many
        handle(exc)
```

`except*` can handle multiple exception types in sequence in the same `try` block. Both can match; both handlers run before any unmatched exceptions propagate.

### Q4: How do you test code that raises `ExceptionGroup`?

**Model answer:**

```python
import pytest

def run_batch():
    raise ExceptionGroup("batch", [
        ValueError("item 0"),
        TypeError("item 1"),
    ])

# pytest supports ExceptionGroup assertions:
with pytest.raises(ExceptionGroup) as exc_info:
    run_batch()

eg = exc_info.value
assert len(eg.exceptions) == 2
assert any(isinstance(e, ValueError) for e in eg.exceptions)
assert any(isinstance(e, TypeError) for e in eg.exceptions)

# Or use pytest.raises with match on specific subexceptions:
# pytest 7.2+ has experimental ExceptionGroup support
```

For testing `except*` code:
```python
async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fail_with(ValueError))
            tg.create_task(fail_with(TypeError))
    except* ValueError:
        ...

# Use pytest-asyncio:
@pytest.mark.asyncio
async def test_group_handling():
    with pytest.raises(ExceptionGroup) as exc_info:
        await main()
    # Ensure unhandled TypeError propagated
    assert any(isinstance(e, TypeError) for e in exc_info.value.exceptions)
```

### Q5: When should you use `raise X from None` vs `raise X from original`?

**Model answer:**

**`raise X from original`** — use when the original exception adds debugging value the caller should see:
```python
def parse_config(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid config at {path}") from e
    # Traceback shows: JSONDecodeError (which line/col in JSON) → ConfigError
    # Very helpful for debugging malformed config files
```

**`raise X from None`** — use when the original exception is an implementation detail that would confuse the caller:
```python
class SecretStore:
    def get(self, key: str) -> str:
        try:
            return self._backend.fetch(key)   # internal backend details
        except _BackendConnectionError:       # internal error type
            raise SecretNotFoundError(key) from None
    # Caller shouldn't know about _BackendConnectionError or _backend
```

Rule: expose chains that help callers debug their code. Suppress chains that expose your internal implementation.

---

## Gotcha Follow-ups

**"Can `except*` handle non-group exceptions?"**
No — `except*` only matches inside `ExceptionGroup`. If a bare `ValueError` is raised (not inside a group), `except*` does not catch it. You'd get a `TypeError: expected an ExceptionGroup`. Mix `except` (for non-group) and `except*` (for groups) if needed.

**"Does exception chaining affect memory usage?"**
Yes — each chained exception holds a reference to the previous one, which in turn holds a traceback, which holds frame references. Long chains can keep large frames alive. In exception-heavy code paths, use `from None` to break the chain and allow garbage collection of intermediate frames.

---

## Under the Hood

`__cause__`, `__context__`, `__suppress_context__` are C-level fields on `PyBaseExceptionObject` (`Objects/exceptions.c`). When `raise X from Y` is executed, the `RAISE_VARARGS` opcode sets `X.__cause__ = Y` and `X.__suppress_context__ = True`. When `raise X` is raised inside an active `except` handler, the VM calls `_PyErr_SetObject` which sets `X.__context__` to the current active exception automatically.

`ExceptionGroup` (`Lib/test/test_exception_group.py`, `Objects/exceptions.c`): stores `_excs` as a tuple and a `message` string. `split()` recursively splits nested groups, pruning branches where nothing matches.
