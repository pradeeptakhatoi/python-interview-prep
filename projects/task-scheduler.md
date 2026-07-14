# Task Scheduler

## Requirements
- Build with Python 3.12+.
- Use type hints and clear module boundaries.
- Include tests for success paths, edge cases, and failures.
- Add logging and configuration where appropriate.

## Folder Structure
```text
task_scheduler/
  pyproject.toml
  src/task_scheduler/
    __init__.py
    app.py
    models.py
    services.py
  tests/
    test_app.py
```

## Implementation
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectResult:
    name: str
    status: str


def run_project(name: str) -> ProjectResult:
    return ProjectResult(name=name, status="ready")
```

## Improvements
- Add authentication or authorization if the project exposes user data.
- Add persistence with migrations.
- Add observability: structured logs, metrics, and traces.
- Add deployment documentation with Docker.

## Interview Talking Points
- Explain the architecture and trade-offs.
- Discuss failure modes and testing strategy.
- Identify bottlenecks and scaling options.
- Explain what you would improve with more time.
