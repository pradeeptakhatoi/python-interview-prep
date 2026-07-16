# Structural Pattern Matching (match/case)

## Concept

Structural pattern matching (`match`/`case`, PEP 634, Python 3.10+) is not just a switch statement — it matches against the structure and content of objects, sequences, mappings, and class instances. Understanding what it compiles to and when it actually destructures is essential.

### Basic Patterns

```python
# Literal pattern:
def http_status(code: int) -> str:
    match code:
        case 200:
            return "OK"
        case 404:
            return "Not Found"
        case 500:
            return "Internal Server Error"
        case _:   # wildcard — matches anything, binds nothing
            return f"Unknown {code}"

# Capture pattern — binds the value to a name:
def describe(value):
    match value:
        case 0:
            print("zero")
        case n if n > 0:   # guard expression after pattern
            print(f"positive: {n}")
        case n:
            print(f"negative: {n}")   # n is bound here
```

### Sequence Pattern

```python
def process_command(command: list[str]) -> str:
    match command:
        case ["quit"]:
            return "Exiting"
        case ["go", direction]:            # binds 'direction'
            return f"Going {direction}"
        case ["go", direction, speed]:     # binds two variables
            return f"Going {direction} at {speed}"
        case ["look", *where]:             # star pattern — rest of list
            return f"Looking at {where}"
        case [first, *rest]:               # first element + rest
            return f"Command: {first}, args: {rest}"
        case _:
            return f"Unknown: {command}"

print(process_command(["go", "north"]))      # Going north
print(process_command(["go", "east", "fast"]))  # Going east at fast
print(process_command(["look", "left", "right"]))  # Looking at ['left', 'right']
```

### Mapping Pattern

```python
def handle_event(event: dict) -> str:
    match event:
        case {"type": "click", "button": button, "x": x, "y": y}:
            return f"Click {button} at ({x}, {y})"
        case {"type": "keydown", "key": key}:
            return f"Key pressed: {key}"
        case {"type": "resize", **rest}:    # **rest captures remaining keys
            return f"Resize event, extra: {rest}"
        case {"type": str(event_type)}:     # class pattern inside mapping
            return f"Unknown event type: {event_type}"
        case _:
            return "Malformed event"

print(handle_event({"type": "click", "button": "left", "x": 10, "y": 20}))
print(handle_event({"type": "keydown", "key": "Enter"}))
```

### Class Pattern

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

@dataclass
class Circle:
    center: Point
    radius: float

@dataclass
class Rectangle:
    top_left: Point
    bottom_right: Point

def describe_shape(shape) -> str:
    match shape:
        case Circle(center=Point(x=0, y=0), radius=r):
            return f"Circle centered at origin, radius {r}"
        case Circle(center=Point(x=cx, y=cy), radius=r):
            return f"Circle at ({cx}, {cy}), radius {r}"
        case Rectangle(top_left=Point(x=x1, y=y1),
                       bottom_right=Point(x=x2, y=y2)):
            w = x2 - x1
            h = y2 - y1
            return f"Rectangle {w}x{h} at ({x1},{y1})"
        case _:
            return "Unknown shape"

print(describe_shape(Circle(Point(0, 0), 5)))   # Circle centered at origin, radius 5
print(describe_shape(Circle(Point(1, 2), 3)))   # Circle at (1, 2), radius 3

# Class pattern works with __match_args__:
print(Point.__match_args__)   # ('x', 'y') — defined by @dataclass
```

### OR Patterns and Guards

```python
def classify_http_method(method: str) -> str:
    match method.upper():
        case "GET" | "HEAD" | "OPTIONS":    # OR pattern
            return "safe"
        case "POST" | "PUT" | "PATCH" | "DELETE":
            return "unsafe"
        case m if m.startswith("X-"):       # guard
            return f"extension method: {m}"
        case _:
            return "unknown"

# AS pattern — bind after matching:
def process(value):
    match value:
        case [x, y] as point:    # 'point' bound to the whole matched sequence
            print(f"Point: {point}, x={x}, y={y}")

process([1, 2])   # Point: [1, 2], x=1, y=2
```

### What `match` Compiles To

```python
import dis

def simple_match(x):
    match x:
        case 1:
            return "one"
        case 2:
            return "two"
        case _:
            return "other"

dis.dis(simple_match)
# match/case compiles to:
# COPY (or LOAD_FAST) x
# For literal patterns: COMPARE_OP + POP_JUMP_IF_FALSE to next case
# For capture patterns: STORE_FAST (always succeeds)
# For class patterns: GET_LEN, MATCH_CLASS, etc.

# It is NOT a jump table (unlike C switch) — it's sequential if-elif checks
# For literals: O(n) — test each case in order until one matches
# For class patterns: uses __match_args__ and attribute access
```

---

## Interview Questions

### Q1: How does class pattern matching work and what is `__match_args__`?

**Model answer:**
When a class pattern is used, Python:
1. Calls `isinstance(subject, ClassName)` — if False, pattern doesn't match.
2. Uses `__match_args__` (a class attribute, auto-generated by `@dataclass`) to map positional pattern arguments to attribute names.
3. For each keyword argument in the pattern, accesses `getattr(subject, name)` and matches it recursively.

```python
class Vector:
    __match_args__ = ('x', 'y', 'z')   # positional pattern order

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

v = Vector(1, 2, 3)

match v:
    case Vector(x, y, z):   # positional — maps to x=1, y=2, z=3 via __match_args__
        print(f"Vector: {x}, {y}, {z}")

    case Vector(x=1, y=y_val):  # keyword — accesses v.x and v.y
        print(f"x=1, y={y_val}")

# Without __match_args__, only keyword patterns work:
class NoMatchArgs:
    def __init__(self, val):
        self.val = val

    # No __match_args__

match NoMatchArgs(5):
    case NoMatchArgs(val=v):   # OK — keyword pattern
        print(v)
    # case NoMatchArgs(v):     # TypeError — __match_args__ not defined
```

### Q2: What are the performance characteristics of `match`/`case` vs `if`/`elif`?

**Model answer:**
`match`/`case` compiles to essentially the same bytecode as `if`/`elif` chains. There is no jump table optimization for literal patterns — it's O(n) sequential matching.

```python
import dis

# These compile to nearly identical bytecode:
def with_match(x):
    match x:
        case 1: return "a"
        case 2: return "b"
        case _: return "c"

def with_elif(x):
    if x == 1: return "a"
    elif x == 2: return "b"
    else: return "c"

# For performance-critical code with many integer cases, use a dispatch dict:
DISPATCH = {1: "a", 2: "b"}
def dict_dispatch(x):
    return DISPATCH.get(x, "c")   # O(1) dict lookup

# match/case advantages:
# 1. More readable for complex structural patterns
# 2. Type-safe destructuring (extracts values without manual indexing)
# 3. Exhaustiveness checking (mypy/pyright can warn on unhandled cases with Never)
# 4. No accidental variable shadowing in nested conditions
```

### Q3: What is the difference between a "capture pattern" and a "value pattern" in match/case?

**Model answer:**
This is a crucial gotcha. A bare name in a `case` is ALWAYS a capture (binds the value). To match against a constant stored in a variable, you must use a dotted name:

```python
# WRONG: case x doesn't match the value of x — it captures!
target = 42

match value:
    case target:   # This CAPTURES value into target, doesn't compare!
        print("matched")  # Always runs (capture always succeeds)

# CORRECT: use dotted name to reference a constant
class Status:
    OK = 200
    NOT_FOUND = 404

match code:
    case Status.OK:         # value pattern — compares code == Status.OK
        print("OK")
    case Status.NOT_FOUND:  # value pattern — dotted name lookup
        print("Not found")

# Also correct: use literal values (not variables) for literal patterns
THRESHOLD = 100  # module-level constant
match n:
    case n if n == THRESHOLD:  # guard with explicit comparison
        ...
    # case THRESHOLD:  # WRONG — would capture into THRESHOLD, shadowing it!
```

This is the most common `match`/`case` bug: `case some_var` doesn't compare against `some_var` — it captures the matched value into `some_var`.

### Q4: How do you use `match`/`case` for exhaustive ADT-style pattern matching?

**Model answer:**
Use sealed class hierarchies (all subclasses known) and type checkers for exhaustiveness:

```python
from dataclasses import dataclass
from typing import Never

@dataclass
class Ok:
    value: int

@dataclass
class Err:
    message: str

type Result = Ok | Err   # Python 3.12 type alias

def process(result: Result) -> str:
    match result:
        case Ok(value=v):
            return f"Success: {v}"
        case Err(message=msg):
            return f"Error: {msg}"
        # mypy/pyright will warn if any subtype of Result is unhandled

# Exhaustiveness check via Never:
def assert_never(value: Never) -> Never:
    raise AssertionError(f"Unexpected value: {value!r}")

def process_exhaustive(result: Result) -> str:
    match result:
        case Ok(value=v):
            return f"Success: {v}"
        case Err(message=msg):
            return f"Error: {msg}"
        case _ as unreachable:
            assert_never(unreachable)   # type error if Result gains a new variant

# Practical example: AST processing
@dataclass
class Literal:
    value: int

@dataclass
class Add:
    left: 'Expr'
    right: 'Expr'

@dataclass
class Mul:
    left: 'Expr'
    right: 'Expr'

type Expr = Literal | Add | Mul

def evaluate(expr: Expr) -> int:
    match expr:
        case Literal(value=v):
            return v
        case Add(left=l, right=r):
            return evaluate(l) + evaluate(r)
        case Mul(left=l, right=r):
            return evaluate(l) * evaluate(r)

result = evaluate(Add(Mul(Literal(2), Literal(3)), Literal(4)))
print(result)   # 10
```

### Q5: How does pattern matching handle custom classes that don't use `@dataclass`?

**Model answer:**
Any class can participate in structural pattern matching by defining `__match_args__` and ensuring the matched attributes are accessible:

```python
class HTTPRequest:
    __match_args__ = ('method', 'path', 'headers')

    def __init__(self, method: str, path: str, headers: dict):
        self.method = method
        self.path = path
        self.headers = headers

    # Optional: custom matching via __match_class__
    # (Not a standard dunder — class patterns use isinstance + attribute access)

def route(request: HTTPRequest) -> str:
    match request:
        case HTTPRequest('GET', '/', _):
            return "home page"
        case HTTPRequest('POST', '/api/users', headers) if 'Authorization' in headers:
            return "create user (authenticated)"
        case HTTPRequest(method, path, _):
            return f"{method} {path} — unhandled"

req = HTTPRequest('GET', '/', {})
print(route(req))   # home page

# For built-in types: use their natural patterns
# str: matches as a string literal or captures as variable
# int, float: matches as numeric literal or capture
# list, tuple: use sequence patterns
# dict: use mapping patterns

# Note: bool is a subclass of int, so:
match True:
    case True:   # literal pattern matches
        print("true")
    # case 1: would ALSO match True! (True == 1)
    # Match is structural — types matter: use 'case bool() if value:' for type-safe bool check
```

---

## Gotcha Follow-ups

**"Does `match`/`case` short-circuit or evaluate all patterns?"**
It evaluates patterns in order and stops at the first match (`case` is like `elif`). Patterns are NOT evaluated if a previous case already matched. However, the guard expression (`if condition`) is evaluated for each case even after the pattern matches — if the guard is False, matching continues to the next case.

**"Can you fall through between cases like in C switch?"**
No — there is no fall-through. Each `case` block is independent. This is intentional: fall-through in C switch is a notorious source of bugs. If you need the same action for multiple patterns, use OR patterns: `case 1 | 2 | 3: return "small"`.

---

## Under the Hood

`match`/`case` is compiled in `Python/compile.c: compiler_match()` and `compiler_pattern_*()` functions. Each pattern type has a dedicated compiler function:
- Literal: `COMPARE_OP` (== comparison) or `IS_OP` (for None/True/False)
- Capture: `STORE_FAST` (always succeeds)
- Sequence: `GET_LEN` + `MATCH_SEQUENCE` + `UNPACK_SEQUENCE`
- Mapping: `MATCH_MAPPING` + `MATCH_KEYS`
- Class: `MATCH_CLASS` (calls `isinstance()` + extracts `__match_args__` attributes)

`MATCH_CLASS` opcode (`Python/ceval.c`): calls `match_class()` which: (1) `isinstance(subject, cls)`, (2) resolves positional patterns via `__match_args__`, (3) calls `getattr(subject, attr)` for each named pattern, (4) stores extracted values for subsequent `STORE_FAST` opcodes. There is no fallthrough and no computed goto optimization — each `case` block ends with a `JUMP_FORWARD` to skip remaining cases.
