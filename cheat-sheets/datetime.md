# datetime Cheat Sheet

## Essentials
| Task | Python 3.12+ Example |
|---|---|
| Define a typed function | `def add(a: int, b: int) -> int: return a + b` |
| Iterate with index | `for index, value in enumerate(values): ...` |
| Build a list | `[transform(item) for item in items]` |
| Handle missing dict key | `mapping.get(key, default)` |
| Open a file safely | `with Path(path).open() as file: ...` |

## Interview Notes
- Prefer clarity over clever one-liners.
- Know the common methods, but also know their complexity.
- Mention edge cases: empty input, invalid input, duplicates, ordering, mutation, and resource cleanup.

## Mini Example
```python
from __future__ import annotations

def first_duplicate(values: list[int]) -> int | None:
    seen: set[int] = set()
    for value in values:
        if value in seen:
            return value
        seen.add(value)
    return None
```
