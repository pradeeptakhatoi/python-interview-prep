# Common Typing Pitfalls in Large Codebases

## Concept

Python's type system has several sharp edges that become apparent only in large, multi-module codebases. These pitfalls can make type checking impractical without understanding the right workarounds.

### Circular Type Imports

The most common production typing problem: two modules each import from the other for type annotations only.

```
# File: models.py
from services import UserService   # needs UserService for type hint

# File: services.py
from models import User            # needs User for type hint

# Result: ImportError or circular import at runtime
```

**Solution: `TYPE_CHECKING` guard**

```python
# models.py
from __future__ import annotations   # makes all annotations strings (lazy)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import UserService   # only imported during static analysis

class User:
    def get_service(self) -> UserService:   # OK — annotation is a string
        from services import UserService    # local import at runtime
        return UserService(self)
```

```python
# services.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import User

class UserService:
    def __init__(self, user: User) -> None:
        self.user = user
```

The `from __future__ import annotations` makes ALL annotations lazy strings, so the `UserService` name is never evaluated at class definition time — only when `get_type_hints()` is called.

### Forward References

Without `from __future__ import annotations`, referring to a class before it's defined raises `NameError`:

```python
# WRONG:
class Node:
    def __init__(self, next: Node | None = None):   # NameError — Node not yet defined
        self.next = next

# FIX 1: String annotation (explicit)
class Node:
    def __init__(self, next: 'Node | None' = None):   # string — not evaluated at definition
        self.next = next

# FIX 2: from __future__ import annotations (file-wide lazy)
from __future__ import annotations

class Node:
    def __init__(self, next: Node | None = None):   # OK — all annotations are lazy strings
        self.next = next

# FIX 3: Python 3.12+ type alias
type NodeOrNone = Node | None

class Node:
    def __init__(self, next: NodeOrNone = None): ...
```

### `Optional` vs `X | None`

```python
from typing import Optional

# Equivalent:
def f1(x: Optional[str]) -> None: ...    # old style (Python 3.5+)
def f2(x: str | None) -> None: ...      # new style (Python 3.10+)

# Common mistake: thinking Optional[str] means "optional parameter"
def bad(x: Optional[str]) -> None:      # x can be None; NOT "x is optional"
    x.upper()   # Type error — x could be None!

def good(x: str | None) -> None:
    if x is not None:
        x.upper()   # OK — narrowed to str after None check

# Optional parameter is expressed with default value:
def has_default(x: str = "default") -> None: ...   # optional parameter
def nullable(x: str | None = None) -> None: ...    # optional AND nullable
```

### Type Narrowing

Type checkers perform **type narrowing** — they narrow the type after an `isinstance()` or `is None` check:

```python
def process(value: str | int | None) -> str:
    if value is None:
        return "nothing"
    # Here: value is str | int (narrowed from str | int | None)

    if isinstance(value, str):
        return value.upper()   # value is str (narrowed)
    else:
        return str(value)   # value is int (narrowed)

# Narrowing with TypeGuard (custom narrowing function):
from typing import TypeGuard

def is_list_of_str(val: list) -> TypeGuard[list[str]]:
    return all(isinstance(x, str) for x in val)

def process_list(items: list[str | int]) -> None:
    if is_list_of_str(items):
        items[0].upper()   # OK — narrowed to list[str]
```

### `Any` Contamination

```python
from typing import Any

# Data from external source — unavoidable Any:
import json
data: Any = json.loads(response.body)

# Problem: Any spreads to everything it touches
user_id = data["user_id"]        # inferred as Any
name = data["name"].upper()      # Any — no checking
count = len(data["items"]) + 1   # Any — mypy won't catch if len() fails

# Solution: cast at the boundary
from typing import cast, TypedDict

class UserResponse(TypedDict):
    user_id: int
    name: str
    items: list[str]

# Explicit cast — you take responsibility for correctness:
user: UserResponse = cast(UserResponse, data)
user["user_id"]   # now typed as int

# Better: validate (pydantic) — runtime enforcement + static typing:
from pydantic import TypeAdapter
ta = TypeAdapter(UserResponse)
user = ta.validate_python(data)   # raises on bad data + statically typed
```

### Overusing `cast()`

`cast(T, x)` is a static-only assertion — it does nothing at runtime (returns `x` unchanged). Overusing it defeats the purpose of type checking:

```python
from typing import cast

# Wrong pattern: castway-everything
def bad() -> int:
    data = get_some_data()   # returns Any
    count = cast(int, data["count"])   # silently wrong if data["count"] is "42"
    return count

# Better: validate or narrow properly
def good() -> int:
    data = get_some_data()
    raw_count = data["count"]
    if not isinstance(raw_count, int):
        raise TypeError(f"Expected int count, got {type(raw_count)}")
    return raw_count   # narrowed to int
```

### `NoReturn` and Unreachable Code

`NoReturn` types a function that never returns (raises or loops forever):

```python
from typing import NoReturn

def die(msg: str) -> NoReturn:
    raise SystemExit(msg)

def assert_never(x: Never) -> NoReturn:   # Never = Python 3.11+
    raise AssertionError(f"Expected unreachable: {x!r}")

# Exhaustive matching:
from typing import Literal

Status = Literal['pending', 'active', 'closed']

def describe(s: Status) -> str:
    if s == 'pending':
        return 'waiting'
    elif s == 'active':
        return 'running'
    elif s == 'closed':
        return 'done'
    else:
        assert_never(s)   # type checker: s is Never (all cases handled)
                          # at runtime: unreachable (if Literal is respected)
```

### Generic Type Aliases

```python
from typing import TypeAlias, TypeVar

T = TypeVar('T')

# Python 3.9+ implicit alias:
Matrix = list[list[float]]

# Python 3.10+ explicit alias:
Matrix: TypeAlias = list[list[float]]

# Python 3.12+ new syntax (PEP 695):
type Matrix = list[list[float]]
type Pair[T] = tuple[T, T]   # generic alias

# Common pitfall: using a non-generic type alias where a generic was needed:
from typing import Callable

Handler = Callable[[str], None]  # not generic — fine for fixed type
# GenericHandler[T] = Callable[[T], None]  # need TypeAlias + TypeVar
GenericHandler: TypeAlias = Callable[[T], None]  # works but T must be in scope
```

### `Literal` Types

`Literal` constrains a value to specific literal values:

```python
from typing import Literal

HttpMethod = Literal['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

def make_request(method: HttpMethod, url: str) -> None:
    ...

make_request('GET', 'https://...')     # OK
make_request('FETCH', 'https://...')   # Type error — 'FETCH' not in Literal

# Narrowing with Literal:
def handle(event: Literal['click', 'hover', 'scroll']) -> None:
    if event == 'click':
        ...    # narrowed to Literal['click']
    elif event == 'hover':
        ...    # narrowed to Literal['hover']
    else:
        ...    # narrowed to Literal['scroll'] — exhaustive!
```

---

## Interview Questions

### Q1: How do you handle typing in a codebase with many circular imports?

**Model answer:**
The three-part solution:

1. **`TYPE_CHECKING` guard:** import types only during static analysis, not at runtime.
2. **`from __future__ import annotations`:** make all annotations lazy strings, avoiding runtime evaluation of type names.
3. **Restructure if possible:** move shared types to a `types.py` or `interfaces.py` module that neither side of the cycle imports from the other.

```python
# Preferred: create a shared types module
# types.py (no imports from models or services)
from typing import Protocol

class UserLike(Protocol):
    id: int
    name: str

# models.py
from .types import UserLike  # no cycle

# services.py
from .types import UserLike  # no cycle
```

For cases where restructuring is impractical:
```python
# service.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Model   # import only seen by type checker

class Service:
    def create(self, data: dict) -> Model:   # annotation is lazy string
        from .model import Model             # runtime import at call time
        return Model(data)
```

### Q2: What is `TypeGuard` and how does it differ from a simple `isinstance()` check?

**Model answer:**
`isinstance()` narrowing works automatically for built-in types. `TypeGuard` is for custom narrowing functions whose logic the type checker can't infer:

```python
from typing import TypeGuard

def is_valid_user(data: dict) -> TypeGuard[dict[str, str]]:
    """Return True iff data is a dict with all string values."""
    return all(isinstance(v, str) for v in data.values())

def process(raw: dict) -> None:
    if is_valid_user(raw):
        raw["name"].upper()   # OK — narrowed to dict[str, str]
        # raw.values() are all str
    else:
        # raw is still dict (no narrowing on else branch)
        ...
```

The type checker trusts the `TypeGuard[T]` annotation — it narrows the input to `T` in the `if` branch without inspecting the function body.

Key limitation: `TypeGuard` only narrows in the `if True` branch, not the `else` branch. Python 3.13 adds `TypeIs` for two-way narrowing.

### Q3: When should you use `cast()` vs `TypeGuard` vs validation?

**Model answer:**

| Tool | Runtime cost | Safety | Use when |
|------|-------------|--------|----------|
| `cast(T, x)` | None — no-op | None — you assert correctness | You are 100% sure of the type from context the checker can't see |
| `TypeGuard` | Cost of your check function | Medium — checker trusts your function | Custom narrowing logic for complex conditions |
| `isinstance()` | O(1) | High — runtime verified | Built-in types, class hierarchy checks |
| pydantic/validation | Higher | Highest — full validation | External data (APIs, user input, config files) |

```python
from typing import cast

# CORRECT use of cast: C extension returns untyped result we know the type of
import ctypes
result = ctypes.CDLL('libm.so.6').sqrt(4.0)   # returns c_double
sqrt_result = cast(float, result)   # safe — we know the C type

# WRONG use of cast: suppressing a real type mismatch
bad: list[str] = cast(list[str], [1, 2, 3])   # lies to the checker — runtime will fail
bad[0].upper()   # AttributeError: 'int' object has no attribute 'upper'
```

Rule of thumb: `cast()` for C extensions, ctypes, and truly untyped external sources where you've manually verified the type. Validation for actual runtime enforcement.

### Q4: What does `from __future__ import annotations` break and when should you NOT use it?

**Model answer:**
`from __future__ import annotations` (PEP 563) turns all annotations into strings — they're never evaluated at function/class definition time. This can break code that uses annotations at runtime:

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Config:
    timeout: float = 30.0  # annotation is now a string "float"

# dataclass uses __annotations__ to find fields
# In Python 3.10+, dataclasses call get_type_hints() which evaluates strings
# But in some edge cases, lazy evaluation breaks framework introspection

import typing
hints = typing.get_type_hints(Config)
# Works — get_type_hints() evaluates the string in the right namespace
print(hints)  # {'timeout': <class 'float'>}  ✓

# What BREAKS:
# 1. Using annotation values directly:
def f(x: int) -> None: pass
print(f.__annotations__)   # {'x': 'int', 'return': 'None'} — strings, not types!
# Code that does isinstance(x, f.__annotations__['x']) breaks

# 2. Pydantic v1 (not v2) — it read __annotations__ directly without get_type_hints()
# Pydantic v2 handles this correctly.

# 3. attrs with certain configurations before 22.2.0
```

When NOT to use it:
- Libraries that read `__annotations__` directly (check your framework version).
- When you need annotation values at runtime for custom logic.
- In libraries where users may not be using Python 3.10+ (PEP 563 behavior can differ between versions).

### Q5: How do you type a function that returns different types based on a `Literal` input flag?

**Model answer:**
Use `@overload` with `Literal` parameter types:

```python
from typing import overload, Literal

@overload
def parse(data: str, mode: Literal['json']) -> dict: ...
@overload
def parse(data: str, mode: Literal['csv']) -> list[list[str]]: ...
@overload
def parse(data: str, mode: Literal['text']) -> str: ...

def parse(data: str, mode: str) -> dict | list[list[str]] | str:
    if mode == 'json':
        import json
        return json.loads(data)
    elif mode == 'csv':
        import csv, io
        return list(csv.reader(io.StringIO(data)))
    else:
        return data

result_json: dict = parse('{"key": 1}', 'json')  # type checker: returns dict
result_csv: list = parse('a,b\n1,2', 'csv')       # type checker: returns list[list[str]]
result_txt: str  = parse('hello', 'text')          # type checker: returns str
```

Without `@overload`, the return type would be `dict | list[list[str]] | str` for all calls, requiring the caller to narrow the result. With `@overload`, the type checker selects the right overload based on the `Literal` argument, giving a precise return type at each call site.

---

## Gotcha Follow-ups

**"Does `isinstance(obj, str | int)` work in Python 3.10+?"**
Yes — `isinstance()` accepts `X | Y` union syntax (a `types.UnionType`) in Python 3.10+. Before 3.10, you had to use `isinstance(obj, (str, int))`. Static type checkers accept both forms.

**"What is `ParamSpecArgs` / `ParamSpecKwargs` and when do you need them?"**
These are used inside a `ParamSpec`-using decorator when you need to pass `*args` and `**kwargs` through to the inner function with correct types. Without them, `*args: P.args` and `**kwargs: P.kwargs` — the simpler pattern — suffices for most cases. `P.args` and `P.kwargs` can only be used together in the same function signature.

---

## Under the Hood

`from __future__ import annotations` compiles to `co_flags |= CO_FUTURE_ANNOTATIONS`. At the bytecode level, annotations are not executed as expressions — the AST node `AnnAssign` generates no code to evaluate the annotation (in contrast to non-future mode where the expression is evaluated and stored). Annotations are stored as the string source text in `__annotations__`.

`TYPE_CHECKING` is `typing.TYPE_CHECKING`, which is the literal `False` constant. The `if TYPE_CHECKING:` block is compiled but never executed at runtime (the condition is always `False`). Type checkers define their own version of `typing.TYPE_CHECKING = True` during analysis.
