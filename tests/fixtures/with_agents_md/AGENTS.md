# MyProject Agent Instructions

This project is a web application built with Python and React.

## Setup

- Python 3.12 required
- Node.js >= 18 required
- `pip install -e ".[dev]"`
- `npm install`

## Commands

- `pytest` — run all tests
- `ruff check .` — lint Python code
- `npm run build` — build frontend

```bash
make dev
make test
make lint
```

## Conventions

- Use snake_case for Python functions
- Use camelCase for JavaScript functions
- Always add type annotations to public functions
- Never use `print()` for logging — use structlog
- Prefer immutable data structures

## Architecture

- `src/` contains the Python backend
- `frontend/` contains the React frontend
- `tests/` contains all test files

## Testing

- Use pytest for all Python tests
- Use jest for JavaScript tests
- Always write tests before code (TDD)

## Workflows

- Run lint before committing
- Create a PR for every change
- Use conventional commits
