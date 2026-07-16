"""
C3 Linearization Demo — Diamond Inheritance and MRO

Demonstrates:
- C3 algorithm computed by hand vs Python's __mro__
- Diamond inheritance with cooperative super()
- Where super() goes without cooperative calls
- MRO-based method resolution gotchas
- Practical patterns for cooperative multiple inheritance
"""

from __future__ import annotations
from typing import Any


# =============================================================================
# 1. Computing C3 linearization manually
# =============================================================================
def c3_linearize(cls_name: str, linearizations: dict[str, list[str]]) -> list[str]:
    """
    Compute C3 linearization for a class.

    Args:
        cls_name: class to linearize (e.g., "D")
        linearizations: dict mapping class name -> its MRO (e.g., {"A": ["A", "object"]})

    Returns:
        The MRO list for cls_name
    """
    if cls_name in linearizations:
        return linearizations[cls_name]

    raise ValueError(f"No linearization for {cls_name}")


def merge(sequences: list[list[str]]) -> list[str]:
    """C3 merge algorithm. sequences is a list of MRO lists."""
    result = []
    while True:
        # Remove empty sequences:
        sequences = [s for s in sequences if s]
        if not sequences:
            return result

        # Find the first head that is not in the tail of any other list:
        for seq in sequences:
            candidate = seq[0]
            # Check: is candidate in the TAIL of any other sequence?
            in_tail = any(candidate in other[1:] for other in sequences)
            if not in_tail:
                result.append(candidate)
                # Remove candidate from all sequences:
                sequences = [
                    [x for x in s if x != candidate]
                    for s in sequences
                ]
                break
        else:
            raise TypeError(
                f"Cannot create a consistent MRO. "
                f"Remaining sequences: {sequences}"
            )


def compute_mro(cls_name: str, bases: list[str], base_mros: dict[str, list[str]]) -> list[str]:
    """
    Compute MRO for a class with given bases.

    L[C(B1, B2, ...)] = C + merge(L[B1], L[B2], ..., [B1, B2, ...])
    """
    sequences = [base_mros[b] for b in bases] + [list(bases)]
    return [cls_name] + merge(sequences)


def demo_c3():
    print("=== C3 Linearization (computed manually) ===\n")

    # Classic diamond:
    #     A
    #    / \
    #   B   C
    #    \ /
    #     D
    mros: dict[str, list[str]] = {
        "object": ["object"],
        "A": ["A", "object"],
    }
    mros["B"] = compute_mro("B", ["A", "object"], mros)
    mros["C"] = compute_mro("C", ["A", "object"], mros)
    mros["D"] = compute_mro("D", ["B", "C"], mros)

    print("Diamond hierarchy:")
    print(f"  L[A] = {mros['A']}")
    print(f"  L[B] = {mros['B']}")
    print(f"  L[C] = {mros['C']}")
    print(f"  L[D] = {mros['D']}")

    # Verify against Python:
    class A: pass
    class B(A): pass
    class C(A): pass
    class D(B, C): pass

    python_mro = [c.__name__ for c in D.__mro__]
    print(f"\n  Python's D.__mro__ = {python_mro}")
    assert mros["D"] == python_mro, "Mismatch!"
    print("  ✓ Manual computation matches Python's MRO\n")

    # More complex hierarchy:
    #    F   E   D
    #     \  |  /
    #      C  B
    #       \ |
    #        A
    mros2: dict[str, list[str]] = {
        "object": ["object"],
        "F": ["F", "object"],
        "E": ["E", "object"],
        "D": ["D", "object"],
    }
    mros2["C"] = compute_mro("C", ["D", "F"], mros2)
    mros2["B"] = compute_mro("B", ["E", "D"], mros2)
    mros2["A"] = compute_mro("A", ["B", "C"], mros2)

    print("Complex hierarchy (A(B, C), B(E, D), C(D, F)):")
    for name in ["B", "C", "A"]:
        print(f"  L[{name}] = {mros2[name]}")

    class F2: pass
    class E2: pass
    class D2: pass
    class C2(D2, F2): pass
    class B2(E2, D2): pass
    class A2(B2, C2): pass

    python_mro2 = [c.__name__.rstrip("2") for c in A2.__mro__]
    print(f"\n  Python's A2.__mro__ = {python_mro2}")


# =============================================================================
# 2. Cooperative super() in diamond inheritance
# =============================================================================
def demo_cooperative():
    print("\n=== Cooperative super() ===\n")

    class Base:
        def __init__(self, **kwargs: Any):
            print(f"  Base.__init__ called, remaining kwargs: {kwargs}")
            super().__init__(**kwargs)   # object.__init__ — must accept no kwargs

        def greet(self) -> str:
            return "Base"

    class Loggable(Base):
        def __init__(self, *, log_level: str = "INFO", **kwargs: Any):
            print(f"  Loggable.__init__ (log_level={log_level})")
            self.log_level = log_level
            super().__init__(**kwargs)   # forward remaining kwargs up the chain

        def greet(self) -> str:
            return f"[{self.log_level}] {super().greet()}"

    class Cacheable(Base):
        def __init__(self, *, cache_ttl: int = 60, **kwargs: Any):
            print(f"  Cacheable.__init__ (cache_ttl={cache_ttl})")
            self.cache_ttl = cache_ttl
            super().__init__(**kwargs)

        def greet(self) -> str:
            return f"(cached:{self.cache_ttl}s) {super().greet()}"

    class Service(Loggable, Cacheable):
        """MRO: Service → Loggable → Cacheable → Base → object"""
        def __init__(self, name: str, **kwargs: Any):
            print(f"  Service.__init__ (name={name})")
            self.name = name
            super().__init__(**kwargs)  # passes log_level, cache_ttl to chain

        def greet(self) -> str:
            return f"[{self.name}] {super().greet()}"

    print("MRO:", [c.__name__ for c in Service.__mro__])
    print()
    svc = Service(name="auth", log_level="DEBUG", cache_ttl=300)
    print(f"\nGreeting: {svc.greet()}")
    # Output: [auth] [DEBUG] (cached:300s) Base

    print("\n=== Without cooperative super() (broken chain) ===\n")

    class BrokenMixin(Base):
        def __init__(self, **kwargs: Any):
            Base.__init__(self, **kwargs)  # WRONG: bypasses MRO; Cacheable never called
            print("  BrokenMixin: called Base directly")

    class BrokenService(BrokenMixin, Cacheable):
        def __init__(self, **kwargs: Any):
            super().__init__(**kwargs)

    print("MRO:", [c.__name__ for c in BrokenService.__mro__])
    bs = BrokenService(cache_ttl=60)
    print(f"  cache_ttl initialized? {hasattr(bs, 'cache_ttl')}")  # False — Cacheable.__init__ never ran


# =============================================================================
# 3. MRO-based method resolution gotcha
# =============================================================================
def demo_mro_gotcha():
    print("\n=== MRO super() gotcha ===\n")

    class A:
        def method(self):
            return "A"

    class B(A):
        def method(self):
            return f"B→{super().method()}"

    class C(A):
        def method(self):
            return f"C→{super().method()}"

    class D(B, C):
        def method(self):
            return f"D→{super().method()}"

    d = D()
    result = d.method()
    print(f"D().method() = {result}")
    print(f"MRO: {[c.__name__ for c in D.__mro__]}")
    print()

    # B's super() is NOT A in this context — it's C!
    # B is defined to inherit from A, but when called on a D instance,
    # super() in B resolves to C (next in D's MRO after B).
    b = B()
    print(f"B().method() = {b.method()}")  # "B→A" — B called directly, MRO is B→A→object

    # This is the critical insight: super() doesn't mean "my parent class"
    # it means "the next class in type(self).__mro__ after my class"


# =============================================================================
# 4. Inconsistent MRO detection
# =============================================================================
def demo_inconsistent_mro():
    print("\n=== Inconsistent MRO detection ===\n")

    class X: pass
    class Y: pass

    class A(X, Y): pass  # requires X before Y
    class B(Y, X): pass  # requires Y before X

    try:
        class C(A, B): pass  # CONTRADICTION — can't satisfy both
    except TypeError as e:
        print(f"TypeError caught: {e}")
        print("This is C3 correctly detecting an unresolvable constraint.\n")

    # Resolution: redesign the hierarchy to remove the contradiction
    class FixedA(X, Y): pass
    class FixedB(X, Y): pass  # now both require X before Y

    class FixedC(FixedA, FixedB): pass
    print(f"FixedC MRO: {[c.__name__ for c in FixedC.__mro__]}")


# =============================================================================
# 5. Practical: Mixin pattern with abstract base
# =============================================================================
def demo_mixin_pattern():
    print("\n=== Practical Mixin Pattern ===\n")

    from abc import ABC, abstractmethod

    class Serializable(ABC):
        @abstractmethod
        def to_dict(self) -> dict: ...

        def to_json(self) -> str:
            import json
            return json.dumps(self.to_dict(), indent=2)

    class Validatable(ABC):
        @abstractmethod
        def validate(self) -> bool: ...

        def validated_dict(self) -> dict:
            if not self.validate():
                raise ValueError(f"{self!r} is invalid")
            return self.to_dict()  # relies on Serializable being in MRO too

    class User(Serializable, Validatable):
        def __init__(self, name: str, email: str):
            self.name = name
            self.email = email

        def to_dict(self) -> dict:
            return {"name": self.name, "email": self.email}

        def validate(self) -> bool:
            return "@" in self.email and len(self.name) > 0

    user = User("Alice", "alice@example.com")
    print(f"MRO: {[c.__name__ for c in User.__mro__]}")
    print(f"to_json: {user.to_json()}")
    print(f"validated_dict: {user.validated_dict()}")


# =============================================================================
# Main
# =============================================================================
if __name__ == '__main__':
    demo_c3()
    demo_cooperative()
    demo_mro_gotcha()
    demo_inconsistent_mro()
    demo_mixin_pattern()
