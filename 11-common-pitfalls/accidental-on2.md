# Accidental O(n²) Patterns

## Concept

O(n²) complexity is often introduced accidentally in Python through common idioms that appear innocuous but have hidden linear cost inside loops. The most frequent culprits: membership tests on lists, string concatenation in loops, and nested iterations over the same data.

### Pattern 1: Membership Test on a List

```python
import time

# O(n²) — list.__contains__ is O(n), called n times:
def find_duplicates_slow(items: list[int]) -> list[int]:
    seen = []
    duplicates = []
    for item in items:
        if item in seen:          # O(n) scan of seen
            duplicates.append(item)
        else:
            seen.append(item)
    return duplicates

# O(n) — set.__contains__ is O(1):
def find_duplicates_fast(items: list[int]) -> list[int]:
    seen = set()
    duplicates = []
    for item in items:
        if item in seen:          # O(1) hash lookup
            duplicates.append(item)
        else:
            seen.add(item)
    return duplicates

# Benchmark:
data = list(range(10_000))
import random
random.shuffle(data)

start = time.perf_counter()
find_duplicates_slow(data)
print(f"list: {time.perf_counter() - start:.3f}s")   # ~0.5s

start = time.perf_counter()
find_duplicates_fast(data)
print(f"set: {time.perf_counter() - start:.4f}s")    # ~0.001s
```

### Pattern 2: String Concatenation in a Loop

```python
# O(n²) — each += copies the entire string so far:
def build_slow(parts: list[str]) -> str:
    result = ""
    for part in parts:
        result += part    # creates a new string object each iteration
    return result

# O(n) — join allocates once:
def build_fast(parts: list[str]) -> str:
    return "".join(parts)

# Note: CPython 3.11+ has an optimization for += in simple cases
# (avoids the copy if the left operand has refcount==1), but don't rely on it
# for production code — str.join is always correct and clear.

# In practice:
lines = [f"line {i}\n" for i in range(100_000)]
result = "".join(lines)   # always prefer this
```

### Pattern 3: O(n²) List-of-Lists

```python
# O(n²): for each item, check each bucket:
def group_by_category_slow(items):
    groups = []
    categories = []
    for item in items:
        if item['category'] in categories:          # O(n) list scan
            idx = categories.index(item['category'])  # O(n) again!
            groups[idx].append(item)
        else:
            categories.append(item['category'])
            groups.append([item])
    return dict(zip(categories, groups))

# O(n): use defaultdict:
from collections import defaultdict

def group_by_category_fast(items):
    groups = defaultdict(list)
    for item in items:
        groups[item['category']].append(item)
    return dict(groups)
```

### Pattern 4: Nested Loop with Quadratic Work

```python
# O(n²): find all pairs whose sum == target
def find_pairs_slow(nums: list[int], target: int) -> list[tuple]:
    pairs = []
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):   # n*(n-1)/2 iterations
            if nums[i] + nums[j] == target:
                pairs.append((nums[i], nums[j]))
    return pairs

# O(n): hash-based complement lookup
def find_pairs_fast(nums: list[int], target: int) -> list[tuple]:
    seen = set()
    pairs = []
    for num in nums:
        complement = target - num
        if complement in seen:
            pairs.append((complement, num))
        seen.add(num)
    return pairs
```

### Pattern 5: `list.insert(0)` or `list.remove()` in a Loop

```python
from collections import deque
import time

n = 100_000

# O(n²): list.insert(0) shifts all elements right
start = time.perf_counter()
lst = []
for i in range(n):
    lst.insert(0, i)    # O(n) each time!
print(f"list.insert(0): {time.perf_counter() - start:.3f}s")  # ~3s

# O(n): deque.appendleft is O(1)
start = time.perf_counter()
dq = deque()
for i in range(n):
    dq.appendleft(i)    # O(1)
print(f"deque.appendleft: {time.perf_counter() - start:.4f}s")  # ~0.01s

# Also O(n²): list.remove() searches linearly then shifts
```

### Detecting Accidental O(n²) — Profiling

```python
# Use py-spy or cProfile to spot unexpected linear scans:
import cProfile

def process_large_dataset(data):
    result = []
    blacklist = [...]   # should be a set!
    for item in data:
        if item not in blacklist:   # O(n) — spotted by profiler
            result.append(item)
    return result

cProfile.run('process_large_dataset(large_data)', sort='cumtime')
# Look for: __contains__ or index showing high tottime relative to call count
```

---

## Interview Questions

### Q1: Why is checking membership in a list O(n) but in a set O(1)?

**Model answer:**
A `list` stores elements contiguously in memory with no indexing by value. Checking `x in list` requires scanning every element from the beginning until a match or end-of-list — O(n) in the worst case.

A `set` (implemented as an open-addressing hash table) computes `hash(x)`, uses that to find the likely bucket in O(1) time, then compares the element at that bucket. With a good hash function and reasonable load factor, this is effectively O(1) on average — O(n) worst case with pathological hash collisions, but practically never relevant.

```python
import timeit

data = list(range(10_000))
s = set(data)

# list: O(n) — looking for last element
print(timeit.timeit("9999 in data", globals={'data': data}, number=10000))

# set: O(1)
print(timeit.timeit("9999 in s", globals={'s': s}, number=10000))
# Ratio: ~100-300x faster for n=10,000
```

**Decision rule:** if you ever write `if x in my_list` inside a loop, the loop is O(n²). Convert `my_list` to a `set` before the loop.

### Q2: What's the complexity of `str +=` in a loop and what's the correct alternative?

**Model answer:**
Python strings are immutable. Each `s += part` creates a new string object of length `len(s) + len(part)` and copies both strings' characters into it. Over n iterations with average part length m:
- Total copies: m + 2m + 3m + ... + nm = m·n(n+1)/2 = O(n²·m)

`"".join(parts)`: allocates one buffer of total length, copies each part once = O(n·m).

```python
parts = ["x"] * 100_000

# Measure:
import timeit

# += loop:
def slow():
    s = ""
    for p in parts:
        s += p
    return s

# join:
def fast():
    return "".join(parts)

print(timeit.timeit(slow, number=10))   # ~0.5s
print(timeit.timeit(fast, number=10))   # ~0.003s
```

**When is `+=` OK?** For a small, fixed number of concatenations (not in a loop), readability wins. `f"Hello {name}!"` is fine. Building a string from 10,000 parts: use `join`.

### Q3: How would you refactor code that accidentally runs in O(n²) to O(n log n) or better?

**Model answer:**
Common refactoring patterns:

| Pattern | O(n²) code | O(n) fix |
|---------|-----------|---------|
| Membership test | `if x in my_list` | Convert to `set`, then `if x in my_set` |
| Deduplication | `if x not in result_list` | `result = dict.fromkeys(items)` |
| Grouping | `list.index(category)` | `defaultdict(list)` |
| Prefix-of-prefix | String build `+=` | `"".join(parts)` |
| Remove duplicates preserving order | `if x not in seen_list` | `seen = set(); if x not in seen; seen.add(x)` |

For O(n log n) sorting-based solutions:

```python
# Find pairs that sum to target — sort then two-pointer:
def find_pairs_nlogn(nums: list[int], target: int) -> list[tuple]:
    nums_sorted = sorted(nums)   # O(n log n)
    lo, hi = 0, len(nums_sorted) - 1
    pairs = []
    while lo < hi:
        total = nums_sorted[lo] + nums_sorted[hi]
        if total == target:
            pairs.append((nums_sorted[lo], nums_sorted[hi]))
            lo += 1; hi -= 1
        elif total < target:
            lo += 1
        else:
            hi -= 1
    return pairs
```

### Q4: How do you identify accidental O(n²) in a code review, without running the code?

**Model answer:**
Look for these patterns:

1. **Linear scan inside a loop:**
   ```python
   for item in collection:     # outer: O(n)
       if item in another_list: # inner: O(n) — total O(n²)
   ```

2. **Building output with `+`/`+=` in a loop:**
   ```python
   result = ""
   for x in items:
       result += transform(x)   # O(n²) due to string immutability
   ```

3. **`list.remove()`, `list.pop(0)`, `list.insert(0, x)` in a loop:**
   Each is O(n); in a loop of n iterations → O(n²).

4. **Nested loops over correlated data:**
   ```python
   for user in users:
       for order in orders:         # O(n * m)
           if order.user_id == user.id:  # should be a lookup
   ```
   Fix: build a dict `orders_by_user = defaultdict(list, ...)` first.

5. **`sorted()` or `min()`/`max()` inside a loop:** O(n log n) inside O(n) = O(n² log n).

### Q5: What's wrong with `list.remove(item)` to deduplicate, and what's the correct approach?

**Model answer:**
`list.remove(item)` scans the list to find the first occurrence and removes it (shifting subsequent elements). O(n) per call. In a loop: O(n²).

```python
# O(n²): remove duplicates in-place
def dedup_slow(lst):
    i = 0
    while i < len(lst):
        while lst.count(lst[i]) > 1:   # count is O(n)!
            lst.remove(lst[i])          # remove is O(n)!
        i += 1

# O(n): use set for seen, build new list
def dedup_fast_ordered(lst):
    seen = set()
    result = []
    for x in lst:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result

# O(n): dict.fromkeys preserves insertion order (Python 3.7+)
def dedup_fastest(lst):
    return list(dict.fromkeys(lst))
```

---

## Gotcha Follow-ups

**"CPython sometimes optimizes `+=` for strings — can you rely on it?"**
CPython 3.11+ has a peephole optimization: if `s` has `refcount == 1` at the time of `+=`, it reallocates in-place instead of copying. This turns simple `s += part` loops into O(n) in practice. BUT: this is an implementation detail of CPython, not guaranteed by the language spec. It breaks in PyPy, if `s` is referenced elsewhere, or in future CPython versions. Write `"".join(parts)` for correctness and portability.

**"What if the inner loop is very small — does O(n²) still matter?"**
Yes, at scale. For n=1,000: n²=1,000,000 — fine. For n=100,000: n²=10,000,000,000 — catastrophic. The actual threshold depends on the constant factor, but O(n²) algorithms always become unusable eventually. Profile on realistic data sizes before declaring it "fine."

---

## Under the Hood

CPython's `list.__contains__` (`Objects/listobject.c: list_contains()`) iterates from index 0, calling `PyObject_RichCompareBool(item, value, Py_EQ)` on each element — O(n) comparisons. `set.__contains__` (`Objects/setobject.c: set_contains_key()`) computes the hash, indexes into `so_table[hash & mask]`, and compares one entry — amortized O(1). The hash table uses open addressing with quadratic probing, load factor ≤ 2/3, and SipHash-1-3 for string keys (PYTHONHASHSEED randomization for security).
