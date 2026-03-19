# System

## What this system does

RKP is a local-first, evidence-backed intelligence layer for software repositories. It extracts structured claims (conventions, validated commands, prerequisites, guardrails, module boundaries) from code, config, CI definitions, and documentation; governs them through human review; projects them faithfully into 5 host-native instruction formats (AGENTS.md, CLAUDE.md, copilot-instructions.md, .cursor/rules, .windsurf/rules); and serves live context via MCP. No repo content leaves the local machine.

## Domain model

**Claims** are the core abstraction: structured facts about a repository carrying provenance, confidence, source authority, and review state. Types: `always-on-rule`, `scoped-rule`, `skill-playbook`, `environment-prerequisite`, `validated-command`, `permission-restriction`, `module-boundary`, `conflict`.

**Source authority** determines precedence (lower = higher authority): `human-override` (10) > `declared-reviewed` (20) > `executable-config`/`ci-observed` (30) > `declared-imported-unreviewed` (35) > `checked-in-docs` (40) > `inferred-high` (50) > `inferred-low` (60). Conflicts are resolved by precedence; equal-precedence conflicts are surfaced for human review.

**Evidence** links claims to source files with hashes and line ranges. Evidence levels: `discovered` > `prerequisites-extracted` > `ci-evidenced` > `environment-profiled` > `sandbox-verified` (Phase 2).

**Review states**: `unreviewed` (default) -> `approved` | `edited` | `suppressed` | `tombstoned`. `needs-declaration` -> `approved` (after human responds to a declaration prompt).

**Sensitivity**: `public` (projected anywhere), `team-only` (version-controlled but not in MCP responses for unauthenticated use), `local-only` (never leaves `.rkp/local/`).

**Managed artifacts**: tracked projected files with ownership modes (`imported-human-owned`, `managed-by-rkp`, `mixed-migration`) and drift detection via content hashing.

## Architecture

Four planes with strict separation:

1. **Extraction Plane** — parsers (tree-sitter for Python/JS/TS) and config parsers (pyproject.toml, package.json, Makefile, Dockerfile, docker-compose, GitHub Actions, version files) produce evidence records. Extractors handle conventions, commands, prerequisites, CI evidence, boundaries, guardrails, conflicts, docs evidence.

2. **Claim Plane** — claim builders produce canonical claims with content-addressable IDs (`SHA-256(type:scope:content)[:16]`, prefixed `claim-`). Deduplication and conflict detection operate here.

3. **Projection Plane** — pure function: `claims + adapter_caps + policy -> artifacts + excluded_report`. Five adapters (AGENTS.md GA, CLAUDE.md GA, Copilot Beta, Cursor Alpha, Windsurf Alpha). Sensitivity filtering at a single enforcement point just before output.

4. **Serving & Governance Plane** — MCP tools (11 tools, 10 read-only + `refresh_index`), CLI commands (init, review, apply, refresh, status, import, preview, audit, quality, doctor, serve, purge), audit trail, overrides persistence.

Key isolation rules: extractors don't know hosts, adapters don't infer claims, review layer doesn't parse host formats.

## Constraints

- All YAML via `yaml.safe_load()` or `strictyaml` — never `yaml.load()`.
- All logging to stderr; stdout reserved for MCP protocol.
- All paths via `pathlib.Path.resolve()` with repo root containment check.
- Claims carry provenance on every response (index version, HEAD, branch, timestamp).
- No instruction file written without human review (`apply` gates on `review_state`).
- `local-only` claims never leave `.rkp/local/` — not in overrides, not in MCP.
- Passive analysis only; active verification (sandbox execution) deferred to Phase 2.
- Imported claims at precedence 3.5 — below `executable-config` until reviewed.

## Key patterns

- **Content-addressable IDs** — `SHA-256(claim_type:scope:content)[:16]` prefixed `claim-`. Immutable after creation; edits change content, not ID.
- **Protocol + constructor injection** — `ClaimStore`, `GitBackend`, `RepoGraph` defined as `typing.Protocol`. No DI framework. SQLite implementations injected via constructor.
- **Store pattern** — Protocol interface + SQLite implementation with `_row_to_*` converters. Migration runner uses `PRAGMA user_version` with numbered SQL files.
- **SQLite WAL** — busy_timeout=5000ms, cache_size=64MB, foreign_keys ON, mmap_size=256MB. `check_same_thread=False` for MCP server (threadpool dispatch).
- **Sensitivity filter** — single enforcement point (`projection/sensitivity.py`) called just before every output boundary (projection and MCP response).
- **Response envelope** — every MCP response includes `status`, `data`, `warnings`, `provenance` (repo_head, branch, index_version), and `freshness` metadata.

## Gotchas

- **tree-sitter v0.25+**: uses `QueryCursor`, not `Query.captures()`. The old API is removed.
- **FastMCP Client**: must be opened inside test functions, not fixtures — async context manager lifecycle.
- **`check_same_thread=False`**: required for MCP server because FastMCP dispatches tool handlers in a threadpool.
- **FTS5**: table created in schema but triggers not yet wired. Search uses SQL LIKE queries, not FTS.
- **`claim_evidence` table**: designed but not populated by extraction pipeline. Freshness checker falls back to git diff between indexed HEAD and current HEAD.
- **Windsurf deduplication**: Windsurf auto-reads AGENTS.md, so the adapter deduplicates claims already projected to AGENTS.md.
