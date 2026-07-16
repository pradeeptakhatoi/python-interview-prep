# Python Interview Prep — Staff Engineer / Architect Level

A focused study guide for senior Python engineers targeting Staff Software Engineer or Architect roles. Content goes beyond syntax into CPython internals, runtime behavior, and language-level architectural decisions at scale.

**Target:** 12+ years experience, deep production Python background  
**Scope:** Core Python — language, CPython runtime, standard library. No web frameworks, no ORMs.

---

## Study Roadmap

### Legend

| Symbol | Meaning |
|--------|---------|
| ★★★ | Must-know — will appear in virtually every senior Python interview |
| ★★☆ | High value — expected at Staff level |
| ★☆☆ | Differentiator — separates Architect candidates from strong Seniors |

---

### Suggested Order and Time Estimates

| # | Section | Priority | Est. Days | Notes |
|---|---------|----------|-----------|-------|
| 1 | [Language Fundamentals](01-language-fundamentals/) | ★★★ | 2 | Descriptors and metaclasses are the leveling questions |
| 2 | [Memory Management & GC](02-memory-management-and-gc/) | ★★★ | 2 | Reference cycles + weakref are almost always asked |
| 3 | [Concurrency Models](03-concurrency-models/) | ★★★ | 3 | GIL, asyncio internals — the most common Staff-level deep dive |
| 4 | [Data Structures & Performance](04-data-structures-and-performance/) | ★★☆ | 1.5 | dict/list internals, `__slots__`, real-world tradeoffs |
| 5 | [Typing & Static Analysis](05-typing-and-static-analysis/) | ★★☆ | 1.5 | Protocol vs ABC, variance — expected at Staff+ |
| 6 | [Error Handling & Context Managers](06-error-handling-and-context-managers/) | ★★★ | 1 | ExitStack, exception groups, contextvars |
| 7 | [Packaging & Environments](07-packaging-and-environments/) | ★★☆ | 1 | Import system internals, circular imports |
| 8 | [Testing & Profiling](08-testing-and-profiling/) | ★★☆ | 1 | py-spy, flame graphs, benchmarking correctness |
| 9 | [C Extensions & Interop](09-c-extensions-and-interop/) | ★☆☆ | 1 | Buffer protocol, GIL release — Architect differentiator |
| 10 | [Architecture & Design Patterns](10-architecture-and-design-patterns/) | ★★☆ | 2 | Plugin systems, DI, async producer/consumer |
| 11 | [Common Pitfalls](11-common-pitfalls/) | ★★★ | 0.5 | Quick review; every interviewer probes these |
| 12 | [Expert Internals & Edge Cases](12-expert-internals-and-edge-cases/) | ★☆☆ | 2.5 | Bytecode, adaptive interpreter, import hooks — Architect level |

**Total:** ~19 days of focused study (2-3 hours/day)

---

### Accelerated Track (1 week)

If time is short, hit these in order:

1. `03-concurrency-models/` — GIL, asyncio, multiprocessing
2. `02-memory-management-and-gc/` — reference counting, cycles, weakref
3. `01-language-fundamentals/` — descriptors, metaclasses, closures
4. `11-common-pitfalls/` — fast review
5. `12-expert-internals-and-edge-cases/bytecode-and-dis.md` + `coroutine-internals.md`

---

## Complete Topic List

### 01 — Language Fundamentals ★★★

| File | Topics Covered |
|------|---------------|
| [mutable-immutable-identity.md](01-language-fundamentals/mutable-immutable-identity.md) | Identity vs equality, `is` vs `==`, interning, copy vs deepcopy, immutable containers with mutable contents |
| [scoping-and-closures.md](01-language-fundamentals/scoping-and-closures.md) | LEGB rule, `global`/`nonlocal`, closure cells, late binding, `__closure__` |
| [decorators.md](01-language-fundamentals/decorators.md) | `functools.wraps`, class decorators, decorator factories, stacking order, `__wrapped__` |
| [descriptors.md](01-language-fundamentals/descriptors.md) | `__get__`/`__set__`/`__delete__`, data vs non-data priority, `__set_name__`, property internals, functions as descriptors |
| [metaclasses.md](01-language-fundamentals/metaclasses.md) | `type()` as class factory, `__prepare__`/`__new__`/`__init__` sequence, `__init_subclass__`, metaclass conflicts |

### 02 — Memory Management & GC ★★★

| File | Topics Covered |
|------|---------------|
| [reference-counting.md](02-memory-management-and-gc/reference-counting.md) | `ob_refcnt`, `sys.getrefcount`, `Py_INCREF`/`Py_DECREF`, immortal objects (3.12+) |
| [generational-gc.md](02-memory-management-and-gc/generational-gc.md) | Three generations, `gc` module, thresholds, `gc.collect()`, `gc.disable()` trade-offs |
| [reference-cycles.md](02-memory-management-and-gc/reference-cycles.md) | How cycles form, `tp_traverse`/`tp_clear`, `objgraph` for leak detection |
| [weak-references.md](02-memory-management-and-gc/weak-references.md) | `weakref.ref`, `WeakValueDictionary`, `WeakKeyDictionary`, finalizers |
| [memory-profiling.md](02-memory-management-and-gc/memory-profiling.md) | `tracemalloc`, `memory_profiler`, heap snapshots, `sys.getsizeof` limitations |
| [interning.md](02-memory-management-and-gc/interning.md) | String interning rules, `sys.intern()`, small integer cache (−5 to 256), `id()` gotchas |

### 03 — Concurrency Models ★★★

| File | Topics Covered |
|------|---------------|
| [gil-internals.md](03-concurrency-models/gil-internals.md) | `eval_breaker`, `ceval_gil.c`, switch interval, GIL release/acquire, why IO-bound threading works |
| [threading.md](03-concurrency-models/threading.md) | `threading.Thread`, `Lock`/`RLock`/`Condition`/`Semaphore`, `ThreadPoolExecutor`, daemon threads |
| [multiprocessing.md](03-concurrency-models/multiprocessing.md) | `Process`, `Pool`, `Queue`/`Pipe`, `Manager`, shared memory, `spawn` vs `fork` vs `forkserver` |
| [concurrent-futures.md](03-concurrency-models/concurrent-futures.md) | `ThreadPoolExecutor`/`ProcessPoolExecutor`, `Future`, `as_completed`, `wait`, `submit` vs `map` |
| [asyncio-internals.md](03-concurrency-models/asyncio-internals.md) | Event loop, `selector`, `Task` driving coroutines, `Future`, `TaskGroup`, cancellation semantics |
| [mixing-paradigms.md](03-concurrency-models/mixing-paradigms.md) | `run_in_executor`, `asyncio.to_thread`, bridging sync/async, `loop.run_until_complete` |
| [gil-removal-pep703.md](03-concurrency-models/gil-removal-pep703.md) | PEP 703 free-threaded Python 3.13+, biased refcounting, per-object locks, `Py_MOD_GIL_NOT_USED` |

### 04 — Data Structures & Performance ★★☆

| File | Topics Covered |
|------|---------------|
| [list-dict-set-internals.md](04-data-structures-and-performance/list-dict-set-internals.md) | `PyListObject` over-allocation, compact dict `dk_indices`/`dk_entries`, set hash table probing |
| [time-complexity.md](04-data-structures-and-performance/time-complexity.md) | Full complexity tables: list, dict, set, deque, heapq, bisect; amortized analysis |
| [slots.md](04-data-structures-and-performance/slots.md) | `__slots__` memory savings, `member_descriptor`, inheritance pitfalls, `@dataclass(slots=True)` |
| [choosing-data-structures.md](04-data-structures-and-performance/choosing-data-structures.md) | Decision matrix for 15+ scenarios, `deque`, `heapq`, `Counter`, `defaultdict`, `bisect` |
| [hashability.md](04-data-structures-and-performance/hashability.md) | Hash/eq contract, `__hash__=None` when `__eq__` defined, `hash(-1)==-2`, SipHash randomization |

### 05 — Typing & Static Analysis ★★☆

| File | Topics Covered |
|------|---------------|
| [generics-typevar-protocol.md](05-typing-and-static-analysis/generics-typevar-protocol.md) | `TypeVar` constrained vs bounded, `Generic[T]`, `Protocol`, `@runtime_checkable`, `@overload`, `ParamSpec`, `Self` |
| [variance.md](05-typing-and-static-analysis/variance.md) | Covariant/contravariant/invariant, `T_co`/`T_contra`, `Callable` variance, `list` vs `Sequence` |
| [runtime-vs-static-checking.md](05-typing-and-static-analysis/runtime-vs-static-checking.md) | mypy vs pyright, pydantic v2, beartype O(1) sampling, typeguard full-depth, `get_type_hints()` |
| [structural-vs-nominal.md](05-typing-and-static-analysis/structural-vs-nominal.md) | Protocol vs ABC isinstance overhead, `__subclasshook__`, virtual subclasses |
| [typing-pitfalls.md](05-typing-and-static-analysis/typing-pitfalls.md) | `TYPE_CHECKING` guard, `Optional` vs `| None`, `TypeGuard`, `cast()` misuse, `NoReturn`/`Never` |

### 06 — Error Handling & Context Managers ★★★

| File | Topics Covered |
|------|---------------|
| [exception-hierarchies.md](06-error-handling-and-context-managers/exception-hierarchies.md) | Domain vs infrastructure layers, `__init_subclass__` auto-registration, structured error attributes |
| [exception-chaining.md](06-error-handling-and-context-managers/exception-chaining.md) | `raise X from Y`, `__cause__`/`__context__`, `ExceptionGroup` (PEP 654), `except*`, `.split()` |
| [context-managers.md](06-error-handling-and-context-managers/context-managers.md) | `__exit__` suppression, `@contextmanager` + try/finally, `ExitStack`, `pop_all()`, async context managers |
| [contextvars.md](06-error-handling-and-context-managers/contextvars.md) | `ContextVar` per-task vs `threading.local()` per-thread, `Token`, `copy_context()`, thread pool propagation |

### 07 — Packaging & Environments ★★☆

| File | Topics Covered |
|------|---------------|
| [virtual-environments.md](07-packaging-and-environments/virtual-environments.md) | `pyvenv.cfg`, `sys.prefix` vs `sys.base_prefix`, pip backtracking resolver, `pip-compile`, `uv` |
| [import-system-internals.md](07-packaging-and-environments/import-system-internals.md) | 10-step import pipeline, `sys.meta_path`, `VirtualModuleFinder`, circular import resolution, `importlib.reload` |
| [namespace-packages.md](07-packaging-and-environments/namespace-packages.md) | No `__init__.py`, `_NamespacePath`, monorepo pattern, mixing pitfall, namespace detection |
| [distributable-packages.md](07-packaging-and-environments/distributable-packages.md) | `pyproject.toml` (PEP 517/518/621), src layout, wheel vs sdist, `entry_points`, manylinux, trusted publishing |

### 08 — Testing & Profiling ★★☆

| File | Topics Covered |
|------|---------------|
| [pytest-internals.md](08-testing-and-profiling/pytest-internals.md) | Fixture scoping, dependency graph, `parametrize` cartesian product, `indirect`, `conftest.py`, assertion rewriting AST |
| [profiling.md](08-testing-and-profiling/profiling.md) | `cProfile` tottime vs cumtime, py-spy sampling via ptrace, pyinstrument async-aware, tracemalloc |
| [benchmarking.md](08-testing-and-profiling/benchmarking.md) | `timeit` min() not mean(), GC disabled, warmup for SAI (3.11+), constant folding pitfall, `pytest-benchmark` |

### 09 — C Extensions & Interop ★☆☆

| File | Topics Covered |
|------|---------------|
| [when-to-extend.md](09-c-extensions-and-interop/when-to-extend.md) | Decision matrix: ctypes / cffi / Cython / pybind11 / PyO3, libffi, `annotate=True`, numpy array passing |
| [buffer-protocol.md](09-c-extensions-and-interop/buffer-protocol.md) | `Py_buffer`, `memoryview` zero-copy slicing, `cast()`, strided buffers, `socket.sendfile()` |
| [gil-release.md](09-c-extensions-and-interop/gil-release.md) | `Py_BEGIN/END_ALLOW_THREADS`, `CDLL` vs `PyDLL`, Cython `with nogil:` + `prange`, free-threaded 3.13 |

### 10 — Architecture & Design Patterns ★★☆

| File | Topics Covered |
|------|---------------|
| [dependency-injection.md](10-architecture-and-design-patterns/dependency-injection.md) | Constructor injection, composition root, `functools.partial` currying, lightweight DI container, async DI |
| [plugin-architectures.md](10-architecture-and-design-patterns/plugin-architectures.md) | `entry_points` discovery, `__init_subclass__` auto-registration, lazy registry, `importlib.util`, validation |
| [async-event-driven.md](10-architecture-and-design-patterns/async-event-driven.md) | `asyncio.Queue` pub/sub, backpressure, `asyncio.Event`/`Condition`/`Queue` trade-offs, async state machine |
| [package-boundaries.md](10-architecture-and-design-patterns/package-boundaries.md) | Circular import causes, ADP layered architecture, `import-linter`, `graphlib.TopologicalSorter` |
| [versioning-deprecation.md](10-architecture-and-design-patterns/versioning-deprecation.md) | `warnings.warn` + stacklevel, `DeprecationWarning` vs `FutureWarning`, `@typing.deprecated` (3.13+), semver lifecycle |

### 11 — Common Pitfalls ★★★

| File | Topics Covered |
|------|---------------|
| [accidental-on2.md](11-common-pitfalls/accidental-on2.md) | `if x in list` in loops, string `+=`, `list.insert(0)`, nested loops, spotting via cProfile |
| [floating-point.md](11-common-pitfalls/floating-point.md) | IEEE 754, `math.isclose`, `Decimal` from string not float, `math.fsum`, banker's rounding |
| [inheritance-vs-composition.md](11-common-pitfalls/inheritance-vs-composition.md) | Diamond problem, C3 MRO, cooperative `super()`, mixin `__init__` with `**kwargs`, composition prefer |
| [mutable-defaults-late-binding.md](11-common-pitfalls/mutable-defaults-late-binding.md) | `def f(x=[])`, `__defaults__`, late-binding closures in loops, `i=i` fix, `functools.partial` |
| [mutating-while-iterating.md](11-common-pitfalls/mutating-while-iterating.md) | `RuntimeError` on dict/set, silent element skipping on list, safe patterns: copy/comprehension/reverse index |

### 12 — Expert Internals & Edge Cases ★☆☆

| File | Topics Covered |
|------|---------------|
| [abstract-base-classes-protocols.md](12-expert-internals-and-edge-cases/abstract-base-classes-protocols.md) | `__subclasshook__`, virtual subclasses, `collections.abc` mixin methods, ABC vs Protocol isinstance overhead |
| [bytecode-and-dis.md](12-expert-internals-and-edge-cases/bytecode-and-dis.md) | Code objects, `dis.get_instructions()`, peephole optimizer, constant folding, generator/coroutine opcodes |
| [c3-linearization-mro.md](12-expert-internals-and-edge-cases/c3-linearization-mro.md) | C3 algorithm in pure Python, worked diamond example, MRO conflict diagnosis, `__mro_entries__` |
| [coroutine-internals.md](12-expert-internals-and-edge-cases/coroutine-internals.md) | Generator protocol, `yield from`, `async/await` desugaring, awaitable protocol, `asyncio.Task` step loop |
| [custom-import-hooks.md](12-expert-internals-and-edge-cases/custom-import-hooks.md) | `MetaPathFinder` + `Loader`, AST-rewriting loader, database-backed modules, encrypted module loading |
| [function-calls-internals.md](12-expert-internals-and-edge-cases/function-calls-internals.md) | `PyFrameObject`, `f_locals` snapshot vs `localsplus`, call overhead, `inspect.stack()` performance |
| [specializing-adaptive-interpreter.md](12-expert-internals-and-edge-cases/specializing-adaptive-interpreter.md) | PEP 659 inline caching, specialized opcodes, `tp_version_tag`, deoptimization, warmup for benchmarks |
| [structural-pattern-matching.md](12-expert-internals-and-edge-cases/structural-pattern-matching.md) | Sequence/mapping/class patterns, `__match_args__`, capture vs value pattern gotcha, exhaustiveness + `Never` |
| [sys-settrace-setprofile.md](12-expert-internals-and-edge-cases/sys-settrace-setprofile.md) | Trace function protocol, coverage.py internals, pdb breakpoints, profiler overhead, `sys.monitoring` (3.12+) |

### Runnable Snippets

| File | What It Demonstrates |
|------|---------------------|
| [snippets/custom_descriptor.py](snippets/custom_descriptor.py) | Data descriptor with `__set_name__` and validation |
| [snippets/thread_safe_singleton.py](snippets/thread_safe_singleton.py) | Double-checked locking with `threading.Lock` |
| [snippets/asyncio_producer_consumer.py](snippets/asyncio_producer_consumer.py) | Bounded `asyncio.Queue` with backpressure |
| [snippets/custom_context_manager.py](snippets/custom_context_manager.py) | `@contextmanager` with cleanup and `ExitStack` |
| [snippets/plugin_loader.py](snippets/plugin_loader.py) | `entry_points`-based plugin discovery |
| [snippets/c3_linearization_demo.py](snippets/c3_linearization_demo.py) | C3 merge algorithm implemented in pure Python |

---

## How to Use This Repo

Each topic file follows a consistent structure:

1. **Concept** — concise explanation grounded in CPython internals
2. **Interview Questions** — 3–5 realistic questions with model answers
3. **Gotcha Follow-ups** — the questions interviewers use to separate real depth from memorized answers
4. **Runnable Code** — Python 3.11+ snippets, not pseudocode
5. **Under the Hood** — what actually happens in CPython (bytecode / source references)

---

## Key Differentiators at the Staff/Architect Level

Mid-level engineers know *what* Python does. Staff engineers know *why* and can make architectural decisions based on it:

- **GIL vs. free-threaded CPython (PEP 703)** — knowing the current status and what it breaks
- **Asyncio cancellation semantics** — `TaskGroup`, `shield()`, cleanup in `__aexit__`
- **Descriptor protocol** — understanding properties, classmethods as descriptors, not just using them
- **Memory model at scale** — `tracemalloc`, `objgraph`, diagnosing leaks in production
- **Import system hooks** — writing `MetaPathFinder` / `Loader`, not just using `importlib`
- **C3 MRO** — computing it by hand in a diamond hierarchy, knowing where `super()` goes wrong
- **Bytecode awareness** — reading `dis.dis()` output, understanding `RESUME`, `CACHE`, `SPECIALIZED` opcodes in 3.11+

---

*All content targets Python 3.11+ unless explicitly testing version-specific behavior.*
