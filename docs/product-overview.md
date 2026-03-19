# Product Overview

## What this is

Repo Knowledge Plane (RKP) is an intelligence layer for AI coding agents. It extracts durable, evidence-backed operational knowledge from a codebase — conventions, validated commands, environment prerequisites, module boundaries, security guardrails — and projects that knowledge into each agent's native instruction format via CLI or MCP server. The core problem: AI agents are stateless and rediscover (or guess wrong about) repo context every session, while teams maintain multiple overlapping instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `copilot-instructions.md`, `.windsurf/rules`) by hand. RKP is the single source of truth: extract once, govern centrally, project everywhere.

Primary consumers are AI coding agents (via MCP). Secondary consumers are tech leads and platform teams who govern what agents are told.

## Stack

- **Runtime**: Python 3.12+ (src layout, hatchling build, distributed via `pip install repo-knowledge-plane` or `uvx`)
- **Database**: SQLite in WAL mode with FTS5 (`.rkp/local/rkp.db`), schema versioned via `PRAGMA user_version`
- **CLI**: Typer with Rich for terminal UI
- **MCP**: FastMCP >= 3.1, stdio transport, standalone server behind abstraction
- **Parsing**: tree-sitter >= 0.25 (v0.25+ QueryCursor API — old `query.captures()` removed) + tree-sitter-language-pack for Python, JS, TS
- **Config models**: Pydantic v2 + pydantic-settings at IO boundaries; frozen dataclasses for internal domain models
- **YAML**: `pyyaml` (`yaml.safe_load()` only — never `yaml.load()`) for repo files; `strictyaml` for `.rkp/overrides/`
- **Logging**: structlog, all output to stderr (stdout reserved for MCP protocol and data output)
- **Linting**: ruff (lint + format), pyright (strict mode)
- **Testing**: pytest + hypothesis (property-based) + syrupy (snapshot) + pytest-asyncio + pytest-benchmark
- **Task runner**: nox (sessions: `lint`, `typecheck`, `test`, `quality`, `docs`, `ci`)
- **Git**: Git CLI subprocess backend (default), pygit2 optional (deferred to Phase 2)
- **Docker**: dockerfile-parse for Dockerfile extraction
- **Docs**: mkdocs-material, towncrier for changelog

## Architecture

### High-level data flow

```
Repository sources (code, configs, CI, docs, existing instruction files)
    ↓
Indexer: config parsers → tree-sitter → extractors → claim builder
    ↓
Claim Store (SQLite): claims, evidence, history, module edges, environment profiles
    ↓
Projection Engine: sensitivity filter → confidence filter → authority prioritization → adapter
    ↓
Output: instruction files (AGENTS.md, CLAUDE.md, .cursor/rules, etc.) or MCP tool responses
```

### Request flow through MCP

1. Agent calls MCP tool (e.g., `get_conventions(scope="src/payments/")`)
2. FastMCP server dispatches to tool handler in `server/mcp.py`
3. Handler calls pure function in `server/tools.py` with injected stores
4. Function queries `SqliteClaimStore.get_by_precedence()` with scope filter
5. Results pass through `response_filter.py` (injection scan, sensitivity check)
6. Response returned as JSON with provenance + freshness metadata
7. TraceLogger appends JSONL record to `.rkp/local/traces.jsonl`

### Layered architecture

- **Core** (`core/`): Domain types, models, claim builder, security, freshness, config — zero I/O dependencies
- **Store** (`store/`): SQLite implementations behind Protocol interfaces — all persistence here
- **Indexer** (`indexer/`): Config parsers, tree-sitter language parsers, claim extractors — reads repo, writes claims
- **Importer** (`importer/`): Ingests existing instruction files as governed claims
- **Graph** (`graph/`): Module dependency graph (import edges from tree-sitter)
- **Projection** (`projection/`): Engine + per-host adapters + budget tracking + sensitivity filtering
- **Server** (`server/`): MCP tool definitions, response envelope, trace capture
- **CLI** (`cli/`): Typer commands, Rich UI, composition root (AppState)
- **Git** (`git/`): Backend Protocol + CLI subprocess implementation
- **Quality** (`quality/`): Conformance harness, leakage tests, drift tests, adapter maturity promotion

## Directory structure

```
src/rkp/
├── __init__.py                    # Version: "0.1.0"
├── __main__.py                    # python -m rkp entry point
├── core/
│   ├── types.py                   # Enums: ClaimType, SourceAuthority, ReviewState, Sensitivity, RiskClass, EvidenceLevel
│   ├── models.py                  # Frozen dataclasses: Claim, Evidence, Provenance, ClaimHistory, etc.
│   ├── ids.py                     # Content-addressable claim ID: SHA-256(type:scope:content)[:16]
│   ├── claim_builder.py           # Build, deduplicate, detect conflicts, merge claims
│   ├── config.py                  # RkpConfig (Pydantic BaseSettings), SourceAllowlist
│   ├── freshness.py               # Staleness detection: time-based, evidence-hash, branch-change, git-diff fallback
│   ├── security.py                # Injection detection (41 patterns), secret scanning, safe YAML, path validation
│   └── errors.py                  # Exception hierarchy: RkpError → ClaimError, StoreError, SecurityError, ConfigError
├── store/
│   ├── database.py                # SQLite connection factory: WAL, PRAGMAs, migration runner
│   ├── claims.py                  # ClaimStore Protocol + SqliteClaimStore (CRUD + precedence ordering)
│   ├── evidence.py                # SqliteEvidenceStore (claim ↔ source file linkage)
│   ├── history.py                 # SqliteHistoryStore (append-only audit trail)
│   ├── overrides.py               # FileSystemOverrideStore (.rkp/overrides/ YAML, strictyaml)
│   ├── artifacts.py               # SqliteArtifactStore (managed file tracking + drift detection)
│   ├── metadata.py                # SqliteMetadataStore (single-row index freshness)
│   └── migrations/                # Numbered SQL: 0001_init.sql, 0002_index_metadata.sql
├── indexer/
│   ├── orchestrator.py            # 13-phase extraction pipeline
│   ├── config_parsers/            # pyproject.py, package_json.py, dockerfile.py, docker_compose.py,
│   │                              #   github_actions.py, makefile.py, version_files.py
│   ├── parsers/                   # python.py, javascript.py (tree-sitter AST extraction)
│   └── extractors/                # conventions.py, commands.py, prerequisites.py, boundaries.py,
│                                  #   ci_evidence.py, docs_evidence.py, guardrails.py, conflicts.py
├── importer/
│   ├── engine.py                  # Discover, parse, security scan, build claims, deduplicate, register artifacts
│   ├── models.py                  # ParsedInstructionFile, ParsedClaimInput, ImportResult
│   └── parsers/                   # agents_md.py, claude_md.py, copilot.py, cursor.py, markdown_utils.py
├── projection/
│   ├── engine.py                  # Pure project() function: filter → prioritize → adapter.project()
│   ├── budget.py                  # BudgetTracker (hard bytes, soft lines, workspace bytes), prioritize_claims()
│   ├── capability_matrix.py       # HostCapability per target, size constraints
│   ├── sensitivity.py             # filter_sensitive(): single enforcement point
│   └── adapters/                  # base.py (Protocol), agents_md.py, claude_md.py, copilot.py,
│                                  #   cursor.py, windsurf.py, skills.py
├── server/
│   ├── mcp.py                     # FastMCP server, lifespan, 11 tool handlers
│   ├── tools.py                   # Pure tool implementations (query stores, build responses)
│   ├── resources.py               # MCP resource URI handlers
│   ├── response.py                # ToolResponse envelope (status, data, warnings, provenance, freshness)
│   ├── response_filter.py         # Injection scan + sensitivity warnings on outbound responses
│   └── trace.py                   # TraceLogger → .rkp/local/traces.jsonl (JSONL, append-only, secrets redacted)
├── graph/
│   └── repo_graph.py              # SqliteRepoGraph: import/contains/tests edges, module detection
├── git/
│   ├── backend.py                 # GitBackend Protocol
│   └── cli_backend.py             # CliGitBackend (subprocess, 10s timeout)
└── quality/
    ├── harness.py                 # Fixture-based quality tests
    ├── conformance.py             # Round-trip adapter validation
    ├── leakage.py                 # Sensitive claim leakage checks
    ├── promotion.py               # Adapter maturity tier promotion
    ├── benchmark.py               # Performance measurement
    ├── fixtures.py                # Test fixture repos
    └── types.py                   # QualityResult structures

tests/
├── conftest.py                    # Global fixtures: tmp_db_path, db, builder, sample_claim
├── unit/                          # ~70 files: every module has unit tests
├── property/                      # Hypothesis: ID determinism, precedence ordering, SQLite roundtrip
├── integration/                   # ~50 files: CLI commands, MCP contract, orchestrator, quality harness
├── snapshot/                      # Syrupy: projection output regression tests
└── fixtures/simple_python/        # Minimal Python project for extraction tests
```

## Core concepts

### Claims

The central abstraction. A **Claim** is a structured fact about a repository with provenance. Every piece of extracted knowledge — "use frozen dataclasses," "run `nox -s test`," "requires Python 3.12+" — is a claim.

```
Claim:
  id: "claim-a1f2b3c4d5e6f7g8"     # Content-addressable, immutable after creation
  content: "Use frozen dataclasses for domain models"
  claim_type: ALWAYS_ON_RULE         # One of 8 types
  source_authority: EXECUTABLE_CONFIG # Where it came from
  scope: "src/rkp/core/**"           # Glob-based applicability
  confidence: 0.92                   # 0.0–1.0, reduced when stale
  review_state: APPROVED             # Human governance state
  sensitivity: PUBLIC                # Controls visibility in projections
  evidence: ["pyproject.toml:12"]    # Where in the repo this was found
  provenance: {repo_head, branch, extraction_version, timestamp}
```

**Claim types** (8): `always-on-rule`, `scoped-rule`, `skill-playbook`, `environment-prerequisite`, `validated-command`, `permission-restriction`, `module-boundary`, `conflict`

### Source authority precedence

Not all knowledge is equal. Lower number = higher authority:

| Precedence | Authority | Example |
|---|---|---|
| 10 | `HUMAN_OVERRIDE` | Human approves/edits a claim |
| 20 | `DECLARED_REVIEWED` | Explicit human declaration |
| 30 | `EXECUTABLE_CONFIG` | pyproject.toml scripts, CI config |
| 30 | `CI_OBSERVED` | Command seen running in CI |
| 35 | `DECLARED_IMPORTED_UNREVIEWED` | Imported from existing CLAUDE.md (not yet reviewed) |
| 40 | `CHECKED_IN_DOCS` | README, architecture docs |
| 50 | `INFERRED_HIGH` | Strong pattern across many files |
| 60 | `INFERRED_LOW` | Weak pattern, few files |

This hierarchy resolves conflicts (higher authority wins), determines what goes in size-limited instruction files (highest authority first), and ensures imported claims never silently outrank executable config (precedence 35 > 30 intentionally).

### Review states

Claims progress through a governance lifecycle: `UNREVIEWED` → (`APPROVED` | `EDITED` | `SUPPRESSED` | `TOMBSTONED`). A suppressed claim is hidden from projections but retained. A tombstoned claim is soft-deleted (hard-delete via `rkp purge`). A `NEEDS_DECLARATION` state surfaces when conflicting signals require human disambiguation.

Human decisions are persisted as YAML files in `.rkp/overrides/` (version-controlled, survives re-extraction). Local-only claims are never written to overrides — they exist only in the local DB.

### Sensitivity

Three levels: `PUBLIC` (always included), `TEAM_ONLY` (excluded from public projections), `LOCAL_ONLY` (never in checked-in files, never in `.rkp/overrides/`, only in local DB). Filtering happens at a single enforcement point (`projection/sensitivity.py`) applied at every output boundary.

### Freshness

Claims go stale. Freshness is evaluated by:
1. **Evidence hash** — source file changed (primary trigger)
2. **File deletion** — evidence file removed
3. **Time expiry** — exceeds `staleness_window_days` (default: 90)
4. **Branch change** — indexed branch differs from current branch
5. **Git diff fallback** — when `claim_evidence` table is empty, falls back to `git diff` between indexed HEAD and current HEAD

Stale claims get a multiplicative confidence reduction: `effective = confidence * (1 - reduction_factor)`. MCP responses include freshness metadata so agents know when context is stale.

### Content-addressable IDs

Claim IDs are `claim-` + first 16 hex chars of `SHA-256(claim_type:scope:content)`. IDs are **immutable after creation** — edits change the content field but not the ID. This ensures override files, audit logs, and external references remain stable.

## Key patterns and conventions

### Code style

- `from __future__ import annotations` at top of every source file
- Explicit return types on all public functions
- Frozen dataclasses for domain models; Pydantic v2 at IO/config boundaries
- `typing.Protocol` for interfaces; constructor injection for dependencies
- No mutable default arguments; no global mutable state
- All logging to stderr via structlog; stdout reserved for MCP protocol

### Architectural patterns

- **Store pattern**: Protocol interface + SQLite implementation with `_row_to_*` converter functions. Every store (claims, evidence, history, artifacts, metadata, overrides) follows this shape.
- **Single enforcement point**: Sensitivity filtering happens in one place (`projection/sensitivity.py`), called at every output boundary (projection engine, MCP response filter). Not duplicated per-adapter.
- **Pure tool functions**: MCP tool implementations in `server/tools.py` are pure functions that take stores as arguments. The MCP handlers in `server/mcp.py` are thin wrappers that inject dependencies.
- **Deterministic output**: Projection adapters sort claims by (authority, scope, type, id) so output is reproducible. Timestamps are the only variance.
- **Budget tracking**: `BudgetTracker` enforces per-file hard limits (bytes), soft limits (lines), and workspace-wide limits (Windsurf's 12K total). When over budget, lowest-priority claims are dropped.
- **Content-addressable deduplication**: Same claim content produces the same ID, so re-extraction naturally deduplicates.

### Error handling

- Custom exception hierarchy rooted at `RkpError`
- `ClaimNotFoundError`, `DuplicateClaimError`, `ClaimConflictError` for domain errors
- `PathTraversalError`, `UnsafeYamlError`, `InjectionDetectedError` for security violations
- `MigrationError` for schema issues
- CLI catches exceptions and maps to `typer.Exit(code=N)`

### Security

- **Injection detection**: 41 regex patterns across HIGH/MEDIUM/LOW severity (covers `[INST]`, `<|im_start|>`, role impersonation, `<<SYS>>`, etc.). Severity downgraded by one level inside fenced code blocks.
- **Secret scanning**: Provider-specific patterns (AWS, GitHub, OpenAI, Anthropic, Slack, DB URLs, SSH keys) + Shannon entropy-based generic detection. Secrets redacted before tracing.
- **Path validation**: Resolves symlinks, rejects null bytes, checks containment within repo root.
- **YAML safety**: `yaml.safe_load()` everywhere; `strictyaml` for override files; `yaml.load()` banned (immutable rule #2).
- **MCP response filtering**: Every outbound response scanned for injection markers. Content not modified — warnings attached.

## Data layer

### Database

SQLite in WAL mode (write-ahead log), stored at `.rkp/local/rkp.db` (gitignored, regenerable). Connection factory applies production PRAGMAs:

- `journal_mode = WAL` (concurrent read/write)
- `synchronous = NORMAL`
- `busy_timeout = 5000` (5s)
- `cache_size = -64000` (64 MB)
- `foreign_keys = ON`
- `temp_store = MEMORY`
- `mmap_size = 268435456` (256 MB memory-mapped I/O)

Schema versioned via `PRAGMA user_version`. Migrations are numbered SQL files in `store/migrations/` applied sequentially.

### Schema (v2)

| Table | Purpose | Key columns |
|---|---|---|
| `claims` | All extracted/imported claims | id (PK), content, claim_type, source_authority, authority_level, scope, applicability (JSON), sensitivity, review_state, confidence, evidence (JSON), provenance (JSON), risk_class, stale |
| `claim_evidence` | Source file linkage per claim | claim_id (FK), file_path, file_hash, line_start, line_end, evidence_level |
| `claim_history` | Append-only audit trail | claim_id (FK), action, content_before, content_after, actor, timestamp, reason |
| `claim_applicability` | Normalized applicability tags | claim_id (FK), tag — enables efficient tag-based queries |
| `managed_artifacts` | Tracked instruction files | path (PK), target_host, expected_hash, ownership_mode |
| `environment_profiles` | Aggregated prerequisites | name, runtime, tools (JSON), services (JSON), env_vars (JSON) |
| `module_edges` | Dependency graph | source_path, target_path, edge_type (imports/contains/tests) |
| `session_log` | MCP session events | session_id, event_type, event_data (JSON) |
| `index_metadata` | Single-row freshness tracker | last_indexed, repo_head, branch, file_count, claim_count |
| `claims_fts` | FTS5 virtual table | Full-text search on claim content (created but not actively populated in v0.1) |

11 indexes for efficient queries on type, review state, repo, scope, sensitivity, tags, evidence files, history, module edges, and sessions.

### Override persistence

Human governance decisions stored as YAML files in `.rkp/overrides/` (checked into git). File naming: `{claim_id}_{action}.yaml`. Uses `strictyaml` for safe deserialization. Actions: `approved`, `edited`, `suppressed`, `tombstoned`, `declared`. Claim IDs validated against path traversal (alphanumeric + hyphens only). Local-only claims never written here.

## API surface

### MCP tools (11 total)

All tools return a `ToolResponse` envelope: `{status, data, warnings, provenance, freshness}`.

| Tool | Purpose | Read/Write |
|---|---|---|
| `get_conventions` | Scoped conventions with authority, confidence, evidence | Read |
| `get_validated_commands` | Build/test/lint commands with risk class and evidence level | Read |
| `get_prerequisites` | Runtimes, tools, services, env vars | Read |
| `get_guardrails` | Security restrictions and dangerous operations | Read |
| `get_module_info` | Module boundaries, dependencies, test locations, scoped rules | Read |
| `get_conflicts` | Where declared and inferred knowledge disagree | Read |
| `get_claim` | Full detail on one claim: content, evidence chain, history | Read |
| `get_instruction_preview` | What a specific agent host would see (projected artifacts) | Read |
| `get_repo_overview` | Languages, modules, claim statistics, support envelope | Read |
| `get_preflight_context` | Minimum actionable bundle for agent startup | Read |
| `refresh_index` | Incremental re-extraction after file changes | **Write** |

### MCP resources

- `rkp://repo/overview`, `rkp://repo/conventions`, `rkp://repo/conventions/{path}`
- `rkp://repo/instructions/{consumer}`, `rkp://repo/architecture/modules`, `rkp://repo/prerequisites`

### CLI commands (12 total)

| Command | Purpose |
|---|---|
| `rkp init` | Scan repo, run full extraction, bootstrap `.rkp/` |
| `rkp status` | Index health, pending reviews, stale claims, drift |
| `rkp review` | Interactive governance: approve, edit, suppress, tombstone, declare |
| `rkp preview --host <target>` | Preview projected artifacts without writing |
| `rkp apply --host <target>` | Write instruction files to disk (gates on review_state) |
| `rkp import` | Ingest existing instruction files as governed claims |
| `rkp refresh` | Re-analyze repo, flag changed/stale claims |
| `rkp serve` | Start MCP server (stdio transport) |
| `rkp audit` | Query the governance audit trail |
| `rkp quality` | Run quality harness (conformance, leakage, drift, fidelity) |
| `rkp doctor` | Validate environment: Python, git, SQLite, tree-sitter, MCP |
| `rkp purge` | Hard-delete tombstoned claims and their evidence |

All commands accept `--repo <path>`, `--json`, `--verbose`, `--quiet`.

## Extraction pipeline

The orchestrator (`indexer/orchestrator.py`) runs a 13-phase pipeline:

1. **Config parsers**: pyproject.toml → scripts, tool requirements, python-requires; package.json → npm scripts, engines; Makefile → targets with risk classification
2. **Docker parsers**: Dockerfile → base images, runtime hints, tool installs, ENV, ports; docker-compose.yml → services, images, environment, dependencies
3. **CI parsers**: GitHub Actions → triggers, jobs, matrix strategies, runtime setup actions (Python/Node/Go/Java versions), CI commands, services, environment variables
4. **Version files**: .python-version, .nvmrc, .node-version, .tool-versions → runtime version hints
5. **Docs evidence**: README and docs/ → command blocks from fenced code, runtime requirements from prose
6. **CI evidence cross-reference**: Cross-references CI commands against config commands → upgrades authority to CI_OBSERVED when matched
7. **Prerequisites aggregation**: Combines all runtime/tool/service/env var discoveries into environment profiles
8. **Python parsing**: tree-sitter → functions, classes, imports, constants, decorators, test detection
9. **JS/TS parsing**: tree-sitter → functions (including arrow), classes, imports (ES + CommonJS require), exports, test patterns
10. **Convention extraction**: Naming patterns (snake_case, camelCase, PascalCase, SCREAMING_SNAKE), test placement, import styles, type annotation coverage, docstring presence
11. **Guardrail extraction**: Destructive commands → restrictions; security tools → advisories; CI security scan patterns
12. **Boundary extraction**: Module detection (Python packages via `__init__.py`, JS via `index.ts/js`), import resolution, dependency graph construction
13. **Conflict detection**: Version conflicts, command conflicts, convention mismatches

Each phase produces claims through the `ClaimBuilder`, which generates content-addressable IDs and handles deduplication. Security scanning (injection + secrets) runs on all content before persistence.

## Projection system

### Adapters and their output

| Adapter | Maturity | Output files | Budget | Key behaviors |
|---|---|---|---|---|
| **AgentsMd** (Codex) | GA | `AGENTS.md` | 32 KiB hard | Deterministic sort, risk-class command grouping |
| **ClaudeMd** (Claude Code) | GA | `CLAUDE.md`, `.claude/rules/*.md`, `.claude/skills/*/SKILL.md`, `.claude/settings-snippet.json` | ~200 lines soft (CLAUDE.md) | Scoped rules in separate files, enforceable restrictions → deny patterns, skills from overflow |
| **Copilot** | Beta | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `copilot-setup-steps.yml`, `.copilot-tool-allowlist.json` | 300 lines soft | Thin instructions (Copilot reads AGENTS.md), setup-steps validation, conservative tool allowlist |
| **Cursor** | Alpha | `.cursor/rules/rkp-*.md` | 500 lines soft | YAML frontmatter (description, globs, alwaysApply), all prefixed `rkp-`, no native skills |
| **Windsurf** | Alpha | `.windsurf/rules/rkp-*.md` | 6K/file, 12K workspace | YAML frontmatter (trigger: always_on/glob), deduplicates with AGENTS.md, priority: guardrails > commands > setup > conventions |

### Skills projection

Claims tagged with specific applicability (e.g., "test", "build", "deploy") overflow from main instruction files into skill files. Tag-to-skill mapping produces files like `.claude/skills/validate-and-test/SKILL.md`. Per-skill: minimum 2 claims (or 1 high-value), max 20K chars body, max 10 skills per repo.

### Projection pipeline

1. Filter by sensitivity (local-only/team-only removed per target)
2. Filter by minimum confidence threshold
3. Prioritize by source authority precedence (lowest number first), then confidence (highest first)
4. Run adapter with BudgetTracker (hard_budget_bytes, soft_budget_lines, workspace_budget_bytes)
5. Return files dict + excluded claims + overflow report

## Import system

`rkp import` discovers existing instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md, .cursor/rules/, .windsurf/rules/), parses each with format-specific parsers, runs security scanning, builds claims at `DECLARED_IMPORTED_UNREVIEWED` authority (precedence 35 — between executable-config and checked-in-docs), deduplicates against existing claims, and registers imported files in the artifact store with ownership tracking.

Artifact ownership: `IMPORTED_HUMAN_OWNED` protects human-authored files from silent overwrite; `MANAGED_BY_RKP` means RKP controls the file; `MIXED_MIGRATION` for files being transitioned.

## Environment and config

### RkpConfig (Pydantic BaseSettings, `RKP_` env prefix)

| Setting | Default | Purpose |
|---|---|---|
| `repo_root` | `Path()` | Repository root path |
| `db_path` | `.rkp/local/rkp.db` | SQLite database location |
| `log_level` | `INFO` | structlog level |
| `staleness_window_days` | `90` | Time-based freshness threshold |
| `max_file_size_bytes` | `1_000_000` | Skip files larger than this |
| `excluded_dirs` | vendor, node_modules, dist, build, __pycache__, .git | Directories to skip during extraction |
| `confidence_reduction_on_stale` | `0.2` | Multiplicative confidence penalty for stale claims |
| `trace_enabled` | `True` | Enable MCP trace logging |

### Source allowlist

Controls which file types and directories are scanned. Defaults include `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.toml`, `.json`, `.yml`, `.yaml`, `.md`, `Makefile`, `Dockerfile`. Excludes `vendor/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `.git/`.

### Repo structure

```
.rkp/                              # Checked into git
├── config.yaml                    # RKP settings
├── overrides/                     # Human governance decisions (YAML, strictyaml)
│   └── claim-abc123_approved.yaml
└── local/                         # Gitignored, regenerable
    ├── rkp.db                     # SQLite index
    └── traces.jsonl               # MCP tool call trace log
```

The `.rkp/overrides/` directory is the durable record of team decisions. The database is a cache — delete it and `rkp init` rebuilds from repo + overrides.

## Testing

### Structure

- **Unit tests** (~70 files): Every module has dedicated tests. Core domain (types, models, IDs, builder, security, freshness), all stores, all parsers, all extractors, all adapters, overrides, graph, git backend.
- **Property-based tests** (Hypothesis): Claim ID determinism (same inputs → same ID), source authority total ordering, SQLite roundtrip fidelity (all fields preserved).
- **Integration tests** (~50 files): End-to-end CLI commands, MCP protocol contract, orchestrator extraction on fixture repos, quality harness, import engine roundtrip, data isolation by repo_id.
- **Snapshot tests** (Syrupy): Projection output regression for AGENTS.md, CLAUDE.md, Copilot, scoped projections.

### Running tests

```bash
nox -s test           # Run all tests
nox -s lint           # ruff check + format
nox -s typecheck      # pyright strict
nox -s quality        # Quality harness (conformance, leakage, drift)
nox -s ci             # All of the above
pytest -m "not slow"  # Skip slow tests
```

### Test fixtures

`tests/fixtures/simple_python/` — minimal Python project used for extraction integration tests. Quality harness has its own fixture repos for conformance, leakage, and import fidelity testing.

### Key test invariants verified

- IDs are deterministic and content-addressable
- Source authority is a total order (every pair comparable)
- DECLARED_IMPORTED_UNREVIEWED at precedence 35 (between EXECUTABLE_CONFIG=30 and CHECKED_IN_DOCS=40)
- SQLite roundtrips preserve all claim fields exactly
- Extraction is idempotent (second run creates zero new claims)
- Sensitivity filtering: LOCAL_ONLY never appears in projections or on-disk overrides
- Projection output is deterministic (same claims → identical output modulo timestamps)
- Budget enforcement: hard limits are never exceeded
- Injection markers detected across all severity levels with code-block downgrade
- WAL mode allows concurrent reader/writer access

## Important decisions and tradeoffs

### Why SQLite, not Postgres or a file-based store (ADR-001)

Local-first, zero-dependency deployment. The database is a regenerable cache — the durable state is the repo itself plus `.rkp/overrides/`. WAL mode provides concurrent read/write for MCP serving. FTS5 table created but not actively populated in v0.1 (ADR-008, deferred for performance measurement).

### Why Git CLI subprocess, not pygit2 (ADR-002)

Every developer already has git. pygit2 requires libgit2 which is a build dependency headache. CLI backend is 10 operations, all with 10s timeout. pygit2 deferred to Phase 2 for performance-sensitive paths.

### Why `check_same_thread=False` for MCP (ADR-009)

FastMCP's async handlers may dispatch across threads. SQLite in WAL mode with proper PRAGMAs is safe for this. The flag is only set for the MCP server, not CLI commands.

### Why imported claims at precedence 3.5 (ADR-007)

Imported claims from existing instruction files shouldn't outrank executable config (e.g., pyproject.toml scripts). But they should outrank mere docs references. Precedence 35 puts them between executable-config (30) and checked-in-docs (40).

### Why content-addressable IDs are immutable (ADR-006)

Override files, audit logs, and external references all use claim IDs. If editing a claim changed its ID, all references would break. Instead, edits change content but preserve the ID, and the history store records what changed.

### Why adapter maturity is earned via conformance harness (ADR-004, immutable rule #7)

No GA/Beta labels without the quality harness passing. Cursor and Windsurf are Alpha because they're export-only with limited conformance coverage. Promotion requires passing M13+ conformance tests.

### Why tree-sitter v0.25+ QueryCursor API (ADR-010, immutable rule #8)

The old `query.captures()` API was removed in tree-sitter 0.25. All parsing code uses `QueryCursor` — this is an enforced invariant, not just a preference.

### Windsurf-specific decisions (ADR-012, ADR-013)

Windsurf has unique constraints: 6K per-file limit, 12K workspace total, and it auto-reads AGENTS.md. RKP deduplicates Windsurf projections against AGENTS.md claims and enforces the workspace budget across all rule files.

## Gotchas

- **stdout is sacred**: All diagnostics, progress, and errors go to stderr. stdout is reserved for MCP protocol and JSON data output. If you add logging that writes to stdout, the MCP server will break.
- **`yaml.load()` is banned**: Immutable rule #2. Always `yaml.safe_load()` for repo files, `strictyaml` for `.rkp/` files. Violation would be a security vulnerability.
- **Claim IDs look like hashes but are stable**: Don't regenerate them for the same (type, scope, content). The SHA-256 prefix is the identity, and override files reference it.
- **The `apply` command gates on review_state**: Unreviewed claims don't get projected to disk. This is immutable rule #1 — no instruction file written without human review.
- **Sensitivity filter at every output boundary**: Immutable rule #3. If you add a new output path (new MCP tool, new CLI command, new adapter), it must pass through the sensitivity filter. There was a gap found and fixed in M10.
- **MCP tools are read-only except `refresh_index`**: Immutable rule #10. Adding a new write operation requires explicit acknowledgment.
- **tree-sitter QueryCursor, not query.captures()**: The old API is gone in v0.25. If you write new tree-sitter code, use `QueryCursor`. This is enforced.
- **Local-only claims have restricted storage**: They never go to `.rkp/overrides/` (immutable rule #9), only the local DB. This is enforced in the FileSystemOverrideStore.
- **Windsurf budget is workspace-wide**: Unlike other adapters where budget is per-file, Windsurf has a 12K total across all rule files. The BudgetTracker's `workspace_budget_bytes` handles this.
- **FTS5 table exists but isn't populated**: Created in the initial migration for future use, but claim insertion doesn't write to it. Don't assume full-text search works.
- **The database is a cache**: Delete `.rkp/local/rkp.db` and `rkp init` rebuilds everything. The source of truth is the repo + `.rkp/overrides/`.
- **Copilot reads AGENTS.md natively**: The Copilot adapter produces a thin `copilot-instructions.md` because Copilot already reads AGENTS.md. Don't duplicate content.
