# Runtime vs Static Type Checking

## Concept

Python's type annotations are by default **informational** — they're not enforced at runtime. The ecosystem offers multiple approaches for when you want actual enforcement, each with different trade-offs.

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"

greet(42)   # Runs fine — no runtime error
            # mypy/pyright report: Argument 1 to "greet" has incompatible type "int"
```

### Static Type Checking: mypy vs pyright

| Feature | mypy | pyright / pylance |
|---------|------|-------------------|
| Language | Python | TypeScript |
| Speed | Slower | Much faster |
| Strictness | Configurable | Very strict by default |
| Protocol support | Good | Excellent |
| VSCode integration | Plugin | Built-in (Pylance) |
| Daemon mode | Yes (`dmypy`) | Yes |

```bash
# mypy basic usage:
pip install mypy
mypy my_module.py
mypy --strict my_module.py    # stricter: no implicit Any, full inference

# pyright:
npm install -g pyright
pyright my_module.py
```

### `Any` — The Escape Hatch

`Any` is both a subtype and supertype of every type — it turns off type checking for that variable:

```python
from typing import Any

def process(data: Any) -> Any:   # effectively untyped
    return data.whatever()  # type checker: no error — Any allows everything

# Any is contagious:
x: Any = get_external_data()
y: int = x + 1   # no error — x is Any, so x + 1 is Any
z: str = y        # still no error — y is inferred as Any
```

`--strict` in mypy disallows implicit `Any` and requires explicit typing for all public APIs.

### Runtime Validation: `pydantic` v2

Pydantic validates data at runtime using Python's type annotations:

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Annotated

class UserConfig(BaseModel):
    name: str
    age: int
    email: str
    timeout: Annotated[float, Field(gt=0, le=300)] = 30.0

# Validation at construction:
try:
    config = UserConfig(
        name="Alice",
        age="not_an_int",   # will be coerced to int if possible
        email=123,           # coerced to str
        timeout=-5.0         # will FAIL — constraint gt=0 violated
    )
except ValidationError as e:
    print(e)   # detailed error including field name, expected type, value received

# Successful construction:
config = UserConfig(name="Alice", age=30, email="alice@example.com")
config.model_dump()    # {'name': 'Alice', 'age': 30, ...}
config.model_dump_json()  # JSON string

# Parse from dict (common in API validation):
raw = {"name": "Bob", "age": "25"}   # age is string
config = UserConfig(**raw)   # pydantic coerces "25" → 25
```

**pydantic v2 performance:** core validation is implemented in Rust (`pydantic-core`), making it 5-50× faster than v1.

### Runtime Type Enforcement: `beartype`

`beartype` decorates functions to enforce type hints at call time with near-zero overhead:

```python
from beartype import beartype
from beartype.typing import List, Dict

@beartype
def process_items(items: List[int], config: Dict[str, str]) -> str:
    return str(sum(items))

process_items([1, 2, 3], {"key": "val"})   # OK
process_items([1, "2", 3], {})              # TypeError at runtime — "2" is not int
process_items(range(3), {})                 # TypeError — range is not list[int]
```

`beartype` uses `O(1)` checking — it doesn't iterate entire containers. For `List[int]`, it checks a random element (or first element), not all elements. This is a deliberate design trade-off for production use.

### `typeguard`: Full Runtime Checking

`typeguard` checks the entire collection (O(n)), suitable for tests or development:

```python
from typeguard import typechecked

@typechecked
def process_all(items: list[int]) -> int:
    return sum(items)

process_all([1, 2, 3])    # OK
process_all([1, "2", 3])  # TypeCheckError — checks ALL elements
```

Use `typeguard.install_import_hook()` to enable runtime checking for an entire codebase during testing:

```python
# In pytest conftest.py:
from typeguard import install_import_hook
install_import_hook('mypackage')   # all functions in mypackage are @typechecked
```

### `typing.get_type_hints()` — Accessing Annotations at Runtime

```python
import typing

class Server:
    host: str
    port: int
    debug: bool = False

    def start(self, timeout: float = 30.0) -> None: ...

# Get annotations with forward references resolved:
hints = typing.get_type_hints(Server)
print(hints)   # {'host': <class 'str'>, 'port': <class 'int'>, 'debug': <class 'bool'>}

# For a function:
hints = typing.get_type_hints(Server.start)
print(hints)   # {'timeout': <class 'float'>, 'return': <class 'NoneType'>}
```

`get_type_hints()` evaluates string annotations (forward references) in the correct namespace.

### `TYPE_CHECKING` Guard

```python
from __future__ import annotations  # PEP 563: all annotations become strings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mymodule import HeavyType   # only imported during type checking, not runtime

def process(data: 'HeavyType') -> None:  # string annotation for forward reference
    ...
```

`TYPE_CHECKING` is `False` at runtime, `True` only during static analysis. This avoids circular imports and heavy import overhead for type-only dependencies.

### `from __future__ import annotations` (PEP 563)

Defers evaluation of all annotations — they become strings instead of being evaluated at definition time:

```python
from __future__ import annotations

class Tree:
    def __init__(self, left: Tree | None = None):  # Forward reference without quotes
        self.left = left

# Without 'from __future__ import annotations':
class Tree2:
    def __init__(self, left: Tree2 | None = None):  # NameError at class definition!
        self.left = left
# Fix: use string: 'Tree2 | None'
```

PEP 649 (Python 3.14) proposes a better mechanism (lazy evaluation), superseding PEP 563.

---

## Interview Questions

### Q1: What's the difference between mypy, pydantic, and beartype? When do you use each?

**Model answer:**

| Tool | When it runs | What it checks | Use case |
|------|-------------|----------------|----------|
| mypy / pyright | Development time (CI) | All annotated code, statically | Catch bugs before they run |
| pydantic | Runtime, at object creation | Data from external sources (APIs, config, user input) | Validate and parse untrusted input |
| beartype | Runtime, at every function call | Function parameter and return types | Low-overhead production safety net |
| typeguard | Runtime, at every call (full depth) | Full container contents | Tests and development only |

Decision flow:
1. Always use **mypy/pyright** in CI — catches errors for free before runtime.
2. At system boundaries (HTTP endpoints, config files, CLI args, database output): use **pydantic** to parse and validate.
3. If you want runtime enforcement across the codebase with minimal overhead: **beartype**.
4. For comprehensive testing: **typeguard** with `install_import_hook`.

### Q2: Why is `Any` dangerous in a typed codebase, and how do you identify where it's spreading?

**Model answer:**
`Any` is "type-safe" from the checker's perspective — it accepts all operations. But it spreads to anything it touches, silently turning off type checking for those variables:

```python
from typing import Any, cast

def fetch(url: str) -> Any:   # returns untyped data
    ...

result = fetch("https://api.example.com/data")
result.whatever()   # no error — Any allows all attribute access
count: int = result["count"]   # no error — Any allows subscript
# The real value might be a str or None — silent runtime failure

# To stop the spread: cast or validate at the boundary:
from pydantic import TypeAdapter
from typing import TypedDict

class Response(TypedDict):
    count: int
    items: list[str]

ta = TypeAdapter(Response)
response: Response = ta.validate_python(fetch("https://..."))
# Now response is properly typed; Any doesn't spread further
```

Finding `Any` spread: `mypy --warn-return-any --disallow-any-generics` flags dangerous Any usage. pyright's strict mode errors on implicit Any.

### Q3: Explain how pydantic v2's validation model differs from a simple `isinstance()` check.

**Model answer:**
`isinstance()` checks the Python type of an existing object — it doesn't coerce or create objects. Pydantic constructs a validated object from raw data, with coercion:

```python
from pydantic import BaseModel
from datetime import datetime

class Event(BaseModel):
    name: str
    count: int
    created_at: datetime

# Pydantic coerces from dict with string values:
raw = {"name": "deploy", "count": "42", "created_at": "2024-01-15T10:30:00"}
event = Event.model_validate(raw)
print(type(event.count))       # int — "42" coerced to int
print(type(event.created_at))  # datetime — ISO string parsed to datetime

# isinstance check would reject this entirely:
isinstance(raw, Event)   # False — it's a dict
```

Pydantic v2's validation pipeline:
1. **Validation mode:** coerce and validate (default for input data).
2. **Strict mode:** no coercion, exact types only.
3. **Custom validators:** `@field_validator`, `@model_validator` for business logic.

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    email: str
    age: int

    @field_validator('email')
    @classmethod
    def email_must_contain_at(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()

    @field_validator('age')
    @classmethod
    def age_must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError('Age must be non-negative')
        return v
```

### Q4: What is `TypedDict` and when is it better than `dataclass` or `pydantic.BaseModel`?

**Model answer:**
`TypedDict` adds type information to plain dicts — the runtime object IS a dict, not an instance of a new class. No construction overhead, no coercion, no validation:

```python
from typing import TypedDict

class Point(TypedDict):
    x: float
    y: float

p: Point = {"x": 1.0, "y": 2.0}   # just a dict
p["x"]    # dict access
len(p)    # 2
isinstance(p, dict)   # True

# TypedDict wins when:
# 1. Interoperating with JSON/dict-expecting APIs (no serialization step)
# 2. Adding types to existing code that passes dicts
# 3. Typing the output of json.loads()
```

Comparison:
| | `TypedDict` | `dataclass` | `pydantic.BaseModel` |
|-|------------|-------------|---------------------|
| Runtime type | `dict` | class instance | class instance |
| Validation | No | No | Yes |
| Coercion | No | No | Yes |
| Serialization | Manual | Manual | Built-in |
| Attribute access | `d['key']` | `d.key` | `d.key` |
| Performance | Fastest | Fast | Slower (validation) |
| Use for | Typed dicts | In-memory data | External data I/O |

### Q5: How does `get_type_hints()` differ from `__annotations__`?

**Model answer:**
`__annotations__` stores raw annotations — if `from __future__ import annotations` is active, everything is strings (not evaluated). Forward references remain as strings:

```python
from __future__ import annotations

class Node:
    def __init__(self, next: Node | None = None):
        self.next = next

print(Node.__init__.__annotations__)
# {'next': 'Node | None', 'return': 'None'} — strings, not resolved
```

`get_type_hints()` evaluates the string annotations in the correct namespace and resolves forward references:

```python
import typing

hints = typing.get_type_hints(Node.__init__)
# {'next': Node | None, 'return': type(None)} — actual types
```

This matters when:
1. Building frameworks that introspect types at runtime (pydantic, attrs, dataclasses, FastAPI).
2. Implementing custom validators or serializers.
3. Using forward references (`if TYPE_CHECKING: from ...`).

Always use `get_type_hints()` in frameworks — `__annotations__` is too raw. But beware: `get_type_hints()` imports everything referenced in the annotations, which can cause circular imports. The `include_extras` parameter (Python 3.11+) controls whether `Annotated` metadata is preserved.

---

## Gotcha Follow-ups

**"Can mypy check code that uses `setattr` or `getattr` dynamically?"**
Partially — mypy tracks `setattr(obj, 'known_attr', val)` if the attribute name is a string literal and the object's type is known. But dynamic attribute names (variables) produce `Any`. This is a fundamental limitation of static analysis — dynamism escapes the type system. Pattern: define a typed interface and keep the dynamic part behind a boundary.

**"What does `Annotated[int, Field(ge=0)]` mean?"**
`Annotated[T, *metadata]` (PEP 593) wraps a type with arbitrary metadata. The type checker sees only `int`; frameworks like pydantic read the `Field(ge=0)` constraint at runtime for validation. `Annotated` lets you attach runtime metadata to types without affecting static checking.

---

## Under the Hood

`typing.get_type_hints()` (`Lib/typing.py`): calls `eval()` on string annotations using the module's `__globals__` and optionally provided `localns`/`globalns`. Handles `TYPE_CHECKING = True` for evaluation context. The `include_extras=True` parameter preserves `Annotated` wrapper (default strips it, returning the base type).

pydantic v2 uses `pydantic-core` (Rust library) which compiles validators from the schema at model class creation time. The schema is derived from type annotations via `get_type_hints()` and pydantic's own type resolution. The compiled Rust validator is cached on the model class as `__pydantic_validator__`.
