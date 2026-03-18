---
description: Code style and established patterns.
---
# Conventions

- Tests in `tests/` directory: `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/snapshot/`
- Explicit return types on all public functions
- `from __future__ import annotations` at top of every source file
- Formatter (ruff format) handles formatting — don't bikeshed
- Frozen dataclasses for domain models; Pydantic v2 at IO/config boundaries
- No mutable default arguments; no global mutable state
- `typing.Protocol` for interfaces; constructor injection for dependencies
- YAML: always `yaml.safe_load()` for repo files, `strictyaml` for `.rkp/` files — never `yaml.load()`
- Path operations: `pathlib.Path.resolve()` + repo root containment check
- All logging to stderr; stdout reserved for MCP protocol

## Established Patterns

- **Content-addressable IDs**: `SHA-256(type:scope:content)[:16]` prefixed `claim-`. See `src/rkp/core/ids.py`.
- **Source authority precedence**: Lower number = higher authority. See `src/rkp/core/types.py`.
- **Store pattern**: Protocol interface + SQLite implementation with `_row_to_*` converters. See `src/rkp/store/claims.py`.
- **Migration runner**: Numbered SQL files in `src/rkp/store/migrations/`, `PRAGMA user_version` tracking. See `src/rkp/store/database.py`.
