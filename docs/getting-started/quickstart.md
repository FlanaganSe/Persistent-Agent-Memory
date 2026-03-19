# Quick Start

This guide is intentionally split into the two real starting points: a repo that has no existing agent instructions yet, and a repo that already has them.

## Track A: Fresh RKP adoption

### 1. Check the environment

```bash
cd your-repo
rkp doctor
```

### 2. Initialize the repo

```bash
rkp init
```

This creates the checked-in `.rkp/config.yaml`, the `.rkp/overrides/` directory, and the local SQLite index under `.rkp/local/`.

### 3. Inspect what was extracted

```bash
rkp status
rkp preview --host codex
```

Preview includes unreviewed claims, but intentionally hides suppressed and tombstoned ones.

### 4. Govern the claims

Interactive:

```bash
rkp review
```

Fast demo path:

```bash
rkp review --approve-all --threshold 0.95
```

### 5. Write reviewed artifacts

```bash
rkp apply --host claude --yes
```

`apply` only writes claims in `approved` or `edited` review state.

### 6. Serve the same knowledge over MCP

```bash
rkp serve
```

Example MCP client config:

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

## Track B: Repo already has instruction files

If the repo already has `AGENTS.md`, `CLAUDE.md`, Copilot instructions, or Cursor rules, still start with `init`:

```bash
rkp init
rkp import
rkp status
```

Imported claims enter as `declared-imported-unreviewed`, which is intentionally lower authority than executable config and CI evidence until a human reviews them.

Then continue with the same governance flow:

```bash
rkp review
rkp apply --host codex --yes
```

## Common follow-up commands

```bash
rkp refresh
rkp audit
rkp preview --host copilot
```

## Repo layout after `init`

```text
.rkp/
├── config.yaml          # checked in
├── overrides/           # checked in
└── local/               # gitignored
    └── rkp.db
```
