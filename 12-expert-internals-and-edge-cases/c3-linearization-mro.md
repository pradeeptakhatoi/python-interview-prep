# C3 Linearization and Method Resolution Order

## Concept

Python uses the **C3 linearization algorithm** to compute the Method Resolution Order (MRO) — the sequence of classes that Python searches when looking up an attribute via `super()` or direct inheritance. It was adopted in Python 2.3 (new-style classes) and is the only supported algorithm in Python 3.

### The Problem with Naive MRO

Before C3, Python used "depth-first, left-to-right" search, which produced incorrect results in diamond inheritance:

```
    A
   / \
  B   C
   \ /
    D

Depth-first: D → B → A → C → A  (A appears twice, wrong order)
C3: D → B → C → A               (each class appears once, monotone)
```

### C3 Algorithm

Given `class D(B, C)`:
```
L[D] = D + merge(L[B], L[C], [B, C])
```

Where `merge` works by:
1. Take the first list's head.
2. Check if that head is in the **tail** (everything after the first element) of any other list.
3. If not: add it to the output, remove it from all lists, repeat.
4. If yes: skip to the next list's head and try again.
5. If no valid head is found: raise `TypeError` (inconsistent MRO).

### Computing MRO by Hand

```
class A: pass
class B(A): pass
class C(A): pass
class D(B, C): pass

L[object] = [object]
L[A] = [A, object]
L[B] = [B, A, object]
L[C] = [C, A, object]

L[D] = D + merge([B, A, object], [C, A, object], [B, C])

Step 1: head = B
  Is B in tail of [C, A, object]? No (tail = [A, object])
  Is B in tail of [B, C]? No (tail = [C])
  → Output B; remove B from all lists
  Lists: [A, object], [C, A, object], [C]

Step 2: head = A
  Is A in tail of [C, A, object]? YES (tail = [A, object]) — skip!
  Try next list: head = C
  Is C in tail of [A, object]? No
  Is C in tail of [C]? No (tail is empty)
  → Output C; remove C from all lists
  Lists: [A, object], [A, object], []

Step 3: head = A
  Is A in tail of [A, object]? No (no other lists with A in tail, [] is empty)
  → Output A; remove A
  Lists: [object], [object]

Step 4: Output object

L[D] = [D, B, C, A, object]
```

```python
class A: pass
class B(A): pass
class C(A): pass
class D(B, C): pass

print(D.__mro__)
# (<class '__main__.D'>, <class '__main__.B'>, <class '__main__.C'>,
#  <class '__main__.A'>, <class 'object'>)
```

### Inconsistent MRO (TypeError)

```python
class X: pass
class Y: pass
class A(X, Y): pass
class B(Y, X): pass

class C(A, B): pass  # TypeError: Cannot create a consistent method resolution order (MRO)
# L[A] requires X before Y
# L[B] requires Y before X
# These constraints are contradictory — no valid linearization exists
```

This is a feature: C3 makes problematic inheritance hierarchies explicit rather than silently producing wrong behavior.

### `super()` and MRO

`super()` doesn't mean "my parent class" — it means "the next class in the MRO of the instance's type":

```python
class A:
    def method(self):
        print(f"A.method, self.__class__ = {self.__class__.__name__}")
        # Note: no super() call here — end of chain

class B(A):
    def method(self):
        print(f"B.method")
        super().method()  # next in MRO after B

class C(A):
    def method(self):
        print(f"C.method")
        super().method()  # next in MRO after C

class D(B, C):
    def method(self):
        print(f"D.method")
        super().method()  # next in MRO after D = B

d = D()
d.method()
# D.method
# B.method
# C.method
# A.method
```

**Key insight:** `B.method`'s `super()` call ends up calling `C.method`, even though `B` doesn't know about `C`. This is because `super()` uses `type(self).__mro__` (D's MRO), not `B.__mro__`. This is **cooperative multiple inheritance** — each class in the chain calls `super()` to pass control to the next class.

### `super()` with Arguments

```python
# super() with no args (Python 3 magic):
class B(A):
    def method(self):
        super().method()  # equivalent to super(B, self).method()

# super() internals: uses __class__ cell variable (compiler-injected closure)
# and the first argument of the method (conventionally 'self')

# Explicit super() with args (needed in some edge cases):
class B(A):
    def method(self):
        super(B, self).method()  # same result; explicit form

# super() with a class: useful for calling a specific class in the MRO
class D(B, C):
    def method(self):
        super(C, self).method()  # starts search AFTER C in D's MRO → A.method
```

### Diamond Inheritance in Practice

```python
class Loggable:
    def log(self, msg):
        print(f"[LOG] {msg}")

class Serializable:
    def serialize(self):
        return {}

class Base(Loggable, Serializable):
    def __init__(self):
        super().__init__()  # cooperative — calls next in MRO
        self.log("Base initialized")

class Extended(Base):
    def __init__(self):
        super().__init__()  # calls Base.__init__
        self.log("Extended initialized")

# All __init__ calls are chained via super()
# MRO: Extended → Base → Loggable → Serializable → object
print(Extended.__mro__)
```

---

## Interview Questions

### Q1: Compute the MRO for this hierarchy by hand:

```python
class F: pass
class E: pass
class D: pass
class C(D, F): pass
class B(E, D): pass
class A(B, C): pass
```

**Model answer:**
```
L[F] = [F, object]
L[E] = [E, object]
L[D] = [D, object]
L[C] = [C, D, F, object]
L[B] = [B, E, D, object]

L[A] = A + merge([B, E, D, object], [C, D, F, object], [B, C])

Step 1: head=B; in tail of [C,D,F,object]? No; in tail of [B,C]? No → output B
  Lists: [E,D,object], [C,D,F,object], [C]

Step 2: head=E; in tail of [C,D,F,object]? No; in tail of [C]? No → output E
  Lists: [D,object], [C,D,F,object], [C]

Step 3: head=D; in tail of [C,D,F,object]? YES (tail=[D,F,object]) — skip
  Next: head=C; in tail of [D,object]? No; in tail of [C]? No → output C
  Lists: [D,object], [D,F,object], []

Step 4: head=D; in tail of [D,F,object]? No (tail=[F,object]) → output D
  Lists: [object], [F,object]

Step 5: head=object; in tail of [F,object]? YES — skip
  Next: head=F; in tail of [object]? No → output F
  Lists: [object], [object]

Step 6: output object

L[A] = [A, B, E, C, D, F, object]
```

```python
print(A.__mro__)
# (<class 'A'>, <class 'B'>, <class 'E'>, <class 'C'>, <class 'D'>, <class 'F'>, <class 'object'>)
```

### Q2: Why must every class in a cooperative multiple inheritance hierarchy call `super().__init__()`?

**Model answer:**  
If any class in the MRO chain omits `super().__init__()`, the chain is broken and subsequent classes in the MRO don't get their `__init__` called.

```python
class A:
    def __init__(self):
        super().__init__()
        print("A initialized")

class B:
    def __init__(self):
        super().__init__()
        print("B initialized")

class Broken(A, B):
    def __init__(self):
        A.__init__(self)  # BAD: calls A directly, bypassing MRO
        B.__init__(self)  # BAD: double-calls if B is reachable via A's MRO too
        print("Broken initialized")

class Correct(A, B):
    def __init__(self):
        super().__init__()  # follows MRO: Correct → A → B → object
        print("Correct initialized")

Correct()
# B initialized (last in chain before object)
# A initialized
# Correct initialized
```

The cooperative pattern requires:
1. Every class (except the base) calls `super().__init__()`.
2. Signatures must be compatible (use `*args, **kwargs` to pass through unexpected arguments).

### Q3: What is the `super()` proxy object and how does it find the next class?

**Model answer:**  
`super()` (with no args in Python 3) uses a `__class__` cell variable that the compiler automatically injects into any method that uses `super()`. The `__class__` cell holds the class the method is defined in (not `type(self)`).

```python
class B(A):
    def method(self):
        # Compiler implicitly adds: __class__ = B (a cell closure)
        super()  # equivalent to: super(__class__, self) = super(B, self)
```

The `super()` proxy:
1. Gets the MRO of `type(self)`.
2. Finds `__class__` (B) in that MRO.
3. Returns a proxy that starts searching AFTER B in the MRO.

**The trap — `super()` in lambdas or nested functions:**
```python
class B(A):
    def method(self):
        # This works:
        s = super()

        # This BREAKS — lambda doesn't get the __class__ cell:
        fn = lambda: super()  # NameError or wrong class

        # Fix:
        cls = __class__  # capture before lambda
        fn = lambda: super(cls, self)
```

### Q4: When would you prefer explicit MRO traversal over `super()`?

**Model answer:**  
`super()` is right for cooperative multiple inheritance. But in some cases, you need to call a specific class directly:

1. **When you know exactly which base class method you need:**
```python
class D(B, C):
    def method(self):
        A.method(self)  # skip B and C entirely — intentional, not cooperative
```

2. **In metaclasses, where `super()` can be confusing:**
```python
class MyMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)  # correct
        return cls
```

3. **When debugging an MRO issue:**
```python
# Walk the MRO manually to understand what super() would do:
for cls in type(instance).__mro__:
    if 'method' in cls.__dict__:
        print(f"Found in {cls}")
        break
```

4. **Calling `object.__init__` explicitly** when you're at the end of a cooperative chain and don't want to pass unknown kwargs upward.

### Q5: What is the `mro()` method and when would you override it?

**Model answer:**  
`type.mro(cls)` is a method on the metaclass that computes and returns the MRO as a list. By default it calls `C3Linearize(cls)`. You can override it in a custom metaclass:

```python
class PrioritizedMeta(type):
    def mro(cls):
        # Custom MRO: always put a specific mixin first
        standard_mro = super().mro()
        # Sort to move PriorityMixin to the front (after cls itself):
        priority = [c for c in standard_mro if issubclass(c, PriorityMixin)]
        rest = [c for c in standard_mro if c not in priority]
        return [standard_mro[0]] + priority + rest[1:]  # cls first, then priority, then rest
```

**Real-world use case:** Plugin systems where you want to inject a tracing mixin before all other classes without having every class explicitly inherit from it. Or frameworks that need to control attribute lookup order.

**Warning:** Custom MRO can break `super()` in unexpected ways and makes code harder to reason about. Prefer explicit mixin ordering in the class definition over MRO manipulation.

---

## Gotcha Follow-ups

**"Can you have a class whose MRO doesn't include `object`?"**  
No — all Python 3 classes implicitly inherit from `object`. `object` is always last in the MRO (before or at the very end). The C3 algorithm guarantees this because `object` is the root of all class hierarchies.

**"What does `super()` return exactly, and is it a class?"**  
`super()` returns a **proxy object** of type `super` — not a class. It implements `__getattribute__` to look up attributes in the correct part of the MRO. When you call `super().method()`, the proxy's `__getattribute__` finds `method` in the next class in MRO and returns a bound method with the original `self`. The proxy is not cacheable across `self` changes — create it fresh in each call.

---

## Under the Hood

C3 linearization is in `Objects/typeobject.c`, function `mro_internal()`. It calls `mro_implementation()` which implements the algorithm via `pmerge()` (the merge operation). The resulting MRO list is stored in `tp_mro` on the type object.

`super()` is implemented in `Objects/typeobject.c` as a `type` with custom `__init__` and `__getattribute__`. The no-argument form uses a compiler trick: the compiler injects `__class__` as a free variable (closure cell) into any method that uses `super()` (even if no argument is passed). This is done by the AST-to-bytecode compiler when it detects `super()` in a method body.
