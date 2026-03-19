# Configuration

RKP has two configuration scopes today:

1. Checked-in repo config in `.rkp/config.yaml`
2. Process-level settings from environment variables or programmatic `RkpConfig`

That split is intentional. Checked-in config stays narrow so repos do not accidentally hard-code machine-local behavior.

## Checked-in `.rkp/config.yaml`

`rkp init` creates this file.

The currently loaded keys are:

```yaml
support_envelope:
  languages: [Python, TypeScript]

thresholds:
  staleness_days: 90

discovery:
  exclude_dirs:
    - dist
    - tests/fixtures
```

### Supported checked-in keys

| Key | Meaning |
|---|---|
| `thresholds.staleness_days` | Repo default for time-based staleness windows |
| `discovery.exclude_dirs` | Extra repo-relative paths to skip during extraction |
| `support_envelope.*` | Informational metadata preserved in the file but not currently used for runtime behavior |

Unknown keys are ignored rather than failing startup.

### Notes on exclusions

`discovery.exclude_dirs` supports:

- simple directory names such as `dist`
- nested repo-relative paths such as `tests/fixtures`

RKP still applies its built-in exclusions like `.git`, `node_modules`, and `__pycache__`.

## Environment and process-level settings

These live on `RkpConfig` and are best treated as machine or process settings:

| Variable | Meaning |
|---|---|
| `RKP_REPO` | Default repo root |
| `RKP_DB_PATH` | Override the SQLite path |
| `RKP_LOG_LEVEL` | Logging level |
| `RKP_STALENESS_WINDOW_DAYS` | Default staleness window |
| `RKP_TRACE_ENABLED` | Enable or disable MCP trace capture |

The broader `RkpConfig` surface also includes:

- `max_file_size_bytes`
- `confidence_reduction_on_stale`
- `source_allowlist`

Those are currently runtime/programmatic settings, not loaded from checked-in `.rkp/config.yaml`.

## Directory layout

```text
.rkp/
├── config.yaml
├── overrides/
└── local/
    ├── rkp.db
    └── traces.jsonl
```

## Override files

Human decisions are stored one file per claim under `.rkp/overrides/`. That keeps the governance history merge-friendly and version-controlled.
