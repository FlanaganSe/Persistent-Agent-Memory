---
description: Technology choices and constraints.
---
# Stack

- **Runtime**: Python 3.12+ (`src` layout, hatchling build)
- **Frontend**: N/A (tooling/infrastructure project)
- **Database**: SQLite (WAL mode, FTS5), in `.rkp/local/rkp.db`
- **Styling**: N/A
- **Tests**: pytest + hypothesis + syrupy (tests/ directory, unit/property/integration/snapshot)
- **Package manager**: uv + hatchling (PyPI distribution via `uvx`)
- **Linter**: ruff (lint + format), pyright (strict mode)
- **CLI**: typer[all] (includes Rich)
- **MCP**: fastmcp >= 3.1 (standalone, behind abstraction)
- **Parsing**: tree-sitter >= 0.25 + tree-sitter-language-pack (Python, JS, TS)
- **Config**: pydantic-settings (IO boundaries), frozen dataclasses (internal domain)
- **YAML**: pyyaml (yaml.safe_load only), strictyaml (.rkp/ overrides)
- **Logging**: structlog (stderr only)
- **Task runner**: nox (lint, typecheck, test, ci sessions)
- **Git**: Git CLI default backend, pygit2 optional (Phase 2)
