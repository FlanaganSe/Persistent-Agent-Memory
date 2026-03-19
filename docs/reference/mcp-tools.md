# MCP Tools Reference

RKP exposes 11 MCP tools via `rkp serve`. All tools except `refresh_index` are read-only (`readOnlyHint: true`).

Every response includes a standard envelope:

```json
{
  "status": "ok",
  "data": { ... },
  "warnings": [],
  "provenance": {
    "repo_head": "abc1234",
    "branch": "main",
    "index_version": "2026-03-19T10:00:00"
  },
  "freshness": {
    "index_age_seconds": 120,
    "stale_claims_in_response": 0,
    "head_current": true
  }
}
```

## Tools

### `get_conventions`

Scoped conventions with source authority and confidence.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path_or_symbol` | string | `**` | Path or symbol to scope conventions to |
| `include_evidence` | bool | false | Include evidence file paths |
| `task_context` | string? | null | Filter by task type (e.g., `test`, `lint`) |
| `limit` | int | 50 | Page size (1–500) |
| `cursor` | string? | null | Pagination cursor |
| `detail_level` | string | `normal` | `terse`, `normal`, or `detailed` |

### `get_validated_commands`

Build/test/lint commands with evidence and risk classification.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `scope` | string | `**` | Scope filter |
| `limit` | int | 50 | Page size |
| `cursor` | string? | null | Pagination cursor |
| `detail_level` | string | `normal` | `terse`, `normal`, or `detailed` |

Returns commands with `risk_class` (`safe-readonly`, `safe-mutating`, `test-execution`, `build`, `destructive`), `evidence_level`, and `source` file paths.

### `get_prerequisites`

Environment prerequisites and profiles (runtimes, tools, services, env vars).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `command_or_scope` | string? | null | Filter to prerequisites for a specific command |

Returns `prerequisites` (claim list) and `profiles` (aggregated environment profiles with runtime, tools, services, env_vars, setup_commands).

### `get_guardrails`

Security restrictions and permission claims.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path_or_scope` | string | `**` | Scope filter |
| `host` | string? | null | Target host for enforcement info |
| `limit` | int | 50 | Page size |
| `cursor` | string? | null | Pagination cursor |
| `detail_level` | string | `normal` | `terse`, `normal`, or `detailed` |

Returns guardrails with `enforceable_on` (list of hosts where the guardrail can be enforced) and `enforcement_mechanism` (`settings.json permissions.deny`, `tool-allowlist`, or `advisory text only`).

### `get_module_info`

Module boundary info, dependencies, dependents, and test locations.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path_or_symbol` | string | (required) | Path or module name |

Returns `module`, `dependencies`, `dependents`, `test_locations`, and `scoped_rules` applicable to the module.

### `get_conflicts`

Where declared and inferred knowledge disagree.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path_or_scope` | string | `**` | Scope filter |
| `limit` | int | 50 | Page size |
| `cursor` | string? | null | Pagination cursor |
| `detail_level` | string | `normal` | `terse`, `normal`, or `detailed` |

### `get_instruction_preview`

Preview projected instruction artifacts for a target consumer.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `consumer` | string | `codex` | Target: `codex`, `agents-md`, `claude`, `copilot`, `cursor`, `windsurf` |

Returns `files` (dict of filename → content), `excluded_sensitive`, `excluded_low_confidence`, and `overflow_report`.

### `get_repo_overview`

High-level repository summary.

No parameters. Returns: `languages`, `modules`, `build_test_entrypoints`, `claim_summary` (total, by_type, by_review_state, conflicts), and `support_envelope`.

### `get_claim`

Full detail on a single claim.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `claim_id` | string | (required) | The claim ID |

Returns all claim fields plus `evidence_chain` (detailed evidence records) and `review_history` (audit trail entries).

### `get_preflight_context`

Minimum actionable bundle an agent needs before starting work.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path_or_symbol` | string | (required) | Path or symbol being worked on |
| `task_context` | string? | null | Task type filter |
| `host` | string? | null | Target host for enforcement info |
| `detail_level` | string | `terse` | `terse`, `normal`, or `detailed` |

Returns `scoped_rules`, `validated_commands`, `guardrails`, `environment`, `unsupported_areas`, and `warnings` in a single bounded response.

### `refresh_index`

Trigger re-indexing after file changes. **This is the only read-write tool** (`readOnlyHint: false`).

| Parameter | Type | Default | Description |
|---|---|---|---|
| `paths` | list[string]? | null | Paths to re-index (currently runs full extraction) |

Returns `files_parsed`, `claims_created`, `claims_deduplicated`, `elapsed_seconds`.

## Pagination

Tools that return claim lists support cursor-based pagination:

- `limit`: page size (1–500, default 50)
- `cursor`: pass the `next_cursor` from the previous response
- Response includes `next_cursor`, `has_more`, and `total_count`

## Detail Levels

- **terse**: `id`, `content_preview` (100 chars), `claim_type`, `confidence`
- **normal**: all claim fields except raw evidence blobs (default)
- **detailed**: all fields + `evidence_chain` from evidence store + freshness details
