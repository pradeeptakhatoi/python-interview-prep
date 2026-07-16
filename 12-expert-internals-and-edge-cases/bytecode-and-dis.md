# CPython Bytecode and dis.dis()

## Concept

CPython compiles Python source to bytecode — a sequence of instructions executed by the CPython virtual machine (ceval.c). Understanding bytecode is essential for explaining performance characteristics, debugging subtle bugs, and understanding optimizations like the specializing adaptive interpreter.

### Reading `dis` Output

```python
import dis

def add_and_return(a, b):
    result = a + b
    return result

dis.dis(add_and_return)
```

Output (Python 3.12):
```
  2           RESUME           0

  3           LOAD_FAST        0 (a)
              LOAD_FAST        1 (b)
              BINARY_OP        0 (+)
              STORE_FAST       2 (result)

  4           LOAD_FAST        2 (result)
              RETURN_VALUE
```

Column meanings:
- Line number (source)
- Bytecode offset (in bytes in the `.pyc` file)
- Opcode name
- Opcode argument (integer index)
- Human-readable argument (in parentheses)

### Code Objects

```python
code = add_and_return.__code__

print(code.co_varnames)    # ('a', 'b', 'result') — local variable names
print(code.co_consts)      # (None,) — constants used
print(code.co_name)        # 'add_and_return'
print(code.co_argcount)    # 2
print(code.co_filename)    # '<stdin>' or actual path
print(code.co_firstlineno) # 1
print(code.co_stacksize)   # 2 (max stack depth needed)
print(code.co_code)        # raw bytes of bytecode (Python 3.11: co_code is deprecated, use co_code)
print(code.co_flags)       # bitmask: CO_NESTED, CO_GENERATOR, CO_COROUTINE, etc.

# co_code is a bytes object; in Python 3.12 use code.co_code or dis.get_instructions():
for instr in dis.get_instructions(add_and_return):
    print(f"{instr.offset:3d} {instr.opname:<25} {instr.argval!r}")
```

### Inspecting More Complex Bytecode

```python
import dis

def comprehension_demo(n):
    return [x * x for x in range(n) if x % 2 == 0]

dis.dis(comprehension_demo)
# Note: the comprehension compiles to a NESTED code object
# dis.dis() recursively disassembles nested code objects

# Disassemble the comprehension's code object separately:
code = comprehension_demo.__code__
for const in code.co_consts:
    if hasattr(const, 'co_code'):
        print("Nested code object:")
        dis.dis(const)
```

### Peephole Optimizer — Constant Folding

```python
import dis

# CPython folds constants at compile time:
def folded():
    return 2 + 2   # never sees BINARY_OP at runtime

dis.dis(folded)
# LOAD_CONST   4   ← 2+2 computed at compile time, not runtime!
# RETURN_VALUE

def also_folded():
    return "hello" + " " + "world"
# LOAD_CONST   'hello world'  ← joined at compile time

def not_folded(x):
    return x + 2   # x is a variable — can't fold
# LOAD_FAST   0 (x)
# LOAD_CONST  2
# BINARY_OP   0 (+)  ← must compute at runtime
```

### Bytecode for Exception Handling

```python
import dis

def with_try(x):
    try:
        return 1 / x
    except ZeroDivisionError:
        return 0

dis.dis(with_try)
# Python 3.11+: uses PUSH_EXC_INFO, POP_EXCEPT for exception table
# Python 3.12: uses a separate exception table (co_exceptiontable)

# Exception table is now separate from bytecode for better performance:
code = with_try.__code__
print(dis.findlinestarts(code))   # map offset → line number

# Python 3.12: exception table entries:
for entry in code.co_exceptiontable:
    pass   # PEP 664 — exception table for 3.11+
```

### Generator and Coroutine Bytecode

```python
import dis

def gen():
    yield 1
    yield 2

dis.dis(gen)
# RESUME           0
# LOAD_CONST       1 (1)
# YIELD_VALUE           ← pauses execution, returns value to caller
# RESUME           1   ← resumes here on next()
# LOAD_CONST       2 (2)
# YIELD_VALUE
# LOAD_CONST       None
# RETURN_VALUE

async def coro():
    await some_awaitable()

dis.dis(coro)
# RESUME           0
# LOAD_GLOBAL      ... (some_awaitable)
# CALL             0
# GET_AWAITABLE    0
# LOAD_CONST       None
# SEND             ...   ← drives the awaitable
# YIELD_VALUE           ← suspends coroutine
# RESUME           3
# POP_TOP
# RETURN_VALUE
```

---

## Interview Questions

### Q1: What is CPython bytecode and how does it relate to the source code?

**Model answer:**
CPython bytecode is a platform-independent intermediate representation produced by the Python compiler (`Python/compile.c`) from the AST. It's a sequence of 2-byte (Python 3.6+) or 1-word (Python 3.12+, "wordcode") instructions — an opcode byte/word followed by an argument — executed by the CPython evaluation loop (`Python/ceval.c: _PyEval_EvalFrameDefault()`).

The pipeline: `.py` source → tokenizer → parser → AST → `compile()` → `code` object (bytecode + metadata) → `.pyc` cached file → executed by the VM.

```python
import ast, dis, compile

source = "x = 1 + 2"

# Step 1: AST
tree = ast.parse(source)
print(ast.dump(tree, indent=2))

# Step 2: compile
code = compile(source, "<string>", "exec")

# Step 3: bytecode
dis.dis(code)
# LOAD_CONST   3 (1+2 folded)
# STORE_NAME   0 (x)
# LOAD_CONST   None
# RETURN_VALUE
```

Bytecode is NOT machine code — it's still interpreted. CPython walks the instruction list in a `for` loop (or switch statement). PyPy, by contrast, JIT-compiles hot bytecode to native machine code.

### Q2: What information is in a `code` object and how do you access it?

**Model answer:**
A `code` object (`PyCodeObject`) contains everything the VM needs to execute a function:

| Attribute | Type | Contents |
|-----------|------|----------|
| `co_code` | bytes | Raw bytecode (deprecated 3.12, use `co_code`) |
| `co_consts` | tuple | Constants: None, literals, nested code objects |
| `co_varnames` | tuple | Local variable names (indexed by LOAD_FAST arg) |
| `co_names` | tuple | Global/attribute names (indexed by LOAD_GLOBAL/LOAD_ATTR) |
| `co_freevars` | tuple | Names closed over from enclosing scope |
| `co_cellvars` | tuple | Names closed over by nested functions |
| `co_argcount` | int | Number of positional parameters |
| `co_stacksize` | int | Maximum stack depth (pre-computed by compiler) |
| `co_flags` | int | Bitmask: CO_GENERATOR, CO_COROUTINE, CO_OPTIMIZED, etc. |
| `co_filename` | str | Source file path |
| `co_firstlineno` | int | First source line number |

```python
def outer():
    x = 1
    def inner():
        return x    # x is in co_freevars
    return inner

print(outer.__code__.co_cellvars)   # ('x',) — closed over by inner
print(outer().__code__.co_freevars) # ('x',) — captured from outer
```

### Q3: How does CPython's peephole optimizer work and what does it optimize?

**Model answer:**
The peephole optimizer (`Python/flowgraph.c` in Python 3.12, formerly `Python/peephole.c`) runs after compilation to eliminate obviously redundant instructions:

1. **Constant folding:** `1 + 2` → `LOAD_CONST 3`. Applies to arithmetic, string concatenation, tuple construction from constants.
2. **Constant tuple construction:** `(1, 2, 3)` → single `LOAD_CONST (1, 2, 3)` instead of 3 loads + `BUILD_TUPLE`.
3. **Dead code elimination:** code after `return` or `raise` at the top level of a block.
4. **Jump optimization:** chains of unconditional jumps collapsed to single jump.
5. **`None`/`True`/`False` constant folding:** `if True:` blocks have the condition removed.

```python
import dis

def folded_tuple():
    return (1, 2, 3)   # not 3 pushes + BUILD_TUPLE

dis.dis(folded_tuple)
# LOAD_CONST   (1, 2, 3)  ← single constant!
# RETURN_VALUE

def no_fold(x):
    return (x, 2, 3)   # x is a variable — can't fold

dis.dis(no_fold)
# LOAD_FAST    0 (x)
# LOAD_CONST   2
# LOAD_CONST   3
# BUILD_TUPLE  3
# RETURN_VALUE
```

Notably, the peephole optimizer does NOT optimize: list/dict/set literals with constants (these are always constructed at runtime), function calls, or attribute access.

### Q4: What's the difference between `dis.dis()`, `dis.code_info()`, and `dis.get_instructions()`?

**Model answer:**
- `dis.dis(obj)`: pretty-print disassembly, recursively descends into nested code objects (comprehensions, lambdas, nested functions). Best for human reading.
- `dis.code_info(obj)`: summary of the code object's attributes (name, filename, argcount, varnames, etc.) without the bytecode itself.
- `dis.get_instructions(obj)`: returns an iterator of `Instruction` named tuples — machine-readable. Use this for programmatic analysis.

```python
import dis

def square(x):
    return x * x

# dis.dis: human-readable
dis.dis(square)

# dis.code_info: metadata
print(dis.code_info(square))

# dis.get_instructions: programmatic
for instr in dis.get_instructions(square):
    print(f"offset={instr.offset} op={instr.opname} arg={instr.argrepr}")
    # offset=2 op=LOAD_FAST arg='x'
    # offset=4 op=LOAD_FAST arg='x'
    # offset=6 op=BINARY_OP arg='*'
    # offset=10 op=RETURN_VALUE arg=''

# Count opcodes:
from collections import Counter
op_counts = Counter(
    instr.opname for instr in dis.get_instructions(square)
)
print(op_counts)  # Counter({'LOAD_FAST': 2, 'BINARY_OP': 1, 'RETURN_VALUE': 1, ...})
```

### Q5: How can you modify bytecode at runtime and what are the risks?

**Model answer:**
Code objects are immutable in Python — you can't modify them in-place. But you can create a new code object with modified bytecode using `types.CodeType` or the `bytecode` library:

```python
import dis, types

def original(x):
    return x + 1

# Create a modified version that returns x + 2:
code = original.__code__

# Replace constant 1 with 2 (change co_consts):
new_consts = tuple(2 if c == 1 else c for c in code.co_consts)

# Python 3.8+: code.replace() (immutable, returns new code object)
new_code = code.replace(co_consts=new_consts)
new_fn = types.FunctionType(new_code, original.__globals__)

print(original(10))   # 11
print(new_fn(10))     # 12

# Risks:
# 1. CPython interns code objects — modifying shared code objects affects all instances
# 2. The specializing adaptive interpreter (3.11+) assumes bytecode is stable — modifying
#    bytecode after specialization causes crashes or incorrect behavior
# 3. No type checking or safety: wrong bytecode causes SystemError or segfault
# 4. Breaks between CPython versions — bytecode is not a stable API
```

For legitimate use cases (coverage.py, debuggers, monkey-patching): use `sys.settrace` or `sys.audit` hooks instead of bytecode manipulation. The `bytecode` library provides a safe, version-aware abstraction over raw bytecode modification.

---

## Gotcha Follow-ups

**"Is Python bytecode portable between CPython versions?"**
No — `.pyc` files embed a magic number (version-specific) in the first 4 bytes. CPython rejects `.pyc` files from a different version. Bytecode opcodes, their encoding, and even their argument semantics change between minor versions (e.g., Python 3.11 added `RESUME`, `PUSH_EXC_INFO`; 3.12 changed to 2-byte "wordcode"). Never distribute `.pyc` files as part of a package — always distribute source.

**"What is `co_flags` used for?"**
`co_flags` is a bitmask that tells the VM how to set up a frame:
- `CO_OPTIMIZED (0x01)`: locals stored as fast locals (array), not dict
- `CO_NEWLOCALS (0x02)`: function has its own locals namespace
- `CO_VARARGS (0x04)`: function has `*args`
- `CO_VARKEYWORDS (0x08)`: function has `**kwargs`
- `CO_NESTED (0x10)`: nested function
- `CO_GENERATOR (0x20)`: generator function (`yield` present)
- `CO_COROUTINE (0x100)`: async def function
- `CO_ASYNC_GENERATOR (0x200)`: async generator

---

## Under the Hood

CPython's execution loop (`Python/ceval.c: _PyEval_EvalFrameDefault()`) is a giant `switch` statement over opcodes (Python 3.11+: computed goto for ~20% speedup on supported compilers). Each frame (`PyFrameObject`) maintains a value stack (array of `PyObject*`), the bytecode pointer (`prev_instr`), and the local variables array (`localsplus`). In Python 3.11+, frames are allocated on the C stack (not heap) for common cases, eliminating allocation overhead. The `.pyc` file format: 4-byte magic, 4-byte flags, 4-byte source timestamp/hash, 4-byte source size, then a marshalled `code` object.
