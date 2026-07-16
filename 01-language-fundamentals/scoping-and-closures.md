# Scoping and Closures: LEGB Rule, Late Binding, nonlocal vs global

## Concept

Python resolves names using the **LEGB** rule — searching four scopes in order until the name is found or a `NameError` is raised:

| Scope | Acronym | What It Is |
|-------|---------|-----------|
| Local | L | Names defined in the current function |
| Enclosing | E | Names in enclosing functions (for closures) |
| Global | G | Module-level names |
| Built-in | B | Names in `builtins` (`len`, `print`, `None`, etc.) |

```python
x = "global"

def outer():
    x = "enclosing"

    def inner():
        x = "local"
        print(x)   # "local" — L wins

    def inner_no_local():
        print(x)   # "enclosing" — L misses, E wins

    inner()
    inner_no_local()

outer()
```

### The Compiled Scope Decision

Python's compiler decides at **compile time** whether a name is local, enclosing, global, or built-in. This has a non-obvious consequence:

```python
x = 10

def broken():
    print(x)    # UnboundLocalError — not NameError!
    x = 20      # compiler sees this assignment → x is LOCAL in this function
                # so the print above refers to local x, which isn't assigned yet

broken()  # UnboundLocalError: local variable 'x' referenced before assignment
```

The presence of `x = 20` anywhere in the function body makes `x` local throughout that function.

### `global` — Reaching Module Scope

```python
counter = 0

def increment():
    global counter      # declares: counter is the MODULE-LEVEL name
    counter += 1        # reads and writes module-level counter

increment()
increment()
print(counter)   # 2

# Without global:
def broken_increment():
    counter += 1    # UnboundLocalError — counter treated as local
```

`global` should be used sparingly. Module-level mutable state is hard to test, hard to parallelize, and creates implicit coupling between functions.

### `nonlocal` — Reaching Enclosing Scope

`nonlocal` allows an inner function to write to a variable in the nearest enclosing scope that has that name:

```python
def make_counter():
    count = 0

    def increment():
        nonlocal count    # refers to 'count' in make_counter's scope
        count += 1
        return count

    def reset():
        nonlocal count
        count = 0

    return increment, reset

inc, rst = make_counter()
print(inc())   # 1
print(inc())   # 2
rst()
print(inc())   # 1 — reset worked
```

`nonlocal` only reaches enclosing function scopes — NOT the module scope. For module scope, use `global`.

### Closures and Cell Objects

A closure is an inner function that captures variables from its enclosing scope. CPython implements this via **cell objects** — shared containers between the enclosing frame and the closure:

```python
def make_adder(n):
    def add(x):
        return x + n     # n is a "free variable" — captured from make_adder
    return add

add5 = make_adder(5)
add10 = make_adder(10)

print(add5(3))    # 8
print(add10(3))   # 13

# Inspecting the closure:
print(add5.__code__.co_freevars)   # ('n',)
print(add5.__closure__)            # (<cell at 0x...>,)
print(add5.__closure__[0].cell_contents)  # 5
```

### Late Binding — The Classic Closure Trap

Closures capture variables by **reference** (via the cell object), not by value. This causes unexpected behavior in loops:

```python
# WRONG — all closures share the same cell for 'i':
funcs = [lambda: i for i in range(5)]
print([f() for f in funcs])   # [4, 4, 4, 4, 4] — all see the final value of i

# FIX 1: Default argument captures the value at definition time:
funcs = [lambda i=i: i for i in range(5)]
print([f() for f in funcs])   # [0, 1, 2, 3, 4]

# FIX 2: Use a factory function (clearest intent):
def make_func(i):
    def f(): return i
    return f

funcs = [make_func(i) for i in range(5)]
print([f() for f in funcs])   # [0, 1, 2, 3, 4]
```

**Why:** The loop variable `i` is ONE cell shared by all lambdas. After the loop, `i` is 4. All lambdas read the same cell and see 4. The factory approach creates a NEW scope (new cell) for each value of `i`.

### Class Scope — The LEGB Exception

Class bodies have their own scope but it is NOT searched for name resolution inside methods:

```python
class MyClass:
    x = 10  # class scope

    def method(self):
        print(x)       # NameError — class scope is NOT in LEGB for methods
        print(self.x)  # OK — attribute lookup, not scope lookup
        print(MyClass.x)  # OK — explicit global name

# List comprehensions inside class body don't see class scope in Python 3:
class Bad:
    items = [1, 2, 3]
    doubled = [x * 2 for x in items]  # NameError: items not in scope of comprehension
    # Fix: use a classmethod or __init__, or tuple/generator expression:
    doubled_ok = tuple(x * 2 for x in [1, 2, 3])  # literals work
```

---

## Interview Questions

### Q1: What is the LEGB rule and what happens when Python can't find a name in any scope?

**Model answer:**
Python searches **L**ocal → **E**nclosing → **G**lobal → **B**uilt-in. If the name isn't found in any scope, `NameError: name 'x' is not defined` is raised. Each scope is a dict-like namespace: local scope is the `localsplus` array (or `locals()` dict), enclosing scopes are accessed via cell objects, global scope is `module.__dict__`, and built-in scope is `builtins.__dict__`.

The search is determined at compile time for local/enclosing/global (`LOAD_FAST`, `LOAD_DEREF`, `LOAD_GLOBAL` opcodes). At runtime, only the value lookup happens.

```python
import dis

def demo():
    x = 1
    return len([x])   # len is LOAD_GLOBAL (falls through to builtins)

dis.dis(demo)
# LOAD_CONST  1    → STORE_FAST x
# LOAD_GLOBAL len  → LOAD_FAST x → BUILD_LIST → CALL → RETURN_VALUE
```

### Q2: Explain the `UnboundLocalError` — when does it occur and why is it different from `NameError`?

**Model answer:**
`UnboundLocalError` occurs when a name is classified as local (because there is an assignment to it somewhere in the function) but is read before it is assigned:

```python
val = "global"

def confusing():
    print(val)    # UnboundLocalError — val is LOCAL because of line below
    val = "local" # this makes val local throughout the function

confusing()
```

The difference from `NameError`:
- `NameError` — name doesn't exist in any scope.
- `UnboundLocalError` — name IS local but hasn't been assigned yet.

`UnboundLocalError` is a subclass of `NameError`. The compiler marks `val` as local (generates `LOAD_FAST`), but at runtime the slot hasn't been filled yet.

Common real-world trigger: conditionally assigning a variable and then reading it outside the condition:
```python
def process(data):
    if data:
        result = transform(data)  # only assigned if data is truthy
    return result   # UnboundLocalError if data was falsy
```

### Q3: What exactly does `nonlocal` do that a simple read of an enclosing variable doesn't?

**Model answer:**
Reading an enclosing variable works automatically — the compiler generates `LOAD_DEREF` which reads through the cell. The issue is *writing*:

```python
def outer():
    count = 0

    def inner_read():
        print(count)   # OK — LOAD_DEREF, reads from cell

    def inner_write():
        count += 1     # ERROR — compiler sees assignment → count is LOCAL
                       # STORE_FAST generated; LOAD_FAST before it → UnboundLocalError

    def inner_nonlocal():
        nonlocal count
        count += 1     # OK — LOAD_DEREF + STORE_DEREF; writes through cell
```

`nonlocal` tells the compiler: "count in this function refers to the cell in the enclosing scope — use `LOAD_DEREF`/`STORE_DEREF`, not `LOAD_FAST`/`STORE_FAST`."

### Q4: Demonstrate a real-world closure use case and explain the memory implications.

**Model answer:**
Closures are commonly used for memoization, partial application, and encapsulating state without a class:

```python
import functools

def memoize(fn):
    cache: dict = {}   # captured by closure — persists between calls

    @functools.wraps(fn)
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]

    wrapper.cache = cache
    wrapper.cache_clear = cache.clear
    return wrapper

@memoize
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

print(fib(50))           # fast, O(n) total calls
print(len(fib.cache))    # 51 entries
```

**Memory implication:** The closure keeps `cache` (and the function `fn`) alive as long as `wrapper` is alive. For a module-level decorated function, the cache is alive for the process lifetime. Use `functools.lru_cache(maxsize=N)` for bounded caching to avoid unbounded memory growth.

### Q5: What are "free variables" and how does Python track which variables a closure captures?

**Model answer:**
Free variables are names used in a function but defined in an enclosing scope (not local, not global). The compiler identifies them and records them in `co_freevars` on the code object:

```python
def outer(x, y):
    def inner(z):
        return x + y + z   # x and y are free variables

    print(inner.__code__.co_freevars)  # ('x', 'y')
    print(inner.__code__.co_varnames)  # ('z',)
    return inner

f = outer(1, 2)
print(f.__closure__)  # two cell objects
print([c.cell_contents for c in f.__closure__])  # [1, 2]
```

When `outer` is compiled, the compiler sees that `x` and `y` are referenced in `inner`. It marks them as cell variables in `outer` (`co_cellvars`) and free variables in `inner` (`co_freevars`). At runtime, when `outer` executes, `x` and `y` are stored in cell objects. When `inner` is created via `MAKE_FUNCTION`, these cells are attached as `inner.__closure__`.

---

## Gotcha Follow-ups

**"Can a closure mutate a list from the enclosing scope without `nonlocal`?"**
Yes — mutating (calling methods on) the captured object doesn't require `nonlocal`. `nonlocal` is only needed to rebind the name. `lst.append(1)` reads `lst` (via `LOAD_DEREF`) and calls a method on it — no rebinding. `lst = lst + [1]` would need `nonlocal` because it rebinds `lst`.

```python
def outer():
    items = []
    def add(x):
        items.append(x)   # no nonlocal needed — mutating, not rebinding
    return add, lambda: items

add, get = outer()
add(1); add(2)
print(get())  # [1, 2]
```

**"Does Python have block scope inside `if`/`for` blocks?"**
No. Python has only function scope, module scope, class scope, and comprehension scope (Python 3). Variables assigned inside `if`/`for`/`while`/`try` blocks are visible throughout the enclosing function:

```python
def demo():
    for i in range(3):
        pass
    print(i)   # 2 — loop variable leaks into function scope

    if True:
        x = 1
    print(x)   # 1 — visible here; NameError only if condition never ran
```

---

## Under the Hood

Cell objects are implemented in `Objects/cellobject.c`. A cell wraps a single Python object pointer. When the compiler determines that a variable in an outer function is referenced by an inner function, it marks the outer function's local as a "cell variable" (`co_cellvars`) and uses `MAKE_CELL` to create the cell wrapper. The inner function gets the cell via `COPY_FREE_VARS`. Both the outer local slot and the inner closure share the same `PyCellObject`, ensuring they see the same value even when the outer function has returned.
