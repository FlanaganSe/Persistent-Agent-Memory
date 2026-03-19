"""Performance benchmarks — 250k LOC generation and timing."""

from __future__ import annotations

import random
import time
from pathlib import Path

import structlog

from rkp.quality.types import BenchmarkResult

logger = structlog.get_logger()

# Template parts for generating realistic Python files.
_IMPORTS = [
    "from __future__ import annotations",
    "import os",
    "import sys",
    "import json",
    "import logging",
    "from pathlib import Path",
    "from dataclasses import dataclass",
    "from typing import Any",
]

_DOCSTRING = '"""Auto-generated module for benchmark testing."""'


def _generate_function(name: str, rng: random.Random) -> str:
    """Generate a realistic Python function."""
    params = ", ".join(
        f"arg_{i}: {rng.choice(['str', 'int', 'float', 'bool', 'list[str]'])}"
        for i in range(rng.randint(0, 4))
    )
    body_lines = rng.randint(3, 15)
    body = "\n".join(f"    x_{i} = {rng.randint(0, 1000)}" for i in range(body_lines))
    return_type = rng.choice(["str", "int", "float", "bool", "None"])
    return f'def {name}({params}) -> {return_type}:\n    """{name} implementation."""\n{body}\n    return None  # type: ignore[return-value]\n'


def _generate_class(name: str, rng: random.Random) -> str:
    """Generate a realistic Python class."""
    methods = rng.randint(2, 5)
    method_strs: list[str] = []
    for i in range(methods):
        method_name = f"method_{i}"
        method_strs.append(
            f'    def {method_name}(self) -> None:\n        """{method_name}."""\n        pass\n'
        )
    return f'class {name}:\n    """{name} class."""\n\n' + "\n".join(method_strs)


def generate_benchmark_repo(
    target_dir: Path,
    *,
    target_loc: int = 250_000,
    seed: int = 42,
) -> int:
    """Generate a deterministic Python repo with approximately target_loc lines.

    Returns the actual line count generated.
    """
    rng = random.Random(seed)
    total_lines = 0
    file_count = 0
    avg_lines_per_file = 100
    target_files = target_loc // avg_lines_per_file

    # Create project structure
    src_dir = target_dir / "src" / "benchmark_app"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text('"""Benchmark app."""\n')
    total_lines += 1

    tests_dir = target_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("")

    # pyproject.toml
    pyproject = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "benchmark-app"
version = "1.0.0"
requires-python = ">=3.12"

[project.scripts]
benchmark = "benchmark_app.main:run"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
"""
    (target_dir / "pyproject.toml").write_text(pyproject)
    total_lines += pyproject.count("\n")

    # README.md
    readme = """# Benchmark App

## Commands

```bash
pytest
ruff check src tests
```

## Development

Install dependencies with `pip install -e '.[dev]'`.
"""
    (target_dir / "README.md").write_text(readme)
    total_lines += readme.count("\n")

    # GitHub Actions workflow
    ci_dir = target_dir / ".github" / "workflows"
    ci_dir.mkdir(parents=True, exist_ok=True)
    ci_yml = """name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e '.[dev]'
      - run: pytest
      - run: ruff check src tests
"""
    (ci_dir / "ci.yml").write_text(ci_yml)
    total_lines += ci_yml.count("\n")

    # Generate Python files
    modules = [
        "core",
        "models",
        "services",
        "utils",
        "handlers",
        "middleware",
        "config",
        "api",
        "db",
        "cache",
    ]

    for module in modules:
        module_dir = src_dir / module
        module_dir.mkdir(exist_ok=True)
        (module_dir / "__init__.py").write_text(f'"""{module} package."""\n')
        total_lines += 1

    while file_count < target_files and total_lines < target_loc:
        module = modules[file_count % len(modules)]
        module_dir = src_dir / module
        file_name = f"mod_{file_count:04d}.py"

        lines: list[str] = list(_IMPORTS[: rng.randint(2, len(_IMPORTS))])
        lines.append("")
        lines.append(_DOCSTRING)
        lines.append("")

        # Generate functions and classes
        num_functions = rng.randint(2, 6)
        num_classes = rng.randint(0, 2)

        for i in range(num_functions):
            func_name = f"process_{module}_{file_count}_{i}"
            lines.append(_generate_function(func_name, rng))

        for i in range(num_classes):
            class_name = f"{module.capitalize()}Handler{file_count}_{i}"
            lines.append(_generate_class(class_name, rng))

        content = "\n".join(lines) + "\n"
        (module_dir / file_name).write_text(content)
        total_lines += content.count("\n")
        file_count += 1

    # Generate some test files
    test_count = max(file_count // 25, 5)
    for i in range(test_count):
        test_content = (
            f'"""Test module {i}."""\n\n\ndef test_placeholder_{i}() -> None:\n    assert True\n'
        )
        (tests_dir / f"test_mod_{i:04d}.py").write_text(test_content)
        total_lines += test_content.count("\n")

    logger.info(
        "Benchmark repo generated",
        files=file_count,
        tests=test_count,
        total_lines=total_lines,
        target_dir=str(target_dir),
    )

    return total_lines


def benchmark_extraction(
    repo_dir: Path,
    *,
    gate_seconds: float = 300.0,
) -> BenchmarkResult:
    """Run extraction on a repo and measure wall-clock time.

    Gate: must complete in < gate_seconds.
    """
    from rkp.graph.repo_graph import SqliteRepoGraph
    from rkp.indexer.orchestrator import run_extraction
    from rkp.store.claims import SqliteClaimStore
    from rkp.store.database import open_database, run_migrations

    db_path = repo_dir / ".rkp" / "local" / "rkp.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = open_database(db_path)
    run_migrations(db)
    store = SqliteClaimStore(db)
    graph = SqliteRepoGraph(db, repo_id="benchmark", branch="main")

    start = time.perf_counter()
    try:
        summary = run_extraction(
            repo_dir,
            store,
            repo_id="benchmark",
            branch="main",
            graph=graph,
        )
        elapsed = time.perf_counter() - start
    finally:
        db.close()

    passed = elapsed < gate_seconds

    logger.info(
        "Benchmark extraction complete",
        elapsed_seconds=round(elapsed, 2),
        files_parsed=summary.files_parsed,
        claims_created=summary.claims_created,
        passed=passed,
    )

    return BenchmarkResult(
        name="250k_loc_extraction",
        total_time_seconds=round(elapsed, 2),
        gate_seconds=gate_seconds,
        passed=passed,
        files_parsed=summary.files_parsed,
        claims_created=summary.claims_created,
    )
