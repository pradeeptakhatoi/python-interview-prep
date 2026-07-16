# Overusing Inheritance: MRO and Diamond Problems

## Concept

Inheritance models an "is-a" relationship and reuses code through the class hierarchy. Composition models a "has-a" relationship and delegates behavior to contained objects. Python's cooperative multiple inheritance (C3 MRO) handles diamond patterns, but the real pitfall is using inheritance for code reuse when composition would be simpler and more maintainable.

### The Diamond Problem and C3 MRO

```python
class A:
    def greet(self) -> str:
        return "Hello from A"

class B(A):
    def greet(self) -> str:
        return f"B -> {super().greet()}"

class C(A):
    def greet(self) -> str:
        return f"C -> {super().greet()}"

class D(B, C):   # Diamond: D inherits B and C, both inherit A
    def greet(self) -> str:
        return f"D -> {super().greet()}"

# C3 MRO: D → B → C → A → object
print(D.__mro__)
# (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)

d = D()
print(d.greet())
# D -> B -> C -> Hello from A
# Each class calls super() — A.greet() is called exactly ONCE despite diamond

# WITHOUT super() — the wrong approach:
class B_wrong(A):
    def greet(self):
        return f"B -> {A.greet(self)}"   # bypasses MRO — A called multiple times

class D_wrong(B_wrong, C):
    def greet(self):
        return f"D -> {B_wrong.greet(self)}"
# B_wrong hardcodes A — C's greet() is skipped entirely
```

### When MRO Fails: Inconsistent Linearization

```python
# Python raises TypeError if C3 cannot produce a consistent MRO:
class X: pass
class Y: pass
class A(X, Y): pass
class B(Y, X): pass

# class C(A, B): pass   # TypeError: Cannot create a consistent MRO!
# A says X before Y, B says Y before X — contradiction.

# This is why you can't always "just use multiple inheritance" — the order matters.
```

### Mixin Pattern — Acceptable Multiple Inheritance

```python
# Mixins: narrow, targeted behavior additions without their own state
class JSONSerializableMixin:
    """Adds to_json() to any class with a to_dict() method."""
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict())

class TimestampMixin:
    """Adds created_at/updated_at to any model."""
    def __init__(self, *args, **kwargs):
        import datetime
        super().__init__(*args, **kwargs)
        self.created_at = datetime.datetime.utcnow()
        self.updated_at = datetime.datetime.utcnow()

    def touch(self):
        import datetime
        self.updated_at = datetime.datetime.utcnow()

class LoggingMixin:
    """Adds self._log to any class."""
    def __init__(self, *args, **kwargs):
        import logging
        super().__init__(*args, **kwargs)
        self._log = logging.getLogger(type(self).__qualname__)

# Use: mixin first, base class last
class UserModel(TimestampMixin, LoggingMixin, JSONSerializableMixin):
    def __init__(self, name: str, email: str):
        super().__init__()   # cooperative — TimestampMixin and LoggingMixin both called
        self.name = name
        self.email = email

    def to_dict(self) -> dict:
        return {"name": self.name, "email": self.email}
```

### Prefer Composition Over Inheritance

```python
# BAD: inheritance for code reuse (not an "is-a" relationship)
class EmailSender:
    def send(self, to: str, subject: str, body: str) -> None:
        ...

class OrderService(EmailSender):   # Order IS-A EmailSender? No!
    def place_order(self, order_id: str) -> None:
        ...
        self.send("customer@example.com", "Order confirmed", f"Order {order_id} placed")

# GOOD: composition (OrderService HAS-A notifier)
from typing import Protocol

class Notifier(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...

class OrderService:
    def __init__(self, notifier: Notifier):   # injected
        self._notifier = notifier

    def place_order(self, order_id: str, customer_email: str) -> None:
        ...
        self._notifier.send(customer_email, "Order confirmed", f"Order {order_id} placed")

# Benefits:
# 1. Can test OrderService with a fake Notifier (no email sending in tests)
# 2. Can swap email for SMS without touching OrderService
# 3. Clear dependency (Notifier is injected, visible in __init__)
# 4. OrderService doesn't inherit all of EmailSender's methods (leaky API)
```

### Method Resolution Order Deep Dive

```python
# Understanding super() in cooperative inheritance:
class Logger:
    def setup(self, *args, **kwargs):
        print("Logger.setup")
        super().setup(*args, **kwargs)  # cooperative!

class Validator:
    def setup(self, *args, **kwargs):
        print("Validator.setup")
        super().setup(*args, **kwargs)

class Base:
    def setup(self, *args, **kwargs):
        print("Base.setup")

class Service(Logger, Validator, Base):
    def setup(self, name: str):
        print(f"Service.setup({name})")
        super().setup(name=name)

# MRO: Service → Logger → Validator → Base → object
# service.setup("x") prints:
# Service.setup(x)
# Logger.setup
# Validator.setup
# Base.setup

# super() always follows the MRO of the INSTANCE's class, not the caller's class.
```

---

## Interview Questions

### Q1: What is the C3 linearization algorithm and why does Python use it?

**Model answer:**
C3 linearization (C3 MRO) is Python's algorithm for computing the Method Resolution Order for a class with multiple inheritance. It produces a linear order of classes that satisfies:
1. **Monotonicity:** if class A appears before class B in a parent's MRO, A appears before B in the child's MRO.
2. **Local precedence:** the order of base classes in `class C(A, B)` is preserved.
3. **Extended precedence graph:** no class appears before its parents.

Python uses it (since Python 2.3) because naive DFS linearization can violate monotonicity in diamond inheritance, leading to `super()` calling a parent before its own parents. C3 prevents this.

```python
# How to compute MRO manually:
# C3(D(B, C)) where B(A), C(A), A(object):
# D's MRO = D + merge(MRO(B), MRO(C), [B, C])
# = D + merge([B, A, obj], [C, A, obj], [B, C])
# Take head B (appears first, not in tail of any list):
# = [D, B] + merge([A, obj], [C, A, obj], [C])
# Take head A? A appears in tail of [C, A, obj] — skip. Take C:
# = [D, B, C] + merge([A, obj], [A, obj], [])
# Take head A:
# = [D, B, C, A] + merge([obj], [obj], [])
# = [D, B, C, A, object]
print(D.__mro__)   # matches!
```

### Q2: When should you use multiple inheritance vs composition in Python?

**Model answer:**
Use multiple inheritance for:
- **Mixins:** narrow, orthogonal behavior (logging, serialization, timestamps) with no shared state between the mixin classes.
- **ABCs with mixin methods:** `collections.abc.MutableMapping` provides default implementations of dict-like methods when you implement just `__getitem__`, `__setitem__`, `__delitem__`, `__len__`, `__iter__`.
- True "is-a" relationships where the diamond represents real semantic overlap.

Use composition for:
- **Code reuse** (not "is-a"): using EmailSender's behavior in OrderService — inject it.
- **Behavior variation:** different strategies (payment methods, serialization formats) — inject the strategy.
- **Testing:** composition makes swapping real/fake implementations trivial.

**Signal to refactor from inheritance to composition:** if you're using `super()` to bypass methods, using `isinstance()` checks to handle different parent behaviors, or a subclass doesn't meaningfully extend the parent (it just borrows one method), switch to composition.

### Q3: What's the correct way to write `__init__` in a class with multiple inheritance?

**Model answer:**
All classes in the chain must use `super().__init__()` cooperatively, and `**kwargs` must be passed through to absorb arguments not consumed at each level:

```python
class Mixin1:
    def __init__(self, value1: int = 0, **kwargs):
        super().__init__(**kwargs)   # pass remaining kwargs up
        self.value1 = value1

class Mixin2:
    def __init__(self, value2: str = "", **kwargs):
        super().__init__(**kwargs)   # pass remaining kwargs up
        self.value2 = value2

class Base:
    def __init__(self, **kwargs):
        # Base should accept and IGNORE unknown kwargs (or assert empty):
        if kwargs:
            raise TypeError(f"Unexpected kwargs: {kwargs}")
        super().__init__()  # calls object.__init__()

class Combined(Mixin1, Mixin2, Base):
    def __init__(self, name: str, **kwargs):
        super().__init__(**kwargs)  # distributes kwargs to Mixin1, Mixin2, Base
        self.name = name

obj = Combined(name="test", value1=42, value2="hello")
print(obj.value1, obj.value2, obj.name)  # 42 hello test
```

**Common mistake:** not passing `**kwargs` through — Mixin1 consumes `value1` but doesn't forward `value2` to Mixin2:

```python
class Mixin1_broken:
    def __init__(self, value1: int = 0):  # no **kwargs!
        self.value1 = value1
        # Mixin2 never gets called through super — value2 not set!
```

### Q4: What are the pitfalls of using mixins with `__init__`?

**Model answer:**

1. **Keyword argument collisions:** two mixins expecting different `value` kwargs by the same name.
2. **Forgetting `super().__init__()`:** breaks the cooperative chain — downstream mixins' `__init__` never runs.
3. **Order dependence:** `class C(A, B)` vs `class C(B, A)` calls `__init__` in different order — can matter if mixins have side effects.
4. **State initialized too late:** a mixin's attribute may be needed by a base class method but set after the base class `__init__` returns.

```python
# Pitfall: mixin that forgets super().__init__():
class LoggingMixin_broken:
    def __init__(self):
        self._log = logging.getLogger(type(self).__name__)
        # Missing: super().__init__() → breaks chain

class Service(LoggingMixin_broken, TimestampMixin):
    def __init__(self):
        super().__init__()
        # LoggingMixin_broken.__init__ called, but NEVER calls TimestampMixin.__init__!
        # self.created_at doesn't exist
```

### Q5: When does Python raise `TypeError: Cannot create a consistent MRO`?

**Model answer:**
Python raises this when C3 linearization cannot find a valid ordering — most commonly when two parent classes specify conflicting orders for the same ancestors:

```python
class X: pass
class Y: pass
class A(X, Y): pass  # says X before Y
class B(Y, X): pass  # says Y before X

class C(A, B): pass  # TypeError: conflict (A: X<Y, B: Y<X)
```

This is intentional: Python refuses to silently choose one ordering that violates a parent's declared order. The fix is to redesign the inheritance hierarchy — usually by extracting a common base or switching to composition.

Less obvious cases:
```python
class M: pass
class A(M): pass

# class B(M, A): pass  # TypeError: M before A, but A depends on M (M must come AFTER A in MRO)
class B(A, M): pass  # OK: A before M — consistent with A's MRO where M comes after A
```

---

## Gotcha Follow-ups

**"Does `super()` always call the immediate parent class?"**
No — `super()` calls the NEXT class in the MRO of the actual instance's class. If `D` inherits `(B, C)` and you call `super()` in `B.method()` from an instance of `D`, `super()` returns `C` (next in D's MRO), not `A` (B's direct parent). This is cooperative inheritance — the MRO of the *instance* determines the chain, not the class where `super()` is written.

**"Can you mix regular inheritance and cooperative inheritance?"**
Yes, but carefully. If any class in the hierarchy uses `ParentClass.method(self)` instead of `super().method()`, it hardcodes the dispatch and breaks the cooperative chain — subsequent classes in the MRO won't get called. All classes in a cooperative chain must use `super()`.

---

## Under the Hood

The MRO is computed by `type.__new__()` when a class is created, using the C3 algorithm in `Objects/typeobject.c: mro_implementation()`. The result is stored in `tp_mro` (a tuple). `super()` is implemented as `Objects/typeobject.c: super_getattro()` — it searches `tp_mro` starting from the class AFTER the one where `super()` is used (or the class passed as the first argument). `type.__mro_entries__` (PEP 560) allows generic aliases like `list[int]` to participate in class hierarchies — `class MyList(list[int])` works because `list[int].__mro_entries__` returns `(list,)`.
