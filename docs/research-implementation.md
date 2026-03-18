# Repo Knowledge Plane — Implementation Research

_Consolidated 2026-03-18. Seven parallel research streams covering every dimension of the build._
_Sources: MCP spec, FastMCP docs, py-tree-sitter docs, pygit2 docs, rustworkx docs, Agent Skills spec, GitHub Actions docs, Copilot/Claude Code/Cursor/Windsurf docs, clig.dev, and 100+ additional sources._

---

## 1. Critical Discoveries

Findings that change assumptions, resolve open questions, or create new constraints.

### 1.1 Two distinct FastMCP packages exist

| Attribute | Official MCP SDK | Standalone FastMCP |
|---|---|---|
| **Import** | `from mcp.server.fastmcp import FastMCP` | `from fastmcp import FastMCP` |
| **Install** | `pip install "mcp[cli]"` | `pip install fastmcp` |
| **Version** | v1.x (frozen feature set) | v3.0 GA (Feb 2026) |
| **Downloads** | Moderate | ~1M/day |

**Decision: Use standalone `fastmcp` v3.0+.** It has lifespan management, background tasks, tool timeouts, component versioning, and active development. The official SDK's built-in FastMCP is frozen at v1.x. Pin version strictly — FastMCP 3.x permits breaking changes in minor versions.

### 1.2 Claude Code does NOT natively read AGENTS.md

As of March 2026, Claude Code does not read AGENTS.md (open feature request #34235). Workaround: reference AGENTS.md from CLAUDE.md via `@AGENTS.md` import syntax. **This strengthens the case for RKP projecting to CLAUDE.md directly rather than relying on AGENTS.md alone.**

### 1.3 Git blob OIDs are free content hashes

Git blob OIDs (SHA-1 of file contents with header) are already content-addressable. No need to compute SHA-256 separately for incremental analysis. Walk the current HEAD tree via pygit2, compare blob OIDs against stored values, re-analyze only changed files.

### 1.4 MCP Apps enable future governance UI

MCP Apps (announced January 26, 2026) allow MCP servers to declare UI resources rendered as sandboxed iframes in Claude, ChatGPT, VS Code, and Goose. This means claim review could happen in a conversation UI rather than just CLI — a Phase 2+ opportunity.

### 1.5 Convention extraction tractability matrix

| Convention | Tree-sitter alone? | Confidence | Notes |
|---|---|---|---|
| Naming conventions | Yes | High | Regex on captured identifiers |
| File naming conventions | Filesystem scan | High | Pattern matching |
| Import ordering/grouping | Yes | Medium-High | Needs stdlib list for Python |
| Test file placement | Filesystem scan | High | Pattern matching |
| Test naming patterns | Yes | High | Query for test functions/classes |
| Type annotation usage | Yes | High | Count annotated vs unannotated |
| Error handling patterns | Yes (structure) | Medium | Shape detection, not adequacy |
| Docstring presence/style | Yes | Medium-High | Detect presence and format |
| Module structure | Filesystem | Medium | Naming heuristics only |
| Architectural layers | No (needs LLM) | Low | Requires semantic understanding |

**Focus on "High" confidence detections for MVP. Defer LLM-assisted extraction.**

### 1.6 Host instruction file size constraints

| Host | Size constraint |
|---|---|
| AGENTS.md (Codex) | 32 KiB combined |
| CLAUDE.md | ~200 lines recommended |
| copilot-instructions.md | Not documented |
| .cursor/rules | 500 lines per rule recommended |
| Windsurf rules | 6K/rule, 12K total |
| SKILL.md | 500 lines, <5000 tokens recommended |
| Copilot custom agents | 30,000 characters max |

### 1.7 No existing tools parse instruction files into structured claims

This is greenfield. No formal grammar or BNF exists for any instruction file format. No standardized approach for merging or reconciling rules from multiple formats. RKP would be first.

### 1.8 MCP security: 30 CVEs in 60 days

2026 MCP security research found 30 CVEs in 60 days across implementations, with prompt injection and tool poisoning as dominant attack classes. RKP must implement layered defenses for content extracted from untrusted repo artifacts.

---

## 2. Confirmed Stack

### 2.1 Core dependencies

```
MCP layer:          fastmcp >= 3.0.0 (standalone package, NOT mcp SDK built-in)
CLI:                typer[all] >= 0.15.0
Terminal UI:        rich (bundled with typer[all])
Parsing:            tree-sitter >= 0.25.0 + tree-sitter-language-pack >= 0.13.0
Git:                pygit2 >= 1.17.0
Graph:              rustworkx >= 0.17.0
Persistence:        sqlite3 (stdlib, WAL mode)
Domain model:       attrs >= 24.3.0 (internal), pydantic >= 2.10.0 (boundaries)
Config:             pydantic-settings >= 2.7.0
Logging:            structlog >= 25.0.0
YAML:               pyyaml >= 6.0.0 (repo configs), strictyaml (rkp configs)
Dockerfile:         dockerfile-parse >= 2.0.0
Build:              hatchling
Distribution:       uvx (uv tool run)
```

### 2.2 Platform wheel coverage

All four compiled dependencies ship pre-built wheels for all major platforms:

| Dependency | macOS (Intel+ARM) | Linux (x86_64+ARM64) | Windows |
|---|---|---|---|
| tree-sitter | Yes (universal2) | Yes | Yes |
| tree-sitter-language-pack | Yes (universal2) | Yes | Yes |
| pygit2 | Yes | Yes | Yes |
| rustworkx | Yes (tier 1) | Yes (tier 1) | Yes (tier 1) |

**No C compiler or Rust toolchain required for end users.**

### 2.3 Why each choice

| Component | Why this, not that |
|---|---|
| `fastmcp` v3.0 not `mcp` SDK | Lifespan, background tasks, tool timeouts, versioning, active development |
| `attrs` not `dataclasses` | Slots, frozen, composable validators, 40% less memory |
| Pydantic at boundaries only | 2-3x overhead vs attrs in tight loops; use only for MCP responses, YAML config, CLI I/O |
| `typer` not `click` | Type annotations, auto-completion, Rich integration, less boilerplate |
| `structlog` not stdlib `logging` | Structured JSON for machines, Rich console for humans, context binding |
| `strictyaml` for `.rkp/` | Prevents code execution, limits YAML complexity, safe for user-controlled config |
| `yaml.safe_load()` for repo configs | Fast, simple, handles anchors; never `yaml.load()` with untrusted data |
| `tomllib` (stdlib) for TOML | Zero dependencies, read-only, safe for untrusted input |

---

## 3. Project Architecture

### 3.1 Directory structure

```
repo-knowledge-plane/
    src/
        rkp/
            __init__.py
            __main__.py             # python -m rkp
            cli/
                app.py              # Typer app, subcommand registration
                commands/
                    init.py         # rkp init
                    review.py       # rkp review
                    apply.py        # rkp apply
                    refresh.py      # rkp refresh
                    status.py       # rkp status
                    import_.py      # rkp import
                    verify.py       # rkp verify
                    audit.py        # rkp audit
                    purge.py        # rkp purge
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
                models.py           # Claim, Evidence, ClaimHistory (attrs, frozen)
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
                migrations/         # Numbered SQL files
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
            graph/
                repo_graph.py       # rustworkx wrapper, node/edge types
            git/
                repository.py       # pygit2 wrapper, blame, history
                coupling.py         # Co-change analysis
                hotspots.py         # File change frequency
            quality/
                harness.py          # Quality harness runner
                fixtures.py         # Fixture repo management
                conformance.py      # Export conformance tests
                leakage.py          # Sensitivity leakage tests
    tests/
        conftest.py
        fixtures/                   # Test repos with known-good answers
            simple_python/
            simple_js/
            with_agents_md/
            with_ci/
            with_conflicts/
            with_drift/
        unit/
        integration/
        property/                   # Hypothesis tests
        snapshot/                   # Syrupy snapshot tests
    pyproject.toml
    uv.lock
```

### 3.2 Entry points

```toml
[project.scripts]
rkp = "rkp.cli.app:main"
```

CLI dispatches to Typer subcommands. `rkp serve` starts the MCP server via `asyncio.run()`. Both share core, store, indexer, projection, and graph modules.

### 3.3 Async vs sync boundaries

| Component | Mode | Rationale |
|---|---|---|
| MCP server | async (FastMCP) | MCP stdio transport is async |
| MCP tool functions | sync | FastMCP auto-dispatches to threadpool |
| CLI commands | sync | No async benefit for CLI |
| Indexer/parser | sync | CPU-bound, asyncio adds no value |
| SQLite access | sync | stdlib sqlite3; no aiosqlite needed |
| File watching (future) | async | Event-driven, watchdog/watchfiles |

**Critical rule:** Never hold a SQLite read transaction across an `await` point. Open connection, query, close within a single sync function.

### 3.4 Dependency injection

Constructor injection + `typing.Protocol` interfaces + composition root in `cli/app.py`. No framework needed.

```python
class ClaimStore(Protocol):
    def get_claims(self, scope: str, task_context: str | None = None) -> list[Claim]: ...
    def save_claim(self, claim: Claim) -> None: ...
```

---

## 4. Data Model

### 4.1 Core domain types (attrs, frozen, slotted)

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
    HUMAN_OVERRIDE = "human-override"         # precedence 1
    DECLARED_POLICY = "declared-policy"        # precedence 2
    EXECUTABLE_CONFIG = "executable-config"    # precedence 3
    CI_OBSERVED = "ci-observed"                # precedence 3
    CHECKED_IN_DOCS = "checked-in-docs"       # precedence 4
    INFERRED_HIGH = "inferred-high"            # precedence 5
    INFERRED_LOW = "inferred-low"              # precedence 6

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

### 4.2 Claim ID generation

Content-addressable: `SHA-256(claim_type + ":" + scope + ":" + content)`, truncated to 16 hex chars, prefixed with `claim-`. Enables deduplication across re-extractions. Immutable after creation.

Alternative for time-sortable needs: ULID (lexicographically sortable, unique without coordination).

### 4.3 SQLite schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -64000;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;

CREATE TABLE claims (
    id              TEXT PRIMARY KEY,
    content         TEXT NOT NULL,
    claim_type      TEXT NOT NULL,
    source_authority TEXT NOT NULL,
    authority_level INTEGER NOT NULL,   -- 1-6, for ordering
    scope           TEXT NOT NULL DEFAULT '**',
    applicability   TEXT NOT NULL DEFAULT '[]',
    sensitivity     TEXT NOT NULL DEFAULT 'public',
    review_state    TEXT NOT NULL DEFAULT 'unreviewed',
    confidence      REAL NOT NULL DEFAULT 0.0,
    evidence        TEXT NOT NULL DEFAULT '[]',
    provenance      TEXT NOT NULL DEFAULT '{}',
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
    line_end         INTEGER,
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
    last_projected  TEXT NOT NULL
);

CREATE TABLE claim_applicability (
    claim_id        TEXT NOT NULL REFERENCES claims(id),
    tag             TEXT NOT NULL,
    PRIMARY KEY (claim_id, tag)
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

CREATE VIRTUAL TABLE claims_fts USING fts5(
    content, content=claims, content_rowid=rowid,
    tokenize='porter unicode61'
);
```

### 4.4 Migration strategy

`PRAGMA user_version` + numbered SQL files in `src/rkp/store/migrations/`. Runner reads `user_version`, executes higher-numbered files in order, each wrapped in a transaction. No ORM, no framework.

### 4.5 Concurrent access pattern

WAL mode enables: multiple MCP server reader connections + one indexer writer connection simultaneously. Readers see consistent snapshots. Writers don't block readers. Only one write transaction at a time; additional writers wait up to `busy_timeout`.

---

## 5. MCP Server Design

### 5.1 Server lifecycle (lifespan pattern)

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
    # Load config, open DB, build in-memory graph
    config = load_config()
    db = open_database(config.db_path)
    graph = build_repo_graph(db)
    try:
        yield {"db": db, "graph": graph, "config": config}
    finally:
        db.close()
```

Graph persists for entire server process lifetime (stdio = client session duration).

### 5.2 Tool annotations

All RKP tools set `readOnlyHint: true` since RKP is a read/query layer. This allows hosts to skip confirmation prompts.

### 5.3 Pagination for large results

MCP does not support streaming tool results. Strategies:
- Accept `cursor`/`limit` params in tool input schema
- Return truncated results with a note and next cursor
- Design tools to return appropriately-scoped results by default

### 5.4 Lazy initialization for indexing

Start indexing in background during lifespan startup. Tools return partial results or "indexing in progress" status until complete. Best UX for agents that start a session and immediately query.

### 5.5 MCP logging

All logging MUST use stderr. stdout is reserved for MCP protocol messages. structlog routes to stderr via stdlib logging handlers.

---

## 6. Instruction File Parsing & Projection

### 6.1 Import parsing strategy (hybrid)

1. **Deterministic parser**: YAML frontmatter, JSON configs, code blocks, glob patterns
2. **Heuristic parser**: Heading classification, bullet extraction, command detection, boundary markers
3. **LLM-assisted** (deferred): Prose paragraphs, architectural descriptions, implicit conventions

### 6.2 Projection rules per host

| Host | Always-on file | Path-scoped | Skills | Env config | Permissions | Adapter maturity |
|---|---|---|---|---|---|---|
| **AGENTS.md** | Root file | Directory-level | Codex skills (Agent Skills) | `setup` section | Advisory | **GA** |
| **CLAUDE.md** | Root file | .claude/rules/ with `paths` frontmatter | SKILL.md in .claude/skills/ | CLAUDE.md or skill | settings.json | **GA** |
| **Copilot** | copilot-instructions.md | .instructions.md with `applyTo` | Copilot custom agents | copilot-setup-steps.yml | Agent tool config | **Beta** |
| **Cursor** | .cursor/rules (alwaysApply) | .cursor/rules (globs) | N/A | Advisory | N/A | **Alpha** |
| **Windsurf** | .windsurf/rules (always_on) | .windsurf/rules (glob) | Workflows | Advisory | Tool toggles | **Alpha** |

### 6.3 Round-trip fidelity

Preserve original file structure as a template. Use anchor-based diffing (stable headings, frontmatter keys). Generate minimal diff against existing content. Respect per-host size constraints.

### 6.4 Agent Skills standard (SKILL.md)

Required fields: `name` (max 64 chars, lowercase/hyphens), `description` (max 1024 chars). Optional: `license`, `compatibility`, `metadata`, `allowed-tools`. Progressive disclosure: metadata at startup (~100 tokens), full instructions on activation (<5000 tokens), resources as needed.

---

## 7. CI Config Parsing

### 7.1 GitHub Actions extraction targets

| What to extract | Where | How |
|---|---|---|
| Commands | `steps[].run` | Direct string extraction |
| Runtime versions | `actions/setup-python`, `setup-node` `with` inputs | Action metadata database |
| Services | `jobs[].services` | Image, env, ports extraction |
| Environment variables | Workflow/job/step `env` | Aggregated, secrets noted |
| OS | `jobs[].runs-on` | Direct |
| Matrix dimensions | `strategy.matrix` | Expand combinations |

### 7.2 CI evidence confidence levels

| Level | Condition |
|---|---|
| **High** | Unconditional step, push/PR trigger, no continue-on-error |
| **Medium** | Conditional step or within matrix job |
| **Low** | continue-on-error: true, or schedule/dispatch only |
| **Unknown** | Inside composite action or unresolvable reusable workflow |

### 7.3 Expression handling

Do NOT build a full GitHub Actions expression evaluator. Extract expressions as strings, resolve simple matrix references, mark unresolvable expressions. This covers 90%+ of practical cases.

### 7.4 Parser priority (value/effort ratio)

1. GitHub Actions workflows — highest value, medium effort
2. pyproject.toml — high value, low effort (tomllib stdlib)
3. package.json — high value, low effort (json stdlib)
4. Dockerfile — medium value, low effort (dockerfile-parse)
5. docker-compose.yml — medium value, low effort (yaml.safe_load)
6. Makefile — medium value, medium effort (custom regex)
7. Runtime version files — low effort, useful cross-reference

---

## 8. Convention Extraction

### 8.1 tree-sitter query patterns

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

### 8.2 Naming convention classification

Capture identifiers by syntactic role, classify with regex:
- `snake_case`: `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`
- `SCREAMING_SNAKE`: `^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$`
- `camelCase`: `^[a-z][a-zA-Z0-9]*$`
- `PascalCase`: `^[A-Z][a-zA-Z0-9]*$`

### 8.3 Confidence thresholds

| Consistency | Classification |
|---|---|
| >= 95% | Strong convention — assert as rule |
| 80-94% | Weak convention — flag for human review |
| < 80% | No convention — do not assert |

Minimum sample: 20+ identifiers per category. Per-scope analysis (not just global).

### 8.4 Formatting conventions from tool configs

Extract from ruff/black/prettier/editorconfig configs directly. Compare declared config against inferred patterns to detect conflicts.

---

## 9. Security

### 9.1 Prompt injection defense (layered)

1. **Input sanitization**: Scan extracted content for injection markers (`[INST]`, `System:`, `role:`, `ignore previous`, `<|im_start|>`)
2. **Content typing**: Structured JSON responses with explicit `content_type` fields. Claim content is data, not meta-instructions
3. **Source authority as trust signal**: Low-confidence inferred claims carry lower weight
4. **Response filtering**: Scan MCP responses for meta-instruction patterns before serving
5. **Human review**: The review state machine is itself an anti-injection mechanism
6. **No executable content**: MCP responses never contain instructions to execute

### 9.2 Safe parsing rules

| Format | Parser | Safety rule |
|---|---|---|
| YAML (repo) | `yaml.safe_load()` | NEVER `yaml.load()` |
| YAML (.rkp/) | `strictyaml` | Prevents all YAML complexity |
| TOML | `tomllib` (stdlib) | Safe by design |
| JSON | `json.loads()` (stdlib) | Safe by design |

### 9.3 Sandbox execution hierarchy

1. **Default**: Passive analysis only (no execution)
2. **Opt-in safe-readonly**: Git worktree isolation
3. **Opt-in test/build**: Podman rootless with `--network=none --read-only --memory 1g --cpus 2 --pids-limit 256 --timeout 300`
4. **Destructive**: Per-command approval + podman, no host secret mounts

### 9.4 Path traversal prevention

`pathlib.Path.resolve()` to follow symlinks, then verify path starts with resolved repo root. Reject paths with null bytes. Never follow symlinks outside repo root.

### 9.5 Secret detection

Lightweight entropy + regex pass on extracted text (patterns from `detect-secrets`). Auto-flag potential secrets as `sensitivity: local-only`. Store env var names but never values.

### 9.6 Sensitivity enforcement

Single enforcement point: filter function applied at the last stage before output (both projection layer and MCP response layer). Quality harness includes automated leakage tests. `local-only` claims stored only in `.rkp/local/`, never in `.rkp/overrides/`.

---

## 10. CLI UX

### 10.1 Output formatting

| Format | When | Example command |
|---|---|---|
| Colored text | Interactive TTY | `rkp status` |
| Tables | Multiple items | `rkp status`, `rkp audit` |
| Unified diff | Before/after changes | `rkp refresh`, `rkp review` |
| JSON | `--json` flag | `rkp status --json` |
| Plain text | Piped / `NO_COLOR` / CI | Auto-detected |

### 10.2 Progress indicators

| Duration | Indicator | RKP application |
|---|---|---|
| < 100ms | None | Warm MCP queries |
| 100ms-3s | Spinner | Incremental update |
| > 3s | X of Y counter | Initial indexing ("Parsing: 847/1,203") |

### 10.3 Interactive review flow (rkp review)

Present each claim in a Rich Panel: id, type, authority, scope, content, evidence, confidence. Offer keyboard shortcuts: [a]pprove, [e]dit, [s]uppress, [t]ombstone, [n]ext, [q]uit. Show running totals: "Reviewed 12/47 (8 approved, 2 edited, 2 suppressed)". For editing: launch `$EDITOR`. For batch: `--approve-all` for high-confidence claims.

### 10.4 Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Findings present (drift, unreviewed claims) |
| 2 | Usage error |
| 3 | Resource not found (not initialized) |
| 130 | Interrupted (Ctrl+C) |

### 10.5 Verbosity levels

- Default: clean, human-friendly
- `-q/--quiet`: exit code only
- `-v/--verbose`: evidence chains, timing
- `-vv/--debug`: full diagnostic output

---

## 11. Testing Strategy

### 11.1 Test organization

```
tests/
    unit/           # Fast, isolated, mocked dependencies
    integration/    # Real filesystem, real SQLite, real tree-sitter
    property/       # Hypothesis: claim model invariants, sensitivity filtering
    snapshot/        # Syrupy: projected instruction file content
```

### 11.2 Fixture repos

| Fixture | Tests |
|---|---|
| `simple_python/` | Python conventions, pytest, src layout |
| `simple_js/` | JS/TS conventions, npm scripts, ESLint |
| `with_agents_md/` | Import workflow for existing AGENTS.md |
| `with_ci/` | GitHub Actions parsing |
| `with_conflicts/` | Declared vs inferred conflicts |
| `with_drift/` | Managed files manually edited |

Each includes `expected_claims.json` for precision/recall measurement.

### 11.3 MCP server testing

FastMCP in-memory client transport (no subprocess, no network):

```python
async def test_get_conventions():
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"path_or_symbol": "src/payments"})
        assert "claim-001" in result[0].text
```

**Gotcha**: Do NOT create Client in pytest fixtures. The async context manager must live within the test function body.

### 11.4 Key test properties (Hypothesis)

- Claim roundtrip through SQLite (store/retrieve identity)
- Claim roundtrip through JSON (serialize/deserialize identity)
- Precedence ordering is a total order
- Sensitivity filtering never leaks (team-only claims never in public projections)
- Scope matching consistency

### 11.5 CI matrix

GitHub Actions: ubuntu-latest + macos-latest + windows-latest, Python 3.12 + 3.13. Steps: setup-uv, sync, ruff check, ruff format --check, mypy, pytest with coverage.

---

## 12. Distribution & Packaging

### 12.1 pyproject.toml key sections

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

Trusted Publishing (OIDC) for PyPI via GitHub Actions. Tag-triggered: `v*`. Changelog via Towncrier (fragment-based, no merge conflicts).

### 12.4 License

**Apache 2.0 for core CLI + MCP server.** Permissive, patent grant, enterprise-friendly. Local-first architecture means no SaaS to protect. Future managed cloud service could be proprietary.

### 12.5 Documentation

MkDocs Material + GitHub Pages. Priority docs: README, Getting Started, CLI Reference, MCP Tool Reference, Concepts guide, Host adapter guides.

---

## 13. Performance

### 13.1 Targets and estimates

| Target | Budget | Estimated |
|---|---|---|
| Warm MCP query | < 500ms | 10-35ms (SQL + scope + applicability + serialization) |
| Initial index (250k LOC) | < 5 min | 3-5 min (parse + graph + SQLite) |
| Incremental update | < 2s | Sub-second per file |
| Idle memory | < 200MB | 70-120MB for 250k LOC repo |

### 13.2 Key optimizations

- In-memory rustworkx graph (loaded at server start)
- SQLite prepared statements, WAL mode, 64MB page cache
- Batch SQLite writes (`executemany()` in single transaction)
- Content-hash tracking via git blob OIDs (free)
- Skip incremental tree-sitter parsing (re-parse from scratch is fast enough)
- File exclusion before parsing (vendor/, node_modules/, etc.)

### 13.3 Profiling tools

| Tool | Use |
|---|---|
| cProfile | Dev profiling, function-level hotspots |
| py-spy | Production MCP server profiling |
| memray | Memory profiling (tracks native C/Rust allocations) |
| line_profiler | Line-level analysis after identifying hotspots |

---

## 14. Rust Acceleration Path

### 14.1 Migration priority

1. **File parsing + convention extraction** — highest value, clean boundary, expected 3-10x speedup
2. **Graph construction** — reduces Python/Rust boundary crossings
3. **Diff computation + scope resolution** — Rust regex ~2x faster
4. **Secret detection** — CPU-bound regex matching

### 14.2 What stays in Python

CLI (typer), MCP server (FastMCP), SQLite I/O, configuration parsing (Pydantic), projection/template rendering.

### 14.3 Boundary design

Data-oriented interfaces (simple types across boundary). Batch operations (process multiple files per Rust call). Always release GIL for CPU-intensive Rust work. Feature flags to switch implementations during transition.

### 14.4 Strategy

Start pure Python for MVP. Profile in production-like conditions. Extract bottlenecks to Rust via PyO3/maturin. If <2x improvement, keep Python. Use Polars' architecture as template (core crate + thin binding crate).

---

## 15. Edge Cases & Failure Modes

### 15.1 Handled gracefully

| Scenario | Behavior |
|---|---|
| tree-sitter parse error | Always produces tree with ERROR nodes; report as "partially analyzed" |
| Corrupted git repo | pygit2.GitError caught; fall back to filesystem-only |
| Corrupted SQLite DB | Regenerable from repo + `.rkp/overrides/`; delete and re-init |
| Monorepo with 50 packages | Detect workspaces, index per-package, support selective indexing |
| Concurrent RKP processes | WAL handles readers+writer; lockfile for exclusive ops |
| Submodules | Detect, report, do NOT index by default |
| Large/generated files | Skip files >1MB by default; respect .gitignore |
| Conflicting instruction files | Create `conflict` claims, surface in `get_conflicts` |
| File renames | Detect via `diff.find_similar()`, update claim scopes |
| Merge conflicts in `.rkp/` | Design override files for merge-friendliness (self-contained entries) |
| Branch switch mid-session | Serve existing claims with warning in provenance; refresh on next query |

### 15.2 Defensive defaults

- File size limit: 1MB (configurable)
- Default exclusions: `vendor/`, `node_modules/`, `dist/`, `build/`, `__pycache__/`, `.git/`
- Convention minimum sample: 20 identifiers per category
- Confidence floor for projection: 0.5 (claims below are never projected to always-on files)
- WAL busy timeout: 5000ms
- Parser timeout: configurable via tree-sitter `timeout_micros`

---

## 16. PRD Amendments Recommended

Based on research findings, the following PRD refinements are recommended:

### 16.1 Confirmed assumptions

| Assumption | Status |
|---|---|
| A3: "Under 5 min" for 250k LOC | **Confirmed feasible** — tree-sitter parses ~10-50 files/sec, ~2500 files = 3-5 min total |
| A5: SQLite + in-memory graph sufficient | **Confirmed** — estimated 70-120MB for 250k LOC; query latency 10-35ms |
| A9: Tree-sitter sufficient for convention mining | **Confirmed for high-confidence conventions** — naming, imports, test patterns |
| A10: MCP stdio is right first transport | **Confirmed** — all target hosts support stdio |
| A15: GitHub Actions sufficient for launch | **Confirmed** — dominant CI system in target repos |

### 16.2 New information to incorporate

1. **Claude Code AGENTS.md gap**: CLAUDE.md projection is more important than AGENTS.md for Claude Code users, since Claude Code doesn't natively read AGENTS.md
2. **FastMCP package identity**: PRD references "FastMCP" but should specify the standalone `fastmcp` v3.0+ package, not `mcp` SDK
3. **MCP Apps**: Future governance UI path via MCP Apps (launched Jan 2026) — adds a concrete answer to Q10 about governance UI timeline
4. **Agent Skills standard maturity**: Claude Code and Codex support it; specification is concrete enough for skill projection

### 16.3 Suggested Q resolutions

| Question | Suggested resolution |
|---|---|
| Q8: Container runtime | Podman preferred (rootless); docker as fallback |
| Q10: MCP App as governance UI | Phase 2+ — MCP Apps are real but ecosystem is early |
| Q11: Applicability tag vocabulary | Start free-form, standardize after design-partner usage |
| Q12: `.rkp/overrides/` format | YAML with strictyaml parsing; consider NDJSON for merge-friendliness |

---

## 17. Risk Register (Implementation-Specific)

| Risk | Severity | Mitigation |
|---|---|---|
| FastMCP 3.x breaking changes in minor versions | Medium | Pin strictly; wrap in thin abstraction layer |
| tree-sitter grammar version changes silently break queries | Medium | Pin tree-sitter-language-pack version; test queries against fixture repos in CI |
| pygit2 submodule crashes | Low | Detect submodules, skip by default, catch exceptions |
| MCP prompt injection via repo artifacts | High | Layered defense (§9.1); human review as ultimate backstop |
| tree-sitter-language-pack vs tree-sitter-languages package confusion | Low | Use `tree-sitter-language-pack` (newer, actively maintained) |
| Pydantic v2 + attrs version conflicts | Low | Pin both; test in CI |
| SQLite WAL file unbounded growth | Low | Periodic checkpoint at shutdown; short-lived read transactions |
| Memory leaks in long-running MCP server | Medium | memray in CI; profiling with py-spy |
| Convention threshold too aggressive/conservative | Medium | Make configurable; calibrate with design partners |

---

## 18. Sources Index

### Standards & Protocols
- [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
- [Agent Skills Specification](https://agentskills.io/specification)
- [AGENTS.md Specification](https://agents.md/)
- [MCP Apps Announcement](http://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)

### Libraries
- [FastMCP 3.0 Documentation](https://gofastmcp.com)
- [FastMCP 3.0 Launch Post](https://www.jlowin.dev/blog/fastmcp-3-launch)
- [py-tree-sitter Documentation](https://tree-sitter.github.io/py-tree-sitter/)
- [tree-sitter-language-pack](https://github.com/Goldziher/tree-sitter-language-pack)
- [pygit2 Documentation](https://www.pygit2.org/)
- [rustworkx Documentation](https://www.rustworkx.org/)
- [PyO3 User Guide](https://pyo3.rs/)
- [maturin User Guide](https://www.maturin.rs/)

### Agent Configuration
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [Claude Code Memory/CLAUDE.md](https://code.claude.com/docs/en/memory)
- [Claude Code Settings](https://code.claude.com/docs/en/settings)
- [Codex AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md)
- [Codex Skills](https://developers.openai.com/codex/skills)
- [Copilot Custom Instructions](https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot)
- [Copilot Setup Steps](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment)
- [Copilot Custom Agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents)
- [Cursor Rules](https://cursor.com/docs/context/rules)
- [Windsurf Rules](https://docs.windsurf.com/windsurf/cascade/memories)
- [GitHub AGENTS.md Lessons](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)

### Architecture & Patterns
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLite Performance Tuning](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/)
- [Pydantic for Boundaries Only](https://leehanchung.github.io/blogs/2025/07/03/pydantic-is-all-you-need-for-performance-spaghetti/)
- [CLI Guidelines (clig.dev)](https://clig.dev/)
- [Polars PyO3 Patterns](https://github.com/pola-rs/pyo3-polars)

### Security
- [MCP Security: 30 CVEs in 60 Days](https://www.heyuan110.com/posts/ai/2026-03-10-mcp-security-2026/)
- [PyYAML Unsafe Load RCE](https://www.sourcery.ai/vulnerabilities/python-pyyaml-unsafe-load-rce)
- [Podman vs Docker 2026](https://www.xurrent.com/blog/podman-vs-docker-complete-2025-comparison-guide-for-devops-teams)
- [detect-secrets](https://github.com/Yelp/detect-secrets)

### Testing
- [FastMCP Testing Guide](https://gofastmcp.com/development/tests)
- [Syrupy Snapshot Testing](https://github.com/syrupy-project/syrupy)
- [Hypothesis + Pydantic](https://docs.pydantic.dev/latest/integrations/hypothesis/)

---

_End of implementation research. This document supersedes no prior research — it complements `docs/research.md` (market/competitive/academic) with concrete implementation decisions._
