# CLI Reference

All commands support these global options:

| Option | Description |
|---|---|
| `--repo PATH` | Repository root (default `.`) |
| `--json` | Machine-readable JSON output |
| `--verbose`, `-v` | More diagnostics on `stderr` |
| `--quiet`, `-q` | Suppress non-essential human output |

## Core lifecycle

### `rkp doctor`

Validate the current machine and repo prerequisites.

```bash
rkp doctor
```

### `rkp init`

Initialize `.rkp/`, extract claims, and create the local index.

```bash
rkp init
```

### `rkp status`

Show index health, freshness, review backlog, and managed-file drift.

```bash
rkp status
```

`status` expects the repo to have been initialized first.

### `rkp review`

Review claims interactively or in batches.

```bash
rkp review [OPTIONS]
```

Common options:

| Option | Description |
|---|---|
| `--approve-all` | Batch-approve claims above a threshold |
| `--threshold FLOAT` | Threshold used by `--approve-all` |
| `--type TYPE` | Filter by claim type |
| `--scope SCOPE` | Filter by claim scope |
| `--state STATE` | Filter by review state |

### `rkp preview`

Preview projected artifacts without writing them.

```bash
rkp preview --host codex
```

Hosts: `codex`, `agents-md`, `claude`, `copilot`, `cursor`, `windsurf`

Preview includes unreviewed claims but hides suppressed and tombstoned claims.

### `rkp apply`

Write projected artifacts to disk.

```bash
rkp apply --host claude
```

Common options:

| Option | Description |
|---|---|
| `--host HOST` | Projection target |
| `--dry-run` | Show changes without writing |
| `--yes`, `-y` | Skip confirmation |

Only `approved` and `edited` claims are written.

### `rkp serve`

Run the MCP server on stdio transport.

```bash
rkp serve
```

## Import, maintenance, and audit

### `rkp import`

Import existing instruction files as governed claims.

```bash
rkp import
```

Auto-discovery looks for:

- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`
- `.github/workflows/copilot-setup-steps.yml`
- `.cursor/rules/`

Run `rkp init` first so the repo has `.rkp/config.yaml` and a local index.

### `rkp refresh`

Re-extract the repo and refresh freshness/drift signals.

```bash
rkp refresh
```

### `rkp audit`

Query the governance audit trail.

```bash
rkp audit [OPTIONS]
```

### `rkp purge`

Permanently delete tombstoned claims plus their evidence, history, and override files.

```bash
rkp purge --dry-run
```

This does not delete the entire database.

## Quality and docs

### `rkp quality`

Run the adapter quality harness.

```bash
rkp quality --report quality-report.json
```

The harness exercises conformance, sensitivity leakage, drift handling, and import fidelity.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Command returned findings or a non-fatal failure condition |
| `2` | Usage error or command failure |
| `3` | Repo not initialized |
| `130` | Interrupted |
