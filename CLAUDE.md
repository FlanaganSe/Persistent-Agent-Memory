# Repo Knowledge Plane

Intelligence layer for coding agents: architecture recovery, change-impact graphs, repo instruction synthesis, cross-session memory, agent evals, and merge-risk prediction.

## Commands
```bash
uv pip install ".[dev]"       # Install dev dependencies
uv run nox -s lint            # Ruff lint + format check
uv run nox -s typecheck       # Pyright strict
uv run nox -s test            # Unit, integration, property, snapshot tests
uv run nox -s quality         # Adapter conformance, leakage, drift harness
uv run nox -s docs            # MkDocs build
uv run nox -s ci              # All of the above
uv build                      # Build wheel
```

## Rules
<!-- Auto-discovered from .claude/rules/ — listed here for visibility -->
@.claude/rules/immutable.md
@.claude/rules/conventions.md
@.claude/rules/stack.md

## System

## Decisions
See `docs/decisions.md` — append-only ADR log. Read during planning, not loaded every session.

## Personal Overrides
Create `CLAUDE.local.md` (gitignored) for personal, project-specific preferences.

## Workflow
`/prd` → `/research` → `/plan` → `/milestone` (repeat) → `/complete`

## Escalation Policy
- If you discover a new invariant, add it to `.claude/rules/immutable.md`.
