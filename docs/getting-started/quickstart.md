# Quick Start

This guide walks through using RKP on a repository for the first time.

## 1. Initialize

```bash
cd your-repo
rkp init
```

RKP scans your repository and extracts claims from:

- Config files (pyproject.toml, package.json, Makefile, Dockerfile)
- CI workflows (GitHub Actions)
- Source code (Python, JS/TS via tree-sitter)
- Documentation (README, docs/)
- Version files (.python-version, .nvmrc, .tool-versions)

Output shows how many files were parsed and claims created.

## 2. Review

```bash
rkp review
```

Interactive review: approve, edit, suppress, or skip each claim. Your decisions are saved to `.rkp/overrides/` (version-controlled).

Options:

- `--approve-all` — batch approve all unreviewed claims
- `--type validated-command` — filter by claim type
- `--scope src/` — filter by file scope
- `--state unreviewed` — filter by review state

## 3. Preview

```bash
rkp preview --host claude
rkp preview --host codex
rkp preview --host copilot
```

See what would be generated without writing files. Preview shows all claims; apply only writes approved ones.

## 4. Apply

```bash
rkp apply --host claude
rkp apply --host codex
```

Writes instruction files to disk. Only approved/edited claims are projected. Shows a diff preview before writing.

## 5. Serve

```bash
rkp serve
```

Starts the MCP server on stdio transport. Configure your agent to connect:

```json
{
  "mcpServers": {
    "rkp": {
      "command": "rkp",
      "args": ["serve"]
    }
  }
}
```

Agents can then call tools like `get_conventions`, `get_validated_commands`, `get_preflight_context`.

## Importing Existing Files

Already have instruction files? Import them:

```bash
rkp import
rkp review        # Review imported + extracted claims together
rkp apply --host codex  # Re-project with unified governance
```

## Checking Status

```bash
rkp status        # Index health, pending reviews, stale claims, drift
rkp refresh       # Re-check evidence, flag stale claims
rkp audit         # Query the governance audit trail
```

## Repo Structure After Init

```
.rkp/
├── config.yaml          # RKP settings (checked in)
├── overrides/           # Human governance decisions (checked in)
│   └── claim-abc123.yaml
└── local/               # Gitignored, regenerable
    └── rkp.db           # SQLite index
```

The `.rkp/overrides/` directory is your team's durable record. The database is a cache — delete it and `rkp init` rebuilds everything.
