# Specializing Adaptive Interpreter (PEP 659, Python 3.11+)

## Concept

Python 3.11 introduced the specializing adaptive interpreter (SAI) — a form of inline caching that makes the CPython eval loop self-optimizing. Frequently-executed bytecode instructions "specialize" based on the actual types observed, replacing generic opcodes with faster type-specific variants. This is the primary reason Python 3.11 achieved a ~25% average speedup over 3.10.

### The Core Idea

```python
# When CPython sees:
x = obj.attr

# It emits the generic opcode:
# LOAD_ATTR  (slow: calls tp_getattro, checks descriptor protocol, etc.)

# After ~8 executions with the same type:
# LOAD_ATTR_INSTANCE_VALUE  (fast: direct offset read from instance dict)
# or LOAD_ATTR_MODULE  (fast: dict lookup in module namespace)
# or LOAD_ATTR_SLOT  (fast: read from __slots__ array)
```

### Observing Specialization with `dis`

```python
import dis

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

def distance(p: Point) -> float:
    return (p.x ** 2 + p.y ** 2) ** 0.5

# Before specialization (first few calls):
dis.dis(distance)
# LOAD_FAST   0 (p)
# LOAD_ATTR   0 (x)         ← generic
# ...

# After ~8 calls with Point instances:
p = Point(3, 4)
for _ in range(10):
    distance(p)

# The bytecode is now SPECIALIZED in-place:
# LOAD_ATTR_INSTANCE_VALUE  0  ← reads directly from instance dict offset

# Python 3.12 uses 'adaptive' format — dis shows both original and specialized:
# LOAD_ATTR + adaptive cache entries
```

### Specialized Opcodes (Python 3.11-3.12)

```python
# Key specializations:
# LOAD_ATTR → LOAD_ATTR_INSTANCE_VALUE (instance attribute at known offset)
#           → LOAD_ATTR_MODULE (module global via dict)
#           → LOAD_ATTR_SLOT (__slots__ at known index)
#           → LOAD_ATTR_WITH_HINT (instance dict with cached key hash)

# STORE_ATTR → STORE_ATTR_INSTANCE_VALUE
#            → STORE_ATTR_SLOT

# BINARY_OP → BINARY_OP_ADD_INT (int + int, no type check)
#           → BINARY_OP_ADD_FLOAT (float + float)
#           → BINARY_OP_MULTIPLY_INT

# CALL → CALL_PY_EXACT_ARGS (Python function with exact arg count)
#      → CALL_PY_WITH_DEFAULTS
#      → CALL_BUILTIN_CLASS (type()/int()/etc.)
#      → CALL_BUILTIN_FAST (C function with no kwargs)
#      → CALL_METHOD_DESCRIPTOR_FAST

# COMPARE_OP → COMPARE_OP_INT (int comparison: pointer-level for small ints)
#            → COMPARE_OP_FLOAT
#            → COMPARE_OP_STR

# LOAD_GLOBAL → LOAD_GLOBAL_MODULE (with cached dict version)
#             → LOAD_GLOBAL_BUILTIN (with cached dict version)

import opcode
# See all specialized opcodes:
specialized = [name for name in dir(opcode) if 'ADAPTIVE' in name or
               any(x in name for x in ['_INT', '_FLOAT', '_STR', '_MODULE', '_SLOT', '_INSTANCE'])]
```

### How Specialization Works Internally

```python
# The mechanism (simplified):
# 1. Generic opcode starts with a counter (quickening counter)
# 2. Counter decrements on each execution
# 3. At 0: the specializer runs, observing actual types
# 4. If type is stable and optimizable: replace opcode with specialized version
#    in the SAME bytecode array (in-place mutation of the code object's co_code_adaptive)
# 5. Specialized opcode includes a type "guard" (fast check that types match)
# 6. On mismatch: "deoptimize" back to generic or try a different specialization

# This is why:
# - Python 3.11 is faster for monomorphic code (one type)
# - Less speedup for polymorphic code (many different types per opcode)
# - Warmup is needed: first 8+ iterations are not specialized

def benchmark_warmup_effect():
    import timeit

    class MyClass:
        x: int = 0

    obj = MyClass()

    # "Cold" call — no specialization yet:
    def access_cold():
        return obj.x

    # "Warm" call — after specialization:
    def warmup():
        for _ in range(20):
            access_cold()
    warmup()

    t_cold = timeit.timeit(access_cold, number=10)  # new function, cold
    t_warm = timeit.timeit(access_cold, number=10)  # second run, warm
    print(f"Cold: {t_cold:.6f}s, Warm: {t_warm:.6f}s")
    # Warm is typically 20-40% faster for attribute-heavy code
```

### Implications for Benchmarking

```python
import timeit

def benchmark_correctly():
    """Correct way to benchmark in Python 3.11+."""

    def my_function(x):
        return x * x + 2 * x + 1

    # WRONG: first run includes specialization overhead:
    t = timeit.timeit(lambda: my_function(5), number=100)
    # Reported time is misleadingly slow (specialization overhead in early iterations)

    # CORRECT: warmup first, then measure:
    # Warmup (drives specialization):
    for _ in range(20):
        my_function(5)

    # Now measure (specialized):
    t = timeit.timeit(lambda: my_function(5), number=1_000_000)
    print(f"Specialized time: {t:.3f}s")

    # CORRECT: use setup= to warmup before timing:
    setup = """
def f(x):
    return x * x
for _ in range(20): f(5)  # warmup
"""
    t = timeit.timeit("f(5)", setup=setup, number=1_000_000)
    print(f"Warmed up: {t:.3f}s")
```

### When Specialization Fails (Deoptimization)

```python
# Specialization assumes type stability.
# Type changes cause deoptimization:

def polymorphic_add(a, b):
    return a + b   # BINARY_OP_ADD_INT would specialize for int + int

# But call with mixed types:
polymorphic_add(1, 2)      # int + int → specializes for int
polymorphic_add(1.0, 2.0)  # float + float → deoptimizes, tries float specialization
polymorphic_add("a", "b")  # str + str → deoptimizes again

# Final state: "megamorphic" — stays generic, no specialization
# The opcode records a "miss counter" — too many misses → give up on specializing

# Design implication: type-stable code benefits most from Python 3.11+
# Use type annotations and Protocol to make type stability explicit and enforced
```

---

## Interview Questions

### Q1: What is the specializing adaptive interpreter and how does it differ from a JIT?

**Model answer:**
The specializing adaptive interpreter is a form of "inline caching" within the eval loop — not a JIT compiler. The key differences:

| | SAI (Python 3.11+) | JIT (PyPy, HotSpot) |
|-|-------------------|---------------------|
| Output | Specialized bytecode (still interpreted) | Native machine code |
| Scope | Single opcode at a time | Entire hot loops/traces |
| Compilation step | No — opcodes replaced in-place | Yes — compile to native |
| Warmup | ~8 iterations | Hundreds to thousands |
| Memory | Minimal (per-opcode cache) | Significant (JIT code cache) |
| Speedup | 1.2-2x typical | 5-100x for CPU-heavy code |

The SAI avoids the overhead of re-checking types on every execution by caching the result of the type check inside the opcode itself. If the cached type matches, the fast path executes. If not, it deoptimizes.

A JIT (like PyPy's trace-based JIT) compiles entire control-flow paths to machine code, eliminating the interpreter overhead entirely. CPython 3.13 is adding an experimental JIT (copy-and-patch) that will layer on top of the SAI.

### Q2: Which Python operations benefit most from the SAI and which don't?

**Model answer:**
**High benefit:**
- Attribute access on instances of the same type (`obj.attr` where `obj` is always `Point`)
- Integer arithmetic in tight loops (`a + b` where both are always `int`)
- Method calls on known types (`list.append`, `dict.get`)
- Global/builtin lookups (cached module dict version tag)

**Low benefit:**
- Polymorphic code (different types at the same opcode)
- Code running only a few times (never reaches specialization threshold)
- I/O-bound code (SAI optimizes CPU, not I/O)
- Operations already O(n) or worse (algorithmic complexity dominates)

```python
# High benefit: type-stable, computation-heavy
def stable_sum(n: int) -> int:
    total = 0
    for i in range(n):
        total += i   # always int + int → BINARY_OP_ADD_INT
    return total

# Low benefit: polymorphic
def polymorphic_sum(items):
    total = 0
    for item in items:
        total += item   # item could be int, float, Decimal — no stable specialization
    return total
```

### Q3: How should you structure benchmarks to correctly account for the SAI?

**Model answer:**
Always warm up before measuring. The specialization threshold is ~8 executions per opcode, but complex functions may need more:

```python
import timeit, time

def function_under_test(x):
    return x.attr_a + x.attr_b * x.attr_c

class MyObj:
    attr_a = 1
    attr_b = 2
    attr_c = 3

obj = MyObj()

# BAD: no warmup
t_bad = timeit.timeit(lambda: function_under_test(obj), number=100_000)

# GOOD: explicit warmup
WARMUP = 50  # safely above specialization threshold
for _ in range(WARMUP):
    function_under_test(obj)

t_good = timeit.timeit(lambda: function_under_test(obj), number=100_000)

print(f"No warmup: {t_bad:.4f}s")
print(f"Warmed up: {t_good:.4f}s")
# t_bad may be 5-20% higher due to specialization overhead in first iterations

# pytest-benchmark handles this automatically via its calibration phase
```

### Q4: How does the SAI interact with dynamic Python features like `setattr` and `__dict__` modification?

**Model answer:**
The SAI uses type version tags to validate cached specializations. When a class changes (attribute added/removed, `setattr` on the class), the version tag increments — invalidating ALL specializations that cached that type.

```python
class Config:
    debug = False
    timeout = 30

def read_config(cfg: Config) -> tuple:
    return cfg.debug, cfg.timeout   # specializes to LOAD_ATTR_INSTANCE_VALUE

cfg = Config()

# After warmup, reads are specialized:
for _ in range(50):
    read_config(cfg)

# Now modify the class (adds a new attribute):
Config.log_level = "INFO"   # invalidates ALL specializations for Config!

# Next call to read_config triggers re-specialization (8+ calls again)
read_config(cfg)

# Practical implication: don't add attributes to classes at runtime in production.
# Define all attributes in __init__ (or __slots__) to avoid invalidating specializations.

# Similarly: setting instance attributes after construction:
obj = Config()
for _ in range(50):
    obj.debug  # specialized

obj.new_attr = True   # may invalidate instance-specific specializations
```

### Q5: What is the "quickening" mechanism and how does CPython track specialization state per code object?

**Model answer:**
"Quickening" is the process of replacing generic opcodes with specialized variants. In Python 3.11+:

1. Each instruction has an 8-bit counter stored in `_Py_OPCODE_STATS`.
2. On each execution of a specializable instruction, the counter decrements.
3. At 0: `_Py_Specialize_LoadAttr()` (or the appropriate specializer) is called.
4. If specialization succeeds: the opcode in `co_code_adaptive` is replaced with the specialized opcode (e.g., `LOAD_ATTR_INSTANCE_VALUE`), along with cache entries (inline cache) immediately following.
5. If the type guard fails at runtime: `SPECIALIZATION_FAIL` → either try another specialization or mark as "superinstructions" or "polymorphic".

```python
import dis, sys

class T:
    x = 1

obj = T()

def f():
    return obj.x

# Warmup:
for _ in range(30):
    f()

# Inspect specialization:
dis.dis(f)
# In Python 3.12: shows 'cache' entries after LOAD_ATTR showing the specialized type

# The adaptive copy is separate from the "canonical" bytecode:
# f.__code__.co_code  ← original (unspecialized)
# f.__code__._co_code_adaptive  ← specialized version (internal, not public API)
```

---

## Gotcha Follow-ups

**"Does specialization persist across runs (in .pyc files)?"**
No — specialization is done at runtime in memory. The `.pyc` file stores the original unspecialized bytecode. Specialization happens from scratch on every interpreter startup. This is by design: the specialization is based on the actual types seen at runtime, which may differ between runs (different inputs, different import order).

**"Does the SAI work with subclasses?"**
Partially — specialization includes a type guard. If `LOAD_ATTR_INSTANCE_VALUE` is specialized for `Point`, it includes a check that `type(obj) is Point`. A `ColoredPoint(Point)` would fail this check (it's a subclass, not the exact same type), causing deoptimization and re-specialization. Python 3.12 improved some specializations to work with subclasses via `LOAD_ATTR_WITH_HINT` variants.

---

## Under the Hood

The specializing adaptive interpreter lives in `Python/specialize.c` (specializer functions) and `Python/ceval.c` (specialized opcode handlers). Each specializable instruction reserves "inline cache" slots immediately following it in the bytecode array — these slots store cached type pointers, dict version tags, and offsets. `_PyAdaptiveEntry` stores a `counter` and `index`. The type version tag (`tp_version_tag` in `PyTypeObject`) is a global monotonically-increasing counter; each modification to a type (attribute add/remove) gets a new tag. A specialization caches the tag; before using the cache, it verifies `type->tp_version_tag == cached_tag`. `Python/typeobject.c: type_modified_unlocked()` increments the tag on any type modification.
