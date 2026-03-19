# CLI Reference

All commands accept these global options:

| Option | Description |
|---|---|
| `--repo PATH` | Repository root path (default: `.`, env: `RKP_REPO`) |
| `--json` | Output JSON instead of human-readable text |
| `--verbose` / `-v` | Increase verbosity (repeatable: `-vv` for max) |
| `--quiet` / `-q` | Suppress non-essential output |

## Commands

### `rkp init`

Scan the repository and extract claims into the local database.

```bash
rkp init
```

Creates `.rkp/` directory structure, runs extraction pipeline (config parsers, tree-sitter analysis, CI parsing, docs parsing), and stores claims in `.rkp/local/rkp.db`.

### `rkp review`

Interactively review and govern extracted claims.

```bash
rkp review [OPTIONS]
```

| Option | Description |
|---|---|
| `--approve-all` | Batch-approve high-confidence claims |
| `--threshold FLOAT` | Confidence threshold for `--approve-all` (default: 0.95) |
| `--type TYPE` | Filter by claim type (e.g., `validated-command`) |
| `--scope SCOPE` | Filter by file/directory scope |
| `--state STATE` | Filter by review state (e.g., `unreviewed`) |

Actions during review: **a**pprove, **e**dit (opens `$EDITOR`), **s**uppress, **t**ombstone, **n**ext (skip).

Decisions are persisted in `.rkp/overrides/` as strictyaml files.

### `rkp preview`

Preview projected instruction artifacts without writing files.

```bash
rkp preview --host HOST
```

| Option | Description |
|---|---|
| `--host HOST` | Target host: `codex`, `claude`, `copilot`, `cursor`, `windsurf` |

Shows all claims (including unreviewed). Use `rkp apply` to write only approved claims.

### `rkp apply`

Write approved projections to disk.

```bash
rkp apply --host HOST
```

| Option | Description |
|---|---|
| `--host HOST` | Target host: `codex`, `claude`, `copilot`, `cursor`, `windsurf` |
| `--dry-run` | Show what would change without writing |
| `--yes` / `-y` | Skip confirmation prompt |

Only writes claims with `review_state` of `approved` or `edited`. Shows a diff preview before writing. Tracks written files in the artifact store for drift detection.

### `rkp status`

Show index health, pending reviews, stale claims, and drift.

```bash
rkp status
```

Reports: total claims by type and review state, stale claims, drift-detected artifacts, freshness information.

### `rkp refresh`

Re-analyze the repo and flag stale claims.

```bash
rkp refresh [OPTIONS]
```

| Option | Description |
|---|---|
| `--dry-run` | Show what changed without updating the database |

Compares current repo state against indexed state. Flags claims whose evidence files have changed, been deleted, or where the branch has changed.

### `rkp import`

Ingest existing instruction files as claims.

```bash
rkp import
```

Parses existing `AGENTS.md`, `CLAUDE.md`, `copilot-instructions.md`, and `.cursor/rules` files. Imported claims receive `DECLARED_IMPORTED_UNREVIEWED` authority.

### `rkp serve`

Start the MCP server on stdio transport.

```bash
rkp serve
```

Agents connect by configuring the MCP server command. See [MCP Tools](mcp-tools.md) for available tools.

### `rkp audit`

Query the governance audit trail.

```bash
rkp audit [OPTIONS]
```

| Option | Description |
|---|---|
| `--claim-id ID` | Filter to a specific claim |
| `--scope SCOPE` | Filter by claim scope |
| `--action ACTION` | Filter by action type |
| `--since DATE` | Only entries since this ISO date |
| `--limit N` | Max entries to return (default: 100) |

### `rkp quality`

Run the quality harness.

```bash
rkp quality [OPTIONS]
```

| Option | Description |
|---|---|
| `--fixtures PATH` | Path to fixture repos (default: `tests/fixtures/`) |
| `--report PATH` | Output JSON report path |
| `--skip-performance` | Skip the performance benchmark |

Runs extraction precision/recall, export conformance, sensitivity leakage, drift detection, and import fidelity tests.

### `rkp doctor`

Validate environment and repo setup.

```bash
rkp doctor
```

Checks: Python version, Git availability, SQLite FTS5 support, tree-sitter availability.

### `rkp purge`

Permanently delete all tombstoned claims, their evidence, and override files.

```bash
rkp purge [OPTIONS]
```

| Option | Description |
|---|---|
| `--dry-run` | Show what would be purged without purging |
| `--yes` / `-y` | Skip confirmation prompt |

Removes tombstoned claims from the database, their evidence records, history entries, and corresponding `.rkp/overrides/` files. Does not affect active claims or the database itself.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error |
| 2 | Usage error (invalid arguments) |
| 130 | Interrupted (Ctrl+C) |
