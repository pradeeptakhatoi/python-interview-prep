# Mutable Default Arguments and Late-Binding Closures

## Concept

Two of the most common Python footguns:
1. **Mutable default arguments:** default values are evaluated once at function definition, not at each call — a shared mutable default accumulates state across calls.
2. **Late-binding closures:** closures capture variable NAMES, not VALUES — the variable is looked up at call time, not at the time the closure was created.

### Mutable Default Argument

```python
# The footgun:
def append_to(item, result=[]):   # [] created ONCE at function definition
    result.append(item)
    return result

print(append_to(1))   # [1]
print(append_to(2))   # [1, 2]  — same list, not [2]!
print(append_to(3))   # [1, 2, 3]

# Why: default values are stored in __defaults__ on the function object:
print(append_to.__defaults__)   # ([1, 2, 3],)
# Same list object shared across all calls without explicit 'result' argument

# The fix: use None as sentinel, create new list in body:
def append_to_fixed(item, result=None):
    if result is None:
        result = []
    result.append(item)
    return result

print(append_to_fixed(1))   # [1]
print(append_to_fixed(2))   # [2] — fresh list each time
print(append_to_fixed(3))   # [3]

# Shared default is sometimes intentional (cache / memo):
def memoize(func, _cache={}):
    """_cache intentionally shared across calls."""
    def wrapper(*args):
        if args not in _cache:
            _cache[args] = func(*args)
        return _cache[args]
    return wrapper
```

### Mutable Defaults with Dataclasses

```python
from dataclasses import dataclass, field

# WRONG: mutable default in dataclass field:
@dataclass
class Order_wrong:
    items: list = []   # TypeError: mutable default not allowed

# CORRECT: use field(default_factory=...)
@dataclass
class Order:
    items: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    tags: set = field(default_factory=set)

# Each Order instance gets its own list/dict/set:
o1 = Order()
o2 = Order()
o1.items.append("widget")
print(o2.items)   # [] — independent
```

### Late-Binding Closures

```python
# The footgun:
def make_adders():
    adders = []
    for i in range(5):
        adders.append(lambda x: x + i)   # captures 'i' by reference, not value!
    return adders

adders = make_adders()
print(adders[0](10))   # 14, not 10! (i == 4 at call time)
print(adders[2](10))   # 14
print(adders[4](10))   # 14 — all return x + 4

# Why: the closure captures the name 'i' in the enclosing scope.
# After the loop, 'i' == 4. ALL closures see i == 4 when called.

# Fix 1: default argument (evaluated at definition time)
def make_adders_fixed():
    adders = []
    for i in range(5):
        adders.append(lambda x, i=i: x + i)   # i=i captures current value
    return adders

adders = make_adders_fixed()
print(adders[0](10))   # 10
print(adders[2](10))   # 12
print(adders[4](10))   # 14

# Fix 2: functools.partial
import functools

def add(x, n):
    return x + n

adders = [functools.partial(add, n=i) for i in range(5)]
print(adders[0](10))   # 10
print(adders[2](10))   # 12

# Fix 3: factory function (creates a new scope with a fresh binding)
def make_adder(n):
    return lambda x: x + n   # n is a local variable — not shared

adders = [make_adder(i) for i in range(5)]
print(adders[0](10))   # 10
print(adders[2](10))   # 12
```

### Late Binding in Other Contexts

```python
# List comprehension loop variable in Python 2 (leaked into enclosing scope)
# Python 3 fixed this — list comprehension has its own scope:
x = 'outside'
result = [x for x in range(3)]
print(x)   # 'outside' — x not leaked from comprehension in Python 3

# BUT generator expressions still close over the VARIABLE in some cases:
# Safe: the for-variable in the comprehension has its own scope
fns = [lambda: i for i in range(3)]
print([f() for f in fns])   # [2, 2, 2] — late binding!

fns = [lambda i=i: i for i in range(3)]
print([f() for f in fns])   # [0, 1, 2] — fixed

# Button callbacks in GUI code — classic late binding bug:
import tkinter as tk

root = tk.Tk()
buttons = []
for i in range(3):
    btn = tk.Button(
        root,
        text=f"Button {i}",
        command=lambda: print(f"Clicked {i}")  # all print "Clicked 2"!
    )
    # Fix:
    btn = tk.Button(
        root,
        text=f"Button {i}",
        command=lambda i=i: print(f"Clicked {i}")  # correct
    )
    buttons.append(btn)
```

### Inspecting Closures

```python
# See what a closure captures:
def outer(x):
    def inner():
        return x
    return inner

fn = outer(42)
print(fn.__closure__)             # (<cell at 0x...>,)
print(fn.__closure__[0].cell_contents)  # 42
print(fn.__code__.co_freevars)    # ('x',)

# Cell: a mutable container holding the shared variable
# Multiple closures in the same scope share the SAME cell:
def make_closures():
    value = [0]  # mutable container to simulate shared mutable state

    def getter():
        return value[0]

    def setter(n):
        value[0] = n

    return getter, setter

get, set_ = make_closures()
set_(42)
print(get())  # 42 — shared through the same 'value' cell
```

---

## Interview Questions

### Q1: Why does Python evaluate default argument values at function definition time rather than call time?

**Model answer:**
Python evaluates default argument expressions when the `def` statement executes — they become attributes of the function object (`func.__defaults__`). This matches Python's general rule: expressions are evaluated when encountered.

The design rationale: this allows defaults to be computed once (e.g., `default=get_config()` computes config once at startup, not on every call). For immutable defaults (int, str, tuple, frozenset), there's no observable difference. For mutable defaults (list, dict, set), the single shared object is problematic.

```python
# The default is stored as a regular Python object:
def fn(items=[]):
    return items

print(id(fn.__defaults__[0]))   # e.g. 140234567890
fn().append(1)
print(id(fn.__defaults__[0]))   # same id — same list
print(fn.__defaults__)           # ([1],)
```

**The fix pattern:** use `None` as a sentinel and create the mutable in the body:
```python
def fn(items=None):
    if items is None:
        items = []
    return items
```

### Q2: What is a closure and how does late binding affect it?

**Model answer:**
A closure is a function that references free variables from its enclosing scope. The closure maintains a reference to the enclosing scope's "cell" objects — mutable containers for the variable's value. The variable is looked up by name when the closure is called, not when it's created.

```python
def outer():
    x = 1

    def inner():
        return x   # free variable 'x' — looked up in enclosing scope at call time

    x = 2   # modifies x AFTER inner is defined
    return inner

fn = outer()
print(fn())   # 2 — 'x' is 2 at call time, not 1 (when inner was defined)
```

Late binding becomes a footgun in loops because:
1. The loop variable (`i`) is a single name in the enclosing scope.
2. All closures created in the loop capture the same name.
3. After the loop, the name holds the last value.
4. All closures return the same value when called.

Fix: bind at creation time via `lambda i=i: ...` or `functools.partial`.

### Q3: How does `functools.partial` differ from a closure for avoiding late binding?

**Model answer:**
Both capture a value at creation time, but via different mechanisms:

```python
import functools

def add(x, n):
    return x + n

# partial: creates a new callable with arguments pre-filled
adder_5 = functools.partial(add, n=5)
print(adder_5(10))   # 15
print(adder_5.__args__)    # ()
print(adder_5.__keywords__)  # {'n': 5}

# closure (lambda with default):
adder_5_closure = lambda x, n=5: x + n  # n captured at lambda creation

# Differences:
# - partial is more readable for named functions
# - partial preserves the original function's __doc__, __name__ via functools.WRAPPER_ASSIGNMENTS
# - closure is more flexible (can close over multiple variables, include logic)
# - partial works only for positional/keyword pre-filling

# For callbacks/event handlers: partial is idiomatic
button.command = functools.partial(handle_click, item_id=item.id, row=row_num)
```

### Q4: Are there cases where sharing a mutable default is intentional?

**Model answer:**
Yes — when you explicitly want shared mutable state:

```python
# 1. Simple cache/memo (intentional sharing):
def get_config(key: str, _cache: dict = {}):
    if key not in _cache:
        _cache[key] = load_from_env(key)
    return _cache[key]

# 2. Call counter (debugging):
def counted_fn(x, _count: list[int] = [0]):
    _count[0] += 1
    print(f"Call #{_count[0]}: x={x}")
    return x * 2

# 3. Sentinel object (immutable default that tests identity):
_MISSING = object()   # module-level sentinel, not a default

def get(key, default=_MISSING):
    ...
    if result is _MISSING:
        raise KeyError(key)
    return result

# In these cases: DOCUMENT that the sharing is intentional with a clear comment
```

### Q5: How do you detect and debug mutable default issues in an existing codebase?

**Model answer:**

```python
# 1. Inspect __defaults__ at runtime:
def check_mutable_defaults(func):
    defaults = func.__defaults__ or ()
    mutable_types = (list, dict, set)
    for i, default in enumerate(defaults):
        if isinstance(default, mutable_types):
            import warnings
            warnings.warn(
                f"{func.__name__}: parameter at index "
                f"{len(func.__code__.co_varnames) - len(defaults) + i} "
                f"has mutable default {type(default).__name__!r}",
                UserWarning,
                stacklevel=2,
            )
    return func

@check_mutable_defaults
def bad_function(x, items=[]):   # UserWarning emitted
    ...

# 2. Static analysis:
# flake8-bugbear: B006 — do not use mutable data structures for argument defaults
# ruff: B006

# 3. In tests: call the function twice with no explicit default
# and assert the result is independent:
def test_no_shared_state():
    result1 = fn()
    fn().append(99)  # modify what the second call returns
    result2 = fn()
    assert result2 != result1 or True  # should be independent
```

---

## Gotcha Follow-ups

**"Can dataclasses have mutable defaults?"**
Not directly — `@dataclass` raises `ValueError: mutable default <class 'list'> is not allowed`. Use `field(default_factory=list)`. But `@dataclass` DOES allow mutable default values for ClassVar fields (class attributes, not instance fields) — these are explicitly shared across instances.

**"Is the late-binding behavior of closures a bug?"**
It's a deliberate design choice. Late binding allows closures to observe changes to the enclosing variable after the closure is created — useful when the enclosed scope intentionally mutates the variable and wants closures to see the update. The "bug" manifests only when developers expect closures to snapshot the value at creation time (which requires explicit capture via default argument or factory).

---

## Under the Hood

Default argument values are stored in `func.__defaults__` (a tuple for positional defaults) and `func.__kwdefaults__` (a dict for keyword-only defaults). Both are populated by the `MAKE_FUNCTION` opcode when the `def` statement is executed. Closures are implemented via "cell objects" (`CellType` in CPython): the enclosing scope's variable lives in a cell, and all closures in that scope share a pointer to the same cell. `func.__closure__` is a tuple of cells. The LOAD_DEREF and STORE_DEREF bytecodes read/write through cells. This means all closures in the same scope sharing the same variable are always synchronized — changing the variable updates it for all.
