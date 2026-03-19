# Claude Instructions

@.claude/rules/style.md

## Rules

- Always use `from __future__ import annotations`
- Never commit .env files
- Prefer composition over inheritance
- Use frozen dataclasses for domain models

## Commands

```bash
pytest -v
ruff check --fix .
```

## Testing

- Use pytest fixtures for test setup
- Never mock the database — use a test database
