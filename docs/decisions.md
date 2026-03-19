# Architecture Decision Records

Append-only log. Read during planning, not loaded every session.

---

## ADR-001: SQLite as canonical storage

**Status**: Accepted (M1)

**Context**: Need persistent storage for claims, evidence, history, and graph edges. Options: SQLite, PostgreSQL, graph DB.

**Decision**: SQLite with WAL mode. Single-file distribution, no external service dependency, sufficient for single-repo workloads. WAL enables concurrent readers + one writer.

**Consequences**: Simple distribution via `uvx`. No cloud dependency. Schema migrations via numbered SQL files + `PRAGMA user_version`. Regenerable from repo + `.rkp/overrides/`.

---

## ADR-002: Git CLI as default backend

**Status**: Accepted (M1)

**Context**: Need git operations for repo identity, file hashing, diff detection. Options: Git CLI, pygit2, dulwich.

**Decision**: Git CLI as default backend. pygit2 as optional accelerator (Phase 2).

**Consequences**: No native library complexity. Preserves `uvx` adoption story. Avoids GPLv2 linking exception concerns with pygit2. Define `GitBackend` Protocol for future implementations.

---

## ADR-003: Curated parser support envelope

**Status**: Accepted (M1)

**Context**: tree-sitter-language-pack bundles 170+ grammars. Broad support increases supply-chain surface and testing burden.

**Decision**: Curated grammars only: Python, JavaScript, TypeScript for launch. Broader grammar support as optional extra.

**Consequences**: Focused testing and quality. Explicit "unsupported" responses for out-of-envelope queries. Extension via parser registry in Phase 2.

---

## ADR-004: Adapter maturity tiers (GA / Beta / Alpha)

**Status**: Accepted (M1)

**Context**: MCP host capabilities vary. Copilot supports tools only (no resources/prompts). Cursor/Windsurf have different surfaces.

**Decision**: Explicit maturity tiers. GA requires conformance harness passing (M13). Beta requires functional projection with documented gaps. Alpha is export-only.

**Consequences**: Honest expectations for users. GA promotion is earned via quality harness, not declared at implementation time. Phase 1 targets: Codex + Claude = GA, Copilot = Beta, Cursor/Windsurf = Alpha.

---

## ADR-005: `.rkp/overrides/` format — strictyaml

**Status**: Accepted (M1, implementation M9)

**Context**: Human review decisions (approvals, edits, suppressions, declarations) must be version-controlled and team-shareable.

**Decision**: One strictyaml file per override in `.rkp/overrides/`. Self-contained entries for merge-friendliness. strictyaml prevents code execution and limits YAML complexity.

**Consequences**: Merge conflicts are localized to individual override files. `local-only` claims stored in `.rkp/local/` only, never in overrides. Round-trip test: write overrides → clone → `rkp init` → same state.

---

## ADR-006: Content-addressable claim IDs, immutable after creation

**Status**: Accepted (M1)

**Context**: Claims need stable identifiers for references, history, and human decisions. Re-extraction may produce identical claims.

**Decision**: Claim IDs are `SHA-256(claim_type:scope:content)` truncated to 16 hex, prefixed `claim-`. Immutable after creation: edits change content but preserve the original ID. Re-extraction matches by (claim_type, scope, content_similarity), not just ID hash.

**Consequences**: Same extraction input always produces the same claim ID (deduplication). Approved claims survive re-extraction. ID stability enables reliable override references.

---

## ADR-007: Imported claims precedence at 3.5

**Status**: Accepted (M1)

**Context**: When importing existing instruction files (AGENTS.md, CLAUDE.md), the imported claims need a precedence level. They should not outrank executable configuration until a human reviews them.

**Decision**: `DECLARED_IMPORTED_UNREVIEWED` at precedence 3.5 (authority level 35). Below `executable-config`/`ci-observed` at 3 (level 30), above `checked-in-docs` at 4 (level 40). After human review, promoted to `declared-reviewed` at precedence 2.

**Consequences**: Build commands from pyproject.toml outrank unreviewed imported rules. Prevents untrusted imported content from overriding verified configuration evidence. Human review is the trust-promotion mechanism.

---

## ADR-008: FTS5 table creation deferred from trigger wiring

**Status**: Accepted (M1 discovery, documented M16)

**Context**: The initial schema creates an FTS5 virtual table for full-text search over claims. However, wiring up INSERT/UPDATE/DELETE triggers to keep the FTS index in sync would add complexity to the claim store.

**Decision**: Create the FTS5 table in the schema but do not wire up triggers. Search uses SQL `LIKE` queries for now.

**Consequences**: Full-text search is available as a schema feature but not populated. When search performance becomes a bottleneck, triggers can be added in a forward-only migration. No data migration needed — triggers populate the FTS index from existing data.

---

## ADR-009: check_same_thread=False for MCP server

**Status**: Accepted (M2)

**Context**: FastMCP dispatches tool handler functions in a threadpool. SQLite's default Python binding raises `ProgrammingError` when a connection is used from a different thread than the one that created it.

**Decision**: Pass `check_same_thread=False` to `sqlite3.connect()` when opening the database for the MCP server. WAL mode supports concurrent readers, and we have a single writer.

**Consequences**: Safe for our read-heavy workload. The MCP server's lifespan opens the connection; tool handlers (potentially on different threads) read from it. Only `refresh_index` writes, and it runs synchronously.

---

## ADR-010: tree-sitter QueryCursor API migration

**Status**: Accepted (M3)

**Context**: tree-sitter v0.25+ removed the old `Query.captures()` method. The new API uses `QueryCursor` for captures and matches.

**Decision**: Use the new `QueryCursor` API exclusively. All tree-sitter queries go through `QueryCursor(query).captures(node)` which returns `dict[str, list[Node]]`.

**Consequences**: Breaks compatibility with tree-sitter < 0.25. Pinned to `tree-sitter >= 0.25.0` in pyproject.toml. Added to immutable rules as a gotcha.

---

## ADR-011: claim_evidence table not populated / git diff fallback

**Status**: Accepted (M14)

**Context**: The `claim_evidence` table was designed in M1 to store per-claim evidence records with file hashes. However, the extraction pipeline stores evidence file paths in the `Claim.evidence` tuple rather than populating the `claim_evidence` table.

**Decision**: Accept the gap. The freshness checker falls back to `git diff` between indexed HEAD and current HEAD when `claim_evidence` has no records. This provides the same staleness detection with less overhead.

**Consequences**: Evidence-triggered revalidation works via git diff comparison rather than per-file hash comparison. The `claim_evidence` table exists and is populated for some paths (import, explicit evidence storage) but not for the main extraction pipeline. Phase 2 may wire up full evidence population.

---

## ADR-012: Windsurf workspace budget

**Status**: Accepted (M15)

**Context**: Windsurf has a per-rule file size limit (6 KiB) and a total workspace budget (12 KiB). Other hosts only have per-file budgets.

**Decision**: Add `workspace_budget_bytes` to `SizeConstraints` and `BudgetTracker` to support Windsurf's two-tier budget model. The workspace budget tracks total content across all rule files.

**Consequences**: The budget tracker gained a second dimension. The Windsurf adapter checks both per-file and workspace limits. The workspace budget is specific to Windsurf — other adapters ignore it.

---

## ADR-013: Windsurf AGENTS.md deduplication

**Status**: Accepted (M15)

**Context**: Windsurf auto-reads AGENTS.md from the repo root. If RKP projects the same claims to both AGENTS.md and `.windsurf/rules/`, agents see duplicate instructions.

**Decision**: The Windsurf adapter accepts a set of claim IDs already projected to AGENTS.md and excludes them from `.windsurf/rules/` output.

**Consequences**: Requires computing the AGENTS.md projection before the Windsurf projection. The `get_instruction_preview` tool does this internally. Prevents duplication without losing coverage.
