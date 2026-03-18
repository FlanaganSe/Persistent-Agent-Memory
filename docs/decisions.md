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
