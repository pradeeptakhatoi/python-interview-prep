# CPython Bytecode and dis.dis()

## Concept

Python source is compiled to bytecode — a platform-independent instruction set executed by the CPython virtual machine (the "eval loop" in `Python/ceval.c`). Understanding bytecode is essential for: performance analysis, understanding optimization opportunities, debugging obscure behavior, and writing tools (profilers, coverage analyzers, debuggers).

### Reading dis.dis() Output

```python
import dis

def add_numbers(a, b):
    result = a + b
    return result

dis.dis(add_numbers)
```

Output (Python 3.12):
```
  2           RESUME          0

  3           LOAD_FAST       0 (a)
              LOAD_FAST       1 (b)
              BINARY_OP       0 (+)
              STORE_FAST      2 (result)

  4           LOAD_FAST       2 (result)
              RETURN_VALUE
```

**Column meanings:**
1. Source line number
2. Instruction offset (bytes)
3. Opcode name
4. Argument (integer)
5. Argument human-readable (in parentheses)

### Key Opcodes

| Opcode | What It Does |
|--------|-------------|
| `LOAD_FAST n` | Push local variable `n` onto stack |
| `STORE_FAST n` | Pop stack top → local `n` |
| `LOAD_GLOBAL n` | Push global/builtin (3.12: includes NULL check) |
| `LOAD_CONST n` | Push constant from `co_consts[n]` |
| `BINARY_OP n` | Pop two operands, perform operation `n`, push result |
| `CALL n` | Call callable with `n` args from stack |
| `RETURN_VALUE` | Return top of stack to caller |
| `JUMP_BACKWARD n` | Jump back (loops) — also triggers `eval_breaker` check |
| `GET_ITER` | Call `iter()` on top of stack |
| `FOR_ITER n` | Call `next()` on iterator; jump by `n` on `StopIteration` |
| `BUILD_LIST n` | Build list from top `n` stack items |
| `RESUME n` | Entry point marker for coroutines and functions (3.11+) |
| `CACHE` | Inline cache slot for specializing adaptive interpreter (3.11+) |

### Inspecting Code Objects

```python
def example(x, y=10):
    z = x + y
    return z

code = example.__code__
print(code.co_varnames)    # ('x', 'y', 'z') — local variable names
print(code.co_consts)      # (None, 10) — constants
print(code.co_names)       # () — global/attr names used
print(code.co_filename)    # '<stdin>'
print(code.co_firstlineno) # 1
print(code.co_argcount)    # 1 (positional args; defaults separate)
print(code.co_stacksize)   # max stack depth needed (for safety validation)
print(code.co_flags)       # bitmask: CO_OPTIMIZED, CO_NEWLOCALS, CO_VARARGS, etc.

# Raw bytecode as bytes:
print(code.co_code)        # b'\x97\x00|\x00|\x01\x17\x00}\x02|\x02S\x00'
```

### CACHE Opcodes (3.11+ Specializing Interpreter)

In Python 3.11+, several opcodes are followed by `CACHE` entries that the specializing adaptive interpreter uses to store inline caches:

```python
def typed_add(x: int, y: int):
    return x + y

dis.dis(typed_add)
# BINARY_OP followed by CACHE entries that the adaptive interpreter
# will replace with BINARY_OP_ADD_INT after seeing int+int twice
```

These `CACHE` entries are not real instructions — they're memory slots for the specializer. Don't be alarmed when they appear in disassembly.

### Disassembling Different Object Types

```python
import dis

# Functions:
dis.dis(some_function)

# Classes (dis all methods):
dis.dis(SomeClass)

# Generators:
def gen():
    yield from range(10)
dis.dis(gen)

# Lambda:
f = lambda x: x * 2
dis.dis(f)

# String of code:
dis.dis("x = 1 + 2")

# Bytecode object directly:
code = compile("x = 1 + 2", "<string>", "exec")
dis.dis(code)
```

### Real Example: Why `x += 1` is Not Atomic

```python
import dis

def increment():
    global counter
    counter += 1

dis.dis(increment)
```
```
LOAD_GLOBAL    counter     # read counter
LOAD_CONST     1           # push 1
BINARY_OP      +=          # add
STORE_GLOBAL   counter     # write back
```

Four opcodes. The GIL can switch after each one. Two threads can both execute `LOAD_GLOBAL counter` and read the same value. This is why `counter += 1` is not thread-safe.

---

## Interview Questions

### Q1: How do you use `dis` to diagnose a performance issue in a Python function?

**Model answer:**  
Look for expensive opcodes that appear in loops, or operations that trigger type-checking overhead:

```python
import dis

def slow_concat(words):
    result = ""
    for word in words:
        result = result + word  # string concatenation in loop
    return result

dis.dis(slow_concat)
# BINARY_OP + appears in the loop body — O(n²) string concatenation
# Each iteration creates a new string, copying all previous characters
```

What to look for:
1. **`LOAD_GLOBAL` in a tight loop** — global lookups are slower than local. Assign to a local variable outside the loop: `join_fn = "".join`.
2. **`LOAD_ATTR` on hot path** — each attribute access goes through the descriptor protocol. Cache frequently-used attributes: `append = mylist.append`.
3. **`CALL` with many arguments** — function calls have overhead. Consider inlining for hot paths.
4. **Type-check opcodes** — `ISINSTANCE`, `CONTAINS_OP` may trigger slow paths on non-optimized types.

### Q2: What is `co_flags` and what do the flag bits mean?

**Model answer:**  
`co_flags` is a bitmask on the code object that describes properties of the function:

```python
import inspect

def example(*args, **kwargs):
    x = 1
    return x

code = example.__code__
flags = code.co_flags

print(bool(flags & inspect.CO_OPTIMIZED))   # True — uses LOAD_FAST/STORE_FAST
print(bool(flags & inspect.CO_NEWLOCALS))   # True — has its own local namespace
print(bool(flags & inspect.CO_VARARGS))     # True — has *args
print(bool(flags & inspect.CO_VARKEYWORDS)) # True — has **kwargs

# Coroutine flags:
async def coro(): pass
print(bool(coro.__code__.co_flags & inspect.CO_COROUTINE))  # True

def gen():
    yield
print(bool(gen.__code__.co_flags & inspect.CO_GENERATOR))  # True
```

`CO_OPTIMIZED` means locals are accessed via `LOAD_FAST`/`STORE_FAST` (index-based, O(1)) rather than `LOAD_NAME`/`STORE_NAME` (dict lookup). All functions with no `exec()` or unqualified `import *` get this flag. This is why inner functions are faster for locals than global scope.

### Q3: What's the difference between `LOAD_FAST` and `LOAD_GLOBAL`, and why does it matter for performance?

**Model answer:**  

- **`LOAD_FAST n`** — accesses `frame->localsplus[n]` directly by integer index. O(1), single pointer dereference, no dict lookup.
- **`LOAD_GLOBAL name`** — looks up `name` in the function's `__globals__` dict, then the builtins dict if not found. Two dict lookups in the worst case; optimized to one via the inline cache in Python 3.11+.

Practically, `LOAD_FAST` is 2-3x faster than `LOAD_GLOBAL`. In tight inner loops:

```python
import time

data = list(range(1_000_000))

# Slow — LOAD_GLOBAL for 'len' every iteration:
def count_slow(lst):
    count = 0
    for item in lst:
        if len(item) > 0:  # LOAD_GLOBAL 'len' each time
            count += 1
    return count

# Fast — cache global as local:
def count_fast(lst):
    count = 0
    _len = len   # local reference — LOAD_FAST
    for item in lst:
        if _len(item) > 0:
            count += 1
    return count
```

This optimization was more important before Python 3.11's specializing interpreter, which caches global lookups. Still relevant in 3.10 and older.

### Q4: How do you disassemble a compiled .pyc file?

**Model answer:**  
```python
import dis
import marshal
import struct

def disassemble_pyc(path):
    with open(path, 'rb') as f:
        # .pyc header: magic number (4 bytes) + bit flags (4) + timestamps/hash (8+)
        # Python 3.8+: 16-byte header
        f.read(16)
        code = marshal.load(f)

    dis.dis(code)

# Or more simply:
import py_compile
import importlib.util

# Compile a .py to .pyc:
py_compile.compile('myfile.py', 'myfile.pyc')

# Then load and disassemble:
spec = importlib.util.spec_from_file_location("module", "myfile.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Directly from source via compile():
with open('myfile.py') as f:
    source = f.read()
code = compile(source, 'myfile.py', 'exec')
dis.dis(code)
```

Practical use: examining what a decorator or class body compiles to without running it.

### Q5: What does `RESUME 0` at the top of every function mean in Python 3.11+?

**Model answer:**  
`RESUME` was added in Python 3.11 to serve as a unified entry point marker for:
1. Regular function calls (argument `0`).
2. Generator `.send()` or `.__next__()` resumes.
3. Coroutine resumes after `await`.

Before 3.11, the eval loop had implicit entry point logic scattered throughout. `RESUME` makes entry points explicit and allows:
- Tracing tools (`sys.settrace`) to correctly identify call vs. resume events.
- The specializing adaptive interpreter to reset specialization state on entry.
- Better frame introspection tooling.

The argument to `RESUME` indicates the type of resume:
- `0` — regular function call
- `1` — generator `.__next__()`
- `2` — generator `.send(value)` (or coroutine resume via `await`)
- `3` — generator `.throw(exception)` resume

---

## Gotcha Follow-ups

**"Can you modify bytecode at runtime to change a function's behavior?"**  
In older Python versions, you could create a new code object with modified `co_code` and assign it to `func.__code__`. In Python 3.8+, code objects gained `co_code` as a property. In Python 3.11+, `co_code` was split into `co_code` (deprecated) and `co_linetable`, `co_exceptiontable`, etc. Direct bytecode patching is fragile and version-specific. The recommended modern approach is using `dis.Bytecode` + `types.CodeType(...)` to reconstruct. Libraries like `bytecode` (third-party) provide a safer API. This is how some coverage tools work.

**"Why does `dis.dis()` show different output on Python 3.10 vs 3.12 for the same code?"**  
Major changes between versions:
- **3.10→3.11**: `JUMP_ABSOLUTE` removed, replaced with `JUMP_FORWARD`/`JUMP_BACKWARD`. `CALL_FUNCTION`/`CALL_FUNCTION_KW` replaced with unified `CALL`+`KW_NAMES`. `CACHE` entries appeared. `RESUME` added.
- **3.11→3.12**: Exception handling bytecode restructured (`PUSH_EXC_INFO`, `COPY_EXCEPTION`). Cleanup of legacy opcodes.
- Specializing opcodes (`BINARY_OP_ADD_INT`, `LOAD_ATTR_INSTANCE_VALUE`) may or may not appear depending on whether the function has run and been specialized.

Always note the Python version when sharing bytecode analysis.

---

## Under the Hood

The bytecode format is defined in `Include/cpython/code.h`. The evaluator loop is `_PyEval_EvalFrameDefault()` in `Python/ceval.c` — a massive `switch(opcode)` statement with computed gotos for performance. In Python 3.11+, this switch became a `DISPATCH_TABLE`-based jump table for lower branch prediction misses.

Code objects are immutable once created. `compile()` → `co_code` is sealed; you can't modify it in-place. To "patch" bytecode, you must create a new `types.CodeType` via its constructor (30+ arguments as of 3.12).
