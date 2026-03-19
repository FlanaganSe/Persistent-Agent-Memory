# Security Model

RKP processes repository content and projects it into instruction files that AI agents trust. Security is critical — a compromised instruction file can steer agent behavior.

## Threat Model

| # | Threat | Severity | Mitigation |
|---|---|---|---|
| T1 | Prompt injection via repo content | High | Injection marker detection with severity levels and code-block allowlisting |
| T2 | Secret leakage into instruction files | High | Pattern + entropy-based secret detection, auto-redaction, auto-local-only |
| T3 | Path traversal via crafted file paths | High | `pathlib.Path.resolve()` + repo root containment check, null byte rejection |
| T4 | Unsafe YAML parsing (code execution) | High | `yaml.safe_load()` only for repo files, `strictyaml` for `.rkp/` files |
| T5 | Sensitive data in MCP responses | Medium | Sensitivity filtering at single enforcement point before every output |
| T6 | Untrusted imported content outranking build config | Medium | `DECLARED_IMPORTED_UNREVIEWED` at precedence 3.5 (below executable-config) |

## Prompt Injection Defense

RKP scans all content for prompt injection markers at two points: during extraction (pre-store) and in MCP responses (pre-serve).

**Detection patterns** (from `core/security.py`):
- **HIGH severity**: direct instruction injection (`[INST]`, `<|im_start|>`, `<<SYS>>`), instruction override attempts ("ignore previous instructions", "new instructions:")
- **MEDIUM severity**: role impersonation ("System:", "Assistant:"), structured injection (`<tool_call>`, `<function_call>`)
- **LOW severity**: suspicious but potentially legitimate ("you are now a", "act as if", "pretend you are")

**Code-block allowlisting**: markers found inside fenced code blocks (` ``` `) have their severity reduced by one level. A HIGH marker in a code block becomes MEDIUM. This prevents false positives from documentation that discusses injection attacks.

**Response filter** (`server/response_filter.py`): recursively scans all string values in MCP response JSON. Findings are added as warnings to the response — content is never silently dropped (that would break tool contracts).

## Secret Detection

Two detection strategies in `core/security.py`:

**Pattern-based**: provider-specific patterns for AWS keys, GitHub tokens, Anthropic/OpenAI keys, Slack tokens, database connection strings, private keys, and generic key/token/secret assignments.

**Entropy-based**: for assignment contexts (`password=`, `secret=`, `token=`), strings with Shannon entropy > 4.5 and length >= 20 are flagged as potential secrets. Structured non-secrets (UUIDs, git hashes) are excluded.

**Auto-redaction**: `redact_secrets()` replaces secret values with `prefix...REDACTED` markers. Claims with detected secrets are automatically set to `local-only` sensitivity.

## Sensitivity Model

Three levels, enforced at a single point:

| Level | Storage | Projection | MCP | Overrides |
|---|---|---|---|---|
| `public` | DB | Yes | Yes | Yes |
| `team-only` | DB | No | No (unauthenticated) | Yes |
| `local-only` | DB only | No | No | No |

**Single enforcement point**: `projection/sensitivity.py` provides `filter_sensitive()`, called just before every output boundary. Both the projection engine and MCP tool handlers call this function. There is no second code path that could bypass it.

**Key invariant**: `local-only` claims never appear in `.rkp/overrides/` (which is version-controlled). They exist only in the local SQLite database.

## Path Traversal Prevention

`core/security.py` provides `validate_path()`:

1. Rejects paths containing null bytes
2. Resolves the path against the repo root using `pathlib.Path.resolve()` (follows symlinks)
3. Verifies the resolved path starts with the resolved repo root using `is_relative_to()`
4. Returns the resolved path or raises `PathTraversalError`

All file operations in the indexer, importer, and projection engine go through this validation.

## Safe Parsing Rules

| Format | Parser | Why |
|---|---|---|
| YAML (repo files) | `yaml.safe_load()` | Prevents arbitrary Python code execution |
| YAML (.rkp/ files) | `strictyaml` | Prevents code execution AND limits YAML complexity |
| TOML | `tomllib` (stdlib) | Safe by design, no code execution |
| JSON | `json.loads()` (stdlib) | Safe by design |

The `safe_yaml_load()` wrapper in `core/security.py` enforces that only strings are passed to `yaml.safe_load()` and raises `UnsafeYamlError` on type violations.

## Source Allowlists

Configurable in `RkpConfig.source_allowlist`:

- **`allowed_file_types`**: which file extensions may produce claims (default: `.py`, `.js`, `.ts`, `.toml`, `.json`, `.yml`, `.yaml`, `.md`, `Makefile`, `Dockerfile`)
- **`allowed_directories`**: glob patterns for trusted directories (default: `**`)
- **`excluded_directories`**: directories to skip (default: `vendor/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `.git/`)
- **`trusted_evidence_sources`**: which source authority levels are trusted (default: all)

Enforcement: `enforce_allowlist()` in `server/tools.py` filters claims before they appear in MCP responses.

## MCP Response Filtering

Every MCP response passes through `response_filter.py` before being sent:

1. Response data (JSON dict) is recursively scanned for injection markers
2. Findings of HIGH or MEDIUM severity are added as warnings
3. Content is never modified or dropped — warnings let the agent make informed decisions

This happens in `_json()` in `mcp.py`, which serializes every tool response.

## Data Boundary

**What stays local**:
- The SQLite database (`.rkp/local/rkp.db`) — gitignored, regenerable
- `local-only` claims — never serialized outside the database
- Trace logs (`.rkp/local/traces/`) — opt-in, local-only
- MCP server runs on stdio — no network listening in Phase 1

**What RKP controls**:
- Which claims are extracted and stored
- Which claims pass sensitivity filtering
- Which claims are projected into instruction files
- What appears in MCP tool responses

**What RKP does NOT control**:
- What host agents do with projected instruction files after they're written
- Whether host agents transmit instruction file content over the network
- How host agents interpret or follow the instructions
- Network behavior of the host agents themselves

RKP's security boundary ends at the output. It ensures no sensitive data enters the output pipeline, but cannot prevent a host agent from forwarding public instruction content.

## Trust Boundaries

**MCP tools are read-only**: all 10 query tools have `readOnlyHint: true`. Only `refresh_index` (re-extraction) has `readOnlyHint: false`, and it only modifies the internal SQLite index.

**No file writes without review**: the `apply` command gates on `review_state`. Only `approved` and `edited` claims are projected to disk. Unreviewed claims are visible in `preview` but never written.

**Execution boundary**: RKP never executes repository commands. It reads and analyzes configurations, but `rkp verify` (sandbox execution) is deferred to Phase 2.

## Imported Content Trust

When importing existing instruction files (`rkp import`):

1. Imported claims receive `DECLARED_IMPORTED_UNREVIEWED` authority (precedence 35)
2. They are scanned for injection markers and secrets
3. They do NOT outrank executable config until a human reviews them
4. After review, they can be promoted to `declared-reviewed` (precedence 20)

This prevents a scenario where a malicious instruction file, once imported, overrides verified build configuration.
