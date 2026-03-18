# Repo Knowledge Plane — Build Research

_Consolidated 2026-03-18 from 5 research files. Single source of truth for architecture, stack, data model, extraction, security, testing, and implementation guidance._

---

## 1. Stack Decisions (Resolved)

Where research sources disagreed, the resolved decision is stated with rationale.

### 1.1 Core dependencies

```
Runtime:            Python 3.12+ (3.13 added after fixture/adapter surface is stable)
Packaging:          uv + PyPI + `uvx repo-knowledge-plane`
Build:              hatchling
MCP layer:          Official Python MCP SDK as protocol foundation; FastMCP v3.0+ standalone
                    as convenience wrapper behind internal abstraction
CLI:                typer[all] >= 0.15.0 (includes Rich)
Parsing:            tree-sitter >= 0.25.0 + CURATED grammars (Python, JS, TS only for launch)
Git:                Git CLI as default backend; pygit2 >= 1.17.0 as optional accelerator
Graph:              SQLite edges + small in-memory adjacency maps; rustworkx optional accelerator
Persistence:        sqlite3 (stdlib, WAL mode)
Domain model:       Pydantic v2 at IO boundaries; dataclasses/lightweight types internally
Config:             pydantic-settings >= 2.7.0
Logging:            structlog >= 25.0.0 (structured JSON for machines, Rich for humans, stderr only)
YAML (repo):        pyyaml >= 6.0.0 (yaml.safe_load() ONLY — never yaml.load())
YAML (.rkp/):       strictyaml (prevents code execution, limits YAML complexity)
TOML:               tomllib (stdlib, read-only, safe)
JSON:               json (stdlib)
Dockerfile:         dockerfile-parse >= 2.0.0
Typing:             pyright strict + runtime Pydantic validation at boundaries
Lint/format:        Ruff
Tests:              pytest + hypothesis + syrupy + pytest-cov + pytest-benchmark
Task runner:        Nox (better than tox for custom fixture/projection/security workflows)
CI lint:            actionlint + zizmor (for GitHub Actions)
Telemetry:          OpenTelemetry (GenAI semantic conventions; opt-in, local-first)
Docs:               MkDocs Material + GitHub Pages
Changelog:          Towncrier (fragment-based, no merge conflicts)
Supply chain:       pre-commit + dependency review + artifact attestations + CycloneDX SBOM
License:            Apache 2.0 (permissive, patent grant, enterprise-friendly)
```

### 1.2 Key decisions and their rationale

| Decision | Resolved choice | Why |
|----------|----------------|-----|
| FastMCP vs official SDK | Official SDK as protocol anchor; FastMCP behind abstraction | Official SDK is compatibility anchor. FastMCP adds lifespan, background tasks, tool timeouts, versioning — useful but should not be the architectural source of truth. Pin FastMCP strictly (3.x permits breaking changes in minor versions). |
| pygit2 vs Git CLI | Git CLI default, pygit2 optional | Git CLI avoids native library complexity, legal review friction (GPLv2 linking exception), and binary distribution issues. Preserves `uvx` adoption story. Define backend abstraction interface now. |
| rustworkx required vs optional | Optional. SQLite edges first. | P0 graph workload is structured lookups, not large-scale traversal. Adding compiled graph dependency increases install surface without proportional value. Design seam for Phase 2 enrichment. |
| attrs vs dataclasses vs Pydantic | Dataclasses internally; Pydantic at boundaries | Pydantic v2 is Rust-backed with automatic JSON Schema generation — valuable for tool contracts, config validation, adapter conformance. Dataclasses are sufficient internally. Avoid Pydantic overhead in tight loops. |
| tree-sitter-language-pack vs curated | Curated (Python, JS, TS only) | 170+ grammar bundling increases supply-chain surface, update churn, fake support breadth, and test burden. Ship curated defaults; broader grammar as optional extra. |
| structlog vs stdlib | structlog | Structured JSON for machines, Rich console for humans, context binding. Routes to stderr via stdlib handlers. |
| pyright vs mypy | pyright strict | Consistent with Pydantic ecosystem. Runtime boundary validation via Pydantic. |

### 1.3 Two distinct FastMCP packages exist

| Attribute | Official MCP SDK | Standalone FastMCP |
|-----------|-----------------|-------------------|
| **Import** | `from mcp.server.fastmcp import FastMCP` | `from fastmcp import FastMCP` |
| **Install** | `pip install "mcp[cli]"` | `pip install fastmcp` |
| **Version** | v1.x (frozen feature set) | v3.0 GA (Feb 2026) |
| **Downloads** | Moderate | ~1M/day |

Use standalone `fastmcp` v3.0+ behind an internal abstraction. The official SDK's built-in FastMCP is frozen at v1.x.

### 1.4 Platform wheel coverage

All compiled dependencies ship pre-built wheels for all major platforms:

| Dependency | macOS (Intel+ARM) | Linux (x86_64+ARM64) | Windows |
|-----------|-------------------|---------------------|---------|
| tree-sitter | Yes (universal2) | Yes | Yes |
| tree-sitter-language-pack | Yes (universal2) | Yes | Yes |
| pygit2 | Yes | Yes | Yes |
| rustworkx | Yes (tier 1) | Yes (tier 1) | Yes (tier 1) |

**No C compiler or Rust toolchain required for end users.**

### 1.5 Optional extras packaging

```
repo-knowledge-plane          # base install
repo-knowledge-plane[dev]     # development tools
repo-knowledge-plane[full-parsers]  # broader grammar support
repo-knowledge-plane[verify]  # active verification with containers
```

---

## 2. Architecture

### 2.1 4-plane architecture

1. **Extraction Plane** — Parsers for code/config/instruction files/CI workflows. Produces normalized evidence records.
2. **Claim Plane** — Deterministic claim builders + conflict resolver + source authority ordering. Produces canonical claims with provenance and review metadata.
3. **Projection Plane** — Host adapters (Codex, Claude, Copilot, Cursor, Windsurf). Pure function: `canonical_claims + adapter_caps + policy → artifacts + warnings`.
4. **Serving & Governance Plane** — MCP read tools, CLI review/apply/status/import/verify, audit trail, drift detection, freshness orchestration.

**Key isolation**: Extractors never know how hosts want to see something. Adapters never infer claims. Review layer never parses host-specific formats directly except through importers.

### 2.2 Data model boundaries

Three distinct stores:
- **Evidence store**: Immutable-ish event/evidence records
- **Canonical claim state**: Current effective claim per claim_id + history
- **Projection artifacts state**: Expected rendered outputs + hash/signature for drift detection

Avoid coupling: Do not recompute projection diffs by reparsing generated files. Keep projection snapshots in DB and compare to filesystem content hash.

### 2.3 Directory structure

```
repo-knowledge-plane/
    src/
        rkp/
            __init__.py
            __main__.py             # python -m rkp
            cli/
                app.py              # Typer app, subcommand registration, composition root
                commands/
                    init.py         # rkp init
                    review.py       # rkp review
                    apply.py        # rkp apply
                    refresh.py      # rkp refresh
                    status.py       # rkp status
                    import_.py      # rkp import
                    verify.py       # rkp verify (Phase 2)
                    audit.py        # rkp audit
                    doctor.py       # rkp doctor
                    preview.py      # rkp preview
                ui/
                    tables.py       # Rich table renderers
                    diffs.py        # Unified diff rendering
                    review_flow.py  # Interactive claim review UI
                    progress.py     # X of Y progress indicators
            server/
                mcp.py              # FastMCP instance, lifespan, run()
                tools.py            # MCP tool implementations
                resources.py        # MCP resource implementations
            core/
                models.py           # Claim, Evidence, ClaimHistory (dataclasses, frozen)
                types.py            # StrEnums: ClaimType, SourceAuthority, ReviewState, etc.
                errors.py           # Typed exception hierarchy
                config.py           # RkpConfig (pydantic-settings + YAML)
                ids.py              # Content-addressable claim ID generation
            store/
                database.py         # SQLite connection management + PRAGMAs
                claims.py           # Claim CRUD + FTS5 queries
                evidence.py         # Evidence chain storage
                history.py          # Audit trail (append-only)
                artifacts.py        # Managed artifact tracking (drift)
                migrations/
                    0001_init.sql
            indexer/
                orchestrator.py     # Coordinates extraction pipeline
                parsers/
                    python.py       # Python tree-sitter queries
                    javascript.py   # JS/TS tree-sitter queries
                extractors/
                    conventions.py  # Naming, imports, test patterns
                    commands.py     # Build/test/lint from configs
                    prerequisites.py # Runtimes, tools, services
                    ci_evidence.py  # GitHub Actions parsing
                    boundaries.py   # Module detection
                    conflicts.py    # Declared vs inferred
                config_parsers/
                    pyproject.py
                    package_json.py
                    makefile.py
                    dockerfile.py
                    docker_compose.py
                    github_actions.py
                    version_files.py
            importer/
                engine.py           # Instruction file import orchestration
                parsers/
                    agents_md.py    # AGENTS.md parser
                    claude_md.py    # CLAUDE.md parser
                    copilot.py      # copilot-instructions.md + .instructions.md
                    cursor.py       # .cursor/rules parser
                    windsurf.py     # .windsurf/rules parser
            projection/
                engine.py           # Projection orchestration
                adapters/
                    agents_md.py    # AGENTS.md generator (GA)
                    claude_md.py    # CLAUDE.md + .claude/rules/ generator (GA)
                    copilot.py      # copilot-instructions.md + copilot-setup-steps.yml (Beta)
                    cursor.py       # .cursor/rules generator (Alpha)
                    windsurf.py     # .windsurf/rules generator (Alpha)
                    skills.py       # Agent Skills (SKILL.md) generator
                capability_matrix.py # Host capabilities and constraints
                sensitivity.py      # Sensitivity filtering (leakage prevention)
                budget.py           # Context budget tracking and overflow
            graph/
                repo_graph.py       # Graph abstraction (SQLite edges, optional rustworkx)
            git/
                backend.py          # Git backend Protocol interface
                cli_backend.py      # Git CLI implementation (default)
                pygit2_backend.py   # pygit2 implementation (optional)
                coupling.py         # Co-change analysis (Phase 2)
                hotspots.py         # File change frequency (Phase 2)
            quality/
                harness.py          # Quality harness runner
                fixtures.py         # Fixture repo management
                conformance.py      # Export conformance tests
                leakage.py          # Sensitivity leakage tests
    tests/
        conftest.py
        fixtures/
            simple_python/
            simple_js/
            with_agents_md/
            with_ci/
            with_conflicts/
            with_drift/
        unit/
        integration/
        property/           # Hypothesis tests
        snapshot/            # Syrupy snapshot tests
    pyproject.toml
    uv.lock
    noxfile.py
```

### 2.4 Entry points

```toml
[project.scripts]
rkp = "rkp.cli.app:main"
```

CLI dispatches to Typer subcommands. `rkp serve` starts MCP server via `asyncio.run()`. Both share core, store, indexer, projection, and graph modules.

### 2.5 Async vs sync boundaries

| Component | Mode | Rationale |
|-----------|------|-----------|
| MCP server | async (FastMCP) | MCP stdio transport is async |
| MCP tool functions | sync | FastMCP auto-dispatches to threadpool |
| CLI commands | sync | No async benefit for CLI |
| Indexer/parser | sync | CPU-bound; asyncio adds no value |
| SQLite access | sync | stdlib sqlite3; no aiosqlite needed |
| File watching (future) | async | Event-driven, watchdog/watchfiles |

**Critical rule**: Never hold a SQLite read transaction across an `await` point.

### 2.6 Dependency injection

Constructor injection + `typing.Protocol` interfaces + composition root in `cli/app.py`. No framework needed.

```python
class ClaimStore(Protocol):
    def get_claims(self, scope: str, task_context: str | None = None) -> list[Claim]: ...
    def save_claim(self, claim: Claim) -> None: ...
```

---

## 3. Data Model

### 3.1 Core domain types

```python
class ClaimType(StrEnum):
    ALWAYS_ON_RULE = "always-on-rule"
    SCOPED_RULE = "scoped-rule"
    SKILL_PLAYBOOK = "skill-playbook"
    ENVIRONMENT_PREREQUISITE = "environment-prerequisite"
    VALIDATED_COMMAND = "validated-command"
    PERMISSION_RESTRICTION = "permission-restriction"
    MODULE_BOUNDARY = "module-boundary"
    CONFLICT = "conflict"

class SourceAuthority(StrEnum):
    HUMAN_OVERRIDE = "human-override"              # precedence 1
    DECLARED_REVIEWED = "declared-reviewed"         # precedence 2
    DECLARED_IMPORTED_UNREVIEWED = "declared-imported-unreviewed"  # precedence 2.5
    EXECUTABLE_CONFIG = "executable-config"         # precedence 3
    CI_OBSERVED = "ci-observed"                     # precedence 3
    CHECKED_IN_DOCS = "checked-in-docs"            # precedence 4
    INFERRED_HIGH = "inferred-high"                # precedence 5
    INFERRED_LOW = "inferred-low"                  # precedence 6

class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    NEEDS_DECLARATION = "needs-declaration"
    APPROVED = "approved"
    EDITED = "edited"
    SUPPRESSED = "suppressed"
    TOMBSTONED = "tombstoned"

class Sensitivity(StrEnum):
    PUBLIC = "public"
    TEAM_ONLY = "team-only"
    LOCAL_ONLY = "local-only"

class RiskClass(StrEnum):
    SAFE_READONLY = "safe-readonly"
    SAFE_MUTATING = "safe-mutating"
    TEST_EXECUTION = "test-execution"
    BUILD = "build"
    DESTRUCTIVE = "destructive"
```

**Note**: `SourceAuthority` includes the split `DECLARED_REVIEWED` / `DECLARED_IMPORTED_UNREVIEWED` per PRD amendment recommendation. Imported claims should not outrank executable configuration until a human reviews them.

### 3.2 Claim ID generation

Content-addressable: `SHA-256(claim_type + ":" + scope + ":" + content)`, truncated to 16 hex chars, prefixed with `claim-`. Enables deduplication across re-extractions. Immutable after creation.

**Stability**: Git blob OIDs (SHA-1 of file contents with header) are already content-addressable — use them for incremental analysis change detection instead of computing SHA-256 separately.

### 3.3 Core applicability tags (controlled vocabulary)

Core: `build, test, lint, format, docs, review, refactor, debug, security, ci, release, onboarding`

Plus optional custom tags. Standardize after design-partner usage patterns emerge.

### 3.4 SQLite schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -64000;      -- 64MB page cache
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;    -- 256MB

CREATE TABLE claims (
    id              TEXT PRIMARY KEY,
    content         TEXT NOT NULL,
    claim_type      TEXT NOT NULL,
    source_authority TEXT NOT NULL,
    authority_level INTEGER NOT NULL,   -- 1-6, for ordering
    scope           TEXT NOT NULL DEFAULT '**',
    applicability   TEXT NOT NULL DEFAULT '[]',   -- JSON array of tags
    sensitivity     TEXT NOT NULL DEFAULT 'public',
    review_state    TEXT NOT NULL DEFAULT 'unreviewed',
    confidence      REAL NOT NULL DEFAULT 0.0,
    evidence        TEXT NOT NULL DEFAULT '[]',   -- JSON
    provenance      TEXT NOT NULL DEFAULT '{}',   -- JSON
    risk_class      TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    repo_id         TEXT NOT NULL,
    branch          TEXT NOT NULL DEFAULT 'main',

    CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE TABLE claim_evidence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        TEXT NOT NULL REFERENCES claims(id),
    file_path       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,        -- git blob OID
    line_start      INTEGER,
    line_end        INTEGER,
    extraction_version TEXT NOT NULL,
    UNIQUE(claim_id, file_path, extraction_version)
);

CREATE TABLE claim_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        TEXT NOT NULL REFERENCES claims(id),
    action          TEXT NOT NULL,
    content_before  TEXT,
    content_after   TEXT,
    actor           TEXT NOT NULL DEFAULT 'system',
    timestamp       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    reason          TEXT
);

CREATE TABLE managed_artifacts (
    path            TEXT PRIMARY KEY,
    artifact_type   TEXT NOT NULL,
    target_host     TEXT NOT NULL,
    expected_hash   TEXT NOT NULL,
    last_projected  TEXT NOT NULL,
    ownership_mode  TEXT NOT NULL DEFAULT 'managed-by-rkp'
);

CREATE TABLE claim_applicability (
    claim_id        TEXT NOT NULL REFERENCES claims(id),
    tag             TEXT NOT NULL,
    PRIMARY KEY (claim_id, tag)
);

CREATE TABLE environment_profiles (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    runtime         TEXT,               -- e.g., "python:3.12"
    tools           TEXT DEFAULT '[]',  -- JSON array
    services        TEXT DEFAULT '[]',  -- JSON array
    env_vars        TEXT DEFAULT '[]',  -- JSON array (names only, never values)
    setup_commands  TEXT DEFAULT '[]',  -- JSON array
    repo_id         TEXT NOT NULL,
    UNIQUE(name, repo_id)
);

CREATE TABLE module_edges (
    source_path     TEXT NOT NULL,
    target_path     TEXT NOT NULL,
    edge_type       TEXT NOT NULL,      -- imports, contains, tests
    repo_id         TEXT NOT NULL,
    PRIMARY KEY (source_path, target_path, edge_type, repo_id)
);

CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE INDEX idx_claims_review ON claims(review_state);
CREATE INDEX idx_claims_repo ON claims(repo_id, branch);
CREATE INDEX idx_claims_scope ON claims(scope);
CREATE INDEX idx_claims_sensitivity ON claims(sensitivity);
CREATE INDEX idx_applicability_tag ON claim_applicability(tag);
CREATE INDEX idx_evidence_claim ON claim_evidence(claim_id);
CREATE INDEX idx_evidence_file ON claim_evidence(file_path);
CREATE INDEX idx_history_claim ON claim_history(claim_id);
CREATE INDEX idx_module_source ON module_edges(source_path);
CREATE INDEX idx_module_target ON module_edges(target_path);

CREATE VIRTUAL TABLE claims_fts USING fts5(
    content, content=claims, content_rowid=rowid,
    tokenize='porter unicode61'
);
```

### 3.5 Migration strategy

`PRAGMA user_version` + numbered SQL files in `src/rkp/store/migrations/`. Runner reads `user_version`, executes higher-numbered files in order, each wrapped in a transaction. No ORM, no framework.

### 3.6 Concurrent access pattern

WAL mode enables: multiple MCP server reader connections + one indexer writer connection simultaneously. Readers see consistent snapshots. Writers don't block readers. Only one write at a time; additional writers wait up to `busy_timeout` (5000ms).

### 3.7 Artifact ownership modes

- `imported-human-owned`: Existing file imported into claims, but not managed by RKP
- `managed-by-rkp`: File or managed sections may be regenerated after review
- `mixed-migration`: User moving from human-owned to managed, with explicit diffs/warnings

Without this distinction, the product will either overwrite trusted files or become unable to evolve them.

---

## 4. MCP Server Design

### 4.1 Server lifecycle (lifespan pattern)

```python
from fastmcp import FastMCP
from fastmcp.server import Context

mcp = FastMCP(
    "repo-knowledge-plane",
    version="0.1.0",
    instructions="Repo Knowledge Plane: verified operational context for this repository.",
)

@mcp.lifespan
async def lifespan(server):
    config = load_config()
    db = open_database(config.db_path)
    graph = build_repo_graph(db)
    try:
        yield {"db": db, "graph": graph, "config": config}
    finally:
        db.close()
```

Graph persists for entire server process lifetime (stdio = client session duration).

### 4.2 Tool annotations

All RKP tools set `readOnlyHint: true`. This allows hosts to skip confirmation prompts.

### 4.3 Tool response envelope

Every tool response includes:
- `status`
- `supported` or `unsupported_reason`
- `data`
- `warnings`
- `provenance`
- `freshness`
- `review_state`

### 4.4 Recommended tool surface

Core tools:
- `get_preflight_context(path_or_symbol, task_context, host, detail_level)` — summary bundle for current task
- `get_conventions(path_or_symbol, task_context)` — scoped conventions
- `get_prerequisites(scope)` — environment and command prerequisites
- `get_conflicts(scope)` — declared vs inferred conflicts
- `get_claim(claim_id)` / `explain_claim(claim_id)` — claim details with evidence
- `refresh_index(scope)` — trigger incremental re-indexing
- `doctor_support_envelope()` — what's supported, what's not, why

### 4.5 Response-size strategy

Host context windows punish oversized responses. Every tool supports:
- Path scoping
- Pagination (`cursor`/`limit` params) or bounded result counts
- Optional terse vs detailed mode
- Optional inclusion of evidence snippets

MCP does not support streaming tool results. Return truncated results with note and next cursor.

### 4.6 Lazy initialization

Start indexing in background during lifespan startup. Tools return partial results or "indexing in progress" status until complete. Best UX for agents that start and immediately query.

### 4.7 Logging

All logging MUST use stderr. stdout is reserved for MCP protocol messages.

---

## 5. Extraction Strategy

### 5.1 Convention extraction tractability

| Convention | Method | Confidence | Notes |
|-----------|--------|-----------|-------|
| Naming conventions | tree-sitter + regex | High | Captured identifiers classified by regex |
| File naming conventions | Filesystem scan | High | Pattern matching |
| Import ordering/grouping | tree-sitter | Medium-High | Needs stdlib list for Python |
| Test file placement | Filesystem scan | High | Pattern matching |
| Test naming patterns | tree-sitter | High | Query for test functions/classes |
| Type annotation usage | tree-sitter | High | Count annotated vs unannotated |
| Error handling patterns | tree-sitter (structure) | Medium | Shape detection, not adequacy |
| Docstring presence/style | tree-sitter | Medium-High | Detect presence and format |
| Module structure | Filesystem | Medium | Naming heuristics only |
| Architectural layers | No (needs LLM) | Low | Requires semantic understanding |

**Focus on "High" confidence detections for MVP. Defer LLM-assisted extraction.**

### 5.2 Convention hierarchy (most to least authoritative)

1. Enforced by config or tooling (ruff, prettier, editorconfig)
2. Declared by checked-in instruction or policy file
3. Strongly repeated across code samples (>=95% consistency)
4. Weakly inferred from examples (80-94%)
5. Below 80%: no convention — do not assert

**Critical**: If `ruff format` or Prettier owns formatting, do not generate verbose style instructions. Use always-on files for non-inferable conventions, not for restating toolchain defaults.

### 5.3 Confidence thresholds

| Consistency | Classification |
|------------|---------------|
| >= 95% | Strong convention — assert as rule |
| 80-94% | Weak convention — flag for human review |
| < 80% | No convention — do not assert |

Minimum sample: 20+ identifiers per category. Per-scope analysis (not just global).

### 5.4 Tree-sitter query patterns

**Python function definitions:**
```scm
(function_definition name: (identifier) @func_name
  parameters: (parameters) @params body: (block) @body)
```

**Python imports:**
```scm
(import_statement name: (dotted_name) @module)
(import_from_statement module_name: (dotted_name) @source
  name: (dotted_name) @imported_name)
```

**Python classes:**
```scm
(class_definition name: (identifier) @class_name
  superclasses: (argument_list)? @bases body: (block) @body)
```

**Python test detection:**
```scm
(function_definition name: (identifier) @test_func
  (#match? @test_func "^test_"))
```

**JS/TS functions:**
```scm
(function_declaration name: (identifier) @func_name)
(lexical_declaration (variable_declarator
  name: (identifier) @func_name value: (arrow_function)))
```

### 5.5 Naming convention classification (regex)

- `snake_case`: `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`
- `SCREAMING_SNAKE`: `^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$`
- `camelCase`: `^[a-z][a-zA-Z0-9]*$`
- `PascalCase`: `^[A-Z][a-zA-Z0-9]*$`

### 5.6 CI config parsing

**GitHub Actions extraction targets:**

| What to extract | Where | How |
|----------------|-------|-----|
| Commands | `steps[].run` | Direct string extraction |
| Runtime versions | `actions/setup-python`, `setup-node` `with` inputs | Action metadata |
| Services | `jobs[].services` | Image, env, ports extraction |
| Environment variables | Workflow/job/step `env` | Aggregated, secrets noted |
| OS | `jobs[].runs-on` | Direct |
| Matrix dimensions | `strategy.matrix` | Expand combinations |

**CI evidence confidence levels:**

| Level | Condition |
|-------|----------|
| **High** | Unconditional step, push/PR trigger, no continue-on-error |
| **Medium** | Conditional step or within matrix job |
| **Low** | continue-on-error: true, or schedule/dispatch only |
| **Unknown** | Inside composite action or unresolvable reusable workflow |

**Expression handling**: Do NOT build a full GitHub Actions expression evaluator. Extract expressions as strings, resolve simple matrix references, mark unresolvable. Covers 90%+ of practical cases.

### 5.7 Config parser priority (value/effort ratio)

1. GitHub Actions workflows — highest value, medium effort
2. pyproject.toml — high value, low effort (tomllib stdlib)
3. package.json — high value, low effort (json stdlib)
4. Dockerfile — medium value, low effort (dockerfile-parse)
5. docker-compose.yml — medium value, low effort (yaml.safe_load)
6. Makefile — medium value, medium effort (custom regex)
7. Runtime version files — low effort, useful cross-reference

### 5.8 Command extraction evidence scoring

Favor: commands executed in CI, commands in canonical tool manifests, commands declared in human-reviewed repo policy.

Weak: prose docs without corroboration, shell snippets in issue templates or blog-like docs.

Sources: CI workflows, task runners (Makefile, justfile, package.json, pyproject.toml, noxfile.py, tox.ini), existing instruction files, docs with explicit command blocks, user overrides.

### 5.9 Module and boundary extraction (honest scope)

**P0 can reliably return:**
- Top-level packages or services
- Import-based coarse dependencies
- Likely test locations
- Path boundaries from manifests and repo structure

**P0 cannot honestly promise:**
- Semantically complete call graphs
- Runtime dependency guarantees
- Accurate architecture-layer intent without human or doc evidence

Honesty here builds trust.

### 5.10 Instruction file import parsing (hybrid)

1. **Deterministic**: YAML frontmatter, JSON configs, code blocks, glob patterns
2. **Heuristic**: Heading classification, bullet extraction, command detection, boundary markers
3. **LLM-assisted** (deferred): Prose paragraphs, architectural descriptions, implicit conventions

**Critical**: Not all documentation should become claims. Only extract when material is operational, repo-specific, plausibly current, and specific enough to guide work. Ignore generic overview prose, stale templates, aspirational docs, duplicated content.

### 5.11 No existing tools parse instruction files into structured claims

This is greenfield. No formal grammar or BNF exists for any instruction file format. No standardized approach for merging or reconciling rules from multiple formats. RKP would be first.

---

## 6. Instruction Projection Strategy

### 6.1 Thin-by-default is non-negotiable

**Always-on content should include only:**
- Non-inferable repo-specific constraints
- High-confidence, broad-applicability claims
- Critical validation commands
- Dangerous-operation restrictions
- Host usage hints that materially change behavior
- References to on-demand skills or playbooks

**Exclude from always-on:**
- Repo overviews
- Generic architecture descriptions the agent can infer from files
- Style rules already enforced by tooling
- Large command catalogs
- Speculative or weak-confidence conventions

### 6.2 Skills and playbooks for detailed procedures

Examples of strong playbook candidates:
- How to validate Python changes in this repo
- Safe workflow for touching CI configuration
- How to modify generated code
- How to work inside a risky subsystem
- Migration workflow for a particular package area

### 6.3 Context budget tracking

Every projection must track:
- Hard budget (host-specific max)
- Soft budget (recommended max)
- Included claims (with reason)
- Omitted claims (with reason)
- Downgrade route taken (e.g., moved to skill)

### 6.4 Projection decision provenance

Every projected artifact explainable at claim level:
- Why included
- Why excluded
- Why moved to a skill
- Why downgraded for size
- Why filtered for sensitivity
- Which host capability forced the decision

### 6.5 Round-trip fidelity

Preserve original file structure as template. Anchor-based diffing (stable headings, frontmatter keys). Generate minimal diff against existing content. Respect per-host size constraints.

### 6.6 Agent Skills standard (SKILL.md)

Required fields: `name` (max 64 chars, lowercase/hyphens), `description` (max 1024 chars). Optional: `license`, `compatibility`, `metadata`, `allowed-tools`. Progressive disclosure: metadata at startup (~100 tokens), full instructions on activation (<5000 tokens), resources as needed.

### 6.7 Managed-file write policy

- Never silently rewrite files
- Preview exact diffs
- Show omitted claims and why
- Include generation headers and provenance
- Support no-op preview when nothing changed
- If unmanaged edits in managed region: detect drift, refuse blind overwrite, surface reconciliation choices

### 6.8 Determinism requirements

Generated artifacts must be deterministic for the same effective claim state:
- Stable ordering rules
- Normalized whitespace
- Stable tie-breakers
- No timestamp noise inside managed content (except explicitly in headers)

---

## 7. Host Adapter Implementation Details

### 7.1 Adapter contract

Each adapter defines supported primitives:
- `always_on`, `scoped_rules`, `skills`, `env`, `permissions`, `mcp_tools`, `mcp_resources`, `mcp_prompts`, `size_constraints`, `auth_constraints`

Projection engine contract:
- Input: canonical claims + task context + adapter capability descriptor
- Output: artifact set + excluded-claim report + overflow report + security warnings

### 7.2 Internal neutral projection model

Do NOT make AGENTS.md or CLAUDE.md the canonical internal model. The canonical model is claim-based. Keep a neutral projection abstraction with:
- Always-on guidance blocks
- Path-scoped rules
- Playbook references
- Environment/bootstrap directives
- Restrictions or guardrails
- Overflow and omission notes

### 7.3 Codex adapter (GA)

- Root `AGENTS.md` + nested overrides
- `.agents/skills` for procedural workflows
- Optional `.codex/config.toml` templating
- Hard byte budgeting (32 KiB combined) with truncation diagnostics
- Prefer nearest-directory guidance for specialized rules

### 7.4 Claude adapter (GA)

- `CLAUDE.md` and `.claude` surfaces
- Path-scoped rule support via `.claude/rules/` with `paths` frontmatter
- Skills projection to `.claude/skills/`
- Settings guidance for permissions and behavior
- Keep always-on concise; push procedural detail to skills
- Defer hooks/subagent generation until base adapter is stable

### 7.5 Copilot adapter (Beta)

- `.github/copilot-instructions.md`
- `.github/instructions/**/*.instructions.md`
- `.github/workflows/copilot-setup-steps.yml` (validate constraints before writing)
- MCP tool allowlist generation
- **Do NOT rely on resources/prompts** for coding agent flows
- Pre-validate setup workflow constraints (single job named `copilot-setup-steps`, max 59 min timeout, supported keys only)

### 7.6 Cursor/Windsurf adapters (Alpha)

Export-only. Conformance tests gated before claiming parity. Clearly documented gaps. No import promise until behavior is better characterized.

---

## 8. Security & Trust Model

### 8.1 Threat model

1. **Instruction poisoning** from untrusted files
2. **MCP tool overreach/exfiltration**
3. **Secrets leakage** in projected artifacts
4. **Active verification command abuse**
5. **Remote MCP SSRF/token abuse** (future phases)
6. **Prompt injection** via repo artifacts

### 8.2 Prompt injection defense (layered)

1. **Input sanitization**: Scan for injection markers (`[INST]`, `System:`, `role:`, `ignore previous`, `<|im_start|>`)
2. **Content typing**: Structured JSON responses with explicit `content_type` fields. Claim content is data, not meta-instructions.
3. **Source authority as trust signal**: Low-confidence inferred claims carry lower weight
4. **Response filtering**: Scan MCP responses for meta-instruction patterns before serving
5. **Human review**: The review state machine is itself an anti-injection mechanism
6. **No executable content**: MCP responses never contain instructions to execute

### 8.3 Safe parsing rules

| Format | Parser | Safety rule |
|--------|--------|------------|
| YAML (repo) | `yaml.safe_load()` | NEVER `yaml.load()` |
| YAML (.rkp/) | `strictyaml` | Prevents all YAML complexity |
| TOML | `tomllib` (stdlib) | Safe by design |
| JSON | `json.loads()` (stdlib) | Safe by design |

### 8.4 Sandbox execution hierarchy (Phase 2+)

1. **Default**: Passive analysis only (no execution)
2. **Opt-in safe-readonly**: Git worktree isolation
3. **Opt-in test/build**: Podman rootless with `--network=none --read-only --memory 1g --cpus 2 --pids-limit 256 --timeout 300`
4. **Destructive**: Per-command approval + podman, no host secret mounts

### 8.5 Path traversal prevention

`pathlib.Path.resolve()` to follow symlinks, then verify path starts with resolved repo root. Reject null bytes. Never follow symlinks outside repo root.

### 8.6 Secret detection

Lightweight entropy + regex pass (patterns from `detect-secrets`). Auto-flag potential secrets as `sensitivity: local-only`. Store env var names but never values.

### 8.7 Sensitivity enforcement

Single enforcement point: filter function at last stage before output (both projection and MCP response). Quality harness includes automated leakage tests. `local-only` claims stored only in `.rkp/local/`, never in `.rkp/overrides/`.

### 8.8 Concrete trust rules

1. **Default import is text-only.** Do not import executable MCP config, hook config, or script-backed skills without explicit trust promotion.
2. **No token passthrough, ever.** Remote MCP proxying must mint/validate its own downstream credentials.
3. **Remote MCP clients must enforce HTTPS and block private IP ranges by default.**
4. **Copilot tool configs must be explicit allowlists of read-only tools.**
5. **Skill capability model**: Instruction-only skills safer by default; script-backed skills require extra trust and review.
6. **Verification boundary stays hard**: No user secrets, no network by default, rootless containers or throwaway worktrees.
7. **Generated artifact headers include digest or projection ID** for drift detection.

### 8.9 Local-first as a real property

No repo content transmitted off local machine by RKP itself. Requires discipline around: logs, crash reports, optional telemetry, dependency behavior, remote MCP experiments. Default: local-only, no outbound transmission, opt-in export only.

---

## 9. CLI UX Design

### 9.1 Top-level commands (P0)

- `rkp init` — Scan, extract, generate draft claims, present review queue
- `rkp index` — Run/update extraction
- `rkp review` — Interactive claim review
- `rkp apply` — Write approved projections to filesystem
- `rkp import` — Import existing instruction files as claims
- `rkp preview` — Show what would be projected (no write)
- `rkp status` — Operational dashboard (index freshness, drift, pending reviews, adapter state)
- `rkp doctor` — Validate runtime, DB health, parser availability, MCP boot health

Later: `rkp verify`, `rkp export`, `rkp explain`, `rkp check` (CI mode)

### 9.2 Output formatting

| Format | When |
|--------|------|
| Colored text | Interactive TTY |
| Rich tables | Multiple items (`rkp status`, `rkp audit`) |
| Unified diff | Before/after changes (`rkp refresh`, `rkp review`) |
| JSON | `--json` flag |
| Plain text | Piped / `NO_COLOR` / CI |

### 9.3 Progress indicators

| Duration | Indicator | Example |
|----------|-----------|---------|
| < 100ms | None | Warm MCP queries |
| 100ms-3s | Spinner | Incremental update |
| > 3s | X of Y counter | "Parsing: 847/1,203" |

### 9.4 Interactive review flow (rkp review)

Rich Panel per claim: id, type, authority, scope, content, evidence, confidence. Keyboard shortcuts: [a]pprove, [e]dit, [s]uppress, [t]ombstone, [n]ext, [q]uit. Running totals: "Reviewed 12/47 (8 approved, 2 edited, 2 suppressed)". Edit via `$EDITOR`. Batch: `--approve-all` for high-confidence claims.

### 9.5 `rkp init` flow

1. Detect support envelope and repo shape
2. Detect existing managed and unmanaged instruction surfaces
3. Run extraction, build initial claims
4. Present concise findings summary
5. Generate previews for supported adapters
6. Open/print review queue

Must answer quickly: "What did you learn?" and "What are you proposing to write?"

### 9.6 `rkp doctor` flow

Validate: required runtime/tooling, SQLite features and DB health, parser availability, support-envelope matches, MCP server boot health, adapter prerequisites, permissions/path issues.

### 9.7 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Findings present (drift, unreviewed claims) |
| 2 | Usage error |
| 3 | Resource not found (not initialized) |
| 130 | Interrupted (Ctrl+C) |

### 9.8 Verbosity levels

- Default: clean, human-friendly
- `-q/--quiet`: exit code only
- `-v/--verbose`: evidence chains, timing
- `-vv/--debug`: full diagnostic output

---

## 10. Testing Strategy

### 10.1 Test pyramid

**Unit tests:**
- Claim merge logic, confidence scoring, applicability filtering
- Projection prioritization and overflow logic
- Support-envelope checks, precedence ordering

**Parser/extractor tests:**
- Per-extractor fixture inputs, line-accurate evidence expectations
- Malformed file behavior

**Golden projection tests (syrupy):**
- Canonical claims → host artifacts (deterministic snapshots)
- Overflow diagnostics, omission reports

**Round-trip tests:**
- Import existing instruction file → synthesize claims → project preview
- Ensure expected fidelity or expected warning

**CLI integration tests:**
- Temp repo fixtures
- End-to-end `init`, `review`, `preview`, `status`, `apply`

**MCP contract tests:**
- Tool argument validation, response envelope consistency
- Unsupported behavior explicitness

**Performance tests:**
- Cold index on fixture repos, warm query latency, incremental update timing

**Security/leakage tests:**
- Sensitive claim filtering works
- `local-only` claims never escape to checked-in projections
- Tool responses honor sensitivity and support envelope

### 10.2 Fixture repos

| Fixture | Tests |
|---------|-------|
| `simple_python/` | Python conventions, pytest, src layout |
| `simple_js/` | JS/TS conventions, npm scripts, ESLint |
| `with_agents_md/` | Import workflow for existing AGENTS.md |
| `with_ci/` | GitHub Actions parsing |
| `with_conflicts/` | Declared vs inferred conflicts |
| `with_drift/` | Managed files manually edited |

Each includes `expected_claims.json` for precision/recall measurement. Fixtures must be curated, versioned, and stable.

### 10.3 MCP server testing

FastMCP in-memory client transport (no subprocess, no network):

```python
async def test_get_conventions():
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"path_or_symbol": "src/payments"})
        assert "claim-001" in result[0].text
```

**Gotcha**: Do NOT create Client in pytest fixtures. The async context manager must live within the test function body.

### 10.4 Property-based testing (Hypothesis)

- Claim roundtrip through SQLite (store/retrieve identity)
- Claim roundtrip through JSON (serialize/deserialize identity)
- Precedence ordering is a total order
- Sensitivity filtering never leaks (team-only claims never in public projections)
- Scope matching consistency
- Projection prioritization under size limits
- Drift detection correctness under file mutations
- Idempotence of preview without evidence changes

### 10.5 CI matrix

GitHub Actions: ubuntu-latest + macos-latest + windows-latest, Python 3.12 + 3.13. Steps: setup-uv, sync, ruff check, ruff format --check, pyright, pytest with coverage.

### 10.6 P0 SLOs

- Warm query p50 < 500ms for top tools
- Incremental refresh p95 < 3s for single-file change
- Init success on envelope repos > 95%
- Projection conformance for GA adapters > 95%

---

## 11. Performance

### 11.1 Targets

| Target | Budget | Estimated |
|--------|--------|-----------|
| Warm MCP query | < 500ms | 10-35ms |
| Initial index (250k LOC) | < 5 min | 3-5 min |
| Incremental update | < 2s | Sub-second per file |
| Idle memory | < 200MB | 70-120MB for 250k LOC |

### 11.2 Key optimizations

- In-memory graph (loaded at server start)
- SQLite prepared statements, WAL mode, 64MB page cache
- Batch SQLite writes (`executemany()` in single transaction)
- Content-hash tracking via git blob OIDs (free)
- Skip incremental tree-sitter parsing (re-parse from scratch is fast enough)
- File exclusion before parsing (vendor/, node_modules/, etc.)

### 11.3 Profiling tools

| Tool | Use |
|------|-----|
| cProfile | Dev profiling, function-level |
| py-spy | Production MCP server profiling |
| memray | Memory profiling (tracks native C/Rust allocations) |
| line_profiler | Line-level after identifying hotspots |

### 11.4 Rust acceleration path (future)

**Migration priority:**
1. File parsing + convention extraction — highest value, 3-10x speedup
2. Graph construction — reduces boundary crossings
3. Diff computation + scope resolution — Rust regex ~2x faster
4. Secret detection — CPU-bound regex

**Stays in Python:** CLI (typer), MCP server (FastMCP), SQLite I/O, config parsing (Pydantic), projection/template rendering.

**Strategy:** Start pure Python. Profile in production-like conditions. Extract bottlenecks via PyO3/maturin. If <2x improvement, keep Python.

---

## 12. Distribution & Packaging

### 12.1 pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "repo-knowledge-plane"
requires-python = ">=3.12"
version = "0.1.0"

[project.scripts]
rkp = "rkp.cli.app:main"

[tool.hatch.build.targets.wheel]
packages = ["src/rkp"]
```

### 12.2 Versioning

SemVer starting at `0.1.0`. Use `0.x.y` during alpha/beta. Move to `1.0.0` when MCP tool API and claim schema are stable.

### 12.3 Release pipeline

Trusted Publishing (OIDC) for PyPI via GitHub Actions. Tag-triggered: `v*`. Changelog via Towncrier.

### 12.4 Platform support

- Phase 1: macOS and Linux first
- Windows as later support target unless design partner requires it
- Python 3.12 first, 3.13 after fixture/adapter surface is stable
- Reason: shell, path, file watching, and local-agent tooling are materially easier on macOS/Linux first

### 12.5 Remote deployment (future)

1. Ship local-first
2. Ship OCI image + reference deployment
3. Support single-tenant managed pilots
4. Only then evaluate shared service

Do not let remote-mode architecture leak into local-first core.

---

## 13. Edge Cases & Failure Modes

### 13.1 Handled gracefully

| Scenario | Behavior |
|----------|----------|
| tree-sitter parse error | Always produces tree with ERROR nodes; report "partially analyzed" |
| Corrupted git repo | Catch error; fall back to filesystem-only |
| Corrupted SQLite DB | Regenerable from repo + `.rkp/overrides/`; delete and re-init |
| Monorepo with 50 packages | Detect workspaces, index per-package, support selective indexing |
| Concurrent RKP processes | WAL handles readers+writer; lockfile for exclusive ops |
| Submodules | Detect, report, do NOT index by default |
| Large/generated files | Skip >1MB by default; respect .gitignore |
| Conflicting instruction files | Create `conflict` claims, surface in `get_conflicts` |
| File renames | Detect via diff similarity, update claim scopes |
| Merge conflicts in `.rkp/` | Design override files for merge-friendliness (self-contained entries) |
| Branch switch mid-session | Serve existing claims with warning in provenance; refresh on next query |

### 13.2 Defensive defaults

- File size limit: 1MB (configurable)
- Default exclusions: `vendor/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `.git/`
- Convention minimum sample: 20 identifiers per category
- Confidence floor for projection: 0.5 (below never projected to always-on files)
- WAL busy timeout: 5000ms
- Parser timeout: configurable via tree-sitter `timeout_micros`

---

## 14. Git Backend Strategy

### 14.1 Backend interface

Define now, regardless of implementation:
- Get repo root, HEAD, branch identity
- List tracked files
- Compute file hashes and diff status
- Get file history summary
- Read blame or change frequency (later)
- Create clean worktree (for verification)

### 14.2 Git CLI backend (default)

- Git is already a real dependency in every target repo
- Avoids native library complexity
- Reduces legal review friction vs pygit2
- Easier to debug and support
- Preserves `uvx` adoption story

### 14.3 pygit2 backend (optional accelerator)

- GPLv2 with linking exception — may trigger legal review in some orgs
- Better performance for heavy git operations
- Add ADR early on licensing and distribution strategy

### 14.4 History mining stays light in Phase 1

Phase 1 git use: repo identity, branch/head provenance, drift and freshness triggers, optional simple change-frequency heuristics.

Temporal coupling and hotspot analytics belong to Phase 2, after current-state contract is trusted.

---

## 15. Graph Strategy

### 15.1 Phase 1: SQLite edges

Store graph edges in SQLite `module_edges` table. Materialize small in-memory adjacency maps when needed. Profile real workloads before adding compiled graph dependency.

### 15.2 P0 graph responsibilities

- Coarse dependency questions
- Map paths to modules
- Map modules to likely test directories
- "What else is nearby or connected" for review and projection

That's a structured lookup problem, not large-scale graph computation.

### 15.3 Phase 2 enrichment seam

Design interfaces so Phase 2 can add:
- Semantic edges from LSP or SCIP
- Temporal co-change edges
- Ownership and incident edges
- Risk propagation traversals

Design the seam now, not the implementation.

---

## 16. Documentation Strategy

### 16.1 Required doc structure

- `README.md`: Install, quickstart, core commands, support envelope, trust model
- `docs/architecture.md`: System boundaries, data flow, extension seams, constraints
- `docs/decisions.md`: Append-only ADR log
- `docs/claim-model.md`: Canonical claim schema and merge rules
- `docs/host-adapters.md`: Host capability matrix and projection rules
- `docs/quality-harness.md`: Fixture strategy, evals, conformance tests
- `docs/security.md`: Local data boundary, leakage policy, remote risks
- `docs/ops.md`: DB lifecycle, migrations, release, rollback, support commands

### 16.2 Missing docs that matter immediately

- `docs/architecture.md`
- `docs/decisions.md`

Should exist early, be authoritative, not verbose.

### 16.3 Immediate ADR topics

- Canonical storage and migration strategy
- Git backend strategy
- Parser support envelope
- Artifact ownership modes
- Adapter maturity policy
- Remote deployment stance

### 16.4 Dogfooding

Use RKP on its own repo only after import and review flows are trustworthy. Use project as one fixture repo, never the only one.

---

## 17. Quality Harness as Product

The quality harness is the moat, not just a safety net. The product can only succeed if it can repeatedly prove:
1. Extracted claims are good enough
2. Projected artifacts are faithful and thin
3. System does not leak or overstate unsupported information

### 17.1 Unknown-unknowns discovery program (parallel with build)

1. **Host behavior drift tracking**: Weekly adapter smoke tests against latest host versions, snapshot capability matrix updates
2. **Parser correctness drift**: Nightly fixture replay across representative repos, alert on extraction precision drops
3. **Supply-chain and license drift**: Dependency/license scanning at release boundaries
4. **Context-effect regressions**: Track token/runtime overhead by adapter + task type, regression gate for context bloat
5. **Security red-team**: Prompt-injection and MCP overreach simulations quarterly, verification sandbox escape tests

---

## 18. Recommended Immediate Decisions (Pre-Coding)

1. Confirm the canonical package name and research artifacts location
2. Update PRD stack lines for MCP, parsing, git, and graph choices
3. Decide artifact ownership model for imported instruction files
4. Define support envelope precisely for Phase 1
5. Commit to curated parser set for launch
6. Commit to Git CLI backend first
7. Commit to SQLite edge store first
8. Create `docs/architecture.md` and `docs/decisions.md` before implementation fans out
9. Define first fixture repo set and quality harness shape before building extractors
10. Treat Codex and Claude as the only GA targets for Phase 1 planning

---

## 19. Adopt / Defer / Avoid Matrix

| Area | Adopt now | Defer | Avoid for MVP |
|------|----------|-------|---------------|
| Runtime | Python 3.12+ | 3.13 optimization | Polyglot runtime |
| Packaging | `uv`, `uvx`, PyPI | Homebrew formula | Docker-first distribution |
| CLI | Typer + Rich | Textual TUI if demand | Bespoke CLI framework |
| MCP | Official SDK + FastMCP wrapper | Custom protocol stack | — |
| Storage | SQLite WAL + FTS5 + JSON | Postgres for remote mode | Graph DB |
| DB access | Hand-written SQL repositories | Light query builder if pain | Heavy ORM |
| Code parsing | Curated grammars (Py/JS/TS) | Broader grammar pack extras | "All languages" claim |
| Config parsing | TOML/YAML/JSON native parsers | More manifest types | tree-sitter for every config |
| Git | Git CLI backend | Optional pygit2 accelerator | Mandatory libgit2 |
| Graph | SQLite edges + in-memory maps | Optional rustworkx | Required graph library |
| Validation | pytest + hypothesis + golden fixtures | Mutation testing | Manual-only testing |
| Typing | pyright strict + Pydantic boundaries | — | Untyped domain core |
| Lint/format | Ruff | — | Split lint/format toolchain |
| Logging | structlog (stderr) | OTEL export | Ad hoc prints |
| File watch | Simple change detection | Richer daemon mode | Watch-heavy architecture |
| Sandbox verify | Clean worktree seam | Containerized runner Phase 2 | Active verification in P0 |
| Telemetry | OTel format (opt-in, local) | Langfuse export | Always-on telemetry |
| Docs | MkDocs Material | Backstage TechDocs | — |

---

## 20. Source Index

### Libraries
- [FastMCP 3.0](https://gofastmcp.com), [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [py-tree-sitter](https://tree-sitter.github.io/py-tree-sitter/), [tree-sitter-language-pack](https://github.com/Goldziher/tree-sitter-language-pack)
- [pygit2](https://www.pygit2.org/), [rustworkx](https://www.rustworkx.org/)
- [PyO3](https://pyo3.rs/), [maturin](https://www.maturin.rs/)
- [uv docs](https://docs.astral.sh/uv/)

### Standards
- [MCP Spec](https://modelcontextprotocol.io/specification/2025-11-25)
- [Agent Skills Spec](https://agentskills.io/specification)
- [AGENTS.md Spec](https://agents.md/)

### Architecture
- [SQLite WAL](https://www.sqlite.org/wal.html), [SQLite FTS5](https://www.sqlite.org/fts5.html)
- [SQLite Performance Tuning](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/)
- [CLI Guidelines](https://clig.dev/)

### Security
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
- [MCP CVEs (2026)](https://www.heyuan110.com/posts/ai/2026-03-10-mcp-security-2026/)
- [detect-secrets](https://github.com/Yelp/detect-secrets)

### Testing
- [FastMCP Testing](https://gofastmcp.com/development/tests)
- [Syrupy](https://github.com/syrupy-project/syrupy), [Hypothesis](https://hypothesis.readthedocs.io/)

### Tooling
- [actionlint](https://github.com/rhysd/actionlint), [zizmor](https://github.com/woodruffw/zizmor)
- [Nox](https://nox.thea.codes/), [Towncrier](https://towncrier.readthedocs.io/), [pre-commit](https://pre-commit.com/)
- [OpenTelemetry](https://opentelemetry.io/docs/)

---

_End of build research. See `docs/research-product.md` for market context, competitive landscape, and product strategy._
