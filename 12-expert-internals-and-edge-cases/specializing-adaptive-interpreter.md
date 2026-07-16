# Specializing Adaptive Interpreter (PEP 659, Python 3.11+)

## Concept

Python 3.11 introduced the **Specializing Adaptive Interpreter** (PEP 659). Instead of interpreting every opcode generically, the interpreter watches how opcodes are used and replaces them with specialized, faster versions when patterns are stable. This gave CPython a ~25% overall speedup in 3.11 and further gains in 3.12.

### How It Works

Every "adaptive" opcode starts as a **generic** version (e.g., `BINARY_OP`). After the opcode is executed a fixed number of times (currently 8), the interpreter checks what types were actually used and replaces the opcode with a specialized version:

```
BINARY_OP (generic)
   ↓ after 8 calls with int+int
BINARY_OP_ADD_INT (specialized)
   ↓ if types change (deoptimize)
BINARY_OP (generic, but with counter reset)
```

The specialized opcode avoids the general type dispatch, calling `PyLong_Add` directly instead of going through `PyObject_Add` → type lookup → `nb_add` method resolution.

### Seeing Specialization in Action

```python
import dis

def add_ints(a: int, b: int) -> int:
    return a + b

# Before any calls — generic opcode:
dis.dis(add_ints)
# BINARY_OP 0 (+) + CACHE CACHE ...

# Run with integers many times:
for _ in range(100):
    add_ints(1, 2)

# After specialization (use dis.dis with show_caches=True):
dis.dis(add_ints, show_caches=True)
# BINARY_OP_ADD_INT + (inline cache showing observed types)
```

**Note:** The specialized opcodes are visible via `dis.dis(fn, show_caches=True, adaptive=True)`. Without `adaptive=True`, you see the original unspecialized bytecode.

### Specialized Opcodes (3.11/3.12 selection)

| Generic Opcode | Specialized Version | Condition |
|---------------|---------------------|-----------|
| `BINARY_OP +` | `BINARY_OP_ADD_INT` | Both operands are `int` |
| `BINARY_OP +` | `BINARY_OP_ADD_FLOAT` | Both operands are `float` |
| `BINARY_OP +` | `BINARY_OP_ADD_UNICODE` | Both operands are `str` |
| `LOAD_ATTR` | `LOAD_ATTR_INSTANCE_VALUE` | Attribute is in `__dict__` slot |
| `LOAD_ATTR` | `LOAD_ATTR_SLOT` | Attribute is a `__slots__` slot |
| `LOAD_ATTR` | `LOAD_ATTR_MODULE` | Object is a module |
| `CALL` | `CALL_PY_EXACT_ARGS` | Calling a Python function with correct arg count |
| `CALL` | `CALL_BUILTIN_O` | Calling a C builtin with one arg |
| `LOAD_GLOBAL` | `LOAD_GLOBAL_MODULE` | Name found in globals dict (not builtins) |
| `COMPARE_OP` | `COMPARE_OP_INT` | Comparing two ints |
| `FOR_ITER` | `FOR_ITER_LIST` | Iterating a list |
| `STORE_SUBSCR` | `STORE_SUBSCR_LIST_INT` | `list[int] = value` |

### Deoptimization

When types change, the specialized opcode is replaced back with the generic version. This is called **deoptimization**:

```python
def versatile(a, b):
    return a + b

# Call with ints — specializes to BINARY_OP_ADD_INT:
for _ in range(20):
    versatile(1, 2)

# Now call with strings — deoptimizes:
versatile("hello", " world")
# Back to generic BINARY_OP

# Calls with mixed types prevent stable specialization
```

**Architectural implication:** Functions called with multiple types never stabilize. For hot paths, type consistency is valuable — polymorphic hot functions are slower than monomorphic ones.

### CACHE Entries

Each adaptive opcode is followed by inline cache entries (shown as `CACHE` in `dis.dis(show_caches=True)`):

```python
dis.dis(add_ints, show_caches=True)
```
```
RESUME           0
LOAD_FAST        0 (a)
LOAD_FAST        1 (b)
BINARY_OP        0 (+)
    CACHE                  # 4 bytes: specialization counter
    CACHE                  # 4 bytes: left operand type version
    CACHE                  # 4 bytes: right operand type version  
    CACHE                  # 4 bytes: (unused / padding)
RETURN_VALUE
```

These `CACHE` slots are part of the bytecode array but are not instructions — they're treated as data by the specializer. They store:
1. A counter tracking how many times the generic version ran before specializing.
2. Type version tags for the observed operand types.
3. Pointer caches for attribute lookup (method address, class version).

### Impact on Code Patterns

```python
# GOOD: consistent types → stable specialization
def process_numbers(values: list[int]) -> int:
    total = 0
    for v in values:
        total += v    # BINARY_OP_ADD_INT after warmup
    return total

# BAD: mixed types → repeated deoptimization
def process_mixed(values):
    total = 0
    for v in values:
        total += v    # never specializes if v is sometimes int, sometimes float
    return total

# For process_mixed with floats: cast explicitly
def process_float(values: list[float]) -> float:
    total = 0.0
    for v in values:
        total += v    # BINARY_OP_ADD_FLOAT — stable
    return total
```

---

## Interview Questions

### Q1: What is the specializing adaptive interpreter and why was it faster than previous CPython optimization attempts?

**Model answer:**  
Previous attempts at speeding up CPython (e.g., `psyco`, `unladen swallow`) relied on JIT compilation — generating native machine code for hot functions. These required complex infrastructure, had high warmup costs, and were abandoned.

The specializing adaptive interpreter takes a middle path:
- No JIT compilation — stays in the bytecode interpreter.
- Instead, replaces generic bytecodes with specialized variants that skip type dispatch for known-stable types.
- Low overhead: specialization happens lazily after 8 executions, falls back gracefully on type change.
- No warmup penalty in the traditional sense — cold code runs at generic (old CPython) speed; hot code gets specialized.

The speedup (~25% in 3.11) comes from eliminating the two most expensive parts of bytecode execution: the type dispatch (looking up `nb_add` on the type object) and the Python function call overhead (`CALL_PY_EXACT_ARGS` can bypass the general `tp_call` dispatch).

### Q2: How does class attribute access specialization work? What is a "type version tag"?

**Model answer:**  
`LOAD_ATTR_INSTANCE_VALUE` is the specialized opcode for loading an instance attribute that lives in the instance's `__dict__` (not overridden by a descriptor). The inline cache stores:
1. The **type version tag** — a monotonically-increasing integer associated with a class. It increments whenever the class is modified (attribute added, method replaced).
2. The **dict offset** — the offset of the instance's `__dict__` pointer in the C struct.
3. The **slot index** — index into the instance dict's compact values array.

When `LOAD_ATTR_INSTANCE_VALUE` executes:
1. Check `obj.__class__.__version_tag == cached_version_tag` — fast integer comparison.
2. If match: directly read `obj.__dict__[cached_index]` — no string lookup.
3. If mismatch (class was modified, or different class): deoptimize to generic `LOAD_ATTR`.

```python
class Point:
    def __init__(self, x, y):
        self.x = x    # x lives in instance __dict__
        self.y = y

p = Point(1, 2)

def get_x(point):
    return point.x    # LOAD_ATTR → specializes to LOAD_ATTR_INSTANCE_VALUE

# Run 10+ times with Point instances:
for _ in range(20):
    get_x(Point(i, i))

# Now modifying Point invalidates the type version:
Point.z = 0   # increments Point.__version_tag__
# get_x will deoptimize next call, then re-specialize
```

### Q3: Does specialization work across different instances of the same class?

**Model answer:**  
Yes — specialization is per **type**, not per instance. The `LOAD_ATTR_INSTANCE_VALUE` cache stores the type's version tag, not a pointer to a specific instance. As long as all objects passed to the function are instances of the same class (and the class hasn't changed), the specialization is stable.

```python
class Config:
    def __init__(self, value):
        self.value = value

def read_value(cfg: Config):
    return cfg.value  # specializes for Config type

# Different instances — all still specialized:
configs = [Config(i) for i in range(1000)]
for c in configs:
    read_value(c)  # all benefit from LOAD_ATTR_INSTANCE_VALUE
```

But if you pass instances of different classes:
```python
class AltConfig:
    def __init__(self, value):
        self.value = value

read_value(Config(1))
read_value(AltConfig(2))  # different type → deoptimize → never stabilizes
```

Polymorphic call sites (multiple types) prevent stable specialization. This is a real performance consideration for generic utility functions.

### Q4: How do you measure whether specialization is actually happening in your code?

**Model answer:**  
Three approaches:

**1. `dis` with adaptive flag:**
```python
import dis

def fn(a, b):
    return a + b

for _ in range(20):
    fn(1, 2)

dis.dis(fn, adaptive=True)
# Shows actual specialized opcodes in the bytecode
```

**2. `sys.monitoring` (Python 3.12+) or `sys.settrace` to count opcode specializations:**
```python
# Rough approach: time before/after warmup
import time

def bench(fn, *args, n=1000):
    for _ in range(n):  # warmup
        fn(*args)
    start = time.perf_counter()
    for _ in range(n):
        fn(*args)
    return time.perf_counter() - start

def add(a, b): return a + b

cold = bench(add, 1, 2, n=10)    # before specialization
warm = bench(add, 1, 2, n=10000) # after specialization
print(f"Cold: {cold:.6f}s, Warm: {warm:.6f}s")
```

**3. `perf` or `py-spy` flame graphs** — specialized code appears as fewer cycles in the type dispatch path.

### Q5: What types of code patterns prevent or defeat specialization?

**Model answer:**  

**1. Polymorphic inputs (most common):**
```python
def process(x):
    return x + x  # ints sometimes, strings sometimes — never specializes
```

**2. Modifying classes frequently:**
```python
for i in range(1000):
    MyClass.attr = i  # increments version tag each time, defeats caching
```

**3. Very short-lived functions (rarely called):**
```python
def compute_once():
    return expensive()
# Called once — specialization threshold (8 calls) never reached
```

**4. Functions with many early exits:**
```python
def guarded(x):
    if not isinstance(x, int):  # type check on every call
        return None
    return x + 1
# isinstance() itself can be specialized, but the guard path prevents
# BINARY_OP from seeing consistent types
```

**5. Accessing attributes on multiple types in one function:**
```python
def dual_access(obj):
    return obj.name + obj.value
# If obj is sometimes TypeA, sometimes TypeB, LOAD_ATTR never stabilizes
```

**Architectural guidance:** For performance-critical inner loops, keep types consistent, avoid frequent class modification, and prefer separate specialized functions over one polymorphic function.

---

## Gotcha Follow-ups

**"Does specialization persist across garbage collection cycles?"**  
Specialization is stored in the bytecode array of the code object. Code objects live as long as they're referenced (function object holds a reference). GC does not reset specialization. However, specialization can be reset when: (a) the function is redefined (new code object created), (b) the module is reloaded, or (c) a related class is modified.

**"Can specialization cause incorrect results if types change mid-operation?"**  
No — the specializer always checks the type version tag before using cached data. If the check fails, it falls back to the generic opcode, which is always correct. The worst case is a performance regression (back to generic speed), never a correctness error. This property (correct under all type transitions) was the main design constraint that made the specializer safe to add without extensive formal verification.

---

## Under the Hood

The specialization machinery is in `Python/specialize.c`. Key function: `_Py_Specialize_BinaryOp()` — called after the generic `BINARY_OP` runs 8 times. It inspects the types of the operands via the inline cache and writes the specialized opcode directly into the bytecode array (in-place modification of the `co_code` bytes).

The counter is decremented each time the generic opcode runs. At zero, `_Py_Specialize_*` is called. If specialization succeeds, the opcode is replaced and counter reset. If it fails (types too complex), the opcode transitions to a "megamorphic" state that doesn't attempt specialization again.

Python 3.13+ introduces "Tier 2" optimization (stacks of specialized operations translated to a higher-level IR for further optimization). This is the foundation for an eventual tracing JIT in Python 3.14+.
