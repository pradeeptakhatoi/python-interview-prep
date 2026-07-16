# Versioning and Deprecation Strategies

## Concept

Versioning communicates compatibility expectations. Deprecation is the process of retiring old API while keeping existing users working. Python's standard library provides first-class tooling for both.

### Semantic Versioning and `importlib.metadata`

```python
# Package version at runtime:
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("mypackage")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

# In pyproject.toml:
# [project]
# version = "2.1.3"
```

### Deprecation Warnings: The Standard Pattern

```python
import warnings
import functools
from typing import TypeVar, Callable, Any

F = TypeVar('F', bound=Callable[..., Any])

def deprecated(
    reason: str,
    version: str,
    replacement: str | None = None,
    removal_version: str | None = None,
) -> Callable[[F], F]:
    """Decorator that emits DeprecationWarning on first call."""

    def decorator(func: F) -> F:
        msg = f"{func.__qualname__} is deprecated since {version}: {reason}."
        if replacement:
            msg += f" Use {replacement} instead."
        if removal_version:
            msg += f" Will be removed in {removal_version}."

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator

@deprecated(
    reason="Use the async version for better performance",
    version="2.0",
    replacement="async_process()",
    removal_version="3.0",
)
def process(data: list) -> dict:
    ...

# Warning categories:
# DeprecationWarning: hidden by default in production, shown in tests/dev
# PendingDeprecationWarning: even more hidden — for things not yet deprecated
# FutureWarning: shown in production — for end-user behavior changes
# UserWarning: always shown — for runtime issues
```

### Warning Filters

```python
import warnings

# Default: DeprecationWarning is IGNORED in non-__main__ code
warnings.filterwarnings('always', category=DeprecationWarning)

# pytest.ini / pyproject.toml:
# [tool.pytest.ini_options]
# filterwarnings = ["error::DeprecationWarning"]  # turn into test failures

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    result = deprecated_function()
```

### Versioned API Patterns

```python
def create_user(
    name: str,
    email: str,
    role: str | None = None,           # deprecated parameter
    permissions: list[str] | None = None,  # new parameter
) -> 'User':
    if role is not None:
        warnings.warn(
            "The 'role' parameter is deprecated since v2.0. "
            "Use 'permissions' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        permissions = ROLE_PERMISSIONS.get(role, [])
    return User(name=name, email=email, permissions=permissions or [])

# Keep old name as deprecated alias:
def get_user_by_id(user_id: int) -> 'User | None':
    ...

@deprecated("Use get_user_by_id()", version="2.0", replacement="get_user_by_id")
def fetch_user(user_id: int) -> 'User | None':
    return get_user_by_id(user_id)

# Feature flag for future behavior changes:
import os

def parse_config(text: str, strict: bool | None = None) -> dict:
    if strict is None:
        if os.environ.get('MYAPP_NEXT_BEHAVIOR'):
            strict = True
        else:
            warnings.warn(
                "Default for 'strict' will change to True in v3.0. "
                "Pass strict=True to silence this warning.",
                FutureWarning,
                stacklevel=2,
            )
            strict = False
    ...
```

### Version Negotiation

```python
import re

def negotiate_api_version(requested: str, supported: list[str]) -> str:
    """Return the best supported version <= requested."""
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in re.match(r'(\d+)\.(\d+)', v).groups())

    req = parse(requested)
    candidates = sorted(
        [(parse(v), v) for v in supported if parse(v) <= req],
        reverse=True,
    )
    if not candidates:
        raise ValueError(
            f"No supported version <= {requested}. Supported: {supported}"
        )
    return candidates[0][1]
```

### `typing.deprecated` (Python 3.13+)

```python
from typing import deprecated

@deprecated("Use new_function() instead")
def old_function() -> None:
    ...

# mypy/pyright emit warnings at call sites — no runtime behavior change needed.

# Pre-3.13: deprecate class via __init__:
class OldProcessor:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "OldProcessor is deprecated since v2.0. Use NewProcessor instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        warnings.warn(
            f"Subclassing OldProcessor via {cls.__name__} is deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
```

---

## Interview Questions

### Q1: What's the difference between `DeprecationWarning`, `FutureWarning`, and `PendingDeprecationWarning`?

**Model answer:**

| Warning | Default visibility | Used for |
|---------|-------------------|----------|
| `DeprecationWarning` | Hidden in production, shown in tests | API deprecated for library users |
| `PendingDeprecationWarning` | Even more hidden (`-Wd` flag only) | Might be deprecated in the future |
| `FutureWarning` | Always shown | End-user behavior changes |
| `UserWarning` | Always shown | General runtime issues |

```python
# DeprecationWarning: library-to-library-user deprecation
warnings.warn("Use new_fn()", DeprecationWarning, stacklevel=2)
# Hidden in normal use, but pytest turns these into errors

# FutureWarning: end-user behavior will change
# (pandas-style: "Sort behavior changes in v3.0")
warnings.warn("Sort behavior changes in v3.0", FutureWarning, stacklevel=2)
```

`stacklevel=2` is critical: it makes the warning point to the CALLER's line, not the `warn()` call inside the library. This tells users where in their own code to make changes.

### Q2: How do you test that deprecation warnings are properly emitted?

**Model answer:**

```python
import pytest
import warnings

def test_deprecated_function_warns():
    with pytest.warns(DeprecationWarning, match=r"old_function.*deprecated"):
        old_function()

def test_warning_details():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        old_function()

    assert len(caught) == 1
    w = caught[0]
    assert issubclass(w.category, DeprecationWarning)
    assert "old_function" in str(w.message)

# In pytest.ini — turn DeprecationWarnings into test failures:
# [tool.pytest.ini_options]
# filterwarnings = ["error::DeprecationWarning"]

def test_deprecated_and_new_behave_identically(test_data):
    with pytest.warns(DeprecationWarning):
        old_result = old_function(test_data)
    new_result = new_function(test_data)
    assert old_result == new_result
```

### Q3: How do you handle backwards-incompatible changes while keeping semver guarantees?

**Model answer:**
Semver: MAJOR.MINOR.PATCH — MAJOR bumps for breaking changes.

The deprecation lifecycle:

1. **v1.x.x:** Feature works as-is.
2. **v1.y.0 (minor):** New API introduced, old API emits `DeprecationWarning`. Both work.
3. **v1.z.0 (optional):** Louder `FutureWarning` or docs announcement.
4. **v2.0.0 (major):** Old API removed.

Minimum deprecation period: one minor release. Stable libraries: 2+ minor releases or 6+ months.

Document in `CHANGELOG.md`:
```markdown
## v2.0 Breaking Changes
- `old_function()` removed. Use `new_function()` (deprecated since v1.5.0).
- `role` parameter removed from `create_user()`. Use `permissions=[]`.
```

### Q4: How do you communicate API version compatibility in pyproject.toml and type stubs?

**Model answer:**

```toml
[project]
name = "mypackage"
version = "2.0.0"
requires-python = ">=3.11"

[project.optional-dependencies]
# Optional compatibility shim for users still on v1 patterns:
compat = ["mypackage-compat>=1.0,<2.0"]
```

Type stubs for deprecated symbols:

```python
# mypackage/py.typed  # marker file — package is typed

# In type stubs or the module itself (Python 3.13+):
from typing import deprecated

@deprecated("Use new_function() instead. Removed in 3.0.")
def old_function() -> None: ...
# mypy/pyright emit errors at every call site across the codebase

# __init__.pyi — control what's re-exported publicly:
from mypackage._deprecated import old_function as old_function
```

### Q5: How would you deprecate an entire class in a way that's both runtime-safe and statically analyzable?

**Model answer:**

```python
import warnings
from typing import deprecated

# Python 3.13+:
@deprecated("Use NewProcessor instead. Removed in v3.0.")
class OldProcessor:
    def process(self, data: list) -> dict: ...

# Pre-3.13 — combine __init__ + __init_subclass__:
class OldProcessor:
    """
    Deprecated since v2.0. Use NewProcessor instead.

    .. deprecated:: 2.0
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "OldProcessor is deprecated since v2.0. Use NewProcessor.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        warnings.warn(
            f"{cls.__name__} subclasses deprecated OldProcessor. "
            "Subclass NewProcessor instead.",
            DeprecationWarning,
            stacklevel=2,
        )

# Deprecating a class attribute via property:
class Config:
    @property
    def old_setting(self) -> str:
        warnings.warn(
            "Config.old_setting deprecated. Use Config.new_setting.",
            DeprecationWarning, stacklevel=2,
        )
        return self.new_setting
```

---

## Gotcha Follow-ups

**"Why is `stacklevel` important in `warnings.warn()`?"**
`stacklevel=1` (default) makes the warning point to the `warn()` call inside the library — useless to the user. `stacklevel=2` points to the direct caller of the deprecated function — where users must change their code. If the deprecation is inside a decorator wrapper, you may need `stacklevel=3` or more to reach user code.

**"How do you deprecate a parameter rather than an entire function?"**
Python has no per-parameter deprecation syntax. The pattern: accept the old parameter, emit `DeprecationWarning` if it's not `None`/not-default, then convert old value to new. Python 3.13's `@typing.deprecated` only applies to callables and classes, not parameters — for parameters, the runtime warning approach is the only option.

---

## Under the Hood

`warnings.warn()` (`Lib/warnings.py`) checks `warnings.filters` — a list of `(action, message_regex, category, module_regex, lineno)` tuples — to decide whether to emit the warning. The registry (`__warningregistry__` dict on the calling module's `__dict__`) tracks which (message, category, lineno) combinations have been shown, implementing "once per location" default behavior. `warnings.filterwarnings('always')` bypasses this registry. The C implementation is in `Python/_warnings.c`, called by `PyErr_WarnEx()` and `PyErr_WarnExplicit()`.
