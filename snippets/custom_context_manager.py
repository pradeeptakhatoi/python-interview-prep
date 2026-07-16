"""
Custom Context Managers

Demonstrates:
- Class-based __enter__/__exit__ protocol
- contextlib.contextmanager decorator
- contextlib.ExitStack for dynamic resource management
- Async context managers (__aenter__/__aexit__)
- Reentrant context managers
"""

from __future__ import annotations
import contextlib
import asyncio
import logging
import time
import threading
from typing import Generator, Any


# =============================================================================
# 1. Class-based context manager
# =============================================================================
class Timer:
    """Measures elapsed time for a code block."""

    def __init__(self, name: str = "", logger: logging.Logger | None = None):
        self.name = name
        self._logger = logger
        self.elapsed: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self   # 'as' clause receives this

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.elapsed = time.perf_counter() - self._start
        msg = f"{self.name}: {self.elapsed*1000:.2f}ms"
        if exc_type is not None:
            msg += f" (raised {exc_type.__name__})"
        if self._logger:
            self._logger.info(msg)
        else:
            print(msg)
        return False   # False = don't suppress exceptions


class ManagedConnection:
    """Simulates a database connection with proper cleanup."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._connected = False

    def __enter__(self) -> ManagedConnection:
        print(f"Connecting to {self.host}:{self.port}")
        self._connected = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._connected:
            print(f"Disconnecting from {self.host}:{self.port}")
            self._connected = False
        if exc_type is ValueError:
            print(f"Suppressing ValueError: {exc_val}")
            return True  # suppress this specific exception
        return False

    def execute(self, query: str) -> list:
        if not self._connected:
            raise RuntimeError("Not connected")
        return [{"result": query}]


# =============================================================================
# 2. contextlib.contextmanager decorator
# =============================================================================
@contextlib.contextmanager
def managed_temp_file(suffix: str = ".tmp") -> Generator[str, None, None]:
    """Create a temp file, yield its path, ensure cleanup."""
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    print(f"Created temp file: {path}")
    try:
        yield path                    # control passes to 'with' block here
    except Exception:
        print(f"Error occurred, cleaning up {path}")
        raise                         # re-raise — don't suppress
    finally:
        if os.path.exists(path):
            os.unlink(path)
            print(f"Deleted temp file: {path}")


@contextlib.contextmanager
def suppress_and_log(*exceptions, logger: logging.Logger | None = None):
    """Like contextlib.suppress but logs the suppressed exception."""
    try:
        yield
    except exceptions as e:
        msg = f"Suppressed {type(e).__name__}: {e}"
        if logger:
            logger.warning(msg)
        else:
            print(f"[SUPPRESSED] {msg}")


# =============================================================================
# 3. Reentrant context manager
# =============================================================================
class ReentrantLock:
    """Context manager that can be entered multiple times in the same thread."""

    def __init__(self):
        self._lock = threading.RLock()
        self._depth = 0

    def __enter__(self) -> ReentrantLock:
        self._lock.acquire()
        self._depth += 1
        print(f"Acquired (depth={self._depth})")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._depth -= 1
        print(f"Released (depth={self._depth})")
        self._lock.release()
        return False

    @property
    def depth(self) -> int:
        return self._depth


# =============================================================================
# 4. ExitStack — dynamic resource management
# =============================================================================
def open_multiple_resources(paths: list[str]):
    """Open multiple files dynamically; all closed on exit even if some fail."""
    with contextlib.ExitStack() as stack:
        files = []
        for path in paths:
            try:
                f = stack.enter_context(open(path, 'r'))
                files.append(f)
            except FileNotFoundError:
                print(f"Warning: {path} not found, skipping")
                # Other files are still managed; stack cleans up on exit

        # All successfully opened files are available here:
        for f in files:
            print(f"Reading from: {f.name}")
            # f.read() ...

        # Cleanup happens automatically when with block exits


@contextlib.contextmanager
def managed_callbacks() -> Generator[contextlib.ExitStack, None, None]:
    """Use ExitStack to register cleanup callbacks dynamically."""
    with contextlib.ExitStack() as stack:
        # Register a plain callback (not a context manager):
        stack.callback(print, "Callback 1: always runs")
        stack.callback(lambda: print("Callback 2: lambda"))

        yield stack   # caller can add more callbacks

        # All callbacks run LIFO on exit


# =============================================================================
# 5. Async context manager
# =============================================================================
class AsyncManagedConnection:
    """Async context manager for an async database connection."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None

    async def __aenter__(self) -> AsyncManagedConnection:
        print(f"Async connecting to {self.dsn}")
        await asyncio.sleep(0.01)    # simulate async connection setup
        self._conn = object()        # placeholder for real connection
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        print(f"Async disconnecting from {self.dsn}")
        await asyncio.sleep(0.005)   # simulate async cleanup
        self._conn = None
        return False                 # don't suppress exceptions

    async def query(self, sql: str) -> list:
        await asyncio.sleep(0.01)   # simulate async query
        return [{"sql": sql}]


@contextlib.asynccontextmanager
async def async_timer(name: str = ""):
    """Async version of Timer using asynccontextmanager."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{name}: {elapsed*1000:.2f}ms (async)")


# =============================================================================
# Demo
# =============================================================================
def sync_demo():
    print("=== Class-based Timer ===")
    with Timer("computation") as t:
        total = sum(range(1_000_000))
    print(f"Sum: {total}, elapsed stored: {t.elapsed*1000:.2f}ms")

    print("\n=== ManagedConnection (suppresses ValueError) ===")
    with ManagedConnection("localhost", 5432) as conn:
        rows = conn.execute("SELECT 1")
        print(f"Got: {rows}")
        raise ValueError("intentional error")   # will be suppressed

    print("\n=== contextmanager decorator ===")
    with managed_temp_file(".txt") as path:
        with open(path, 'w') as f:
            f.write("hello world")
        print(f"Wrote to {path}")
    # file is deleted after with block

    print("\n=== Reentrant lock ===")
    rlock = ReentrantLock()
    with rlock:
        with rlock:     # same thread can re-enter
            with rlock:
                print(f"Inner depth: {rlock.depth}")
        print(f"After inner exit: {rlock.depth}")

    print("\n=== ExitStack with callbacks ===")
    with managed_callbacks() as stack:
        stack.callback(print, "Callback 3: added inside")
        print("Inside with block")
    # Callbacks run LIFO: 3, 2, 1

    print("\n=== suppress_and_log ===")
    with suppress_and_log(ValueError, TypeError):
        int("not a number")
    print("Execution continued after suppressed ValueError")


async def async_demo():
    print("\n=== Async context manager ===")
    async with AsyncManagedConnection("postgres://localhost/mydb") as conn:
        result = await conn.query("SELECT * FROM users")
        print(f"Query result: {result}")

    print("\n=== asynccontextmanager ===")
    async with async_timer("async operation"):
        await asyncio.sleep(0.05)


if __name__ == '__main__':
    sync_demo()
    asyncio.run(async_demo())
