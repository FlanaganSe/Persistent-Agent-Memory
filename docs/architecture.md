# Architecture

## 4-Plane Architecture

RKP is organized into four planes with strict separation of concerns:

### 1. Extraction Plane
Parsers for code, config, instruction files, and CI workflows. Produces normalized evidence records. Extractors never know how hosts consume data.

**Components**: `indexer/orchestrator.py`, `indexer/parsers/`, `indexer/extractors/`, `indexer/config_parsers/`

### 2. Claim Plane
Deterministic claim builders, conflict resolver, and source authority ordering. Produces canonical claims with provenance and review metadata.

**Components**: `core/types.py`, `core/models.py`, `core/ids.py`, `core/claim_builder.py`

### 3. Projection Plane
Host adapters (Codex, Claude, Copilot, Cursor, Windsurf). Pure function: `canonical_claims + adapter_caps + policy -> artifacts + warnings`. Adapters never infer claims.

**Components**: `projection/engine.py`, `projection/adapters/`, `projection/capability_matrix.py`, `projection/sensitivity.py`, `projection/budget.py`

### 4. Serving & Governance Plane
MCP read tools, CLI review/apply/status/import, audit trail, drift detection, freshness orchestration.

**Components**: `server/mcp.py`, `server/tools.py`, `cli/`, `store/`

## Data Flow

```
Source files -> Extraction Plane -> Evidence records
                                        |
                                        v
                               Claim Plane (builders, dedup, conflict detection)
                                        |
                                        v
                               Canonical Claim Store (SQLite)
                                        |
                    +-------------------+-------------------+
                    |                                       |
                    v                                       v
           Projection Plane                        Serving Plane
           (host adapters)                         (MCP tools, CLI)
                    |
                    v
           Projected artifacts
           (AGENTS.md, CLAUDE.md, skills, etc.)
```

## Key Boundaries

1. **Extraction/Claim boundary**: Extractors produce evidence; claim builders produce claims. No extractor creates a claim directly.
2. **Claim/Projection boundary**: Projection receives claims and adapter capabilities. It never runs extraction or modifies claims.
3. **Serving/Store boundary**: MCP tools and CLI read from the claim store. Only CLI `apply` writes projected artifacts to disk after human review.
4. **Security boundary**: Sensitivity filtering is enforced at a single point just before output (both projection and MCP response).

## Storage Architecture

- **SQLite with WAL mode**: Single-file database in `.rkp/local/rkp.db` (gitignored, regenerable)
- **PRAGMAs**: WAL, busy_timeout=5000ms, cache_size=64MB, foreign_keys ON, mmap_size=256MB
- **Migration**: Forward-only numbered SQL files, `PRAGMA user_version` tracking
- **Concurrent access**: WAL enables multiple readers + one writer simultaneously
- **Human decisions**: Stored in `.rkp/overrides/` (checked in, version-controlled)

## Identity Model

Four identities are first-class in the data model:
- **Repo identity**: Unique repository (by remote URL or local path)
- **Branch identity**: Which branch claims are validated against
- **Worktree identity**: Which worktree the index was built from
- **Session identity**: Logical agent work session for eval traces
