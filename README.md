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

## Repository Structure

```
python-interview-prep/
├── 01-language-fundamentals/
│   ├── mutable-immutable-identity.md
│   ├── scoping-and-closures.md
│   ├── decorators.md
│   ├── descriptors.md
│   └── metaclasses.md
│
├── 02-memory-management-and-gc/        ← FULLY POPULATED ★★★
│   ├── reference-counting.md
│   ├── generational-gc.md
│   ├── reference-cycles.md
│   ├── weak-references.md
│   ├── memory-profiling.md
│   └── interning.md
│
├── 03-concurrency-models/              ← FULLY POPULATED ★★★
│   ├── gil-internals.md
│   ├── threading.md
│   ├── multiprocessing.md
│   ├── concurrent-futures.md
│   ├── asyncio-internals.md
│   ├── mixing-paradigms.md
│   └── gil-removal-pep703.md
│
├── 04-data-structures-and-performance/
│   ├── list-dict-set-internals.md
│   ├── time-complexity.md
│   ├── slots.md
│   ├── choosing-data-structures.md
│   └── hashability.md
│
├── 05-typing-and-static-analysis/
│   ├── generics-typevar-protocol.md
│   ├── variance.md
│   ├── runtime-vs-static-checking.md
│   ├── structural-vs-nominal.md
│   └── typing-pitfalls.md
│
├── 06-error-handling-and-context-managers/
│   ├── exception-chaining.md
│   ├── exception-hierarchies.md
│   ├── context-managers.md
│   └── contextvars.md
│
├── 07-packaging-and-environments/
│   ├── import-system-internals.md
│   ├── virtual-environments.md
│   ├── distributable-packages.md
│   └── namespace-packages.md
│
├── 08-testing-and-profiling/
│   ├── pytest-internals.md
│   ├── profiling.md
│   └── benchmarking.md
│
├── 09-c-extensions-and-interop/
│   ├── when-to-extend.md
│   ├── buffer-protocol.md
│   └── gil-release.md
│
├── 10-architecture-and-design-patterns/
│   ├── package-boundaries.md
│   ├── plugin-architectures.md
│   ├── dependency-injection.md
│   ├── async-event-driven.md
│   └── versioning-deprecation.md
│
├── 11-common-pitfalls/
│   ├── mutable-defaults-late-binding.md
│   ├── mutating-while-iterating.md
│   ├── floating-point.md
│   ├── inheritance-vs-composition.md
│   └── accidental-on2.md
│
├── 12-expert-internals-and-edge-cases/  ← FULLY POPULATED ★☆☆
│   ├── bytecode-and-dis.md
│   ├── function-calls-internals.md
│   ├── specializing-adaptive-interpreter.md
│   ├── coroutine-internals.md
│   ├── c3-linearization-mro.md
│   ├── abstract-base-classes-protocols.md
│   ├── sys-settrace-setprofile.md
│   ├── custom-import-hooks.md
│   └── structural-pattern-matching.md
│
└── snippets/                           ← Copy-paste ready code
    ├── custom_descriptor.py
    ├── thread_safe_singleton.py
    ├── asyncio_producer_consumer.py
    ├── custom_context_manager.py
    ├── plugin_loader.py
    └── c3_linearization_demo.py
```

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
