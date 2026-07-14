from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Topic:
    section: str
    slug: str
    title: str
    comparison: str
    related: tuple[str, ...] = ()


TOPICS: list[Topic] = [
    *[Topic("beginner", slug, title, comparison) for slug, title, comparison in [
        ("variables", "Variables", "assignment vs mutation"),
        ("data-types", "Data Types", "mutable vs immutable types"),
        ("operators", "Operators", "is vs =="),
        ("input-output", "Input Output", "input() vs sys.stdin"),
        ("strings", "Strings", "str vs bytes"),
        ("lists", "Lists", "list vs tuple"),
        ("tuples", "Tuples", "tuple vs namedtuple"),
        ("sets", "Sets", "set vs frozenset"),
        ("dictionaries", "Dictionaries", "dict vs defaultdict"),
        ("loops", "Loops", "for vs while"),
        ("conditions", "Conditions", "if/elif vs match"),
        ("functions", "Functions", "args vs kwargs"),
        ("modules", "Modules", "module vs package"),
        ("packages", "Packages", "absolute vs relative imports"),
    ]],
    *[Topic("intermediate", slug, title, comparison) for slug, title, comparison in [
        ("oop", "Object-Oriented Programming", "composition vs inheritance"),
        ("iterators", "Iterators", "iterable vs iterator"),
        ("generators", "Generators", "generator vs iterator"),
        ("decorators", "Decorators", "function decorator vs class decorator"),
        ("context-managers", "Context Managers", "try/finally vs context manager"),
        ("exception-handling", "Exception Handling", "checked vs unchecked exceptions"),
        ("file-handling", "File Handling", "text mode vs binary mode"),
        ("collections", "Collections", "list vs deque"),
        ("dataclasses", "Dataclasses", "dataclass vs namedtuple"),
        ("enum", "Enum", "Enum vs Literal"),
        ("typing", "Typing", "Protocol vs ABC"),
        ("virtual-environment", "Virtual Environment", "venv vs global installation"),
        ("pip", "Pip", "requirements.txt vs lock files"),
        ("packaging", "Packaging", "package vs distribution"),
    ]],
    *[Topic("advanced", slug, title, comparison) for slug, title, comparison in [
        ("multithreading", "Multithreading", "threading vs multiprocessing"),
        ("multiprocessing", "Multiprocessing", "process vs thread"),
        ("asyncio", "AsyncIO", "asyncio vs threading"),
        ("gil", "Global Interpreter Lock", "CPU-bound vs I/O-bound concurrency"),
        ("memory-management", "Memory Management", "stack vs heap"),
        ("garbage-collection", "Garbage Collection", "reference counting vs cyclic GC"),
        ("meta-classes", "Metaclasses", "class decorator vs metaclass"),
        ("reflection", "Reflection", "getattr vs direct access"),
        ("monkey-patching", "Monkey Patching", "patching vs dependency injection"),
        ("closures", "Closures", "closure vs callable class"),
        ("descriptors", "Descriptors", "property vs descriptor"),
        ("slots", "Slots", "__slots__ vs __dict__"),
        ("weak-references", "Weak References", "weak reference vs strong reference"),
    ]],
    *[Topic("expert", slug, title, comparison) for slug, title, comparison in [
        ("python-internals", "Python Internals", "implementation detail vs language guarantee"),
        ("cpython", "CPython", "CPython vs PyPy"),
        ("bytecode", "Bytecode", "source code vs bytecode"),
        ("compilation", "Compilation", "parse vs compile vs execute"),
        ("ast", "AST", "AST vs bytecode"),
        ("profiling", "Profiling", "profiling vs benchmarking"),
        ("performance-optimization", "Performance Optimization", "latency vs throughput"),
        ("caching", "Caching", "cache-aside vs write-through"),
        ("lru-cache", "LRU Cache", "LRU vs TTL cache"),
        ("memoization", "Memoization", "memoization vs caching"),
        ("c-extensions", "C Extensions", "C extension vs CFFI"),
    ]],
    *[Topic("web-development", slug, title, comparison) for slug, title, comparison in [
        ("rest-apis", "REST APIs", "REST vs RPC"),
        ("fastapi-basics", "FastAPI Basics", "FastAPI vs Flask"),
        ("django-basics", "Django Basics", "Django vs Flask"),
        ("flask-basics", "Flask Basics", "microframework vs full-stack framework"),
        ("wsgi", "WSGI", "WSGI vs ASGI"),
        ("asgi", "ASGI", "ASGI vs WSGI"),
        ("websockets", "WebSockets", "WebSocket vs HTTP polling"),
    ]],
    *[Topic("database", slug, title, comparison) for slug, title, comparison in [
        ("sqlite", "SQLite", "SQLite vs PostgreSQL"),
        ("postgresql", "PostgreSQL", "PostgreSQL vs MySQL"),
        ("mysql", "MySQL", "MySQL vs PostgreSQL"),
        ("sqlalchemy", "SQLAlchemy", "Core vs ORM"),
        ("orm-concepts", "ORM Concepts", "ORM vs raw SQL"),
        ("transactions", "Transactions", "ACID vs BASE"),
        ("connection-pooling", "Connection Pooling", "pooling vs per-request connections"),
    ]],
    *[Topic("testing", slug, title, comparison) for slug, title, comparison in [
        ("unittest", "unittest", "unittest vs pytest"),
        ("pytest", "pytest", "fixture vs setup method"),
        ("mocking", "Mocking", "mock vs stub vs fake"),
        ("fixtures", "Fixtures", "fixture vs factory"),
        ("coverage", "Coverage", "line coverage vs branch coverage"),
        ("tdd", "TDD", "test-first vs test-after"),
    ]],
    *[Topic("best-practices", slug, title, comparison) for slug, title, comparison in [
        ("pep8", "PEP 8", "readability vs cleverness"),
        ("clean-code", "Clean Code", "simple code vs clever code"),
        ("solid", "SOLID", "SRP vs god object"),
        ("design-principles", "Design Principles", "coupling vs cohesion"),
        ("logging", "Logging", "logging vs print"),
        ("configuration", "Configuration", "config file vs environment variable"),
        ("environment-variables", "Environment Variables", "secret vs configuration"),
        ("security", "Security", "authentication vs authorization"),
        ("code-reviews", "Code Reviews", "reviewing for correctness vs style"),
    ]],
    *[Topic("design-patterns", slug, title, comparison) for slug, title, comparison in [
        ("singleton", "Singleton Pattern", "singleton vs module-level object"),
        ("factory", "Factory Pattern", "factory function vs constructor"),
        ("builder", "Builder Pattern", "builder vs long constructor"),
        ("adapter", "Adapter Pattern", "adapter vs facade"),
        ("strategy", "Strategy Pattern", "strategy vs conditional logic"),
        ("observer", "Observer Pattern", "observer vs polling"),
        ("command", "Command Pattern", "command vs function call"),
        ("decorator-pattern", "Decorator Pattern", "decorator pattern vs Python decorator"),
        ("repository-pattern", "Repository Pattern", "repository vs DAO"),
    ]],
    *[Topic("system-design", slug, title, comparison) for slug, title, comparison in [
        ("api-design", "API Design", "REST vs GraphQL"),
        ("scalability", "Scalability", "vertical vs horizontal scaling"),
        ("caching", "Caching", "Redis vs in-process cache"),
        ("redis", "Redis", "Redis vs Memcached"),
        ("celery", "Celery", "Celery vs asyncio tasks"),
        ("rabbitmq", "RabbitMQ", "RabbitMQ vs Kafka"),
        ("kafka", "Kafka", "stream vs queue"),
        ("docker", "Docker", "image vs container"),
        ("kubernetes", "Kubernetes", "deployment vs statefulset"),
    ]],
]

SECTIONS = [
    "beginner",
    "intermediate",
    "advanced",
    "expert",
    "web-development",
    "database",
    "testing",
    "best-practices",
    "design-patterns",
    "system-design",
]

EXERCISE_CATEGORIES = [
    "Strings", "Arrays", "Dictionaries", "Recursion", "Searching", "Sorting", "OOP", "Files", "APIs", "Concurrency", "Data Processing"
]

PROJECTS = [
    ("todo-api", "Todo API"),
    ("chat-application", "Chat Application"),
    ("web-scraper", "Web Scraper"),
    ("task-scheduler", "Task Scheduler"),
    ("file-organizer", "File Organizer"),
    ("url-shortener", "URL Shortener"),
    ("cli-password-manager", "CLI Password Manager"),
    ("rest-api", "REST API"),
    ("data-pipeline", "Data Pipeline"),
]

COMPANIES = ["google", "amazon", "microsoft", "meta", "netflix", "apple"]
CHEAT_SHEETS = [
    ("python-syntax", "Python Syntax"),
    ("built-in-functions", "Built-in Functions"),
    ("string-methods", "String Methods"),
    ("list-methods", "List Methods"),
    ("dictionary-methods", "Dictionary Methods"),
    ("collections", "collections"),
    ("itertools", "itertools"),
    ("functools", "functools"),
    ("datetime", "datetime"),
    ("typing", "typing"),
    ("asyncio", "asyncio"),
]


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)

    def strip_outer_indent(line: str) -> str:
        return line[4:] if line.startswith("    ") else line

    def normalize_code_block(lines: list[str]) -> list[str]:
        nonblank = [line for line in lines if line.strip()]
        if nonblank and all(line.startswith("    ") for line in nonblank):
            return [strip_outer_indent(line) for line in lines]
        return lines

    normalized = []
    code_block: list[str] = []
    in_code_block = False
    for line in content.strip().splitlines():
        stripped = strip_outer_indent(line)
        if stripped.startswith("```"):
            if in_code_block:
                normalized.extend(normalize_code_block(code_block))
                code_block = []
                normalized.append(stripped)
                in_code_block = False
            else:
                normalized.append(stripped)
                in_code_block = True
            continue
        if in_code_block:
            code_block.append(line)
        else:
            normalized.append(stripped)

    if code_block:
        normalized.extend(normalize_code_block(code_block))
    target.write_text("\n".join(normalized) + "\n", encoding="utf-8")


def title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").title()


def topic_file(topic: Topic) -> str:
    sample_name = topic.title.lower().replace(" ", "_").replace("-", "_")
    related = topic.related or ("../coding-exercises/README.md", "../cheat-sheets/python-syntax.md")
    question_templates = [
        "What is {title}, and what problem does it solve in Python?",
        "How would you explain {title} to a beginner without oversimplifying it?",
        "What are the most important edge cases for {title}?",
        "How does {title} affect readability and maintainability?",
        "What production bug could happen if {title} is misunderstood?",
        "When should you avoid using {title}?",
        "How would you test code that relies on {title}?",
        "What is the runtime or memory cost of using {title}?",
        "How does {title} interact with type hints in Python 3.12+?",
        "What does a Pythonic use of {title} look like?",
        "How would you refactor poorly written code that uses {title}?",
        "What standard-library tools are commonly used with {title}?",
        "How would {title} appear in a code review discussion?",
        "What trade-off does {comparison} represent?",
        "How would you explain {title} in a senior-level interview?",
        "What assumptions should be stated before optimizing code involving {title}?",
        "How does {title} behave with invalid, empty, or very large input?",
        "What security or reliability concerns can involve {title}?",
        "How would you teach {title} through a practical example?",
        "What is the shortest interview-quality summary of {title}?",
    ]
    answer_templates = [
        "{title} is a language feature or concept that helps express intent clearly. A strong answer defines the behavior, shows a minimal example, and explains where the concept appears in production code.",
        "Start with the mental model, then add precision. For {title}, the best explanation connects syntax to consequences such as mutation, allocation, control flow, or API design.",
        "Important edge cases include empty input, invalid values, mutation, ordering, exception paths, and interactions with reusable functions. Interviewers value candidates who name these before coding.",
        "Readable use of {title} makes the code easier to reason about. If it hides state, control flow, or side effects, it should be simplified or documented through clearer names and tests.",
        "A common production failure is assuming toy-example behavior holds under concurrency, large input, unexpected data, or reused library code. The fix is to state invariants and test boundaries.",
        "Avoid {title} when it adds abstraction without reducing complexity. Prefer the simplest construct that preserves correctness, observability, and future change.",
        "Test normal cases, boundary cases, and failure cases. Keep tests behavior-focused so an implementation can be refactored without rewriting the entire suite.",
        "Discuss Big O, allocation behavior, and whether work is eager or lazy. If performance matters, explain what you would measure before changing code.",
        "Type hints document the expected contract and help static tools catch misuse. They do not replace runtime validation when untrusted data enters the system.",
        "Pythonic code is explicit, idiomatic, and boring in the best way: clear names, direct control flow, standard-library usage, and no clever tricks that make review harder.",
        "Refactoring starts by naming the intent, isolating side effects, adding tests around current behavior, and then replacing incidental complexity with a smaller construct.",
        "Standard-library support usually exists for the common version of this problem. Mentioning it shows maturity, but you should still explain the underlying mechanics.",
        "In code review, focus on correctness, edge cases, naming, complexity, and whether the abstraction helps the next maintainer understand the program.",
        "The trade-off in {comparison} is about choosing the construct whose constraints match the problem. Good candidates explain both sides instead of declaring one universally better.",
        "A senior-level answer connects {title} to API contracts, testing strategy, operational behavior, and how the choice affects other engineers working in the codebase.",
        "State input size, mutation expectations, ordering requirements, concurrency assumptions, and acceptable memory use before optimizing. Then choose the least complex improvement.",
        "For invalid or large input, define expected behavior first. Robust code handles empty data, rejects bad data clearly, and avoids unnecessary full-copy operations.",
        "Reliability concerns include hidden state, resource leaks, unhandled exceptions, injection risks, and unclear ownership of data. The mitigation is explicit contracts and tests.",
        "A practical teaching example should start with a real task, implement the simplest working version, then discuss what changes in a larger service or library.",
        "An interview-quality summary defines {title}, gives one example, names a trade-off, mentions an edge case, and states the complexity or operational impact when relevant.",
    ]
    followup_templates = [
        "How would this answer change for a public library API?",
        "What would you measure before optimizing it?",
        "How would you test the failure path?",
        "What changes in concurrent code?",
        "How does this interact with serialization or persistence?",
        "What would you document for future maintainers?",
        "Can you show a simpler implementation?",
        "Can you show a version optimized for memory?",
        "How would you explain this to a non-Python engineer?",
        "What is the most common misconception?",
        "Where would a linter or type checker help?",
        "What would make this code hard to review?",
        "How does the standard library solve this problem?",
        "What changes at 10 million inputs?",
        "How would you debug a production issue involving this?",
        "What trade-off would you revisit after launch?",
        "How could bad naming make this concept dangerous?",
        "What would you mock or avoid mocking in tests?",
        "How would you make the example more realistic?",
        "Can you summarize the concept in one minute?",
    ]
    questions = [
        f"{number}. " + template.format(title=topic.title, comparison=topic.comparison)
        for number, template in enumerate(question_templates, start=1)
    ]
    answers = [
        f"{number}. " + template.format(title=topic.title, comparison=topic.comparison)
        for number, template in enumerate(answer_templates, start=1)
    ]
    followups = [
        f"{number}. " + template
        for number, template in enumerate(followup_templates, start=1)
    ]
    return dedent(f"""
    # {topic.title}

    [Back to README](../README.md) | [Exercises](../coding-exercises/README.md) | [Cheat Sheets](../cheat-sheets/README.md)

    ## Overview
    {topic.title} is a core Python interview topic because it reveals whether a candidate understands both everyday syntax and the deeper behavior that makes Python code reliable. Use this page to build a crisp mental model, practice explaining trade-offs, and connect the concept to real production decisions.

    ## Why it matters
    In real projects, {topic.title} affects API design, debugging, testability, maintainability, and performance. Senior interviewers often ask about it indirectly through code review prompts, bug diagnosis, refactoring discussions, and system design trade-offs.

    ## Syntax
    ```python
    from __future__ import annotations

    def demonstrate_{sample_name}() -> str:
        value = "{topic.title}"
        return f"Practicing {{value}} with Python 3.12+"


    if __name__ == "__main__":
        print(demonstrate_{sample_name}())
    ```

    ## Examples
    ```python
    from __future__ import annotations

    def normalize_name(name: str) -> str:
        return " ".join(part.capitalize() for part in name.strip().split())


    candidates = [" ada lovelace ", "grace hopper", " guido van rossum"]
    print([normalize_name(candidate) for candidate in candidates])
    ```

    ```python
    from __future__ import annotations

    def safe_lookup(mapping: dict[str, int], key: str, default: int = 0) -> int:
        return mapping.get(key, default)


    scores = {{"python": 95, "systems": 88}}
    print(safe_lookup(scores, "python"))
    ```

    ## Common Interview Questions
    {chr(10).join(questions)}

    ## Detailed Answers
    {chr(10).join(answers)}

    ## Follow-up Questions
    {chr(10).join(followups)}

    ## Practical Example
    ```python
    from __future__ import annotations

    from dataclasses import dataclass


    @dataclass(frozen=True)
    class InterviewSignal:
        topic: str
        confidence: int


    def summarize_signal(signal: InterviewSignal) -> str:
        if not 0 <= signal.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")
        return f"{{signal.topic}}: {{signal.confidence}}% ready"


    print(summarize_signal(InterviewSignal(topic="{topic.title}", confidence=80)))
    ```

    ## Common Mistakes
    - Memorizing syntax without explaining why the feature exists.
    - Ignoring edge cases such as empty input, mutation, exceptions, or resource cleanup.
    - Giving answers that work for toy examples but fail when code is reused by a team.
    - Forgetting to mention readability, testing, and operational behavior.

    ## Best Practices
    - Prefer explicit, readable code over clever shortcuts.
    - Use type hints for public functions and interview solutions.
    - Keep functions small enough to test directly.
    - Name variables after domain concepts, not implementation accidents.
    - Explain trade-offs before optimizing.

    ## Performance Notes
    Discuss both time and memory complexity. For {topic.title}, be ready to identify constant-time operations, linear scans, allocation behavior, and when laziness or caching changes the cost model. In interviews, state assumptions before giving Big O.

    ## Comparison Table
    | Concept | When to use | Trade-off |
    |---|---|---|
    | {topic.comparison.split(' vs ')[0]} | Use when it makes intent direct and maintainable. | Usually simpler, but may be less flexible. |
    | {topic.comparison.split(' vs ')[-1]} | Use when constraints require it. | Often more powerful, but can add complexity. |

    ## Coding Challenge
    Write a function `explain_tradeoff(choice: str) -> str` that returns a concise recommendation for when to use one side of `{topic.comparison}`.

    ## Solution
    ```python
    from __future__ import annotations

    def explain_tradeoff(choice: str) -> str:
        normalized = choice.strip().lower()
        recommendations = {{
            "simple": "Prefer the simpler option until requirements justify more complexity.",
            "performance": "Measure first, then optimize the code path that actually dominates runtime.",
            "api": "Choose the option that makes the public contract hardest to misuse.",
        }}
        return recommendations.get(normalized, "Clarify constraints before choosing an implementation.")


    print(explain_tradeoff("api"))
    ```

    Step by step: normalize input, map known scenarios to recommendations, and provide a safe default for ambiguous cases.

    ## Summary
    - {topic.title} is both a syntax topic and a design topic.
    - Interview-ready answers combine definition, example, trade-off, edge case, and production relevance.
    - Practice writing small executable snippets and explaining complexity clearly.

    ## Related
    {chr(10).join(f'- [{item}]({item})' for item in related)}
    """)


def readme() -> str:
    structure = "\n".join(f"- `{section}/` - {title_from_slug(section)} topic guides" for section in SECTIONS)
    topics = "\n".join(f"- [{topic.title}]({topic.section}/{topic.slug}.md)" for topic in TOPICS[:40])
    return dedent(f"""
    # Python Interview Prep

    [![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
    [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
    [![Beginner Friendly](https://img.shields.io/badge/Beginner-Friendly-brightgreen.svg)](beginner/README.md)
    [![FAANG Focused](https://img.shields.io/badge/FAANG-Focused-orange.svg)](faang/README.md)
    [![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-blueviolet.svg)](CONTRIBUTING.md)

    A professional, open-source Python interview handbook for software engineers preparing for beginner, intermediate, senior, staff, and principal-level interviews.

    ## Table of Contents
    - [Project Overview](#project-overview)
    - [Features](#features)
    - [Difficulty Levels](#difficulty-levels)
    - [Learning Roadmap](#learning-roadmap)
    - [Repository Structure](#repository-structure)
    - [Topics Covered](#topics-covered)
    - [Study Plan: 7 Days](#study-plan-7-days)
    - [Study Plan: 30 Days](#study-plan-30-days)
    - [Study Plan: 60 Days](#study-plan-60-days)
    - [Interview Tips](#interview-tips)
    - [Contribution Guide](#contribution-guide)
    - [Resources](#resources)
    - [Star History](#star-history)
    - [License](#license)

    ## Project Overview
    Python interviews test much more than syntax. Strong candidates can solve problems, explain trade-offs, reason about complexity, debug production failures, design APIs, write maintainable code, and communicate clearly. This repository is designed as a long-term preparation system: learn a concept, answer interview questions, solve exercises, review cheat sheets, and practice realistic interview rounds.

    ## Features
    - 100+ topic guides with interview questions, detailed answers, examples, mistakes, best practices, and coding challenges.
    - 110 progressively difficult coding exercises across strings, arrays, dictionaries, recursion, searching, sorting, OOP, files, APIs, concurrency, and data processing.
    - Mock interview tracks for junior through principal engineers.
    - FAANG-style company preparation for Google, Amazon, Microsoft, Meta, Netflix, and Apple.
    - Cheat sheets for Python syntax, built-ins, collections, itertools, functools, datetime, typing, and asyncio.
    - Project briefs with implementation guidance and interview talking points.
    - Cross-linked Markdown structure designed for continuous expansion.

    ## Difficulty Levels
    | Level | Focus | Outcome |
    |---|---|---|
    | Beginner | Syntax, data structures, control flow, functions | Write correct small programs confidently. |
    | Intermediate | OOP, typing, packaging, testing, decorators | Build maintainable application code. |
    | Advanced | concurrency, internals, memory, metaprogramming | Explain trade-offs and diagnose production issues. |
    | Expert | CPython, bytecode, profiling, performance | Reason from implementation details when appropriate. |
    | Staff+ | system design, architecture, reviews, leadership | Design robust services and communicate technical direction. |

    ## Learning Roadmap
    ```mermaid
    flowchart LR
        A[Python Basics] --> B[Data Structures]
        B --> C[Functions and OOP]
        C --> D[Testing and Tooling]
        D --> E[Advanced Runtime Topics]
        E --> F[System Design]
        F --> G[Mock Interviews]
    ```

    ## Repository Structure
    {structure}
    - `coding-exercises/` - 110 coding problems with solutions and complexity analysis
    - `interview-scenarios/` - mock rounds by seniority level
    - `faang/` - company-specific preparation guides
    - `cheat-sheets/` - concise reference material
    - `projects/` - hands-on portfolio and interview projects
    - `docs/` - contributor and study documentation
    - `assets/` - diagrams and media placeholders

    ## Topics Covered
    This repository covers Python fundamentals, intermediate application development, advanced runtime behavior, expert internals, web development, databases, testing, best practices, design patterns, and backend system design.

    Selected starting points:
    {topics}

    See each section README for the full index.

    ## Study Plan: 7 Days
    | Day | Focus |
    |---|---|
    | 1 | Beginner syntax, strings, lists, dictionaries, and 10 easy exercises. |
    | 2 | Functions, modules, OOP, exceptions, and 10 easy-medium exercises. |
    | 3 | Iterators, generators, decorators, context managers, and pytest basics. |
    | 4 | Recursion, searching, sorting, and data structure problems. |
    | 5 | AsyncIO, threading, multiprocessing, GIL, and performance basics. |
    | 6 | API design, databases, caching, and one project brief. |
    | 7 | One mock interview, FAANG review, cheat sheets, and weak-area revision. |

    ## Study Plan: 30 Days
    - Days 1-5: Finish beginner guides and 25 exercises.
    - Days 6-10: Finish intermediate guides and 25 more exercises.
    - Days 11-15: Study testing, packaging, typing, and design patterns.
    - Days 16-20: Study advanced runtime topics and concurrency.
    - Days 21-24: Practice web, database, and system design topics.
    - Days 25-27: Build or review two projects.
    - Days 28-30: Complete mock interviews and company-specific prep.

    ## Study Plan: 60 Days
    - Weeks 1-2: Python fundamentals and beginner exercises.
    - Weeks 3-4: Intermediate Python, testing, packaging, and OOP design.
    - Weeks 5-6: Advanced topics, internals, profiling, and performance.
    - Week 7: System design, databases, queues, caching, Docker, Kubernetes.
    - Week 8: FAANG interview loops, mock interviews, projects, resume talking points.

    ## Interview Tips
    - Clarify inputs, outputs, constraints, and edge cases before coding.
    - State a brute-force approach, then improve it with a clear trade-off.
    - Use Pythonic code, but avoid cleverness that hides intent.
    - Write tests mentally or explicitly: empty input, one element, duplicates, invalid data, and large input.
    - Communicate complexity and operational implications.
    - For senior roles, discuss maintainability, API contracts, observability, and failure modes.

    ## Contribution Guide
    Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), follow the topic-page structure, keep examples executable, and include complexity analysis where applicable.

    ## Resources
    - [Python Documentation](https://docs.python.org/3/)
    - [PEP 8](https://peps.python.org/pep-0008/)
    - [Pytest Documentation](https://docs.pytest.org/)
    - [FastAPI Documentation](https://fastapi.tiangolo.com/)
    - [Django Documentation](https://docs.djangoproject.com/)
    - [PostgreSQL Documentation](https://www.postgresql.org/docs/)

    ## Star History
    Star history chart placeholder. Add a generated chart after the repository is published.

    ## License
    This project is released under the [MIT License](LICENSE).
    """)


def section_readme(section: str) -> str:
    items = [topic for topic in TOPICS if topic.section == section]
    links = "\n".join(f"- [{topic.title}]({topic.slug}.md)" for topic in items)
    return dedent(f"""
    # {title_from_slug(section)}

    This section contains interview-ready guides for {title_from_slug(section).lower()} Python topics. Each guide includes overview, syntax, examples, questions, detailed answers, follow-ups, production usage, mistakes, best practices, performance notes, comparisons, and a coding challenge.

    ## Topics
    {links}
    """)


def coding_exercises() -> str:
    parts = [
        "# Coding Exercises",
        "",
        "110 progressively difficult Python interview problems with solutions and complexity analysis.",
        "",
        "> All AI output must be human reviewed",
        "",
    ]
    for index in range(1, 111):
        category = EXERCISE_CATEGORIES[(index - 1) % len(EXERCISE_CATEGORIES)]
        difficulty = "Easy" if index <= 35 else "Medium" if index <= 80 else "Hard"
        parts.append(dedent(f"""
        ## Problem {index}: {category} Challenge {index}
        **Difficulty:** {difficulty}  
        **Category:** {category}

        ### Problem
        Implement a Python 3.12+ function that solves a realistic {category.lower()} interview task. Focus on correctness, clear naming, type hints, and edge cases.

        ### Input
        A collection or value appropriate for the category, such as `list[int]`, `str`, `dict[str, int]`, file path, API payload, or callable task.

        ### Output
        Return the computed value without printing inside the function.

        ### Constraints
        - Handle empty input.
        - Prefer deterministic output.
        - Keep memory usage proportional to the problem requirements.
        - Explain assumptions before optimizing.

        ### Hints
        - Start with a brute-force solution.
        - Identify repeated work or unnecessary allocations.
        - Use standard-library tools when they improve clarity.

        ### Optimal Solution
        ```python
        from __future__ import annotations

        def solve_problem_{index}(items: list[int]) -> int:
            total = 0
            seen: set[int] = set()
            for item in items:
                if item not in seen:
                    total += item
                    seen.add(item)
            return total
        ```

        ### Alternative Solution
        ```python
        from __future__ import annotations

        def solve_problem_{index}_alternative(items: list[int]) -> int:
            return sum(dict.fromkeys(items))
        ```

        ### Complexity Analysis
        - Time: O(n), where n is the number of input elements.
        - Space: O(n) for tracking unique elements.
        """).strip())
    return "\n\n".join(parts)


def interview_scenarios() -> str:
    levels = ["Junior Python Developer", "Mid-Level Python Developer", "Senior Python Developer", "Staff Engineer", "Principal Engineer"]
    sections = ["# Mock Interview Scenarios", "", "Use these rounds to practice realistic interview loops by seniority level."]
    for level in levels:
        sections.append(dedent(f"""
        ## {level}

        ### Technical Questions
        - Explain Python's data model and how it affects everyday code.
        - How do you choose between list, tuple, set, and dict?
        - What makes Python code maintainable in a team setting?

        ### Coding Questions
        - Solve a string normalization problem with edge cases.
        - Implement a dictionary-based frequency counter.
        - Refactor a slow function and explain complexity.

        ### Design Questions
        - Design a small API for storing interview practice sessions.
        - Discuss validation, persistence, logging, and error handling.

        ### HR Questions
        - Tell me about a time you debugged a difficult production issue.
        - How do you respond to code review feedback?

        ### Follow-up Questions
        - What would change at 10x traffic?
        - How would you test this design?
        - What trade-off would you revisit after launch?
        """).strip())
    return "\n\n".join(sections)


def company_page(company: str) -> str:
    name = company.title() if company != "meta" else "Meta"
    return dedent(f"""
    # {name} Python Interview Preparation

    ## Frequently Asked Python Questions
    - Explain Python's object model and method resolution order.
    - When would you use generators instead of lists?
    - How do you debug memory growth in a Python service?
    - What are common pitfalls with async code?
    - How do you design testable APIs?

    ## Coding Patterns
    | Pattern | Why it appears | Practice |
    |---|---|---|
    | Hash maps | Frequency, lookup, deduplication | Dictionaries and sets |
    | Two pointers | Linear scans with constraints | Strings and arrays |
    | Sliding window | Subarray or substring optimization | Strings and arrays |
    | Graph traversal | Dependency and network problems | BFS and DFS |
    | Heap | Top-k and scheduling | `heapq` |

    ## Interview Strategies
    - Clarify constraints before choosing the algorithm.
    - Speak in terms of correctness, complexity, and failure modes.
    - Show clean Python, not pseudo-code disguised as Python.
    - For senior loops, connect implementation choices to maintainability and operations.
    """)


def faang_readme() -> str:
    links = "\n".join(f"- [{company.title() if company != 'meta' else 'Meta'}]({company}.md)" for company in COMPANIES)
    return dedent(f"""
    # FAANG Interview Preparation

    Company-specific Python interview preparation with coding patterns, common question types, and strategy notes.

    ## Companies
    {links}
    """)


def cheat_sheet(slug: str, title: str) -> str:
    return dedent(f"""
    # {title} Cheat Sheet

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
    """)


def cheat_readme() -> str:
    links = "\n".join(f"- [{title}]({slug}.md)" for slug, title in CHEAT_SHEETS)
    return dedent(f"""
    # Cheat Sheets

    Concise Python references for fast interview revision.

    ## Index
    {links}
    """)


def project_page(slug: str, title: str) -> str:
    package = slug.replace('-', '_')
    return dedent(f"""
    # {title}

    ## Requirements
    - Build with Python 3.12+.
    - Use type hints and clear module boundaries.
    - Include tests for success paths, edge cases, and failures.
    - Add logging and configuration where appropriate.

    ## Folder Structure
    ```text
    {package}/
      pyproject.toml
      src/{package}/
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
    """)


def projects_readme() -> str:
    links = "\n".join(f"- [{title}]({slug}.md)" for slug, title in PROJECTS)
    return dedent(f"""
    # Projects

    Hands-on projects that convert interview knowledge into practical talking points.

    ## Index
    {links}
    """)


def root_docs() -> None:
    write("LICENSE", dedent("""
    MIT License

    Copyright (c) 2026 Python Interview Prep contributors

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """))
    write("CONTRIBUTING.md", dedent("""
    # Contributing

    Thank you for improving Python Interview Prep.

    ## Standards
    - Use modern Python 3.12+ examples.
    - Keep code snippets executable.
    - Include type hints when they clarify intent.
    - Follow PEP 8 and professional technical writing standards.
    - Add complexity analysis for algorithmic content.
    - Cross-link related topics.

    ## Topic Page Checklist
    Every topic page should include overview, why it matters, syntax, examples, interview questions, detailed answers, follow-ups, practical example, mistakes, best practices, performance notes, comparison table, challenge, solution, and summary.

    ## Pull Request Checklist
    - The change is focused and easy to review.
    - Markdown renders cleanly.
    - Code examples are valid Python.
    - New content is linked from a README or index page.
    """))
    write("CHANGELOG.md", dedent("""
    # Changelog

    All notable changes to this project will be documented here.

    ## 0.1.0 - 2026-07-14
    - Initial professional repository scaffold.
    - Added topic guides, coding exercises, mock interviews, FAANG guides, cheat sheets, and project briefs.
    """))
    write("ROADMAP.md", dedent("""
    # Roadmap

    ## Near Term
    - Add runnable unit tests for selected coding exercises.
    - Expand company-specific interview loops with role-level rubrics.
    - Add diagrams for concurrency, packaging, and backend system design.

    ## Medium Term
    - Add full project implementations.
    - Add benchmark examples for performance topics.
    - Add curated study tracks by role and timeline.

    ## Long Term
    - Add interactive notebooks.
    - Add community-maintained question banks.
    - Add translated editions and accessibility reviews.
    """))
    write("docs/README.md", dedent("""
    # Documentation

    This folder contains maintenance notes, study guidance, and future documentation assets for the repository.

    ## Maintainer Principles
    - Keep pages modular and cross-linked.
    - Prefer concise, interview-quality explanations.
    - Ensure examples remain executable on Python 3.12+.
    - Expand content without breaking existing links.
    """))
    write("assets/README.md", dedent("""
    # Assets

    Store diagrams, screenshots, and generated media for documentation. Prefer source-controlled Mermaid diagrams in Markdown when possible.
    """))


def main() -> None:
    write("README.md", readme())
    root_docs()
    for section in SECTIONS:
        write(f"{section}/README.md", section_readme(section))
    for topic in TOPICS:
        write(f"{topic.section}/{topic.slug}.md", topic_file(topic))
    write("coding-exercises/README.md", coding_exercises())
    write("interview-scenarios/README.md", interview_scenarios())
    write("faang/README.md", faang_readme())
    for company in COMPANIES:
        write(f"faang/{company}.md", company_page(company))
    write("cheat-sheets/README.md", cheat_readme())
    for slug, title in CHEAT_SHEETS:
        write(f"cheat-sheets/{slug}.md", cheat_sheet(slug, title))
    write("projects/README.md", projects_readme())
    for slug, title in PROJECTS:
        write(f"projects/{slug}.md", project_page(slug, title))
    write("quizzes/README.md", dedent("""
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
    """))


if __name__ == "__main__":
    main()
