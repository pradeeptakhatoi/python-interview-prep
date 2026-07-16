# Interning: Small Int Cache and String Interning

## Concept

**Interning** means returning the same object for identical values instead of creating a new object each time. CPython interns certain objects by default as an optimization. Understanding interning is essential for correctly using `is` vs `==` and for avoiding subtle bugs.

### Small Integer Cache

CPython pre-allocates integers from **-5 to 256** at startup. Any operation that produces a value in this range returns the cached object — no new allocation occurs.

```python
a = 100
b = 100
print(a is b)    # True — same cached object

a = 1000
b = 1000
print(a is b)    # False in general (but may be True in REPL or compiled code)
print(a == b)    # True — value equality always works
```

The range -5 to 256 was chosen empirically — these are the values most commonly used in typical Python programs (loop counters, small indices, boolean-ish values).

**Important:** This is an implementation detail of CPython, not guaranteed by the Python language spec. Do NOT write production code that uses `is` for integer comparison.

### String Interning

CPython automatically interns strings that look like identifiers (contain only letters, digits, underscores, and don't start with a digit). This covers variable names, attribute names, and many string literals.

```python
# Auto-interned (identifier-like):
a = "hello"
b = "hello"
print(a is b)    # True — CPython interns these at compile time

# NOT auto-interned:
a = "hello world"
b = "hello world"
print(a is b)    # False in general (space makes it non-identifier)
                 # May be True in the same code block (constant folding)

# Force interning:
import sys
a = sys.intern("hello world")
b = sys.intern("hello world")
print(a is b)    # True — explicitly interned
```

### Compile-Time Constant Folding

The Python bytecode compiler performs constant folding — string literals used in the same module that are identical may be deduplicated at compile time, making `is` return `True` even for non-identifier strings in the same compiled unit:

```python
# This happens at compile time in the same .py file:
x = "hello world"
y = "hello world"
print(x is y)  # Often True in CPython — same constant in code object
               # But not guaranteed; do NOT rely on this

# In the REPL, each line is compiled separately, so this may differ
```

### When to Use `sys.intern`

`sys.intern` is useful when:
1. You have a large number of repeated string instances (e.g., keys from a database with repeated column names, token types in a lexer).
2. You need fast identity-based comparison (`is`) instead of value comparison (`==`).
3. You're building a dictionary-heavy system and want hash collisions to resolve faster (interned strings skip `strcmp` on hash collision since `is` check suffices).

```python
import sys

# Practical use: tokenizer with many repeated token types
TOKEN_TYPES = {
    "IF", "ELSE", "FOR", "WHILE", "DEF", "CLASS", "RETURN"
}
TOKEN_TYPES = {sys.intern(t) for t in TOKEN_TYPES}

def tokenize(source):
    tokens = []
    for word in source.split():
        token_type = sys.intern(word.upper()) if word.upper() in TOKEN_TYPES else word
        tokens.append(token_type)
    return tokens
```

---

## Interview Questions

### Q1: Why does `257 is 257` sometimes return `True` in the REPL but `False` in a .py file?

**Model answer:**  
In the interactive REPL, each expression you type is compiled and evaluated as a separate code object. Two occurrences of `257` in the same expression (e.g., `257 is 257`) are in the same code object and the compiler deduplicates constants within a single code object — so they end up as the same object.

In a .py file executed with `python file.py`, the entire file is compiled into one code object, and constant deduplication applies across the file. However, at runtime when you compute `257` dynamically (e.g., `x = 256 + 1`), no interning occurs.

```python
# In REPL — may return True (same code object, constant dedup):
>>> 257 is 257
True

# At runtime — always False (new int object created):
>>> x = 257
>>> y = 257
>>> x is y
False  # Two separate allocations; outside the small int cache range
```

The takeaway: never use `is` for integer comparison. This behavior is undefined by the language spec.

### Q2: What is the memory impact of interning strings in a large data pipeline?

**Model answer:**  
If a data pipeline processes millions of records with repeated string fields (e.g., status codes, category names, country codes), each record creates a new `str` object even if the value is identical. With `sys.intern`, all occurrences share a single object.

```python
import sys

# Without interning — 1M separate string objects:
records = [{"status": "ACTIVE"} for _ in range(1_000_000)]
# Each "ACTIVE" is a separate allocation (~57 bytes each) = ~57 MB

# With interning — 1M dicts pointing to the same str object:
STATUS = sys.intern("ACTIVE")
records_interned = [{"status": STATUS} for _ in range(1_000_000)]
# "ACTIVE" allocated once; dict values are just pointers (~8 bytes each)
```

Reduction: from 57 MB to ~8 MB just for the status field. The savings multiply across all repeated string fields.

**Caveat:** `sys.intern` keeps strings alive forever (in the intern table) — interning strings that have many distinct values (e.g., user IDs) would be a memory leak.

### Q3: How does Python's interning interact with dictionary lookups?

**Model answer:**  
Python dicts use `PyObject_RichCompareBool(key, dict_key, Py_EQ)` to resolve hash collisions. For strings, this first does a pointer comparison (`key is dict_key`) before falling back to a character-by-character compare. Interned strings that are identical share the same pointer, so the collision check short-circuits immediately.

This is why attribute lookup (`obj.name`) is fast — attribute names are always interned (they're identifier strings). `LOAD_ATTR` effectively does an interned-string identity comparison for the key.

```python
d = {"status": "ok"}

# These lookup paths:
d["status"]   # key "status" is auto-interned; lookup uses identity check first
              # ~O(1) with short-circuit identity comparison

# vs runtime-constructed string:
key = "sta" + "tus"   # "status" — but may or may not be the interned object
d[key]                # still works (== check), but identity shortcut may miss
```

### Q4: Does `sys.intern` affect garbage collection?

**Model answer:**  
Yes — interned strings are held in a global C-level dictionary (`interned` in `Objects/unicodeobject.c`). This keeps the string alive until the interpreter exits, regardless of whether any Python code holds a reference to it.

The intern table holds a **strong** reference. If you intern a string, its refcount will never reach 0 via user-visible means, and it will never be GC'd during the interpreter's lifetime. This means:

- Interning a bounded set of known strings (status codes, enum values): safe.
- Interning arbitrary user-supplied strings: memory leak. The intern table grows without bound.

```python
import sys

# Safe: bounded vocabulary
STATUSES = [sys.intern(s) for s in ["ACTIVE", "INACTIVE", "PENDING", "DELETED"]]

# Dangerous: unbounded user input
def process_request(data):
    key = sys.intern(data["user_id"])  # BAD: leaks every unique user_id
```

### Q5: What's the difference between `is` for strings and `==` for strings, performance-wise?

**Model answer:**  
- `is` — single pointer comparison, O(1) and extremely fast.
- `==` — calls `str.__eq__`, which first compares lengths, then hashes (if available), then falls back to character-by-character comparison. O(n) in the length of the string in the worst case.

For interned strings, `is` is safe and correct. For non-interned strings, `==` is required for correct value comparison. The performance difference only matters in hot comparison paths (tight loops, cache lookups by string key):

```python
import timeit

a = sys.intern("a_long_repeated_key_name")
b = sys.intern("a_long_repeated_key_name")

timeit.timeit(lambda: a is b, number=10_000_000)   # ~0.15s
timeit.timeit(lambda: a == b, number=10_000_000)   # ~0.30s (hash compare shortcut)
# is is ~2x faster; both are sub-microsecond; optimize only if profiling shows it matters
```

---

## Gotcha Follow-ups

**"If CPython interns certain strings, does that mean the GC never collects strings?"**  
Auto-interned strings (identifier-like ones encountered during compilation) are stored in the intern table with a reference. They won't be collected while the intern table holds them. Strings that are NOT interned (constructed at runtime, non-identifier format) are collected normally. Explicitly `sys.intern()`-ed strings are permanently alive.

**"Can you force two string objects to become the same object post-creation?"**  
Yes, via `sys.intern()` — even if two `str` objects with the same value already exist, calling `sys.intern(s)` returns the canonical interned copy. If the string was already interned, you get that back; otherwise, a new interned copy is created and the old objects may be GC'd if they had no other references. There's no way to "merge" two arbitrary objects in CPython — interning works by returning the canonical instance.

---

## Under the Hood

The small int cache is in `Objects/longobject.c`:
```c
#define NSMALLPOSINTS 257    /* 0..256 */
#define NSMALLNEGINTS 5     /* -5..-1 */
static PyLongObject small_ints[NSMALLNEGINTS + NSMALLPOSINTS];
```

String interning is in `Objects/unicodeobject.c`, `PyUnicode_InternInPlace()`. The intern table is a regular Python `dict` stored at the C level. Strings that are interned have their `PyASCIIObject.interned` flag set to `SSTATE_INTERNED_IMMORTAL` (never collected) or `SSTATE_INTERNED_MORTAL` (collected when refcount hits 0 outside intern table).
