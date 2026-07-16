# C3 Linearization and Method Resolution Order

## Concept

C3 linearization is the algorithm CPython uses to compute the Method Resolution Order (MRO) for classes with multiple inheritance. Understanding it at the algorithmic level — not just "subclasses first" — is a Staff/Architect differentiator. Note: basic MRO was covered in section 11 (inheritance-vs-composition.md). This file covers the deep internals, edge cases, and the algorithm's formal properties.

### The C3 Algorithm — Step by Step

```python
# C3 merge algorithm:
# L[C] = C + merge(L[B1], L[B2], ..., [B1, B2, ...])
# where B1, B2, ... are the bases of C in declaration order
#
# merge rule: take the HEAD of the first list that does NOT appear
# in the TAIL of any other list. Remove it from all lists. Repeat.
# If no valid head exists: TypeError (inconsistent MRO).

def c3_merge(sequences: list[list]) -> list:
    """Pure Python implementation of C3 merge."""
    result = []
    while True:
        # Filter out empty sequences:
        sequences = [s for s in sequences if s]
        if not sequences:
            return result

        # Find a good head:
        for seq in sequences:
            candidate = seq[0]
            # candidate is "good" if it doesn't appear in the TAIL of any sequence:
            if not any(candidate in s[1:] for s in sequences):
                result.append(candidate)
                # Remove candidate from all sequences:
                for s in sequences:
                    if s[0] == candidate:
                        del s[0]
                break
        else:
            raise TypeError("Inconsistent MRO — cannot linearize")

def compute_mro(cls, bases: list) -> list:
    """Compute MRO using C3 linearization."""
    return [cls] + c3_merge(
        [list(b.__mro__) for b in bases] + [list(bases)]
    )

# Verify against Python:
class O: pass
class A(O): pass
class B(O): pass
class C(O): pass
class D(A, B): pass
class E(B, C): pass
class F(D, E): pass

computed = compute_mro(F, [D, E])
actual = list(F.__mro__)
print(computed == actual)  # True

print(F.__mro__)
# (F, D, A, E, B, C, O, object)
```

### Worked Example — The Classic Diamond

```
         O
        / \
       A   B
        \ /
         C
```

```python
class O: pass
class A(O): pass
class B(O): pass
class C(A, B): pass

# C3 computation:
# L[O] = [O, object]
# L[A] = [A] + merge([O, object], [O]) = [A, O, object]
# L[B] = [B] + merge([O, object], [O]) = [B, O, object]
# L[C] = [C] + merge(L[A], L[B], [A, B])
#       = [C] + merge([A, O, obj], [B, O, obj], [A, B])
#
# Step 1: head=A. Not in tail of any list? [O,obj], [O,obj], [B] — A not in tails. Take A.
# Result: [C, A]. Remove A from all: [O,obj], [B,O,obj], [B]
#
# Step 2: head=O. In tail of [B,O,obj]? Yes! Skip O.
# Try head=B (next list). Not in any tail? [obj], [O,obj], [] — B not in tails. Take B.
# Result: [C, A, B]. Remove B: [O,obj], [O,obj], []
#
# Step 3: head=O. Not in any tail now (all tails are [obj]). Take O.
# Result: [C, A, B, O, object]

print(C.__mro__)
# (<class 'C'>, <class 'A'>, <class 'B'>, <class 'O'>, <class 'object'>)
```

### MRO Determines super() Dispatch

```python
# super() always follows the MRO of the actual instance type, not the class where it's called

class Animal:
    def speak(self):
        return "..."

class Dog(Animal):
    def speak(self):
        return f"Woof! {super().speak()}"  # super() → Animal in Dog's MRO

class ServiceDog(Dog):
    def speak(self):
        return f"Quiet. {super().speak()}"  # super() → Dog in ServiceDog's MRO

sd = ServiceDog()
print(sd.speak())   # "Quiet. Woof! ..."
# ServiceDog.speak → super() finds Dog next in ServiceDog.__mro__
# Dog.speak → super() finds Animal next in ServiceDog.__mro__ (not Dog.__mro__!)

print(ServiceDog.__mro__)
# (ServiceDog, Dog, Animal, object)

# Key insight: super() in Dog's code uses ServiceDog's MRO when called on a ServiceDog instance
# This is why all cooperative classes MUST use super() — not hardcode parent class names
```

### MRO with Mixins — Ordering Matters

```python
class LogMixin:
    def save(self):
        print("LogMixin.save")
        super().save()

class ValidationMixin:
    def save(self):
        print("ValidationMixin.save")
        super().save()

class Base:
    def save(self):
        print("Base.save")

class Model(LogMixin, ValidationMixin, Base):
    pass

m = Model()
m.save()
# LogMixin.save
# ValidationMixin.save
# Base.save
# Order: LogMixin first (leftmost mixin wins)

print(Model.__mro__)
# (Model, LogMixin, ValidationMixin, Base, object)

# Reversing mixin order changes behavior:
class Model2(ValidationMixin, LogMixin, Base):
    pass

m2 = Model2()
m2.save()
# ValidationMixin.save
# LogMixin.save
# Base.save
```

### Detecting and Fixing MRO Conflicts

```python
# The classic conflict: bases disagree on relative ordering of ancestors
class X: pass
class Y: pass
class A(X, Y): pass   # A says: X before Y
class B(Y, X): pass   # B says: Y before X

try:
    class C(A, B): pass   # Contradiction! Cannot satisfy both
except TypeError as e:
    print(e)
# Cannot create a consistent method resolution order (MRO) for bases X, Y

# Fix 1: change the inheritance order in A or B to agree
class A_fixed(X, Y): pass  # keep as-is
class B_fixed(X, Y): pass  # match A's order

class C_fixed(A_fixed, B_fixed): pass  # works now
print(C_fixed.__mro__)

# Fix 2: introduce a common base that establishes the order
class XY(X, Y): pass   # establish X before Y once

class A2(XY): pass
class B2(XY): pass
class C2(A2, B2): pass   # everyone agrees via XY

# Fix 3: use composition instead of multiple inheritance
```

---

## Interview Questions

### Q1: Explain the C3 linearization algorithm in plain terms. Why can't Python use a simpler algorithm?

**Model answer:**
C3 linearization produces a total ordering of all classes in a hierarchy that satisfies three properties:
1. **Local precedence:** the order of base classes in `class C(A, B)` is preserved (A before B in C's MRO).
2. **Monotonicity:** if A comes before B in a parent's MRO, A comes before B in all descendants' MROs.
3. **Completeness:** every class appears exactly once.

Simpler alternatives fail:
- **Depth-first left-to-right (Python 2 old-style):** violates monotonicity in the diamond case. `D(B, C)` where both inherit `A` → DFS gives `[D, B, A, C, A]` (A appears twice) or `[D, B, A, C]` (C's version of A skipped).
- **Breadth-first:** doesn't preserve local precedence.

C3 is the unique algorithm that satisfies all three properties simultaneously (proven by Kim Barrett et al., 1996). It was adopted from Dylan, CLOS, and Perl's P5.

### Q2: Why does `super()` in Python 3 take no arguments, and what does it actually do?

**Model answer:**
Python 3's `super()` with no arguments uses a `__class__` cell variable (implicit closure) and `self`/`cls` from the current frame. The compiler automatically adds `__class__` as a free variable to any method that uses `super()`.

What `super()` does:
1. Takes two implicit arguments: `__class__` (the class where the method is defined) and the first argument of the enclosing function (typically `self`).
2. Finds `__class__` in `type(self).__mro__`.
3. Returns a proxy object that starts attribute lookup from the class AFTER `__class__` in the MRO.

```python
class A:
    def method(self):
        print(f"__class__ = {__class__}")   # 'A' — the class where this method is defined
        print(f"type(self) = {type(self)}") # the actual instance type (may be B)
        proxy = super()
        # Proxy searches from the class AFTER A in type(self).__mro__
        return proxy

class B(A):
    pass

b = B()
proxy = b.method()
# __class__ = A  (where method is physically defined)
# type(self) = B (actual runtime type)
# proxy searches: B.__mro__ = [B, A, object], starts AFTER A → searches 'object'
```

`super(T, obj)` explicit form: start after `T` in `type(obj).__mro__`. `super(T, T)` for classmethods.

### Q3: What is cooperative multiple inheritance and why must ALL classes in a hierarchy use `super()`?

**Model answer:**
Cooperative multiple inheritance means every class in the MRO chain passes control to the next class via `super()`, even if it doesn't know what comes next. The entire chain acts as a pipeline.

If one class breaks the chain (hardcodes the parent call), all classes below it in the MRO are skipped:

```python
class A:
    def setup(self, **kw):
        print("A.setup")
        super().setup(**kw)

class B(A):
    def setup(self, **kw):
        print("B.setup")
        A.setup(self, **kw)   # HARDCODED — breaks chain! C is skipped

class C(A):
    def setup(self, **kw):
        print("C.setup")
        super().setup(**kw)

class D(B, C):   # MRO: D → B → C → A → object
    pass

D().setup()
# B.setup
# A.setup      ← B calls A directly, skipping C entirely!
# (C.setup never called)

# With proper super() in B:
class B_fixed(A):
    def setup(self, **kw):
        print("B_fixed.setup")
        super().setup(**kw)   # next in MRO: C

class D_fixed(B_fixed, C):
    pass

D_fixed().setup()
# B_fixed.setup
# C.setup
# A.setup
```

### Q4: How do you debug an MRO error when `TypeError: Cannot create a consistent MRO` is raised?

**Model answer:**

```python
# Step 1: print each parent's MRO to find the contradiction:
def diagnose_mro(*bases):
    for cls in bases:
        print(f"{cls.__name__}.__mro__ = {[c.__name__ for c in cls.__mro__]}")

class X: pass
class Y: pass
class A(X, Y): pass
class B(Y, X): pass

diagnose_mro(A, B)
# A.__mro__ = ['A', 'X', 'Y', 'object']  ← X before Y
# B.__mro__ = ['B', 'Y', 'X', 'object']  ← Y before X — contradiction!

# Step 2: draw the inheritance graph; look for cycles or contradictions
# in the partial order defined by the "appears before" relation

# Step 3: pick one of:
# a. Change A or B to agree on X,Y ordering
# b. Extract XY base that establishes the order
# c. Switch to composition (preferred for complex hierarchies)

# Step 4: verify with:
try:
    class C(A, B): pass
    print(C.__mro__)
except TypeError as e:
    print(f"MRO conflict: {e}")
```

### Q5: What is `type.__mro_entries__` and how does it support generic class syntax?

**Model answer:**
`__mro_entries__` (PEP 560, Python 3.7+) is called on base classes during class creation. If a base class has this method, it's called with the full tuple of bases, and the result REPLACES it in the bases tuple for MRO computation.

This enables generic aliases like `list[int]` to be used as base classes:

```python
class MyList(list[int]):   # list[int] is a GenericAlias, not a type
    pass

# Without __mro_entries__: TypeError (GenericAlias is not a type)
# With __mro_entries__: list[int].__mro_entries__ returns (list,)
# So the actual base used for MRO is: list

print(MyList.__bases__)   # (list,) — not list[int]
print(MyList.__orig_bases__)  # (list[int],) — preserved for introspection

# Custom class that customizes how it participates in MRO:
class Proxy:
    def __init_subclass__(cls, *args, **kwargs):
        pass

    def __mro_entries__(self, bases):
        # Called when used as a base class
        # Return a tuple of actual classes to substitute
        return (object,)

p = Proxy()
class MyClass(p):   # p.__mro_entries__ called → (object,) substituted
    pass
print(MyClass.__bases__)  # (object,)
```

---

## Gotcha Follow-ups

**"Does Python's MRO guarantee that a class always appears before its parents?"**
Yes — this is the "extended precedence graph" property of C3. Every class appears before any of its ancestors in the MRO. Formally: if A inherits from B, A always comes before B in any class's MRO that includes both.

**"Can you change a class's MRO after it's been created?"**
No — `__mro__` is read-only. It's computed by `type.__new__()` and stored as a C-level tuple in `tp_mro`. To change an MRO, you must create a new class. However, `__bases__` is writable — assigning to `Foo.__bases__` triggers recomputation of `__mro__` (and all subclass MROs). This is extremely unusual in production code and can cause subtle bugs.

---

## Under the Hood

MRO computation: `type_new()` (`Objects/typeobject.c`) calls `mro_internal()` which calls `mro_implementation()`. This implements the C3 algorithm using `mro_seqs_next()` to advance through input sequences and `mro_check_linearization()` to verify monotonicity. The result is stored in `type->tp_mro` (a Python tuple). `super().__getattribute__()` (`Objects/typeobject.c: super_getattro()`) walks `type->tp_mro` starting from the position AFTER `super->obj_type` (the class passed as the first argument), calling `_PyType_Lookup()` on each class until it finds the attribute. In Python 3.12, there are specializations for common `super().method()` patterns via the specializing adaptive interpreter.
