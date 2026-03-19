# Product Overview

## What this is

Repo Knowledge Plane (RKP) is a local-first intelligence layer for AI coding agents. It solves a fundamental problem: every agent session rediscovers the same repository context — build commands, conventions, module boundaries, guardrails — and each host (Claude Code, Copilot, Cursor, Windsurf) requires a different instruction format. RKP extracts this knowledge once into a normalized claim store, governs it through a human review workflow, and projects it to any host format on demand. It also exposes an MCP server so agents can query repo context mid-session with freshness guarantees.

**Status**: v0.1.0, Alpha. Installable via `uvx rkp` or `pip install rkp`.

## Stack

- **Runtime**: Python 3.12+ (src layout, hatchling build, distributed via PyPI)
- **CLI**: Typer + Rich (12 commands)
- **MCP**: FastMCP 3.1+ (stdio transport, 11 tools, 5 resources)
- **Database**: SQLite (WAL mode, FTS5) at `.rkp/local/rkp.db`
- **Parsing**: tree-sitter 0.25+ with language-pack (Python, JS, TS)
- **Config**: Pydantic v2 at IO boundaries, frozen dataclasses for domain models
- **YAML**: PyYAML (safe_load only), strictyaml for `.rkp/` overrides
- **Logging**: structlog (stderr only — stdout reserved for MCP protocol)
- **Tests**: pytest + hypothesis + syrupy across unit/integration/property/snapshot
- **CI**: GitHub Actions (ruff, pyright strict, pytest, quality harness, MkDocs)
- **Task runner**: nox

## Architecture

RKP operates as a pipeline with four stages:

```
Repository Files
      |
  [1. Index / Extract]    tree-sitter parsing, config parsing, CI evidence
      |
  [2. Claim Store]        SQLite with content-addressable IDs, evidence chains
      |
  [3. Govern]             human review, sensitivity filtering, conflict detection
      |
  [4. Project / Serve]    host adapters (CLAUDE.md, .cursorrules, etc.) + MCP server
```

**Indexing** runs a 13-phase extraction pipeline: config parsers (pyproject.toml, package.json, Makefile, Dockerfile, GitHub Actions) → tree-sitter AST analysis → domain extractors (commands, conventions, guardrails, prerequisites, boundaries, conflicts) → docs evidence from prose. Claims are deduplicated via content-addressable IDs and security-scanned (injection markers, secret redaction) before storage.

**The MCP server** exposes 10 read-only tools + 1 write tool (`refresh_index`). Agents query for validated commands, conventions, guardrails, prerequisites, module info, and repo overviews. Every response includes provenance (index version, repo HEAD, branch) and freshness metadata (stale claim count, index age). A sensitivity filter at the output boundary prevents LOCAL_ONLY claims from reaching agents.

**Projection** transforms claims into host-specific instruction files through adapters with budget tracking (hard/soft character limits per host). Each adapter respects the host's format constraints — YAML frontmatter for Cursor rules, multi-file CLAUDE.md with scoped rules, `.github/copilot-instructions.md` with setup steps.

## Directory structure

```
src/rkp/
  cli/            CLI entry point (Typer app) + 12 command modules + UI rendering
  core/           Domain models, claim builder, IDs, config, security, freshness, errors
  server/         MCP server (FastMCP), tool handlers, resources, response envelope, trace
  indexer/        Extraction pipeline: orchestrator, config parsers, tree-sitter parsers, extractors
  importer/       Import existing instruction files (CLAUDE.md, .cursorrules, etc.) as claims
  projection/     Claim-to-artifact projection: adapter base, 6 host adapters, budget, sensitivity
  store/          SQLite persistence: claims, evidence, history, artifacts, metadata, overrides, migrations
  graph/          Module dependency graph (import edges, containment, test mapping)
  git/            Git backend (Protocol + CLI subprocess implementation)
  quality/        Evaluation harness: conformance, leakage, drift, promotion, benchmarks
tests/
  unit/           54 files — domain models, store, parsing, security, adapters
  integration/    46 files — CLI, MCP protocol, orchestration, quality harness
  property/       1 file — hypothesis-based determinism, ordering, roundtrip tests
  snapshot/       4 files — golden-file projection output verification
  fixtures/       Test repos (simple_python with src/tests structure)
docs/             MkDocs Material site — concepts, reference, development guides
.rkp/             Per-repo config (config.yaml) and local state (local/rkp.db)
```

## Core concepts

### Claims

The central domain object. A claim is a single assertion about the repository: "run `pytest` to test", "use snake_case for functions", "never commit secrets". Claims have:

- **Content-addressable ID**: `claim-{SHA-256(type:scope:content)[:16]}`. Same knowledge = same ID. IDs are immutable after creation.
- **Type**: ALWAYS_ON_RULE, SCOPED_RULE, SKILL_PLAYBOOK, ENVIRONMENT_PREREQUISITE, VALIDATED_COMMAND, PERMISSION_RESTRICTION, MODULE_BOUNDARY, CONFLICT
- **Source authority**: Determines trust. Lower precedence number = higher authority: HUMAN_OVERRIDE (10) > DECLARED_REVIEWED (20) > EXECUTABLE_CONFIG (30) > CI_OBSERVED (30) > DECLARED_IMPORTED_UNREVIEWED (35) > CHECKED_IN_DOCS (40) > INFERRED_HIGH (50) > INFERRED_LOW (60)
- **Scope**: Path pattern (default `**` for global). Enables per-directory rules.
- **Sensitivity**: PUBLIC (safe for agents), TEAM_ONLY (restricted), LOCAL_ONLY (never leaves local DB)
- **Review state**: UNREVIEWED → APPROVED / EDITED / SUPPRESSED / TOMBSTONED. No instruction file is written without human review.
- **Risk class**: SAFE_READONLY, SAFE_MUTATING, TEST_EXECUTION, BUILD, DESTRUCTIVE

### Evidence

Links claims to source files with git object hashes, line ranges, and extraction versions. Enables freshness tracking — when a source file changes, linked claims can be detected as stale.

### Freshness

Claims degrade over time. Staleness triggers: time expiry (configurable, default 90 days), branch change, evidence file deletion, evidence hash mismatch. Stale claims get reduced confidence (default 20% reduction).

### Overrides

Human review decisions serialized as YAML in `.rkp/overrides/` (strictyaml). Override actions: approved, edited, suppressed, tombstoned, declared. LOCAL_ONLY claims are applied to the DB only, never written to override files.

## Key patterns and conventions

- **Frozen dataclasses** for all domain models. Pydantic v2 only at IO/config boundaries.
- **Protocol-based stores**: `ClaimStore`, `EvidenceStore`, `HistoryStore` etc. are Protocols with SQLite implementations. Constructor injection for dependencies.
- **Content-addressable deduplication**: Same type + scope + content = same claim ID. No duplicates stored.
- **Single enforcement point**: Sensitivity filtering happens once at the MCP output boundary via `response_filter.py`, not scattered across tools.
- **Security scanning before persistence**: Injection marker detection and secret redaction run on all extracted/imported content before it reaches the store.
- **`from __future__ import annotations`** at top of every source file. Explicit return types on all public functions.
- **YAML safety invariant**: `yaml.safe_load()` for repo files, `strictyaml` for `.rkp/` state. Never `yaml.load()`. Enforced by tests.
- **stdout/stderr discipline**: stdout is exclusively for MCP protocol. All logging, diagnostics, and CLI output use stderr.

## Data layer

SQLite with WAL mode, foreign keys, 64MB page cache, memory-mapped I/O. Schema at v2 (migration runner uses `PRAGMA user_version`).

**Core tables**: `claims` (primary, with denormalized `authority_level` for sort), `claim_evidence` (many-to-many with file hashes), `claim_history` (append-only audit trail), `claim_applicability` (normalized tags), `managed_artifacts` (drift tracking with expected hashes), `environment_profiles` (grouped prerequisites), `module_edges` (dependency graph), `session_log` (event stream), `index_metadata` (single-row freshness anchor).

FTS5 virtual table on claim content for full-text search (schema ready, population in progress).

## API surface

### MCP Tools (via `rkp serve`)

| Tool | Description | Read-only |
|------|-------------|-----------|
| `get_validated_commands` | Build/test/lint commands with risk class and confidence | Yes |
| `get_conventions` | Code style rules with evidence and applicability | Yes |
| `get_conflicts` | Disagreements between declared and inferred knowledge | Yes |
| `get_guardrails` | Permission restrictions and security policies | Yes |
| `get_prerequisites` | Environment setup requirements | Yes |
| `get_module_info` | Module boundaries, dependencies, associated tests | Yes |
| `get_instruction_preview` | Projected output preview for any host | Yes |
| `get_repo_overview` | Languages, modules, indexing status, claim summary | Yes |
| `get_claim` | Full detail on a single claim with evidence chain and history | Yes |
| `get_preflight_context` | Minimum context bundle for an agent to start work | Yes |
| `refresh_index` | Re-run extraction pipeline | **No** |

All responses wrapped in a `ToolResponse` envelope with status, provenance (index version, repo HEAD, branch, timestamp), and freshness metadata. Paginated tools support limit/cursor/detail_level parameters.

### MCP Resources

- `rkp://repo/overview` — repo summary
- `rkp://repo/conventions` and `rkp://repo/conventions/{path}` — scoped conventions
- `rkp://repo/instructions/{consumer}` — synthesized instruction preview
- `rkp://repo/architecture/modules` — module dependency graph
- `rkp://repo/prerequisites` — environment setup

### CLI Commands

`init`, `serve`, `preview`, `status`, `refresh`, `doctor`, `review`, `apply`, `import`, `audit`, `quality`, `purge`

## Environment and config

**Config file**: `.rkp/config.yaml` (checked in, loaded via `safe_load`)
```yaml
support_envelope:
  languages: [Python, JavaScript, TypeScript]
thresholds:
  staleness_days: 90
discovery:
  exclude_dirs: [vendor, node_modules, dist]
```

**Environment variables** (RKP_ prefix):
- `RKP_LOG_LEVEL` — structlog level (default INFO)
- `RKP_DB_PATH` — database location (default `.rkp/local/rkp.db`)
- `RKP_STALENESS_WINDOW_DAYS` — freshness threshold
- `RKP_TRACE_ENABLED` — audit trace logging to `.rkp/local/trace.jsonl`

**Auto-bootstrap**: `rkp serve` auto-extracts on first run if no database exists.

## Testing

**127 test files** across four categories. Run with `uv run nox -s test`.

- **Unit (54)**: Domain models, store CRUD, config parsing, tree-sitter parsing, security (YAML, path traversal, injection, secrets), sensitivity filtering, adapter output
- **Integration (46)**: CLI lifecycle, MCP protocol contracts (envelopes, pagination, detail levels), end-to-end orchestration, quality harness
- **Property (1)**: Hypothesis-based — claim ID determinism, precedence total ordering, SQLite roundtrip fidelity
- **Snapshot (4)**: Syrupy golden files for projection output correctness

**Quality harness** (`uv run nox -s quality`): Adapter conformance against specifications, sensitivity leakage detection across all boundaries, drift detection, import fidelity verification. This is the primary trust signal for adapter maturity promotion.

**Well-covered**: Claim model, security boundaries, store operations, MCP protocol contracts, sensitivity filtering, CLI commands, adapter projections.

**Known gaps**: Real-world repo fixtures (only `simple_python` tested at scale), remote MCP transport, command sandbox verification, cross-language dependency graphs.

## Important decisions and tradeoffs

- **Content-addressable IDs over UUIDs**: Enables natural deduplication — if the same knowledge is extracted twice, it produces the same claim ID. Tradeoff: edits to claim content don't change the ID (by design), which means the ID represents the *identity* of a piece of knowledge, not its current value.

- **Source authority precedence as a numeric hierarchy**: Rather than complex merge logic, conflicts resolve by comparing a single integer. Imported-but-unreviewed claims (35) deliberately sit below executable-config (30) so that a `pyproject.toml` script always outranks a pasted CLAUDE.md directive.

- **Local-first, no hosted control plane**: All state lives in `.rkp/local/` (gitignored). Override decisions in `.rkp/overrides/` (checked in). No network calls, no accounts, no cloud dependency. This is a deliberate architectural constraint.

- **Human review gate before instruction file writes**: RKP will not apply projected instructions to disk without review state = APPROVED. This prevents hallucinated or low-confidence claims from silently modifying agent behavior.

- **Single enforcement point for sensitivity**: Rather than checking sensitivity in every tool handler, filtering happens once at the response boundary. This was chosen after finding a gap during M10 — scattered checks are error-prone.

- **Adapter maturity earned, not declared**: An adapter cannot be labeled Beta or GA without passing the conformance harness. Alpha adapters ship with explicit warnings. This prevents premature trust in untested projection paths.

- **SQLite over Postgres/other**: Local-first constraint. WAL mode provides concurrent read access for the MCP server's threadpool dispatch. The entire database is a single file in the repo's `.rkp/local/` directory.

- **tree-sitter over regex for code parsing**: Enables accurate extraction of functions, classes, imports, and conventions from Python/JS/TS without fragile regex. The v0.25+ QueryCursor API is mandatory (older API removed).

## Gotchas

- **stdout is sacred**: Any log message, Rich output, or print statement that hits stdout will corrupt the MCP protocol stream. All output must go to stderr. This is enforced by convention and tested, but easy to break with a casual `print()`.

- **`yaml.load()` is banned**: Using PyYAML's unsafe `yaml.load()` anywhere in the codebase is a security violation. Always `yaml.safe_load()` for repo files, `strictyaml` for `.rkp/` state. Tests actively check for this.

- **Claim IDs look random but aren't**: They're SHA-256 hashes, not UUIDs. If you're debugging duplicate detection, the ID is derived from `type:scope:content`. Changing any of those three inputs produces a different ID.

- **The quality harness is a blocking CI check**: Adapter conformance, leakage detection, and drift checks run on every PR. A failing quality session blocks merge, not just test failures.

- **`refresh_index` is the only mutating MCP tool**: All other tools are read-only. This is an immutable rule — adding a new write tool requires updating the invariant in `.claude/rules/immutable.md`.

- **Budget limits are per-host and non-negotiable**: Windsurf has a 6K per-file / 12K workspace hard limit. Cursor has similar constraints. Claims that don't fit within budget are dropped by priority order, not truncated.

- **Override files use strictyaml, not pyyaml**: The `.rkp/overrides/` directory uses strictyaml for safety. Don't mix up the two YAML libraries — they have different APIs and strictyaml rejects many constructs that pyyaml accepts.

- **Imported claims intentionally rank below executable-config**: A claim imported from an existing CLAUDE.md (precedence 35) will lose to a command found in pyproject.toml (precedence 30). This is by design to prevent stale instruction files from overriding ground-truth config.
