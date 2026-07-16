# GIL Removal: PEP 703 and Free-Threaded CPython

## Concept

**PEP 703** ("Making the Global Interpreter Lock Optional") was accepted in Python 3.13 (2024). It adds a build option for "free-threaded" CPython — a Python interpreter without the GIL. This is the most significant architectural change to CPython since reference counting was introduced.

### Current Status (as of Python 3.13/3.14)

- **Python 3.13** — experimental free-threaded build available (`python3.13t`). Not production-ready.
- **Python 3.14** — continued improvement; free-threaded build is more stable but still experimental.
- **Default CPython** — still has the GIL. Free-threaded is an opt-in build, not the default.
- **Target** — the GIL will likely remain the default for several more releases to allow the ecosystem to adapt.

### How the GIL Was Replaced

Removing the GIL required replacing every mechanism that relied on it:

**1. Biased Reference Counting**  
The standard `ob_refcnt` is NOT thread-safe. Free-threaded CPython uses a two-level scheme:
- `ob_ref_local` — a single-word counter, biased toward the owning thread. Modified without a lock when the owning thread touches the object.
- `ob_ref_shared` — a separate, lock-protected counter for references from other threads.

This eliminates atomic operations in the common single-thread case while remaining correct for shared objects.

**2. Per-Object Locks**  
Container types (list, dict, set) now have a per-object lock (a compact "Py_mutex" using OS futexes). Operations that modify structure (append, insert, delete) acquire this lock. Simple reads in tight loops may still contend.

**3. Immortal Objects**  
Common singletons (`None`, `True`, `False`, small integers, interned strings) are marked "immortal" — their refcounts are never incremented or decremented, avoiding all contention on these hot objects.

**4. Critical Sections**  
A new C API (`Py_BEGIN_CRITICAL_SECTION(obj)`) protects object modifications without requiring global locking. The bytecode evaluator uses this for attribute access and other object operations.

### What Changes for Python Code

```python
import threading
import sys

# Check if running in free-threaded build:
print(sys._is_gil_enabled())  # True in standard build, False in free-threaded

# In free-threaded CPython, this can achieve TRUE parallel execution:
import time

def cpu_task(n):
    total = 0
    for i in range(n):
        total += i
    return total

# In standard CPython: threads fight over GIL, no speedup
# In free-threaded CPython: genuine parallel execution on multi-core
threads = [threading.Thread(target=cpu_task, args=(10_000_000,)) for _ in range(4)]
start = time.perf_counter()
for t in threads: t.start()
for t in threads: t.join()
elapsed = time.perf_counter() - start
print(f"Elapsed: {elapsed:.2f}s")
# Free-threaded on 4 cores: ~0.25x serial time
# GIL build on 4 cores: ~1.1x serial time (slower than serial due to contention)
```

### What Breaks Without the GIL

**1. C Extensions Assuming Single-Threaded Access**

Most C extensions were written assuming the GIL prevents concurrent access. In free-threaded builds, they must be audited and potentially rewritten:

```c
/* Old C extension — unsafe in free-threaded build: */
static PyObject *module_state = NULL;  // global, unprotected

PyObject* get_state(PyObject *self, PyObject *args) {
    if (module_state == NULL) {
        module_state = PyList_New(0);  // race: two threads can both see NULL
    }
    return module_state;
}

/* Fixed for free-threaded: use Py_BEGIN_CRITICAL_SECTION or
   py_atomic_load / py_atomic_compare_exchange */
```

**2. Thread-Unsafe Pure Python Code**

Code that "accidentally" relied on the GIL for correctness:

```python
# This was "safe" under the GIL because list.append is atomic
# Under free-threaded CPython, it's still safe (per-object lock),
# but more complex operations are not:

shared_list = []

def appender():
    for i in range(1000):
        shared_list.append(i)  # still atomic in free-threaded (per-object lock)

# But this is NOT atomic even in free-threaded:
def bad_update():
    if len(shared_list) > 0:    # check
        shared_list.pop()       # act — race between check and act
```

**3. Extension Types Without Thread Support**

NumPy, Cython extensions, and many others declare `Py_TPFLAGS_BASETYPE` but don't implement proper locking. They need to opt-in to free-threaded safety with `Py_TPFLAGS_HAVE_FINALIZE` and proper critical section usage.

The `sys.getswitchinterval()` mechanism is also changed — the GIL switch interval no longer applies; thread scheduling reverts to OS preemption.

### Migration Implications

**For pure Python library authors:**
- Code using `threading.Lock` for shared mutable state: already correct, remains correct.
- Code relying on GIL-provided "accidental" atomicity (e.g., checking and setting a module global without a lock): needs a `threading.Lock`.

**For C extension authors:**
- Must audit for unprotected global state.
- Must declare thread-safety via `Py_TPFLAGS_THREAD_SAFE` (tentative name).
- Extensions without this flag will be loaded with a per-extension lock in free-threaded builds — degrading back to GIL-like behavior for that extension.

**For application architects:**
- The primary concurrency model recommendation changes: `asyncio` for I/O-bound (unchanged), `threading` now viable for CPU-bound Python (new!), `multiprocessing` still needed for bypassing Python's per-thread overhead.
- Lock-free data structures and immutable-by-default designs become more valuable.

---

## Interview Questions

### Q1: What is PEP 703 and why is it significant?

**Model answer:**  
PEP 703 adds a build-time option to CPython to remove the Global Interpreter Lock (GIL). Accepted for Python 3.13, it represents a fundamental architectural shift:

- True CPU-parallel Python threads become possible — for the first time in CPython's history, a multi-threaded pure Python program can use multiple CPU cores simultaneously.
- The tradeoff is significantly more complex memory management (biased reference counting, per-object locks), and a major ecosystem compatibility burden (most C extensions must be audited).

Its significance: Python has been unable to use multi-core effectively for pure Python computation since its inception. PEP 703 changes this, at the cost of breaking many ecosystem assumptions.

### Q2: How does biased reference counting work, and why is it better than atomic reference counting?

**Model answer:**  
**Atomic reference counting** (used by Swift, Rust `Arc<T>`) makes every `INCREF`/`DECREF` an atomic compare-and-swap. This is correct but expensive — atomic operations are much slower than non-atomic ones and cause cache line bouncing when multiple threads touch the same counter.

**Biased reference counting** (CPython's free-threaded approach):
- Each object has an "owner thread" (the thread that created it).
- `ob_ref_local` — a fast, non-atomic counter for the owning thread's references.
- `ob_ref_shared` — an atomic counter for references from other threads.

The owning thread can `INCREF`/`DECREF` `ob_ref_local` without any atomic operation. Only when another thread acquires a reference does the more expensive `ob_ref_shared` atomic path activate.

Since most objects are used primarily by one thread (they're local to a function, a coroutine, a request handler), the common case is fast. Only truly shared objects pay the atomic cost.

### Q3: What happens to C extensions that are not updated for free-threaded Python?

**Model answer:**  
Free-threaded CPython (3.13+) uses the `Py_TPFLAGS_DEFAULT` system to detect whether an extension declares thread-safety support. Extensions that don't declare it will be loaded with a compatibility shim — essentially a per-extension GIL. This means:

- Old extensions still work correctly (their internal data is protected by the per-extension lock).
- But they behave as if the GIL still exists for their code — only one thread can execute that extension's code at a time.
- Performance gains from free-threading only apply to pure Python code and extensions that have opted into the new model.

This is the "compatibility ladder" approach: the ecosystem migrates gradually without breaking existing packages.

### Q4: What concurrency model changes should architects plan for in a post-GIL Python world?

**Model answer:**  
The concurrency decision tree changes substantially:

**Before free-threading:**
```
CPU-bound: → multiprocessing (bypass GIL)
I/O-bound concurrent: → asyncio or threading
I/O-bound simple: → threading
```

**After free-threading (gradually, as ecosystem matures):**
```
CPU-bound (pure Python): → threading (finally viable!)
CPU-bound (C extensions): → threading (if extension opts in) or multiprocessing
I/O-bound many concurrent: → asyncio (still best for >1000 connections)
I/O-bound moderate: → threading (simpler, fewer footguns)
```

Architectural implications:
1. **Thread-safety must be explicit.** Every shared mutable data structure needs a lock or must use thread-safe alternatives (`queue.Queue`, `threading.local`). Code that accidentally relied on GIL atomicity will have subtle races.
2. **Immutability is rewarded.** Immutable objects (frozen dataclasses, namedtuples, tuples of scalars) have no contention; they're ideal for sharing across threads.
3. **Actor model / per-thread state** becomes attractive: design systems where threads rarely share mutable state, communicating via queues instead.

### Q5: If you're starting a new Python project today targeting production in 2026, how does PEP 703 affect your architecture decisions?

**Model answer:**  
**Today's recommendation:** Assume standard (GIL) CPython in production. Free-threaded CPython is experimental; the ecosystem (NumPy, Cython, most C extensions) is not yet stable under it.

**Design for future compatibility:**
1. **Use proper locking now.** Don't write code that relies on GIL atomicity. Use `threading.Lock` for any shared mutable state, even in "single-threaded-for-now" code. This is correct today and correct after the GIL is removed.
2. **Prefer asyncio for I/O concurrency.** It's already GIL-independent and will remain the right choice for high-concurrency I/O.
3. **Avoid global mutable state.** Module-level mutable singletons (`_cache = {}` at module level) are already problematic; they become race conditions without the GIL.
4. **Watch key packages:** Once NumPy and the major scientific/ML ecosystem declares free-thread compatibility, the calculus changes. Track `https://py-free-threading.github.io/` for ecosystem status.

**If targeting 2027+:** Free-threaded Python will likely be more mature; design CPU-bound workloads with threading in mind.

---

## Gotcha Follow-ups

**"Can you opt out of free-threading for a specific extension without rebuilding it?"**  
Yes — the compatibility shim (per-extension lock) is applied automatically to extensions that don't declare `Py_GIL_DISABLED` support. The extension doesn't need to do anything; it just won't benefit from true parallelism. Python 3.13 also provides `sys._is_gil_enabled()` so code can check at runtime and take a conservative path.

**"Does removing the GIL make Python faster overall?"**  
Not necessarily — it often makes single-threaded code slightly SLOWER due to the overhead of biased reference counting, per-object locks, and the additional bookkeeping for immortal objects. The benefit is specifically for multi-threaded CPU-bound workloads. Benchmarks from the PEP 703 authors show ~4% single-threaded overhead; real-world overhead varies. The GIL exists partly as a performance optimization for single-threaded code — its removal is a tradeoff of single-thread performance for multi-thread scalability.

---

## Under the Hood

Free-threaded CPython source is in the `nogil` branch (Samyam Rajbhandari's initial work) and has been merged into CPython main. Key files:
- `Include/cpython/object.h` — modified `PyObject` with `ob_ref_local` / `ob_ref_shared`
- `Python/ceval.c` — critical section macros replacing GIL-assumption code
- `Python/gc_free_threading.c` — new GC implementation for free-threaded mode
- `Modules/_threadmodule.c` — updated threading module

The free-threaded build is selected with `--disable-gil` at configure time (or via pyenv `cpython-3.13t`). `sys._is_gil_enabled()` returns `False` in these builds.
