# Quizzes

## Quick Diagnostic
1. What is the difference between `is` and `==`?
2. When should you use a generator?
3. How does the GIL affect CPU-bound Python code?
4. What makes a unit test reliable?
5. How would you design a rate-limited API?

## Answers
1. `is` checks object identity; `==` checks equality according to `__eq__`.
2. Use a generator for lazy iteration and reduced memory pressure.
3. The GIL limits parallel execution of Python bytecode in one process, so CPU-bound work often needs multiprocessing or native extensions.
4. Reliable tests are deterministic, isolated, clear, and assert observable behavior.
5. Use authentication identity, counters or token buckets, storage such as Redis, clear HTTP responses, and monitoring.
