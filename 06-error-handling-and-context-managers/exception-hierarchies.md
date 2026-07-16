# Custom Exception Hierarchies

## Concept

Python's built-in exception hierarchy is a carefully designed tree. Effective Staff-level Python involves designing exception hierarchies that make error handling at module boundaries precise, discoverable, and future-proof.

### Built-in Exception Hierarchy (Relevant Subset)

```
BaseException
├── SystemExit            ← sys.exit(), never catch in application code
├── KeyboardInterrupt     ← Ctrl+C, never catch with bare except
├── GeneratorExit         ← thrown into generators on close()
└── Exception             ← base for all "normal" errors
    ├── StopIteration     ← signals iterator exhaustion
    ├── ArithmeticError
    │   ├── ZeroDivisionError
    │   └── OverflowError
    ├── LookupError
    │   ├── IndexError
    │   └── KeyError
    ├── OSError (alias: IOError, EnvironmentError)
    │   ├── FileNotFoundError
    │   ├── PermissionError
    │   ├── TimeoutError
    │   └── ConnectionError
    │       ├── ConnectionRefusedError
    │       └── ConnectionResetError
    ├── ValueError
    ├── TypeError
    ├── RuntimeError
    │   └── RecursionError
    └── AttributeError
```

### Designing a Library Exception Hierarchy

```python
# errors.py — single module for all exceptions

class AppError(Exception):
    """Root of all application-specific errors. Catch this to handle any app error."""
    pass

# --- Domain layer ---
class ValidationError(AppError):
    """Input data failed business rule validation."""
    def __init__(self, field: str, message: str, value=None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"{field}: {message} (got {value!r})")

class NotFoundError(AppError):
    """Requested resource does not exist."""
    def __init__(self, resource: str, identifier):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier!r}")

class ConflictError(AppError):
    """Operation conflicts with existing state."""
    pass

# --- Infrastructure layer ---
class InfrastructureError(AppError):
    """Base for all infrastructure errors (database, network, etc.)."""
    pass

class DatabaseError(InfrastructureError):
    """Database operation failed."""
    def __init__(self, operation: str, cause: Exception | None = None):
        self.operation = operation
        super().__init__(f"Database error during {operation}")
        if cause:
            self.__cause__ = cause

class CacheError(InfrastructureError):
    pass

class ExternalServiceError(InfrastructureError):
    """Third-party API or service failed."""
    def __init__(self, service: str, status_code: int | None = None):
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service} request failed" + (f" (HTTP {status_code})" if status_code else ""))
```

### Hierarchical Catching

```python
from errors import AppError, DatabaseError, ValidationError

def process_user(user_id: int) -> dict:
    try:
        return db.fetch_user(user_id)
    except DatabaseError as e:
        logger.error("DB error: %s", e)
        raise  # re-raise to let caller decide
    except ValidationError as e:
        # Validation errors are not DB errors — handle separately
        return {"error": str(e), "field": e.field}

# Callers can catch at different granularity:
try:
    process_user(123)
except DatabaseError:
    # handle DB specifically
    ...
except AppError:
    # handle any app error generically
    ...
```

### `__init_subclass__` for Automatic Registration

```python
class AppError(Exception):
    _registry: dict[str, type] = {}

    def __init_subclass__(cls, code: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if code:
            cls.code = code
            AppError._registry[code] = cls

class NotFoundError(AppError, code='NOT_FOUND'):
    pass

class ValidationError(AppError, code='VALIDATION'):
    pass

print(AppError._registry)
# {'NOT_FOUND': NotFoundError, 'VALIDATION': ValidationError}

def error_from_code(code: str) -> type[AppError]:
    return AppError._registry[code]
```

### Exception Attributes for Structured Logging

```python
import uuid
from datetime import datetime, UTC

class AppError(Exception):
    def __init__(self, message: str, **context):
        super().__init__(message)
        self.error_id = str(uuid.uuid4())
        self.timestamp = datetime.now(UTC)
        self.context = context

    def to_dict(self) -> dict:
        return {
            "error_id": self.error_id,
            "type": type(self).__name__,
            "message": str(self),
            "timestamp": self.timestamp.isoformat(),
            **self.context,
        }

class RateLimitError(AppError):
    def __init__(self, user_id: int, limit: int, window_seconds: int):
        super().__init__(
            f"Rate limit exceeded",
            user_id=user_id,
            limit=limit,
            window_seconds=window_seconds,
        )
        self.retry_after = window_seconds

e = RateLimitError(user_id=42, limit=100, window_seconds=60)
print(e.to_dict())
```

---

## Interview Questions

### Q1: When should you catch `Exception` vs `BaseException` vs specific exceptions?

**Model answer:**
- **Specific exceptions** (e.g., `ValueError`, `KeyError`): always prefer when you know what you're handling and have a meaningful response.
- **`Exception`**: acceptable at a top-level handler (e.g., a web framework's request handler) to log and return a 500. Never swallow silently.
- **`BaseException`**: only in cleanup code that must run even on `KeyboardInterrupt` or `SystemExit`. Example: releasing a file lock regardless of how the program exits. Almost never the right choice in application code.

```python
# Framework-level catch-all:
def handle_request(request):
    try:
        return process(request)
    except AppError as e:
        return error_response(e)
    except Exception as e:
        logger.exception("Unhandled error")   # logs full traceback
        return error_response_500()
    # DO NOT catch BaseException here — let KeyboardInterrupt propagate

# Cleanup that must survive Ctrl+C:
try:
    acquire_lock()
    do_work()
finally:
    release_lock()   # always runs, even on KeyboardInterrupt
```

### Q2: Why should custom exceptions inherit from the right built-in base?

**Model answer:**
Inheriting from the appropriate built-in lets callers use existing `except` clauses without modification:

```python
class UserNotFoundError(LookupError):   # IS-A LookupError
    pass

class InvalidConfigError(ValueError):   # IS-A ValueError
    pass

# Library users can catch generically:
try:
    get_user(id)
except LookupError:   # catches UserNotFoundError too — no update needed
    ...

# Or catch your specific type:
try:
    get_user(id)
except UserNotFoundError:
    ...
```

For domain errors with no stdlib equivalent, inherit from `Exception` (or your app's `AppError`). Never inherit from `BaseException` directly for custom errors.

### Q3: What's wrong with raising a bare `Exception("message")`?

**Model answer:**
Bare `Exception` forces callers to parse the message string to understand the error, violating the separation between machine-readable data and human-readable text:

```python
# Bad: caller must parse the string
raise Exception(f"User {user_id} not found")

# Caller:
try:
    ...
except Exception as e:
    if "not found" in str(e):   # fragile string parsing
        ...

# Good: structured exception with attributes
class NotFoundError(AppError):
    def __init__(self, resource: str, identifier):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier!r}")

# Caller:
try:
    ...
except NotFoundError as e:
    logger.info("Resource %s not found: %s", e.resource, e.identifier)
```

Attributes enable: structured logging, HTTP status mapping, retry logic, localization.

### Q4: How do you create an error hierarchy that's backward-compatible when adding new exception types?

**Model answer:**
Design the hierarchy so new specific exceptions are subtypes of existing broad ones. Callers catching the broad type continue to work:

```python
# Version 1.0:
class NetworkError(AppError): pass

# Caller: except NetworkError — catches everything

# Version 2.0: add specifics UNDER NetworkError
class ConnectionError(NetworkError): pass    # subtype — old code still works
class TimeoutError(NetworkError): pass       # subtype — old code still works
class DNSError(NetworkError): pass           # subtype — old code still works

# Old caller code:
except NetworkError:   # still works — catches Connection, Timeout, DNS
    ...

# New caller code (more specific):
except TimeoutError:   # catches only timeouts
    retry()
except NetworkError:   # catches remaining network errors
    fail()
```

Never remove an exception type or move it to a different branch — that breaks existing `except` clauses. Deprecate old types by aliasing them, keeping them in the hierarchy.

### Q5: How do you propagate context from an infrastructure exception to a domain exception?

**Model answer:**
Use explicit exception chaining (`raise DomainError(...) from original_exc`) to preserve the full causal chain for debugging while surfacing the right abstraction level:

```python
class UserRepository:
    def get(self, user_id: int) -> User:
        try:
            row = self.db.query("SELECT * FROM users WHERE id = ?", user_id)
            if not row:
                raise NotFoundError("User", user_id)
            return User.from_row(row)
        except sqlite3.OperationalError as e:
            raise DatabaseError("user lookup") from e   # explicit chain

# Result:
# NotFoundError: User not found: 42
# — OR —
# DatabaseError: Database error during user lookup
#   Caused by: sqlite3.OperationalError: no such table: users

# In logging:
try:
    user = repo.get(42)
except AppError as e:
    logger.exception("Error: %s", e)   # logs full chain including __cause__
```

---

## Gotcha Follow-ups

**"What is `except Exception as e: pass` considered harmful?"**
Silently swallowing exceptions hides bugs entirely. Even `pass` should be `logger.exception(...)`. Use `contextlib.suppress(SpecificError)` for intentional ignoring of specific known errors — it's explicit about what you're suppressing.

**"What does `raise` (bare) vs `raise e` do?"**
Bare `raise` re-raises the current exception preserving the original traceback. `raise e` re-raises but resets the traceback to the current line — losing where the original error occurred. Always use bare `raise` in `except` blocks to re-raise.

---

## Under the Hood

`BaseException` is `Objects/exceptions.c` → `PyBaseExceptionObject`. All exceptions carry `args` (tuple of constructor args), `__traceback__` (a `PyTracebackObject` linked list of frames), `__cause__` (explicit chain via `raise ... from`), `__context__` (implicit chain — the exception active when this one was raised), and `__suppress_context__` (True when `raise ... from` is used, suppressing the implicit chain display).
