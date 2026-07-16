"""
Thread-Safe Singleton Implementations

Three patterns:
1. Double-checked locking (explicit lock)
2. Module-level singleton (Pythonic, leverages import system)
3. Metaclass-based (supports multiple singleton classes)

All three are safe for CPython's current (GIL) and free-threaded (PEP 703) builds.
"""

from __future__ import annotations
import threading
import time
import sys


# =============================================================================
# Pattern 1: Double-checked locking
# =============================================================================
class DatabaseConnection:
    """Classic double-checked locking singleton."""

    _instance: DatabaseConnection | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls):
        # Fast path: if instance already exists, no lock needed
        if cls._instance is None:
            with cls._lock:
                # Slow path: re-check after acquiring lock
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        # Guard against re-initialization when __new__ returns existing instance
        if self._initialized:
            return
        self._initialized = True
        self.connection_id = id(self)
        print(f"DatabaseConnection initialized (id={self.connection_id})")

    def query(self, sql: str) -> str:
        return f"[conn:{self.connection_id}] executing: {sql}"

    @classmethod
    def reset(cls):
        """For testing — resets the singleton state."""
        with cls._lock:
            cls._instance = None


# =============================================================================
# Pattern 2: Metaclass singleton (recommended for library code)
# =============================================================================
class SingletonMeta(type):
    """Metaclass that enforces singleton semantics."""

    _instances: dict[type, object] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]

    def reset(cls):
        """For testing."""
        with cls._lock:
            cls._instances.pop(cls, None)


class AppConfig(metaclass=SingletonMeta):
    def __init__(self, env: str = "production"):
        self.env = env
        self.settings: dict = {}
        print(f"AppConfig created for env={env}")

    def set(self, key: str, value) -> None:
        self.settings[key] = value

    def get(self, key: str, default=None):
        return self.settings.get(key, default)


class CacheManager(metaclass=SingletonMeta):
    def __init__(self):
        self._cache: dict = {}
        print("CacheManager created")

    def put(self, key, value):
        self._cache[key] = value

    def get(self, key):
        return self._cache.get(key)


# =============================================================================
# Pattern 3: Module-level singleton (simplest, most Pythonic)
# =============================================================================
# In a real codebase, put this in its own module (e.g., services/db.py):

class _ConnectionPool:
    def __init__(self, max_connections: int = 10):
        self._max = max_connections
        self._pool: list = []
        self._lock = threading.Lock()
        print(f"ConnectionPool created with max={max_connections}")

    def acquire(self) -> object:
        with self._lock:
            if self._pool:
                return self._pool.pop()
            return object()  # simulate new connection

    def release(self, conn: object) -> None:
        with self._lock:
            if len(self._pool) < self._max:
                self._pool.append(conn)


# Module-level singleton — created once at import time, thread-safe:
connection_pool = _ConnectionPool(max_connections=5)


# =============================================================================
# Thread-safety verification
# =============================================================================
def verify_thread_safety():
    print("\n=== Verifying thread safety under concurrent access ===")
    instances: list[DatabaseConnection] = []
    lock = threading.Lock()

    def create_singleton():
        inst = DatabaseConnection()
        with lock:
            instances.append(inst)

    threads = [threading.Thread(target=create_singleton) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    unique_ids = {id(i) for i in instances}
    print(f"Threads: {len(threads)}, Unique instances: {len(unique_ids)}")
    assert len(unique_ids) == 1, f"Singleton violated! {len(unique_ids)} instances"
    print("✓ Singleton verified: all 50 threads got the same instance")


if __name__ == '__main__':
    print("=== Pattern 1: Double-checked locking ===")
    db1 = DatabaseConnection()
    db2 = DatabaseConnection()
    print(f"db1 is db2: {db1 is db2}")  # True
    print(db1.query("SELECT 1"))

    print("\n=== Pattern 2: Metaclass singleton ===")
    cfg1 = AppConfig("development")
    cfg2 = AppConfig("staging")       # init not re-run
    print(f"cfg1 is cfg2: {cfg1 is cfg2}")   # True
    print(f"env stays: {cfg1.env}")           # "development" — first init wins

    cache1 = CacheManager()
    cache2 = CacheManager()
    print(f"cache1 is cache2: {cache1 is cache2}")  # True

    # Different classes get different singletons:
    print(f"cfg1 is cache1: {cfg1 is cache1}")  # False — separate singletons

    print("\n=== Pattern 3: Module-level ===")
    conn = connection_pool.acquire()
    print(f"Acquired connection: {conn}")
    connection_pool.release(conn)

    verify_thread_safety()
