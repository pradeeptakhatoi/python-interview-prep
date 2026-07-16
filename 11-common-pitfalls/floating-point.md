# Floating Point Precision: float vs Decimal vs Fraction

## Concept

Python's `float` is IEEE 754 double-precision (64-bit). It cannot represent most decimal fractions exactly — the representation is in binary, and most decimal numbers (like 0.1) are repeating fractions in binary, causing surprising rounding errors that accumulate across operations.

### The Core Problem

```python
# IEEE 754 binary64 cannot represent 0.1 exactly:
>>> 0.1 + 0.2
0.30000000000000004

>>> 0.1 + 0.2 == 0.3
False

>>> repr(0.1)
'0.1'           # Python 3 shows the shortest repr that round-trips

>>> format(0.1, '.55f')
'0.1000000000000000055511151231257827021181583404541015625'
# The ACTUAL stored value

# Accumulation in loops:
total = 0.0
for _ in range(100):
    total += 0.1
print(total)   # 9.99999999999998 — NOT 10.0
print(total == 10.0)  # False
```

### Safe Float Comparison

```python
import math

# NEVER use == for float comparison:
a, b = 0.1 + 0.2, 0.3

# Use math.isclose:
print(math.isclose(a, b))            # True (rel_tol=1e-9 default)
print(math.isclose(a, b, rel_tol=1e-9, abs_tol=0.0))

# math.isclose formula:
# abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)

# When a or b could be 0:
# rel_tol alone fails because max(a, b) == 0 → threshold == 0
print(math.isclose(1e-15, 0.0, rel_tol=1e-9))       # False!
print(math.isclose(1e-15, 0.0, abs_tol=1e-10))       # False (correctly)
print(math.isclose(1e-15, 0.0, abs_tol=1e-14))       # True
```

### `decimal.Decimal` — Exact Decimal Arithmetic

```python
from decimal import Decimal, getcontext, ROUND_HALF_UP

# Exact representation of decimal numbers:
print(Decimal('0.1') + Decimal('0.2'))    # 0.3 (exact!)
print(Decimal('0.1') + Decimal('0.2') == Decimal('0.3'))  # True

# WRONG: constructing from float
print(Decimal(0.1))   # Decimal('0.1000000000000000055511151231257827021181583404541015625')
# The float imprecision is already there before Decimal sees it!

# RIGHT: always construct from string:
d = Decimal('0.1')

# Precision control:
getcontext().prec = 50  # 50 significant digits globally

# Rounding modes:
price = Decimal('1.005')
print(price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))  # 1.01
print(round(price, 2))  # 1.00 — float rounding, wrong for financial use!

# Financial calculation example:
def calculate_total(items: list[tuple[str, str, str]]) -> Decimal:
    """items: [(name, price, qty)]"""
    total = Decimal('0')
    for name, price, qty in items:
        total += Decimal(price) * Decimal(qty)   # exact arithmetic
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

### `fractions.Fraction` — Exact Rational Arithmetic

```python
from fractions import Fraction

# Exact representation of any rational number:
print(Fraction(1, 3) + Fraction(1, 6))    # Fraction(1, 2) — exact!
print(Fraction(1, 3) + Fraction(1, 6) == Fraction(1, 2))  # True

# Can construct from float (but still captures float imprecision):
print(Fraction(0.1))    # Fraction(3602879701896397, 36028797018963968) — ugly!
print(Fraction('0.1'))  # Fraction(1, 10) — from string, exact

# Fraction from Decimal:
print(Fraction(Decimal('0.1')))  # Fraction(1, 10) — exact

# Fraction is slower than float/Decimal (arbitrary precision with GCD reduction)
# Use for: mathematical proofs, exact symbolic computation, unit tests
import timeit
print(timeit.timeit("Fraction(1,3) + Fraction(1,6)", globals={'Fraction': Fraction}))
# ~5x slower than float
```

### `math.fsum` — Accurate Floating-Point Summation

```python
import math

values = [0.1] * 10

print(sum(values))        # 0.9999999999999999 — accumulated error
print(math.fsum(values))  # 1.0 — exact (Shewchuk's algorithm)

# fsum uses compensated summation (extended precision accumulators)
# — O(n) but with much lower error than naive sum()

# When to use fsum:
# - Summing many small floats
# - Financial reporting (alongside Decimal for guaranteed correctness)
# - Scientific computation where error accumulation matters
```

### Decimal Performance

```python
import timeit
from decimal import Decimal

# float is significantly faster than Decimal:
def float_calc():
    return sum(0.1 for _ in range(1000))

def decimal_calc():
    return sum(Decimal('0.1') for _ in range(1000))

f_time = timeit.timeit(float_calc, number=100)
d_time = timeit.timeit(decimal_calc, number=100)
print(f"float: {f_time:.3f}s")    # ~0.003s
print(f"Decimal: {d_time:.3f}s")  # ~0.05s — ~15x slower
```

---

## Interview Questions

### Q1: Why does `0.1 + 0.2 != 0.3` in Python?

**Model answer:**
IEEE 754 double-precision binary64 format uses 64 bits: 1 sign bit, 11 exponent bits, 52 mantissa bits. It represents numbers as `±(1 + mantissa) × 2^exponent`.

The decimal fraction 0.1 = 1/10 in binary is 0.0001100110011... (repeating). With 52 mantissa bits, it's rounded to the nearest representable value — not exactly 0.1. Same for 0.2 and 0.3. The three rounded values happen to not satisfy the equality.

```python
# Actual stored values:
from decimal import Decimal
print(Decimal(0.1))  # 0.1000000000000000055511151231257827...
print(Decimal(0.2))  # 0.2000000000000000111022302462515654...
print(Decimal(0.3))  # 0.2999999999999999888977697537484345...

# 0.1 + 0.2 stored: 0.30000000000000004440892...
# 0.3 stored:       0.29999999999999998889...
# They differ at the 17th decimal digit
```

Integers and powers of 2 can be represented exactly. Any fraction whose denominator is not a power of 2 cannot.

### Q2: When should you use `Decimal` vs `float` vs `Fraction`?

**Model answer:**

| Use case | Type | Reason |
|----------|------|--------|
| Financial calculations (money) | `Decimal` | Exact decimal representation, controlled rounding |
| Scientific/engineering computation | `float` | Hardware-accelerated, sufficient precision for most uses |
| Exact mathematical proofs | `Fraction` | Exact rational arithmetic, no rounding |
| Statistics, ML, NumPy | `float` (numpy.float64) | Performance, vectorized operations |
| User input → display (currency) | `Decimal` | Round-trip without floating-point noise |
| Game physics, simulations | `float` | Speed over precision |

```python
# Money: use Decimal
from decimal import Decimal, ROUND_HALF_UP
price = Decimal('19.99')
tax_rate = Decimal('0.0875')
total = (price * (1 + tax_rate)).quantize(Decimal('0.01'), ROUND_HALF_UP)
print(total)  # 21.74 — exact

# Scientific: float is fine (errors cancel over many measurements)
import statistics
measurements = [1.234, 1.236, 1.235, 1.233]
print(statistics.mean(measurements))  # 1.2345 — close enough

# Exact ratio: Fraction
from fractions import Fraction
rate = Fraction(1, 3)   # exact 1/3, no rounding
```

### Q3: What's the difference between `round()` and `Decimal.quantize()` for financial rounding?

**Model answer:**
`round()` uses "banker's rounding" (round half to even, IEEE 754 roundTiesToEven):

```python
# Banker's rounding: round half to even
print(round(0.5))    # 0 (rounds to even)
print(round(1.5))    # 2 (rounds to even)
print(round(2.5))    # 2 (rounds to even)
print(round(3.5))    # 4 (rounds to even)

# Financial rounding usually requires ROUND_HALF_UP:
from decimal import Decimal, ROUND_HALF_UP

values = [Decimal('0.5'), Decimal('1.5'), Decimal('2.5'), Decimal('3.5')]
for v in values:
    print(v.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
# 1, 2, 3, 4 — always rounds up on .5
```

Also: `round()` on `float` first applies IEEE 754 rounding, THEN Python's rounding:
```python
print(round(2.675, 2))  # 2.67 — not 2.68!
# Because 2.675 is stored as 2.67499999... — below the .5 threshold
```

`Decimal.quantize()` operates on exact decimal values — no float imprecision.

### Q4: How do you handle floating-point accumulation errors in a long-running sum?

**Model answer:**

```python
import math
from decimal import Decimal

data = [0.1] * 10_000_000

# 1. math.fsum — compensated summation (Shewchuk's algorithm)
# Maintains a list of partial sums to preserve precision:
result = math.fsum(data)    # 1000000.0 exactly

# 2. Kahan summation — manually:
def kahan_sum(values):
    total = 0.0
    compensation = 0.0   # correction for lost low-order bits
    for x in values:
        y = x - compensation
        t = total + y
        compensation = (t - total) - y   # recover lost bits
        total = t
    return total

print(kahan_sum(data))   # 1000000.0 exactly

# 3. For financial: Decimal (slow but exact)
result_decimal = sum(Decimal('0.1') for _ in range(100))
print(result_decimal)    # 10.0 exactly

# In practice: for scientific code, use numpy which uses compensated algorithms
import numpy as np
print(np.sum(np.full(10_000_000, 0.1)))   # numpy uses pairwise summation
```

### Q5: What output does `round(2.5)` produce and why might this surprise developers?

**Model answer:**
`round(2.5)` returns `2`, not `3`. Python uses IEEE 754 "round half to even" (banker's rounding):

```python
print(round(0.5))   # 0
print(round(1.5))   # 2
print(round(2.5))   # 2
print(round(3.5))   # 4
print(round(4.5))   # 4
```

The rule: when exactly at .5, round to the nearest even number. 2 is even, so 2.5 → 2. 4 is even, so 4.5 → 4.

**Why:** banker's rounding minimizes cumulative rounding error over many operations. Half the time you round up, half down — errors cancel out on average. Standard ROUND_HALF_UP always rounds up, which introduces systematic upward bias.

**The surprise:** `round(2.675, 2)` returns `2.67` not `2.68` — because 2.675 is stored as 2.674999...

Fix: use `Decimal` with explicit `ROUND_HALF_UP` for financial calculations.

---

## Gotcha Follow-ups

**"Is `Decimal` always safe for financial calculations?"**
Safer than float, but there are still traps:
1. `Decimal(0.1)` captures float imprecision — always use `Decimal('0.1')`.
2. Division can still produce non-terminating decimals: `Decimal('1') / Decimal('3')` = `Decimal('0.3333333333333333333333333333')` (precision-limited). Use `quantize()` to round at defined points.
3. `getcontext().prec` is a global — if another part of the codebase reduces it, your calculations lose precision. Use `localcontext()` for isolation.

**"Can numpy arrays use Decimal?"**
No — numpy's dtype system is based on C types. `numpy.float64` is IEEE 754 `double`. For Decimal arithmetic in array contexts, use Python loops or `mpmath` (arbitrary-precision math library), accepting the performance cost.

---

## Under the Hood

IEEE 754 double-precision (`double` in C): 64 bits total: bit 63 (sign), bits 62-52 (11-bit exponent, biased by 1023), bits 51-0 (52-bit mantissa, implicit leading 1). Represents values in range ±(2^-1022) to ±(2^1024 - 1). `decimal.Decimal` (`Modules/_decimal/libmpdec/`) uses Michael Cowlishaw's `libmpdec` (General Decimal Arithmetic specification). `math.fsum` (`Modules/mathmodule.c`) uses Shewchuk's algorithm — maintains a running list of non-overlapping partial sums and merges them in order of decreasing magnitude. `fractions.Fraction` (`Lib/fractions.py`) uses `math.gcd()` on every operation for exact reduction — Python integers are arbitrary precision, so this is correct for any rational number.
