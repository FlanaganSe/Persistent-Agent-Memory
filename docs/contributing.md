# Contributing

## Development Setup

```bash
git clone https://github.com/seanflanagan/repo-knowledge-plane.git
cd repo-knowledge-plane
uv pip install ".[dev]"
```

Requirements: Python 3.12+, uv, Git.

## Running Checks

```bash
# Individual sessions
nox -s lint        # ruff check + ruff format --check
nox -s typecheck   # pyright strict mode
nox -s test        # pytest (1044 tests)
nox -s quality     # quality harness
nox -s docs        # mkdocs build --strict

# All CI checks
nox -s ci          # lint + typecheck + test
```

Or directly:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright
uv run pytest
```

## Test Conventions

Tests live in `tests/` organized by type:

```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # Tests with real databases and CLI
├── property/       # Hypothesis property-based tests
├── snapshot/       # Syrupy snapshot tests for projection output
├── fixtures/       # Curated fixture repos with expected_claims.json
└── conftest.py     # Shared fixtures: tmp_repo, populated_db, claim_factory
```

Guidelines:

- Tests in `tests/unit/` should be fast and have no I/O
- Integration tests may create temporary databases and repos
- Snapshot tests use syrupy for deterministic projection output
- Fixture repos in `tests/fixtures/` have `expected_claims.json` for quality harness

## Code Conventions

- `from __future__ import annotations` at the top of every source file
- Explicit return types on all public functions
- Frozen dataclasses for domain models; Pydantic v2 at IO/config boundaries
- `typing.Protocol` for interfaces; constructor injection for dependencies
- No mutable default arguments; no global mutable state
- All YAML via `yaml.safe_load()` for repo files, `strictyaml` for `.rkp/` files
- All logging to stderr; stdout reserved for MCP protocol
- Paths via `pathlib.Path.resolve()` + repo root containment check

## PR Guidelines

- Run `nox -s ci` before submitting — all checks must pass
- One logical change per PR
- Include tests for new functionality
- Update docs if adding CLI commands, MCP tools, or configuration options
- Snapshot tests may need updating if projection output changes (`--snapshot-update`)

## Architecture

See [Architecture](architecture.md) for the 4-plane design and key boundaries. Key rules:

- Extractors never know how hosts consume data
- Adapters never infer claims
- Sensitivity filtering at a single enforcement point
- No instruction file written without human review
