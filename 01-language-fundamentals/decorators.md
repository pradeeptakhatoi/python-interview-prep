# Decorators: Function, Class, Arguments, functools.wraps, Stacking Order

## Concept

A decorator is a callable that takes a callable and returns a callable (or a class). The `@decorator` syntax is pure syntactic sugar:

```python
@decorator
def func(): ...

# Exactly equivalent to:
def func(): ...
func = decorator(func)
```

### Function Decorators

```python
import functools
import time

def timer(func):
    @functools.wraps(func)   # preserves __name__, __doc__, __module__, etc.
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed*1000:.2f}ms")
        return result
    return wrapper

@timer
def slow_sum(n):
    return sum(range(n))

slow_sum(1_000_000)  # "slow_sum took 42.00ms"
print(slow_sum.__name__)   # "slow_sum" (not "wrapper") — thanks to @wraps
```

### `functools.wraps` — Why It Matters

Without `@functools.wraps`, the wrapper replaces the original function's metadata:

```python
def bad_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper  # NO @wraps

@bad_decorator
def my_func():
    """My docstring."""
    pass

print(my_func.__name__)   # "wrapper" — wrong!
print(my_func.__doc__)    # None — docstring lost!
```

`@functools.wraps(func)` copies `__name__`, `__qualname__`, `__doc__`, `__dict__`, `__module__`, `__annotations__`, and sets `__wrapped__ = func`. The `__wrapped__` attribute allows `inspect.unwrap()` to peel off all decorator layers and reach the original function.

### Decorators with Arguments

A decorator with arguments is a function that returns a decorator (three levels of nesting):

```python
import functools

def retry(max_attempts: int = 3, exceptions: tuple = (Exception,)):
    """Decorator factory: retry on specified exceptions."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    print(f"Attempt {attempt}/{max_attempts} failed: {e}")
            raise last_exc
        return wrapper
    return decorator  # returns the actual decorator

@retry(max_attempts=3, exceptions=(ValueError, TimeoutError))
def fetch_data(url: str) -> dict:
    ...

# Equivalent to:
# fetch_data = retry(max_attempts=3, exceptions=(...))(fetch_data)
```

### Stateful Decorators via Class

Using a class as a decorator to maintain state per decorated function:

```python
import functools

class CallCounter:
    """Decorator class that counts invocations."""

    def __init__(self, func):
        functools.update_wrapper(self, func)
        self.func = func
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        return self.func(*args, **kwargs)

    def reset(self):
        self.call_count = 0

    def __get__(self, obj, objtype=None):
        # Required to work correctly as a METHOD decorator:
        if obj is None:
            return self
        return functools.partial(self.__call__, obj)

@CallCounter
def compute(x):
    return x * 2

compute(5)
compute(10)
print(compute.call_count)   # 2
compute.reset()
print(compute.call_count)   # 0
```

### Class Decorators

A decorator applied to a class — modifies or replaces the class:

```python
def auto_repr(cls):
    """Add a __repr__ based on __init__ parameter names."""
    import inspect
    params = list(inspect.signature(cls.__init__).parameters.keys())[1:]  # skip 'self'

    def __repr__(self):
        attrs = ", ".join(f"{p}={getattr(self, p, '?')!r}" for p in params)
        return f"{cls.__name__}({attrs})"

    cls.__repr__ = __repr__
    return cls   # modifies the class in-place; returns same class

@auto_repr
class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

print(Point(1.0, 2.0))  # Point(x=1.0, y=2.0)
```

### Stacking Order

Decorators stack bottom-up at definition time, top-down in execution:

```python
def deco_a(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("A before"); result = func(*args, **kwargs); print("A after")
        return result
    return wrapper

def deco_b(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("B before"); result = func(*args, **kwargs); print("B after")
        return result
    return wrapper

@deco_a
@deco_b
def greet():
    print("Hello!")

greet()
# A before → B before → Hello! → B after → A after

# Application order: greet = deco_a(deco_b(greet))
# deco_b applied first (innermost), then deco_a
# Execution order: A's wrapper first (outermost), B's wrapper, original
```

---

## Interview Questions

### Q1: What does `functools.wraps` do and what breaks without it?

**Model answer:**
`@functools.wraps(original)` copies metadata from `original` onto the wrapper: `__name__`, `__qualname__`, `__doc__`, `__dict__`, `__module__`, `__annotations__`, and sets `__wrapped__ = original`.

Without it:
1. **Docstrings and `help()` are wrong** — `help(func)` shows the wrapper's empty docstring.
2. **`__name__` is wrong** — logging, tracebacks, and profiler output show "wrapper".
3. **Type checking breaks** — `mypy`/`pyright` see the wrapper's `(*args, **kwargs)` signature instead of the original's typed signature.
4. **`inspect.unwrap()` fails** — can't peel off decorator layers (used by `pytest`, `asyncio`, etc.).
5. **`asyncio.iscoroutinefunction()` may fail** — it checks `__wrapped__` to detect async functions wrapped by sync decorators.

```python
import inspect

def decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@decorator
def process(x: int) -> str:
    """Process x."""
    return str(x)

print(inspect.signature(process))      # (x: int) -> str  ✓
print(inspect.unwrap(process))         # <function process ...> ✓
print(process.__wrapped__)             # original function ✓
```

### Q2: Implement a decorator that enforces argument type-checking at runtime.

**Model answer:**
```python
import functools
import inspect
from typing import get_type_hints

def typecheck(func):
    hints = get_type_hints(func)
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        for param_name, value in bound.arguments.items():
            if param_name in hints and param_name != 'return':
                expected = hints[param_name]
                if not isinstance(value, expected):
                    raise TypeError(
                        f"{func.__name__}(): {param_name} must be "
                        f"{expected.__name__}, got {type(value).__name__}"
                    )
        return func(*args, **kwargs)
    return wrapper

@typecheck
def add(x: int, y: int) -> int:
    return x + y

print(add(1, 2))   # 3
add(1, "2")        # TypeError: add(): y must be int, got str
```

Production note: `beartype` (third-party) does this via code generation with near-zero overhead.

### Q3: How does stacking multiple decorators work? What is the application and execution order?

**Model answer:**
```python
@A
@B
@C
def func(): ...

# Application order (bottom-up): func = A(B(C(func)))
# C is applied first (innermost), then B, then A
```

Execution order is top-down (A → B → C → func → C → B → A) because:
- Calling the decorated function calls A's wrapper first.
- A's wrapper calls B's wrapper via `func(*args, **kwargs)`.
- B's wrapper calls C's wrapper, which calls the original `func`.

Pre-processing runs A → B → C. Post-processing runs C → B → A.

Order matters for auth + logging:
```python
@require_auth    # outer — checks auth first; logging never runs on failed auth
@log_request     # inner
def endpoint(): ...
```

### Q4: What's the difference between a decorator returning a new function vs. modifying and returning the original?

**Model answer:**
Most decorators return a **wrapper function** — a new callable that calls the original. This allows pre/post logic.

Some decorators **modify the original in-place** and return it unchanged:
```python
_registry: dict = {}

def register(name: str):
    def decorator(func):
        _registry[name] = func
        return func   # return ORIGINAL, not a wrapper — zero overhead
    return decorator

@register("compute")
def my_compute(x):
    return x * 2

print(_registry)  # {"compute": <function my_compute ...>}
# my_compute is unchanged — no wrapping overhead at all
```

Returning the original is common for: registration decorators, `@dataclass`, class-modifying decorators that add methods/attributes.

### Q5: How do you write a decorator that works correctly both as a plain decorator and with arguments?

**Model answer:**
The trick is detecting whether the decorator was called with arguments or applied directly to a function:

```python
import functools

def retry(_func=None, *, max_attempts=3):
    """Works as @retry or @retry(max_attempts=5)."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
        return wrapper

    if _func is not None:
        # Called as @retry with no arguments — _func is the decorated function
        return decorator(_func)
    # Called as @retry(...) with arguments — return the decorator
    return decorator

@retry                      # works
def func1(): pass

@retry(max_attempts=5)      # also works
def func2(): pass
```

The `_func=None` sentinel plus keyword-only arguments after `*` is the cleanest pattern for optional-argument decorators.

---

## Gotcha Follow-ups

**"If a decorator returns a class instance (via `__call__`), what are the implications for methods?"**
The decorator instance does NOT bind to `self` automatically when used as a method. Without a `__get__` implementation, calling `instance.method()` passes the decorator instance itself — not the class instance — as the first argument. The `__get__` method turns the decorator into a descriptor, enabling correct binding:

```python
class Decorator:
    def __init__(self, func):
        self.func = func
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return functools.partial(self.__call__, obj)  # bind obj as first arg
```

**"How does `@staticmethod` work as a decorator?"**
`staticmethod` is a descriptor class. When applied as `@staticmethod`, it wraps the function and implements `__get__` to return the raw function (not a bound method). This is why `Class.method()` and `instance.method()` both work without passing `self`. `@classmethod` similarly implements `__get__` to return a bound method with the class as the first argument.

---

## Under the Hood

`@decorator` compiles to:
1. `MAKE_FUNCTION` — pushes the function object.
2. `LOAD_GLOBAL decorator` — loads the decorator.
3. `CALL 1` — calls decorator with the function.
4. `STORE_NAME func` — stores the result back under the function's name.

`functools.wraps` is implemented in `Lib/functools.py` as `update_wrapper(wrapper, wrapped)`, which does `setattr(wrapper, attr, getattr(wrapped, attr))` for attributes in `WRAPPER_ASSIGNMENTS = ('__module__', '__name__', '__qualname__', '__annotations__', '__doc__')` and `wrapper.__dict__.update(wrapped.__dict__)`. It also sets `wrapper.__wrapped__ = wrapped`.
