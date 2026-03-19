# Configuration

## `.rkp/config.yaml`

Created by `rkp init`. Controls RKP behavior for this repository.

```yaml
# Default configuration
repo_root: .
db_path: .rkp/local/rkp.db
log_level: INFO
staleness_window_days: 90
max_file_size_bytes: 1000000
confidence_reduction_on_stale: 0.2
trace_enabled: true
excluded_dirs:
  - vendor
  - node_modules
  - dist
  - build
  - __pycache__
  - .git
```

### Options

| Key | Type | Default | Description |
|---|---|---|---|
| `repo_root` | path | `.` | Repository root path |
| `db_path` | path | `.rkp/local/rkp.db` | SQLite database path |
| `log_level` | string | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `staleness_window_days` | int | `90` | Days before time-based staleness triggers |
| `max_file_size_bytes` | int | `1000000` | Skip files larger than this during extraction |
| `confidence_reduction_on_stale` | float | `0.2` | Multiplicative confidence reduction for stale claims |
| `trace_enabled` | bool | `true` | Enable MCP call trace logging |
| `excluded_dirs` | list[str] | (see above) | Directories to skip during extraction |

### Source Allowlist

Controls which sources are trusted for claim generation:

```yaml
source_allowlist:
  allowed_file_types:
    - .py
    - .js
    - .ts
    - .tsx
    - .jsx
    - .toml
    - .json
    - .yml
    - .yaml
    - .md
    - Makefile
    - Dockerfile
  allowed_directories:
    - "**"
  excluded_directories:
    - vendor/
    - node_modules/
    - dist/
    - build/
    - __pycache__/
    - .git/
  trusted_evidence_sources:
    - human-override
    - declared-reviewed
    - executable-config
    - ci-observed
    - declared-imported-unreviewed
    - checked-in-docs
    - inferred-high
    - inferred-low
```

## Environment Variables

All config options can be set via environment variables with the `RKP_` prefix:

| Variable | Equivalent config |
|---|---|
| `RKP_REPO` | `repo_root` |
| `RKP_DB_PATH` | `db_path` |
| `RKP_LOG_LEVEL` | `log_level` |
| `RKP_STALENESS_WINDOW_DAYS` | `staleness_window_days` |
| `RKP_TRACE_ENABLED` | `trace_enabled` |

## Directory Structure

```
.rkp/
├── config.yaml          # Checked into git — team-wide settings
├── overrides/           # Checked into git — human review decisions
│   └── claim-abc123.yaml   # One file per override
└── local/               # Gitignored — regenerable
    ├── rkp.db           # SQLite database
    └── traces/          # MCP call traces (JSONL)
```

### Override Files

Each override in `.rkp/overrides/` is a strictyaml file:

```yaml
claim_id: claim-abc123def456
action: approved
content: "Use frozen dataclasses for domain models"
actor: human
timestamp: "2026-03-19T10:00:00+00:00"
reason: "Confirmed project convention"
```

Override files are self-contained for merge-friendliness. One file per decision means git merge conflicts are localized.
