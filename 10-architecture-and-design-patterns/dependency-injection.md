# Dependency Injection in Plain Python

## Concept

Dependency Injection (DI) is a technique where an object receives its dependencies rather than creating them. In Python, this doesn't require a framework — the language's duck typing and default argument pattern make DI natural.

### The Core Pattern: Constructor Injection

```python
from typing import Protocol

# 1. Define an interface:
class UserRepository(Protocol):
    def get(self, user_id: int) -> dict | None: ...
    def save(self, user: dict) -> None: ...

# 2. Implementation (depends on the database):
class PostgresUserRepository:
    def __init__(self, conn):
        self.conn = conn

    def get(self, user_id: int) -> dict | None:
        row = self.conn.fetchone("SELECT * FROM users WHERE id=%s", user_id)
        return dict(row) if row else None

    def save(self, user: dict) -> None:
        self.conn.execute("INSERT INTO users ...", user)

# 3. Service (depends on the interface, not the implementation):
class UserService:
    def __init__(self, repo: UserRepository):   # injected
        self._repo = repo

    def get_or_create(self, user_id: int, defaults: dict) -> dict:
        user = self._repo.get(user_id)
        if user is None:
            user = {"id": user_id, **defaults}
            self._repo.save(user)
        return user

# 4. Wire up at the composition root (application startup):
def create_user_service(db_conn) -> UserService:
    repo = PostgresUserRepository(db_conn)
    return UserService(repo)

# 5. Test with a fake (no mock framework needed):
class InMemoryUserRepository:
    def __init__(self):
        self._store: dict[int, dict] = {}

    def get(self, user_id: int) -> dict | None:
        return self._store.get(user_id)

    def save(self, user: dict) -> None:
        self._store[user["id"]] = user

def test_get_or_create():
    repo = InMemoryUserRepository()
    service = UserService(repo)
    user = service.get_or_create(1, {"name": "Alice"})
    assert user["name"] == "Alice"
    # Same call returns existing user:
    user2 = service.get_or_create(1, {"name": "Bob"})
    assert user2["name"] == "Alice"   # not overwritten
```

### Default Arguments for Optional Dependencies

```python
import logging
from typing import Protocol

class Logger(Protocol):
    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...

class OrderProcessor:
    def __init__(
        self,
        payment_gateway: PaymentGateway,
        notification_service: NotificationService,
        logger: Logger | None = None,      # optional dependency
    ):
        self._gateway = payment_gateway
        self._notifier = notification_service
        self._log = logger or logging.getLogger(__name__)  # sensible default

    def process(self, order_id: str) -> bool:
        self._log.info(f"Processing order {order_id}")
        # ...
```

### Factory Functions as the Composition Root

```python
# composition_root.py — the ONLY place that knows about concrete types
import os
from myapp.services import UserService, OrderService
from myapp.repos import PostgresUserRepository, PostgresOrderRepository
from myapp.gateways import StripePaymentGateway
from myapp.db import create_connection

def create_services() -> dict:
    """Build and wire the entire dependency graph."""
    conn = create_connection(os.environ['DATABASE_URL'])
    user_repo = PostgresUserRepository(conn)
    order_repo = PostgresOrderRepository(conn)
    payment = StripePaymentGateway(api_key=os.environ['STRIPE_KEY'])

    return {
        'users': UserService(user_repo),
        'orders': OrderService(order_repo, payment, UserService(user_repo)),
    }

# Application entry point:
services = create_services()
```

### `functools.partial` for Dependency Currying

```python
import functools
from typing import Callable

# Instead of a class, use partial application:
def process_payment(
    gateway: PaymentGateway,
    notification_fn: Callable[[str], None],
    amount: float,
    currency: str,
) -> bool:
    result = gateway.charge(amount, currency)
    if result.success:
        notification_fn(f"Charged {amount} {currency}")
    return result.success

# Bind dependencies at composition time:
send_sms = functools.partial(sms_client.send, from_number="+1234")

charge = functools.partial(
    process_payment,
    gateway=stripe_gateway,
    notification_fn=send_sms,
)

# Usage — only business arguments needed:
charge(amount=99.99, currency="USD")
```

### Lightweight DI Container

```python
from typing import Any, Callable, TypeVar

T = TypeVar('T')

class Container:
    """Simple DI container with lazy singletons."""

    def __init__(self):
        self._factories: dict[type, Callable] = {}
        self._singletons: dict[type, Any] = {}

    def register(self, interface: type, factory: Callable, singleton: bool = True):
        self._factories[interface] = (factory, singleton)

    def resolve(self, interface: type):
        if interface in self._singletons:
            return self._singletons[interface]

        factory, is_singleton = self._factories[interface]
        instance = factory(self)

        if is_singleton:
            self._singletons[interface] = instance

        return instance

container = Container()
container.register(DatabaseConnection, lambda c: PostgresConnection(os.environ['DB_URL']))
container.register(UserRepository, lambda c: PostgresUserRepository(c.resolve(DatabaseConnection)))
container.register(UserService, lambda c: UserService(c.resolve(UserRepository)))

# Usage:
user_service = container.resolve(UserService)
```

---

## Interview Questions

### Q1: What is dependency injection and why is it valuable even without a DI framework?

**Model answer:**
DI is the practice of providing an object's dependencies from outside rather than having the object create them. Instead of `self.repo = PostgresUserRepository()`, the service receives `repo` as a constructor parameter.

Value:
1. **Testability:** swap real dependencies with fakes — no monkeypatching, no `@patch`, no mock magic.
2. **Single responsibility:** each class has one job; wiring up the graph is somebody else's problem (the composition root).
3. **Loose coupling:** `UserService` depends on `UserRepository` (an interface), not `PostgresUserRepository` (an implementation). Swap the DB backend without touching `UserService`.
4. **Explicit dependencies:** `UserService.__init__(self, repo)` makes dependencies visible in the signature — no hidden `import` or global state.

Python doesn't need a DI framework because:
- Duck typing means any object with the right interface works.
- Constructor injection is natural Python.
- Simple factory functions compose the graph cleanly.

### Q2: What's the composition root pattern and why should only one place in the application know about concrete types?

**Model answer:**
The composition root is the single place in the application (usually the startup/main module) where all concrete classes are instantiated and wired together. All other modules depend only on abstractions (Protocols, ABCs, type annotations).

```python
# BAD: UserService imports the concrete PostgresRepo (tight coupling)
# userservice.py
from repos.postgres import PostgresUserRepository  # coupling!
class UserService:
    def __init__(self):
        self.repo = PostgresUserRepository()

# GOOD: only main.py / composition_root.py knows about concrete types
# userservice.py
class UserService:
    def __init__(self, repo: UserRepository): ...   # only the interface

# main.py
from repos.postgres import PostgresUserRepository   # concrete — only here
from services.user import UserService
service = UserService(PostgresUserRepository(conn))
```

Benefits:
- Tests never touch the database — inject a fake repo.
- To add a Redis cache layer: modify only the composition root.
- All modules are independently testable.

### Q3: How do you handle async dependencies in DI?

**Model answer:**
Async resources (database connections, HTTP clients) can't be created in `__init__` — you can't `await` there. Use factory coroutines or lazy initialization:

```python
class AsyncUserService:
    def __init__(self, repo: AsyncUserRepository):
        self._repo = repo   # repo is already initialized

    async def get_user(self, uid: int) -> dict | None:
        return await self._repo.get(uid)

class AsyncPostgresRepo:
    def __init__(self, pool):
        self._pool = pool   # already created pool

    async def get(self, uid: int):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)

# Async composition root (run at app startup):
async def create_async_services():
    import asyncpg
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'])
    repo = AsyncPostgresRepo(pool)
    return AsyncUserService(repo)

# FastAPI lifespan:
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    services = await create_async_services()
    app.state.services = services
    yield
    await services._repo._pool.close()   # cleanup
```

### Q4: When does DI become over-engineering in Python?

**Model answer:**
DI becomes over-engineering when:

1. **The application is a script or one-off tool:** no testing requirements, no swappable backends.
2. **There's only one implementation:** if `UserRepository` will always be `PostgresUserRepository` and never be faked in tests (e.g., it's too coupled to the DB schema), the abstraction adds no value.
3. **Using `pytest.monkeypatch` is simpler:** for testing a single module's behavior, monkeypatching is pragmatic and doesn't require restructuring the entire codebase.
4. **The dependency graph is trivial:** a 200-line script doesn't need a composition root.

The signal to start using DI: you're writing tests that need to mock out external systems (DB, HTTP, file system) and you're using `unittest.mock.patch` extensively. DI makes those mocks disappear because you're injecting fakes directly.

### Q5: How do you inject configuration vs services?

**Model answer:**
Configuration (scalar values, URLs, flags) and services (objects with behavior) should be injected differently:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    """All configuration in one place — from env or config file."""
    db_url: str
    stripe_api_key: str
    debug: bool = False
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> 'AppConfig':
        return cls(
            db_url=os.environ['DATABASE_URL'],
            stripe_api_key=os.environ['STRIPE_KEY'],
            debug=os.environ.get('DEBUG', 'false').lower() == 'true',
        )

# Services receive the config they need:
class PaymentService:
    def __init__(self, config: AppConfig, http_client: HttpClient):
        self._api_key = config.stripe_api_key
        self._retries = config.max_retries
        self._client = http_client

# Or pass only what's needed (principle of least knowledge):
class PaymentService:
    def __init__(
        self,
        api_key: str,        # scalar — what this service needs
        http_client: HttpClient,  # service
        max_retries: int = 3,
    ):
        ...
```

Passing the whole `AppConfig` is convenient but makes the class's actual needs opaque. Passing specific values makes the class independently reusable and testable without constructing an `AppConfig`.

---

## Gotcha Follow-ups

**"What's the difference between DI and a service locator?"**
A **service locator** is a global registry: `services.get('user_service')`. It hides dependencies — from the outside, you can't tell what a class needs without reading its implementation. DI makes dependencies explicit in the constructor. Service locators are generally considered an antipattern in modern Python architecture.

**"Should domain objects (like `User`) receive injected dependencies?"**
No — domain objects should be pure data/logic with no infrastructure dependencies. Injecting a repository into a `User` model couples domain logic to persistence. Keep domain objects as simple as possible (dataclasses, named tuples). Inject infrastructure into services/use cases that orchestrate domain objects.

---

## Under the Hood

Python's dynamic dispatch means you don't need interfaces at runtime — duck typing ensures any object with the right methods works. The Protocol type annotation makes the requirement explicit at the static analysis level. At runtime, passing a fake repository where a Postgres repository is expected works without any metaclass magic, ABC registration, or framework support.
