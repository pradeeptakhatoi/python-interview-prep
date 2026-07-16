# pytest Internals: Fixtures and Parametrize

## Concept

pytest's power comes from its fixture system and plugin architecture. Understanding how fixtures are resolved, scoped, and composed enables clean, maintainable test suites at scale.

### Fixture Lifecycle and Scoping

```python
import pytest

# Scope controls how often a fixture is created/torn down:
# function (default), class, module, package, session

@pytest.fixture(scope="session")
def database_url():
    """Created once per test session."""
    return "postgresql://localhost/test_db"

@pytest.fixture(scope="module")
def db_connection(database_url):
    """Created once per module, depends on database_url."""
    conn = create_connection(database_url)
    yield conn   # setup above yield, teardown below
    conn.close()

@pytest.fixture(scope="function")
def db_transaction(db_connection):
    """Created per test — wraps each test in a transaction."""
    db_connection.begin()
    yield db_connection
    db_connection.rollback()   # test isolation: rollback after each test

def test_create_user(db_transaction):
    db_transaction.execute("INSERT INTO users ...")
    # Rolled back after test — next test sees clean state
```

### How pytest Resolves Fixtures

pytest builds a **fixture dependency graph** at collection time:

1. Collect all fixtures (from conftest.py files, plugins, test modules).
2. For each test, resolve requested fixtures and their transitive dependencies.
3. Sort by scope (broader scopes first) and topological order.
4. Instantiate in order, yield at `yield` (or return), finalize in reverse order.

```python
# conftest.py — fixtures available to all tests in the directory
import pytest

@pytest.fixture
def user_data():
    return {"name": "Alice", "email": "alice@example.com"}

@pytest.fixture
def created_user(user_data, db_transaction):
    user = db_transaction.create_user(**user_data)
    return user

# Test:
def test_user_email(created_user):
    assert created_user.email == "alice@example.com"
# pytest injects: db_transaction → db_connection → db_transaction, user_data, created_user → test
```

### `@pytest.mark.parametrize`

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_upper(input, expected):
    assert input.upper() == expected
# Runs 4 separate tests; each failure reported individually

# Parametrize with ids:
@pytest.mark.parametrize("n,factorial", [
    (0, 1),
    (1, 1),
    (5, 120),
    (10, 3628800),
], ids=["zero", "one", "five", "ten"])
def test_factorial(n, factorial):
    assert compute_factorial(n) == factorial

# Stacked parametrize — cartesian product:
@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [10, 20])
def test_add(x, y):
    assert x + y > 0
# Generates: (1,10), (1,20), (2,10), (2,20) — 4 tests
```

### Fixture Factories and Indirect Parametrize

```python
@pytest.fixture
def make_user(db_transaction):
    """Factory fixture — returns a factory function."""
    created = []

    def _make_user(name: str, role: str = "user") -> User:
        user = db_transaction.create_user(name=name, role=role)
        created.append(user)
        return user

    yield _make_user

    # Teardown — all created users cleaned up
    for user in created:
        db_transaction.delete_user(user.id)

def test_admin_permissions(make_user):
    admin = make_user("Admin", role="admin")
    user = make_user("User", role="user")
    assert can_admin_delete(admin, user)

# Indirect parametrize — fixture receives the parameter:
@pytest.fixture
def server(request):
    host = request.param
    s = start_server(host)
    yield s
    s.stop()

@pytest.mark.parametrize("server", ["localhost", "0.0.0.0"], indirect=True)
def test_server_accepts_connections(server):
    assert server.ping()
```

### pytest Plugins and Hooks

pytest's plugin system uses `pluggy`. Plugins hook into the test lifecycle:

```python
# conftest.py — acts as a local plugin
import pytest

def pytest_collection_modifyitems(config, items):
    """Called after test collection — reorder or skip tests."""
    # Move slow tests to end:
    slow = [i for i in items if i.get_closest_marker('slow')]
    rest = [i for i in items if not i.get_closest_marker('slow')]
    items[:] = rest + slow

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow")

@pytest.fixture(autouse=True)
def reset_global_state():
    """Automatically applied to every test — no need to request explicitly."""
    yield
    global_registry.clear()

# Custom assertion rewriting:
# pytest rewrites `assert` statements to show detailed failure messages
# Plugins can register assertion rewrite via pytest_configure
```

### Testing Async Code

```python
import pytest
import asyncio

# pytest-asyncio:
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_coroutine()
    assert result == expected

# Or with anyio (backend-agnostic):
@pytest.mark.anyio
async def test_with_anyio():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://example.com")
        assert response.status_code == 200

# Async fixtures:
@pytest.fixture
async def async_client():
    async with httpx.AsyncClient(app=myapp, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_endpoint(async_client):
    response = await async_client.get("/api/users")
    assert response.status_code == 200
```

---

## Interview Questions

### Q1: Explain fixture scoping. What's wrong with making everything `scope="session"`?

**Model answer:**
Scope controls how many times a fixture is instantiated:

| Scope | Created | Destroyed |
|-------|---------|-----------|
| `function` (default) | Before each test | After each test |
| `class` | Before first test in class | After last test in class |
| `module` | Before first test in module | After last test in module |
| `package` | Before first test in package | After last test in package |
| `session` | Once at session start | At session end |

**Problem with over-broad scoping:** fixtures at a broader scope can only depend on fixtures of the same or broader scope. A `session`-scope fixture can't use a `function`-scope fixture.

**Test isolation problem:** if state leaks between tests via a `session`-scope fixture, tests become order-dependent. One test's side effects corrupt the next test's environment:

```python
@pytest.fixture(scope="session")
def user_list():
    return []   # shared mutable list across ALL tests!

def test_add_user(user_list):
    user_list.append("alice")
    assert len(user_list) == 1

def test_empty_list(user_list):
    assert len(user_list) == 0   # FAILS — sees alice from previous test!
```

Rule: use the NARROWEST scope that gives acceptable performance. Session scope for truly immutable resources (DB connections, config). Function scope for anything with state.

### Q2: How does `@pytest.mark.parametrize` work with fixtures?

**Model answer:**
Parameters from `@pytest.mark.parametrize` and fixtures are resolved separately:
- Fixture arguments are resolved via the fixture system.
- Parametrize values are injected directly as parameter values.

When a parametrize argument name matches a fixture name, the parametrize value overrides the fixture:

```python
@pytest.fixture
def user():
    return User(name="default", role="user")

@pytest.mark.parametrize("user", [
    User(name="admin", role="admin"),
    User(name="moderator", role="moderator"),
])
def test_permissions(user):
    # 'user' parameter comes from parametrize, NOT from the fixture
    assert user.role in ["admin", "moderator"]
```

`indirect=True` makes parametrize pass values TO the fixture, not bypass it:
```python
@pytest.fixture
def user(request):
    role = request.param   # receives the parametrize value
    return User(name="test", role=role)

@pytest.mark.parametrize("user", ["admin", "user"], indirect=True)
def test_user_creation(user):
    assert user.name == "test"
    # user.role is "admin" then "user" in separate test runs
```

### Q3: How does pytest's assertion rewriting work?

**Model answer:**
pytest intercepts import of test modules and rewrites `assert` statements at the AST level. A rewritten `assert a == b` captures the actual values and produces a detailed failure message:

```python
# Without pytest rewriting:
AssertionError

# With pytest rewriting:
assert result == expected
E       AssertionError: assert [1, 2, 3] == [1, 2, 4]
E         At index 2 diff: 3 != 4
E         Full diff:
E         - [1, 2, 3]
E         ?         ^
E         + [1, 2, 4]
E         ?         ^
```

Implementation: pytest registers a custom import hook in `conftest.py` collection. When a test file is imported, pytest's `AssertionRewriter` (an AST transformer) rewrites each `assert` statement to store intermediate values in temporary variables, then formats them on failure. The rewritten `.pyc` is cached in `__pycache__`.

This is why `pytest.ini` has `addopts = --assert=rewrite` (default) — and why you must tell pytest about assertion-rewriting in non-test modules used in tests via `pytest.register_assert_rewrite('mymodule')`.

### Q4: What is `conftest.py` and what can it do that regular fixtures cannot?

**Model answer:**
`conftest.py` is a special pytest plugin file — it's automatically loaded by pytest for any tests in the same directory or subdirectories. You don't import it; pytest discovers and loads it.

Unique capabilities:
1. **Directory-scoped fixtures:** fixtures in `conftest.py` are available to all tests under that directory, without explicit imports.
2. **Hook implementations:** `conftest.py` can implement pytest hooks (`pytest_collection_modifyitems`, `pytest_configure`, `pytest_runtest_setup`, etc.) that apply to tests in scope.
3. **Plugin behavior:** each `conftest.py` is a mini-plugin loaded by pluggy.

```
tests/
├── conftest.py          ← fixtures available to ALL tests/
├── unit/
│   ├── conftest.py      ← fixtures available to tests/unit/ only
│   └── test_core.py
└── integration/
    ├── conftest.py      ← fixtures available to tests/integration/ only
    └── test_api.py
```

Regular test files can't act as plugins or define directory-scoped fixtures accessible to other files.

### Q5: How do you test code that uses `threading` or `multiprocessing`?

**Model answer:**

```python
import pytest
import threading
import time

# Testing thread safety:
def test_counter_thread_safety():
    counter = ThreadSafeCounter()
    errors = []

    def increment_many():
        for _ in range(1000):
            try:
                counter.increment()
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=increment_many) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
        assert not t.is_alive(), "Thread timed out"

    assert not errors, f"Thread errors: {errors}"
    assert counter.value == 10_000

# Testing timeout-sensitive code:
@pytest.mark.timeout(5)   # pytest-timeout plugin
def test_no_deadlock():
    acquire_lock_a()
    acquire_lock_b()
    # Test passes if it completes in 5s; fails with TimeoutExpired if it hangs

# Testing multiprocessing (use spawn start method for cleanliness):
import multiprocessing

def test_process_result():
    def worker(queue):
        queue.put(compute_something())

    ctx = multiprocessing.get_context('spawn')
    q = ctx.Queue()
    p = ctx.Process(target=worker, args=(q,))
    p.start()
    p.join(timeout=10)
    assert p.exitcode == 0
    result = q.get_nowait()
    assert result == expected
```

---

## Gotcha Follow-ups

**"Can fixtures be used in parametrize IDs?"**
No — parametrize IDs are strings, not fixtures. But you can use `pytest_make_parametrize_id` hook in conftest to customize IDs, or pass `ids=` with a callable: `ids=lambda x: x.name` where `x` is the parametrize value.

**"What's the difference between `yield` and `return` in a fixture?"**
`return` provides the fixture value immediately. `yield` provides the value AND allows teardown code after the `yield`. With `return`, there's no teardown. If teardown is needed, use `yield`. If not, `return` is fine and slightly simpler.

---

## Under the Hood

pytest uses `pluggy` for its hook system. `conftest.py` files and installed pytest plugins register as `pluggy` plugins. Fixture resolution is in `_pytest/fixtures.py`, `FixtureManager.getfixturedefs()`. Fixture instantiation creates `FixtureDef` objects. The scope-based caching uses `FixtureDef._active_fixturedef` to store the current value. Parametrize is implemented via `CallSpec2` which multiplies test items during collection. The `_pytest/assertion/rewrite.py` module contains the AST transformer for assertion rewriting.
