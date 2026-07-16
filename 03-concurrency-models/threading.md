# Threading Module: Synchronization Primitives

## Concept

Python's `threading` module wraps OS threads. Despite the GIL limiting CPU-bound parallelism, threading remains essential for I/O-bound concurrency, background tasks, and cases where shared memory between threads is required. The module provides several synchronization primitives, each solving a specific coordination problem.

### Lock

The basic mutex — allows exactly one thread to hold it at a time.

```python
import threading

_lock = threading.Lock()
_shared_data = {}

def safe_update(key, value):
    with _lock:           # acquire on entry, release on exit (even if exception)
        _shared_data[key] = value

def safe_read(key):
    with _lock:
        return _shared_data.get(key)

# Non-blocking acquire:
if _lock.acquire(blocking=False):
    try:
        _shared_data["x"] = 1
    finally:
        _lock.release()
else:
    print("Could not acquire lock — skipping")
```

**Lock is NOT reentrant.** A thread that holds a `Lock` and tries to acquire it again will deadlock.

### RLock (Reentrant Lock)

Can be acquired multiple times by the **same** thread. The lock is released only when the acquisition count drops to zero.

```python
import threading

rlock = threading.RLock()

def outer():
    with rlock:
        inner()  # OK — same thread can re-acquire

def inner():
    with rlock:  # acquires again; count = 2
        do_work()
    # exits inner: count = 1; lock still held
# exits outer: count = 0; lock released

# Use case: recursive functions or methods that all need the lock
class Tree:
    def __init__(self):
        self._lock = threading.RLock()

    def insert(self, val):
        with self._lock:
            self._insert(val)

    def _insert(self, val):
        with self._lock:  # reentrant — OK
            pass
```

**When to choose RLock over Lock:** when your code paths might re-enter the same lock (recursive algorithms, methods calling other synchronized methods on the same object). RLock has slightly more overhead than Lock.

### Condition

A `Condition` combines a lock with a wait/notify mechanism. The classic producer/consumer primitive.

```python
import threading
import queue as stdlib_queue

class BoundedBuffer:
    def __init__(self, maxsize):
        self._buffer = []
        self._maxsize = maxsize
        self._cond = threading.Condition()

    def put(self, item):
        with self._cond:
            while len(self._buffer) >= self._maxsize:
                self._cond.wait()  # releases lock and blocks; reacquires on notify
            self._buffer.append(item)
            self._cond.notify_all()

    def get(self):
        with self._cond:
            while not self._buffer:
                self._cond.wait()
            item = self._buffer.pop(0)
            self._cond.notify_all()
            return item
```

**Critical pattern:** Always check the condition in a `while` loop, not `if`. Spurious wakeups and changed state between notify and reacquire are both real risks.

### Event

A simple one-shot (or resettable) signaling mechanism.

```python
import threading
import time

startup_complete = threading.Event()

def worker():
    startup_complete.wait()    # blocks until event is set
    print("Worker starting")

def main():
    t = threading.Thread(target=worker)
    t.start()
    time.sleep(1)
    print("Setup done")
    startup_complete.set()     # unblocks all waiting threads
    t.join()

# Event.wait(timeout=5.0) — returns True if set, False if timed out
# Event.clear() — resets to unset state (allows reuse)
# Event.is_set() — check without blocking
```

### Semaphore

Limits the number of concurrent holders to a fixed count. Use for rate limiting or resource pools.

```python
import threading
import time

# Limit to 3 concurrent DB connections:
db_semaphore = threading.Semaphore(3)

def query_db(query_id):
    with db_semaphore:  # blocks if 3 threads already inside
        print(f"Query {query_id} running")
        time.sleep(0.1)
        print(f"Query {query_id} done")

threads = [threading.Thread(target=query_db, args=(i,)) for i in range(10)]
for t in threads: t.start()
for t in threads: t.join()
# At most 3 queries run simultaneously
```

`BoundedSemaphore(n)` — raises `ValueError` if `release()` is called more than `n` times in total. Use this instead of `Semaphore` to catch bugs where you accidentally release more than you acquire.

### Deadlock Scenarios

```python
import threading

lock_a = threading.Lock()
lock_b = threading.Lock()

def thread1():
    with lock_a:          # acquires A
        with lock_b:      # tries to acquire B — may block
            pass

def thread2():
    with lock_b:          # acquires B
        with lock_a:      # tries to acquire A — may block while thread1 holds A
            pass

# Classic deadlock: thread1 holds A, wants B; thread2 holds B, wants A
```

**Deadlock prevention strategies:**
1. **Lock ordering** — always acquire locks in the same global order (`lock_a` before `lock_b` everywhere).
2. **Timeout with backoff** — `lock.acquire(timeout=1.0)`, back off and retry.
3. **Single lock** — use one coarse-grained lock instead of multiple fine-grained ones.
4. **Lock-free data structures** — `queue.Queue`, `collections.deque` (appendleft/pop are thread-safe in CPython due to GIL, but don't rely on this in free-threaded builds).

---

## Interview Questions

### Q1: What's the difference between `Lock` and `RLock`? When would using `Lock` cause a deadlock that `RLock` would avoid?

**Model answer:**  
`Lock` is non-reentrant: if a thread that holds the lock tries to acquire it again (even in the same thread), it deadlocks. `RLock` maintains an acquisition count per thread — the same thread can acquire multiple times; the lock releases only when the count returns to zero.

```python
lock = threading.Lock()

def recursive_function(n):
    with lock:          # first call: acquires
        if n > 0:
            recursive_function(n - 1)  # second call: DEADLOCK — lock already held
```

With `threading.RLock()`, the same code works correctly. Use `Lock` by default (less overhead, more explicit). Switch to `RLock` only when recursion or re-entrant calls are part of the design.

### Q2: Explain the spurious wakeup problem with `Condition.wait()`.

**Model answer:**  
On some OS/hardware implementations, a thread waiting on a condition variable can wake up without `notify()` or `notify_all()` being called — a "spurious wakeup." This is allowed by POSIX. It also occurs legitimately when `notify_all()` wakes all waiters but only some can proceed (e.g., a buffer has space for only one producer).

The fix is always checking the condition in a `while` loop:

```python
# WRONG — susceptible to spurious wakeups:
def get(self):
    with self._cond:
        if not self._buffer:    # if, not while
            self._cond.wait()   # may spuriously wake when buffer is still empty
        return self._buffer.pop(0)  # IndexError if buffer is empty

# CORRECT:
def get(self):
    with self._cond:
        while not self._buffer:  # re-check condition after wakeup
            self._cond.wait()
        return self._buffer.pop(0)
```

Python 3.2+ added `Condition.wait_for(predicate)` which handles this loop internally:
```python
cond.wait_for(lambda: len(buffer) > 0)  # equivalent to the while pattern above
```

### Q3: Is `list.append()` thread-safe in CPython?

**Model answer:**  
In CPython's current (GIL) implementation, `list.append()` is effectively atomic — it's implemented in C and executes without releasing the GIL. The GIL prevents race conditions on the C-level operation.

However:
1. This is a CPython implementation detail, not a Python language guarantee.
2. `list.append()` is safe; compound read-modify-write operations (like `lst[i] += 1` when `lst[i]` is a non-atomic type) are not.
3. In free-threaded CPython (PEP 703), `list.append()` uses internal fine-grained locks.

**Production guidance:** Do not rely on GIL-based thread safety for lists in shared-state code. Use `queue.Queue` for inter-thread communication, which has explicit thread-safe semantics across all Python implementations.

### Q4: How do you implement a thread-safe singleton in Python?

**Model answer:**  
The naive lazy singleton has a race condition:

```python
# BROKEN — two threads can both see instance as None:
class Singleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:     # race: two threads see None
            cls._instance = cls()     # both create instances
        return cls._instance
```

Fix with double-checked locking:

```python
import threading

class Singleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:         # fast path (no lock)
            with cls._lock:               # slow path
                if cls._instance is None: # re-check after acquiring lock
                    cls._instance = cls()
        return cls._instance
```

Even better — use module-level initialization (Python modules are initialized once and their namespace is thread-safe post-init):

```python
# singleton.py
class _Singleton:
    pass

instance = _Singleton()  # created once at import time, thread-safe
```

Or use a metaclass:

```python
class SingletonMeta(type):
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class MyService(metaclass=SingletonMeta):
    pass
```

### Q5: What is `threading.local()` and what problem does it solve?

**Model answer:**  
`threading.local()` creates a storage object where each thread sees its own separate copy of all attributes. It's used for per-thread state that must not be shared.

```python
import threading

_local = threading.local()

def set_user(user_id):
    _local.user_id = user_id  # each thread gets its own .user_id

def get_user():
    return getattr(_local, 'user_id', None)

def handle_request(user_id):
    set_user(user_id)
    # ... process ...
    print(get_user())  # always sees this thread's user_id

threads = [threading.Thread(target=handle_request, args=(f"user_{i}",)) for i in range(5)]
for t in threads: t.start()
for t in threads: t.join()
```

Contrast with `contextvars.ContextVar` (Python 3.7+), which is async-safe — it works correctly with coroutines, where a single thread may handle multiple concurrent requests. `threading.local()` has one value per OS thread; `ContextVar` has one value per execution context (coroutine task).

---

## Gotcha Follow-ups

**"If you use `threading.Lock` inside a `__del__` finalizer, what can go wrong?"**  
At interpreter shutdown, threads may be in arbitrary states. If a finalizer's `__del__` tries to acquire a lock that is held by another thread that has already been forcibly stopped (or is blocked on something else), the finalizer deadlocks. Additionally, module-level variables may be `None` by the time `__del__` runs at shutdown. Rule: avoid non-trivial operations in `__del__`.

**"Is `dict` thread-safe in CPython?"**  
Individual dict operations (get, set, delete) are atomic under the GIL in the sense that no other Python thread can interrupt mid-operation. But multi-operation sequences (read-then-write, iteration, etc.) are not atomic. Iteration over a dict while another thread modifies it raises `RuntimeError: dictionary changed size during iteration`. Use explicit locking for any dict shared across threads.

---

## Under the Hood

Python's `threading.Lock` maps to `pthread_mutex_t` on POSIX and `CRITICAL_SECTION` on Windows. `threading.Condition` is built on top of `Lock` plus `threading.Event` (or `_Condition_notify` which uses a list of waiters). The Python-level primitives add overhead over the raw OS primitives due to Python object overhead and GIL interaction, but the semantics are identical to POSIX threading.

In CPython 3.13+, `threading._bootstrap` was refactored for free-threaded support, but the public API is unchanged.
