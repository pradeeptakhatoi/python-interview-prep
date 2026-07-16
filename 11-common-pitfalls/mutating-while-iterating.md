# Modifying Collections While Iterating

## Concept

Modifying a collection (list, dict, set) during iteration over it produces undefined, surprising, or error-raising behavior. Python's built-in iterators hold a reference to the underlying collection and advance an index or use an internal position — modification invalidates assumptions built into the iteration protocol.

### Dict: `RuntimeError` on Modification

```python
d = {'a': 1, 'b': 2, 'c': 3}

# Raises RuntimeError:
for k in d:
    if d[k] == 2:
        del d[k]   # RuntimeError: dictionary changed size during iteration

# Raises RuntimeError (even value-only changes in Python < 3.3 could):
for k, v in d.items():
    d[k] = v * 2   # safe in Python 3.3+ for value modification, but not for adding/removing

# Safe pattern 1: iterate over a copy of keys
for k in list(d.keys()):   # list() materializes the keys first
    if d[k] == 2:
        del d[k]

# Safe pattern 2: build a new dict
d = {k: v for k, v in d.items() if v != 2}

# Safe pattern 3: collect keys to delete, then delete after
keys_to_delete = [k for k, v in d.items() if v == 2]
for k in keys_to_delete:
    del d[k]
```

### List: Skipped Elements

```python
lst = [1, 2, 3, 4, 5, 6]

# No RuntimeError — but skips elements:
for i, x in enumerate(lst):
    if x % 2 == 0:
        lst.remove(x)   # shifts all subsequent elements left — skips next!

print(lst)   # [1, 3, 5] — correct, but by accident
# Works here because removing even numbers happens to not skip odd ones.

# Counterexample: consecutive duplicates
lst2 = [1, 2, 2, 3]
for x in lst2:
    if x == 2:
        lst2.remove(x)   # removes first 2, shifts, skips second 2
print(lst2)   # [1, 2, 3] — WRONG! One 2 remains.

# Safe: build new list
lst = [x for x in lst if x % 2 != 0]   # [1, 3, 5]

# Safe: reverse iteration (removes don't affect earlier indices)
for i in range(len(lst) - 1, -1, -1):
    if lst[i] % 2 == 0:
        del lst[i]

# Safe: two-pass (collect then delete)
to_remove = [i for i, x in enumerate(lst) if x % 2 == 0]
for i in reversed(to_remove):   # reversed: delete from end to not shift earlier indices
    del lst[i]
```

### Set: `RuntimeError` on Modification

```python
s = {1, 2, 3, 4, 5}

for x in s:
    if x % 2 == 0:
        s.discard(x)   # RuntimeError: Set changed size during iteration

# Safe: iterate over a copy
for x in set(s):   # set() creates a copy
    if x % 2 == 0:
        s.discard(x)

print(s)   # {1, 3, 5}

# Safe: set difference
s -= {x for x in s if x % 2 == 0}
```

### Nested Iteration

```python
# Modifying outer collection while using it in a nested loop:
graph = {
    'A': ['B', 'C'],
    'B': ['A'],
    'C': ['A', 'D'],
    'D': ['C'],
}

# WRONG: modifying graph while iterating over nodes
for node in graph:
    if not graph[node]:   # isolated node
        del graph[node]   # RuntimeError during next iteration!

# SAFE: two-phase
isolated = [node for node, neighbors in graph.items() if not neighbors]
for node in isolated:
    del graph[node]

# SAFE: comprehension
graph = {node: neighbors for node, neighbors in graph.items() if neighbors}
```

### The Iterator Protocol and Why Mutation Breaks It

```python
# Lists use an index-based iterator:
lst = [1, 2, 3, 4]
it = iter(lst)
print(next(it))   # 1 (index 0)
lst.insert(0, 99)   # shifts all elements right
print(next(it))   # 2 (now at index 1 — skipped 99!)

# The list iterator stores an index, not a position reference.
# After mutation, the index points to a different element.

# Safe iteration pattern: snapshot via slice or list():
for x in lst[:]:   # lst[:] creates a shallow copy
    lst.remove(x)   # original list modified, but we're iterating the copy
```

---

## Interview Questions

### Q1: Why does iterating over a dict while modifying it raise `RuntimeError`?

**Model answer:**
Python's dict iterator stores `ma_version_tag` — a version counter that changes on any structural modification (add/remove key). Before each `__next__()` call, the iterator checks whether the version matches the version when iteration started. If they differ, it raises `RuntimeError: dictionary changed size during iteration`.

This is a safety guard: without it, structural changes (rehashing, key deletion) could cause the iterator to skip entries, visit entries twice, or crash with a segfault at the C level (since rehashing moves entries).

```python
import sys

d = {'a': 1, 'b': 2}
it = iter(d)
print(next(it))   # 'a'
d['c'] = 3        # structural modification (adds a key)

try:
    print(next(it))   # RuntimeError!
except RuntimeError as e:
    print(e)   # dictionary changed size during iteration

# Value-only updates on EXISTING keys are safe in Python 3.3+:
d = {'a': 1, 'b': 2}
for k in d:
    d[k] *= 2   # no size change — safe
print(d)   # {'a': 2, 'b': 4}
```

### Q2: Why does removing from a list during iteration skip elements?

**Model answer:**
The list iterator internally maintains an index counter. `remove()` (and `pop(i)`) shifts all subsequent elements left, decrementing their indices. The iterator doesn't know about this — it increments the index normally, landing on the element AFTER the removed one's original position:

```python
lst = [1, 2, 2, 3]
# indices:  0  1  2  3

for x in lst:
    if x == 2:
        lst.remove(x)   # removes the FIRST occurrence

# Iteration 1: index=0, x=1. Not 2, keep. index → 1.
# Iteration 2: index=1, x=2. Remove. List is now [1, 2, 3]. index → 2.
# Iteration 3: index=2, x=3. Not 2, keep. index → 3.
# Loop ends (len=3).
# Element at (new) index 1 (value 2) was NEVER visited!
print(lst)   # [1, 2, 3] — the second 2 survived
```

### Q3: What is the safest, most Pythonic way to filter elements from a list in-place?

**Model answer:**
In-place filtering without creating a new list:

```python
# Method 1: slice assignment — replaces all contents in-place
lst = [1, 2, 3, 4, 5, 6]
lst[:] = [x for x in lst if x % 2 != 0]
print(lst)   # [1, 3, 5]
# lst itself is the same object — aliases to the same list see the update

# Method 2: reverse index deletion — no skipping
for i in range(len(lst) - 1, -1, -1):
    if lst[i] % 2 == 0:
        del lst[i]

# Method 3: filter() (lazy, returns iterator)
result = list(filter(lambda x: x % 2 != 0, lst))

# If in-place mutation is needed (other references to lst must see the change):
# Use method 1 (slice assignment) — it mutates the same list object.
# Creating a new list with comprehension replaces the name, not the object:

lst = [1, 2, 3, 4]
ref = lst
lst = [x for x in lst if x % 2 != 0]  # lst is now a NEW object
print(ref)  # [1, 2, 3, 4] — ref still points to original!
# Use lst[:] = ... instead if you need to update ref too
```

### Q4: Is it safe to append to a list while iterating over it?

**Model answer:**
Technically it won't raise an error, but it's almost always a bug:

```python
lst = [1, 2, 3]
for x in lst:
    if x == 1:
        lst.append(x + 10)   # appends 11 — then iteration visits 11!
    print(x)   # prints: 1, 2, 3, 11

# The list iterator visits indices sequentially. Appending extends the list,
# so the iterator visits the newly appended elements too.
# This creates an unintentional "growing loop" that could run forever:
lst = [1]
for x in lst:
    lst.append(x + 1)   # infinite loop — list grows as fast as it's consumed!
    if x > 100:
        break

# Intentional use (BFS — queue simulation with list):
visited = []
frontier = [start_node]
for node in frontier:   # frontier grows as we discover neighbors
    if node not in visited:
        visited.append(node)
        frontier.extend(get_neighbors(node))  # intentional append during iteration

# Better: use collections.deque for BFS — semantically clearer
```

### Q5: How do you safely remove items matching a predicate from a dict, and what's the most efficient approach for large dicts?

**Model answer:**

```python
# Option 1: dict comprehension (creates new dict)
d = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
d = {k: v for k, v in d.items() if v % 2 != 0}
# O(n) time, O(n) space

# Option 2: list of keys to delete (two-pass)
keys_to_delete = [k for k, v in d.items() if v % 2 == 0]
for k in keys_to_delete:
    del d[k]
# O(n) time, O(k) extra space for key list

# Option 3: slice-copy keys view (clear + update)
d_copy = {k: v for k, v in d.items() if v % 2 != 0}
d.clear()
d.update(d_copy)
# O(n) time, O(n) space — preserves the same dict object (for aliased references)

# Performance comparison for large dicts:
import timeit

large = {i: i for i in range(100_000)}

# comprehension (new dict):
t1 = timeit.timeit(
    lambda: {k: v for k, v in large.items() if v % 2 != 0},
    number=10
)

# two-pass:
def two_pass():
    d = large.copy()
    keys = [k for k, v in d.items() if v % 2 == 0]
    for k in keys:
        del d[k]
    return d

t2 = timeit.timeit(two_pass, number=10)

# comprehension is typically faster — fewer dict operations
# two-pass: useful when you need to keep the SAME dict object
```

---

## Gotcha Follow-ups

**"Is `for k in d.keys()` vs `for k in d` different for mutation safety?"**
No — both are equivalent. `d.keys()` returns a view object, not a snapshot. Both raise `RuntimeError` if the dict changes size during iteration. To iterate safely while modifying, use `for k in list(d.keys())` — `list()` materializes the keys into a new list, decoupling the iteration from the dict's structure.

**"What about `itertools.filterfalse` or `filter()` — do they solve this?"**
`filter()` and `itertools.filterfalse()` are lazy — they don't iterate until you consume the iterator. If you construct `filter(pred, d)` and then modify `d` before consuming it, you'll still get `RuntimeError` at consumption time. Materializing with `list(filter(pred, d))` is a snapshot, making it safe.

---

## Under the Hood

The list iterator (`Objects/listobject.c: listiter_next()`) stores `it_index` (current position) and a pointer to the list. Each `__next__()` call increments `it_index` and reads `list->ob_item[it_index]`. No mutation detection — skipping is silent. The dict iterator (`Objects/dictobject.c: dictiter_iternextkey()`) stores `di_used` (count of active keys at start) and `di_version` (from `ma_version_tag`, incremented on any structural change). It checks `mp->ma_used != di_used` on each `__next__()` and raises `RuntimeError` if they differ. Set iterator follows the same pattern as dict (`Objects/setobject.c: setiter_iternext()`).
