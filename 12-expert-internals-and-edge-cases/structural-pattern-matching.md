# Structural Pattern Matching (match/case)

## Concept

Python 3.10 introduced `match`/`case` (PEP 634). It is NOT a simple `switch` statement — it's a powerful structural decomposition tool that operates on the shape and content of objects. Understanding how it differs from `if/elif` chains and what `__match_args__` enables is essential for using it correctly at scale.

### Basic Syntax and Pattern Types

```python
def describe(command):
    match command:
        case "quit":
            return "Quitting"

        case "go" | "move":           # OR pattern
            return "Moving"

        case ["go", direction]:       # sequence pattern — destructures list/tuple
            return f"Going {direction}"

        case {"action": action, "target": target}:  # mapping pattern
            return f"Action: {action} on {target}"

        case _:                       # wildcard — always matches, no binding
            return "Unknown command"
```

### Pattern Types

```python
value = some_object

match value:
    # Literal patterns:
    case 42: ...
    case "hello": ...
    case True: ...
    case None: ...

    # Capture patterns (bind to name):
    case x:             # matches anything, binds to x
        use(x)

    # Wildcard (no binding):
    case _:             # matches anything, binds nothing
        pass

    # OR patterns:
    case 1 | 2 | 3:     # matches any of these values
        pass

    # Sequence patterns (lists and tuples):
    case [first, *rest]:          # head/tail destructuring
        print(first, rest)
    case (x, y):                  # exactly two elements
        print(x, y)
    case []:                      # empty sequence
        pass

    # Mapping patterns:
    case {"key": value}:          # dict contains "key"; binds value
        pass
    case {"x": int() as x}:       # dict has "x" and it's an int; bind to x
        pass

    # Class patterns:
    case Point(x=0, y=0):         # Point instance with x=0, y=0
        print("origin")
    case Point(x=x_val, y=y_val): # any Point, binds coordinates
        print(f"at ({x_val}, {y_val})")

    # As patterns (bind + check):
    case [x, y] as pair:          # matches 2-element sequence, binds both pair and x,y
        print(x, y, pair)

    # Guard (if clause):
    case x if x > 0:              # match only if x > 0
        pass
```

### Class Patterns and `__match_args__`

Without `__match_args__`, class patterns require keyword syntax:

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

# Without __match_args__ — keyword args only:
match p:
    case Point(x=0, y=0): print("origin")
    case Point(x=x, y=y): print(f"({x}, {y})")

# With __match_args__ — positional args allowed:
class Point:
    __match_args__ = ('x', 'y')  # defines positional pattern order

    def __init__(self, x, y):
        self.x = x
        self.y = y

match p:
    case Point(0, 0): print("origin")          # positional: x=0, y=0
    case Point(x, y): print(f"({x}, {y})")    # positional bind
```

`@dataclass` automatically sets `__match_args__` to the field names in definition order.

### How match/case Differs from if/elif

```python
# These are CONCEPTUALLY similar but mechanically different:

# if/elif version:
def process_if(cmd):
    if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "go":
        direction = cmd[1]
        return f"Going {direction}"
    elif isinstance(cmd, dict) and "action" in cmd:
        action = cmd["action"]
        return f"Action: {action}"
    else:
        return "Unknown"

# match/case version:
def process_match(cmd):
    match cmd:
        case ["go", direction]:
            return f"Going {direction}"
        case {"action": action}:
            return f"Action: {action}"
        case _:
            return "Unknown"
```

**Key differences:**
1. **Sequence matching** — `case [x, y]` checks both structure (2-element) and binds in one step. No separate `isinstance` + `len` check.
2. **Mapping matching** — mapping patterns check for KEY PRESENCE, not exact match. `case {"action": a}` matches any dict with an "action" key, regardless of other keys.
3. **No fall-through** — unlike C `switch`, the first matching case executes and control exits. No `break` needed.
4. **Binding scope** — bindings from patterns are scoped to the `case` block but visible in the surrounding function (variables bound in match cases are available after the match statement).

### Bytecode: It's Not a jump table

```python
import dis

def match_demo(x):
    match x:
        case 1: return "one"
        case 2: return "two"
        case _: return "other"

dis.dis(match_demo)
```

Output shows `MATCH_SEQUENCE`, `MATCH_MAPPING`, `MATCH_CLASS` opcodes — not a simple comparison chain. For literal integer patterns, the compiler does generate comparison-based code, but for structural patterns, it uses the pattern-matching opcodes. There is no bytecode-level jump table; each pattern is evaluated in order.

### Practical Patterns at Scale

```python
from dataclasses import dataclass
from typing import Union

@dataclass
class AddUser:
    username: str
    email: str

@dataclass
class DeleteUser:
    user_id: int

@dataclass
class UpdateEmail:
    user_id: int
    new_email: str

Command = Union[AddUser, DeleteUser, UpdateEmail]

def handle_command(cmd: Command) -> str:
    match cmd:
        case AddUser(username=name, email=email):
            return f"Adding {name} ({email})"
        case DeleteUser(user_id=uid):
            return f"Deleting user {uid}"
        case UpdateEmail(user_id=uid, new_email=email):
            return f"Updating {uid}'s email to {email}"
        case _:
            raise ValueError(f"Unknown command: {cmd!r}")

# Works with exhaustiveness checking in type checkers (pyright, mypy)
```

### `__match_args__` in Custom Classes

```python
class Token:
    __match_args__ = ('type', 'value')

    def __init__(self, type: str, value: str):
        self.type = type
        self.value = value

def parse_token(token: Token):
    match token:
        case Token("NUMBER", value):             # positional: type="NUMBER"
            return int(value)
        case Token("STRING", value):
            return value.strip('"')
        case Token("IDENT", "if"):               # specific keyword
            return "if_keyword"
        case Token("IDENT", name):               # any identifier
            return f"identifier:{name}"
        case Token(tok_type, _):                 # catch-all with type bound
            raise SyntaxError(f"Unexpected {tok_type}")
```

---

## Interview Questions

### Q1: How does structural pattern matching differ from a series of `isinstance` checks?

**Model answer:**  
`match`/`case` goes beyond `isinstance` in three ways:

1. **Simultaneous structure and content checking:**
```python
# isinstance approach — multiple checks:
if isinstance(data, list) and len(data) == 2:
    first, second = data
    if isinstance(first, str):
        process(first, second)

# match approach — one pattern:
match data:
    case [str() as first, second]:  # checks: is list, has 2 elements, first is str
        process(first, second)
```

2. **Mapping partial matching:** `case {"key": val}` matches any dict that HAS "key", not only dicts with exactly one key. `isinstance` + key check requires two operations.

3. **Binding in patterns:** Variables bound in patterns are usable immediately without separate assignment. `case Point(x=x_coord)` both checks and binds in one expression.

The compiler transforms `match`/`case` into efficient bytecode using dedicated opcodes (`MATCH_SEQUENCE`, `MATCH_MAPPING`, `MATCH_CLASS`). For structural patterns, this is clearer AND faster than equivalent `isinstance` chains because it reduces attribute lookups and intermediate boolean checks.

### Q2: What is `__match_args__` and what happens without it?

**Model answer:**  
`__match_args__` is a class-level tuple that maps positional pattern arguments to attribute names. When a class pattern uses positional syntax (`case MyClass(a, b)`), Python uses `__match_args__` to convert positions to keyword lookups:

```python
class Point:
    __match_args__ = ('x', 'y')
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(3, 4)

match p:
    case Point(3, y):  # positional: checks p.x == 3, binds p.y to y
        print(y)       # 4
```

Without `__match_args__`, positional syntax raises `TypeError`. Only keyword patterns work:
```python
class NoMatchArgs:
    def __init__(self, x, y):
        self.x = x
        self.y = y

n = NoMatchArgs(3, 4)
match n:
    case NoMatchArgs(3, y):      # TypeError: NoMatchArgs() accepts no positional patterns
        pass
    case NoMatchArgs(x=3, y=y):  # keyword syntax always works
        print(y)
```

`@dataclass` automatically sets `__match_args__ = tuple(field.name for field in fields)`. Named tuples also set it automatically.

### Q3: Can `match`/`case` be used with arbitrary objects? What protocol does it use?

**Model answer:**  
Class patterns use attribute access, not a special protocol (unlike `__iter__` for sequence patterns). For `case MyClass(x=val)`, Python:
1. Checks `isinstance(subject, MyClass)`.
2. Accesses `subject.x` and checks if it matches `val` (or binds to `val` if it's a capture).

For sequence patterns, the subject must NOT be an instance of `str`, `bytes`, or `bytearray` (to avoid treating strings as character sequences unexpectedly). The check is `isinstance(subject, collections.abc.Sequence)` implicitly.

For mapping patterns, the subject must support `__getitem__` and `keys()` (dict-like). `MATCH_MAPPING` opcode checks `isinstance(subject, collections.abc.Mapping)`.

```python
from collections.abc import Mapping, Sequence

class CustomMapping(Mapping):
    def __init__(self, data):
        self._data = data
    def __getitem__(self, key): return self._data[key]
    def __iter__(self): return iter(self._data)
    def __len__(self): return len(self._data)

cm = CustomMapping({"action": "run"})
match cm:
    case {"action": a}:  # works — CustomMapping IS a Mapping
        print(a)         # "run"
```

### Q4: How does the bytecode compiler handle a large `match` statement vs. a chain of `if/elif`?

**Model answer:**  
For a `match` statement, the compiler generates:
1. A `MATCH_SEQUENCE` / `MATCH_MAPPING` / `MATCH_CLASS` opcode that checks the pattern type.
2. `GET_LEN` + comparisons for fixed-length checks.
3. `STORE_FAST` for bindings.
4. `JUMP_FORWARD` on mismatch to the next case.

This is NOT a jump table. Each case is checked in order — worst case O(n cases). The compiler does not generate a hash-based dispatch for literal patterns (unlike some languages).

For pure literal matching (integers, strings), `if/elif` with `==` and `match`/`case` compile to very similar bytecode — `match` may have slight overhead from the structural check machinery.

```python
import dis

# match with literals:
def m(x):
    match x:
        case 1: return "one"
        case 2: return "two"

# if/elif with literals:
def f(x):
    if x == 1: return "one"
    elif x == 2: return "two"

# Bytecode is nearly identical for the literal case
# match has slight overhead: MATCH_SEQUENCE check, etc.
# For large integer dispatches, a dict is faster than either
```

### Q5: What is an "irrefutable pattern" and why does Python restrict where it can appear?

**Model answer:**  
An irrefutable pattern is one that always succeeds — it can never fail to match. Irrefutable patterns include:
- Wildcard `_`
- Capture patterns (bare names like `x`)
- OR patterns where all alternatives are irrefutable

Python requires that only the LAST case in a `match` statement can be irrefutable:

```python
match x:
    case _:             # irrefutable — always matches
        pass            # must be last; otherwise subsequent cases are unreachable
    case 1:             # SyntaxError: this would never be reached
        pass
```

This prevents unreachable code (analogous to `default:` in C `switch` — must come last). Capture patterns in specific positions are NOT irrefutable because they're part of a larger structural pattern:

```python
match point:
    case Point(x=0, y=y):  # x=0 is refutable; y=y is irrefutable WITHIN the pattern
        # but the case as a whole is refutable (point.x might not be 0)
        pass
    case _:               # correctly placed last
        pass
```

The irrefutability check is done at compile time by the AST-to-bytecode compiler (in `Python/compile.c`), which raises `SyntaxError` for unreachable cases.

---

## Gotcha Follow-ups

**"Does `match` support fall-through like C's `switch`?"**  
No. Python's `match` exits after the first matching case. There is no `break` keyword needed. To handle multiple patterns with the same code, use OR patterns (`case 1 | 2 | 3`) or a single pattern with a guard (`case x if x in {1, 2, 3}`). Fall-through is deliberately excluded from the design (PEP 634).

**"Does pattern matching work on `None`? What's the difference between `case None:` and `case x:` when the value is `None`?"**  
`case None:` is a literal pattern — it only matches `None`. `case x:` is a capture pattern — it matches anything, including `None`, and binds it to `x`. This distinction matters:

```python
match value:
    case None:       # only matches None; uses IS check internally
        pass
    case x:          # matches anything including None; binds to x
        use(x)
```

Internally, `case None:` uses an IS comparison (`value is None`), not `==`. This is efficient and correct for `None`, `True`, and `False` (which are singletons). Literal patterns for these three use identity comparison; numeric literals use `==`.

---

## Under the Hood

Pattern matching is implemented across several files:
- `Python/compile.c` — compiles match statements to bytecode
- `Python/ceval.c` — implements `MATCH_SEQUENCE`, `MATCH_MAPPING`, `MATCH_CLASS` opcodes
- `Objects/matchobject.c` — the match object that accumulates pattern bindings

`MATCH_CLASS` opcode:
1. Checks `isinstance(subject, cls)`.
2. If the class has `__match_args__`, resolves positional patterns to attribute names.
3. For each attribute pattern, reads `getattr(subject, attr_name)` and checks/binds.
4. Returns a tuple of positional attribute values (or None on failure) for the compiler to unpack.

The match statement does NOT implement exhaustiveness checking at runtime — that's left to static type checkers (mypy 0.930+, pyright). At runtime, if no case matches and there's no `case _:`, the match statement simply falls through with no error.
