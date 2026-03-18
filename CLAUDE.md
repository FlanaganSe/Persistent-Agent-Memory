# Repo Knowledge Plane

Intelligence layer for coding agents: architecture recovery, change-impact graphs, repo instruction synthesis, cross-session memory, agent evals, and merge-risk prediction.

## Commands
```bash
# TBD — stack not yet chosen. Fill in when tooling is decided.
# Example placeholders:
# make dev             # Local dev
# make test            # Unit tests
# make ci              # Full CI: typecheck, lint, test
```

## Rules
<!-- Auto-discovered from .claude/rules/ — listed here for visibility -->
@.claude/rules/immutable.md
@.claude/rules/conventions.md
@.claude/rules/stack.md

## System
<!-- Uncomment when SYSTEM.md has real content: -->
<!-- @docs/SYSTEM.md -->

## Decisions
See `docs/decisions.md` — append-only ADR log. Read during planning, not loaded every session.

## Personal Overrides
Create `CLAUDE.local.md` (gitignored) for personal, project-specific preferences.

## Workflow
`/prd` → `/research` → `/plan` → `/milestone` (repeat) → `/complete`

## Escalation Policy
- If you discover a new invariant, add it to `.claude/rules/immutable.md`.
