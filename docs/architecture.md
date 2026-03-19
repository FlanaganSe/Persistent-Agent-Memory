# Architecture

## 4-Plane Architecture

RKP is organized into four planes with strict separation of concerns:

### 1. Extraction Plane
Parsers for code (tree-sitter: Python, JS/TS), config files (pyproject.toml, package.json, Makefile, Dockerfile, docker-compose.yml, GitHub Actions, version files), instruction files, and documentation. Produces normalized evidence records. Extractors never know how hosts consume data.

**Components**: `indexer/orchestrator.py`, `indexer/parsers/`, `indexer/extractors/`, `indexer/config_parsers/`

### 2. Claim Plane
Deterministic claim builders, conflict resolver, and source authority ordering. Produces canonical claims with content-addressable IDs, provenance, and review metadata.

**Components**: `core/types.py`, `core/models.py`, `core/ids.py`, `core/claim_builder.py`, `core/security.py`

### 3. Projection Plane
Five host adapters (AGENTS.md, CLAUDE.md, Copilot, Cursor, Windsurf). Pure function: `canonical_claims + adapter_caps + policy -> artifacts + warnings`. Adapters never infer claims. Sensitivity filtering at a single enforcement point.

**Components**: `projection/engine.py`, `projection/adapters/`, `projection/capability_matrix.py`, `projection/sensitivity.py`, `projection/budget.py`

### 4. Serving & Governance Plane
MCP read tools (11 tools, 10 read-only + refresh_index), CLI commands (12 commands), review/apply governance workflow, audit trail, drift detection, freshness orchestration, overrides persistence.

**Components**: `server/mcp.py`, `server/tools.py`, `server/resources.py`, `server/response.py`, `server/response_filter.py`, `server/trace.py`, `cli/`, `store/`

## Data Flow

```
Source files ──→ Config Parsers ──→ Evidence records
                 Tree-sitter         │
                 Instruction files    │
                                      ▼
                             Claim Builders
                             (dedup, conflict, security scan)
                                      │
                                      ▼
                             Canonical Claim Store (SQLite)
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                   │
                    ▼                 ▼                   ▼
           Projection Engine   MCP Server           CLI Commands
           (5 adapters)        (11 tools)         (review, apply,
                    │                                status, audit)
                    ▼
           Projected artifacts
           (AGENTS.md, CLAUDE.md,
            copilot-instructions.md,
            .cursor/rules/, .windsurf/rules/)
```

## Directory Structure

```
src/rkp/
├── __init__.py, __main__.py
├── core/
│   ├── types.py            # StrEnums: ClaimType, SourceAuthority, ReviewState, etc.
│   ├── models.py           # Frozen dataclasses: Claim, Evidence, etc.
│   ├── ids.py              # Content-addressable claim ID generation
│   ├── claim_builder.py    # Deterministic claim construction and dedup
│   ├── config.py           # RkpConfig via pydantic-settings
│   ├── errors.py           # Typed exception hierarchy
│   ├── freshness.py        # Evidence-triggered stale detection
│   └── security.py         # Safe YAML, path validation, injection/secret scanning
├── store/
│   ├── database.py         # SQLite connection factory, PRAGMAs, migration runner
│   ├── claims.py           # ClaimStore Protocol + SQLite implementation
│   ├── evidence.py         # Evidence chain storage
│   ├── history.py          # Append-only audit trail
│   ├── artifacts.py        # Managed artifact tracking + drift detection
│   ├── overrides.py        # .rkp/overrides/ strictyaml persistence
│   ├── metadata.py         # Index metadata (HEAD, branch, timestamp)
│   └── migrations/
│       ├── 0001_init.sql   # Full schema
│       └── 0002_index_metadata.sql
├── git/
│   ├── backend.py          # GitBackend Protocol
│   └── cli_backend.py      # Git CLI implementation
├── indexer/
│   ├── orchestrator.py     # Extraction pipeline coordinator
│   ├── parsers/
│   │   ├── python.py       # Python tree-sitter queries
│   │   └── javascript.py   # JS/TS tree-sitter queries
│   ├── extractors/
│   │   ├── conventions.py  # Naming, imports, type annotations
│   │   ├── commands.py     # Build/test/lint with evidence levels
│   │   ├── prerequisites.py # Runtimes, tools, services
│   │   ├── ci_evidence.py  # GitHub Actions analysis
│   │   ├── boundaries.py   # Module detection, import graphs
│   │   ├── guardrails.py   # Permission/restriction extraction
│   │   ├── conflicts.py    # Declared-vs-inferred mismatch
│   │   └── docs_evidence.py # README, docs/ content
│   └── config_parsers/
│       ├── pyproject.py, package_json.py, makefile.py
│       ├── dockerfile.py, docker_compose.py
│       ├── github_actions.py, version_files.py
├── importer/
│   ├── engine.py           # Import orchestration
│   ├── models.py           # Import data models
│   └── parsers/
│       ├── agents_md.py    # AGENTS.md → claims
│       ├── claude_md.py    # CLAUDE.md → claims
│       ├── copilot.py      # copilot-instructions.md → claims
│       ├── cursor.py       # .cursor/rules → claims
│       └── markdown_utils.py
├── projection/
│   ├── engine.py           # Projection pipeline: claims → artifacts
│   ├── capability_matrix.py # Per-host capability descriptors
│   ├── sensitivity.py      # Single enforcement point for filtering
│   ├── budget.py           # Context budget tracking + overflow
│   └── adapters/
│       ├── base.py         # BaseAdapter Protocol
│       ├── agents_md.py    # AGENTS.md generator (GA)
│       ├── claude_md.py    # CLAUDE.md + rules + skills (GA)
│       ├── copilot.py      # Copilot surfaces (Beta)
│       ├── cursor.py       # .cursor/rules (Alpha)
│       ├── windsurf.py     # .windsurf/rules (Alpha)
│       └── skills.py       # Cross-host SKILL.md generator
├── graph/
│   └── repo_graph.py       # SQLite-backed module dependency graph
├── server/
│   ├── mcp.py              # FastMCP instance, lifespan, tool registration
│   ├── tools.py            # MCP tool implementations (pure functions)
│   ├── resources.py        # MCP resource implementations
│   ├── response.py         # Response envelope with provenance
│   ├── response_filter.py  # Injection marker scanning on responses
│   └── trace.py            # MCP call trace logging
├── cli/
│   ├── app.py              # Typer app, composition root
│   ├── commands/
│   │   ├── init.py, review.py, apply.py, refresh.py
│   │   ├── status.py, import_.py, preview.py, audit.py
│   │   ├── doctor.py, serve.py, purge.py, quality.py
│   └── ui/
│       ├── output.py, tables.py, diffs.py
│       ├── review_flow.py, progress.py
└── quality/
    ├── harness.py           # Quality harness runner
    ├── fixtures.py          # Fixture repo evaluation
    ├── conformance.py       # Round-trip validation per adapter
    ├── leakage.py           # Sensitivity leakage tests
    ├── benchmark.py         # Performance benchmarks
    ├── promotion.py         # Adapter maturity assessment
    └── types.py             # Quality report dataclasses
```

## Key Boundaries

1. **Extraction/Claim boundary**: extractors produce evidence records; claim builders produce claims. No extractor creates a claim directly — all go through `claim_builder.py`.
2. **Claim/Projection boundary**: projection receives claims and adapter capabilities. It never runs extraction or modifies claims. Pure function.
3. **Serving/Store boundary**: MCP tools and CLI read from the claim store. Only CLI `apply` writes projected artifacts to disk, gated on human review state.
4. **Security boundary**: sensitivity filtering enforced at a single point (`projection/sensitivity.py`) just before output. Both projection and MCP response paths use the same filter. Response filter (`response_filter.py`) additionally scans MCP responses for injection markers.
5. **Import/Extraction boundary**: imported claims get `DECLARED_IMPORTED_UNREVIEWED` authority and must pass through the same security scanning as extracted claims.

## Storage Architecture

- **SQLite with WAL mode**: single-file database in `.rkp/local/rkp.db` (gitignored, regenerable)
- **PRAGMAs**: WAL, busy_timeout=5000ms, cache_size=64MB, foreign_keys ON, mmap_size=256MB
- **Migration**: forward-only numbered SQL files in `store/migrations/`, `PRAGMA user_version` tracking
- **Concurrent access**: WAL enables multiple readers + one writer. `check_same_thread=False` for MCP server.
- **Human decisions**: stored in `.rkp/overrides/` (checked in, version-controlled via strictyaml)
- **Index metadata**: HEAD, branch, timestamp stored in `index_metadata` table for freshness tracking

## Identity Model

Four identities are first-class in the data model:
- **Repo identity**: unique repository (by remote URL or local path)
- **Branch identity**: which branch claims are validated against
- **Worktree identity**: which worktree the index was built from
- **Session identity**: logical agent work session for eval traces

## Extension Seams (Phase 2+)

These interfaces exist in Phase 1 code but are not yet implemented:

1. **`GitBackend` Protocol** — Phase 2 adds optional pygit2 backend for performance
2. **`RepoGraph` interface** — Phase 2 adds optional rustworkx accelerator
3. **Parser registry** — Phase 2 adds Go, Java, Rust grammars via `tree-sitter-language-pack`
4. **Adapter registry** — new hosts plug in via `BaseAdapter` Protocol
5. **Transport abstraction** — Phase 2 adds Streamable HTTP for remote MCP
6. **Sandbox verification seam** — `rkp verify` deferred to Phase 2 (containerized runner)
7. **CI outcome ingestion** — Phase 2 adds CI results beyond config parsing
