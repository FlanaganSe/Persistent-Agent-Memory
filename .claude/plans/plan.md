# Repo Knowledge Plane — Implementation Plan

_v2.0 — 2026-03-18. Revised after two independent critical reviews. Based on PRD v4.0 (`docs/prd.md`), product research (`docs/research-product.md`), build research (`docs/research-build.md`), and verified API research for FastMCP v3.1.1, tree-sitter v0.25+/tree-sitter-language-pack, and Typer v0.24.1._

---

## 1. Summary

RKP is a local-first, evidence-backed intelligence layer for software repositories. It extracts operational context (conventions, validated commands, environment prerequisites, module boundaries, guardrails) from code, config, CI definitions, and git history; stores it as canonical claims with provenance and confidence; lets humans review/govern those claims; and projects them faithfully into host-native instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md), skills, environment configs, and MCP tool responses — so every coding agent queries the same verified substrate.

**Core architectural decision**: The canonical data model is claim-based, not file-based. Projected instruction files, skills, and MCP responses are all derived views of the same claim store. This decouples extraction from projection, enables multi-host output from a single truth, and makes governance a first-class operation.

**Implementation philosophy**: Vertical slices, not horizontal tech buckets. Each milestone delivers end-to-end value — from extraction through claim storage to projection and testing — rather than "parser week" followed by "MCP week." The research is explicit: _"A good slice: 'GitHub Actions command evidence into Codex and Claude projection with review + tests.' Not 'parser week' and 'MCP week.'"_ (`docs/research-product.md` §14).

**Key revision decisions (v2.0)**:
- First end-to-end user value in M2, not M12
- Security fundamentals in M1, full hardening before import
- Environment profiles before any consumer that needs them
- No adapter labeled GA/Beta until conformance harness passes
- Overrides persistence designed in M1, implemented with governance
- All 26 PRD acceptance criteria mapped to specific milestones
- `DECLARED_IMPORTED_UNREVIEWED` precedence corrected to 3.5 (below `executable-config` at 3), per build research §3.1 note: "Imported claims should not outrank executable configuration until a human reviews them"
- Claim IDs are content-addressable at creation, immutable thereafter; edits preserve the original ID

---

## 2. Current State

Greenfield project. No source code exists. Repository contains: `docs/prd.md` (PRD v4.0), `docs/research-product.md`, `docs/research-build.md`, `docs/SYSTEM.md` (template), `CLAUDE.md`, `.claude/rules/` (placeholders), `README.md`, `.gitignore` (minimal).

Stack decisions are resolved in `docs/research-build.md` §1. Directory structure is designed in §2.3.

---

## 3. Pre-Coding Decisions (Must Resolve Before M1)

These are listed as "open questions" but block M1. They must be decided, not deferred.

| Decision | Resolution | Rationale |
|----------|-----------|-----------|
| **Package name** | `repo-knowledge-plane` (CLI: `rkp`) | Descriptive, unique. Verify PyPI availability before M1. |
| **License** | Apache 2.0 | Permissive, patent grant, enterprise-friendly (build research §1.1) |
| **`.rkp/overrides/` format** | strictyaml | Prevents code execution, limits YAML complexity, human-readable, merge-friendly (build research §1.1) |
| **Applicability vocabulary** | Controlled core + custom tags | Core: `build, test, lint, format, docs, review, refactor, debug, security, ci, release, onboarding`. Prevents tag proliferation while remaining flexible (product research §9 P1 #7) |
| **Phase 1 platform scope** | macOS + Linux only | Windows deferred unless design partner requires it (build research §12.4) |
| **Git as prerequisite** | Required; `rkp doctor` validates | Documented in README, validated at runtime |
| **`rkp verify` (active verification)** | Deferred to Phase 2. Seam only in Phase 1. | PRD A11: "Most MVP value comes from passive analysis." Build research §19 explicitly says "Avoid active verification in P0." Levels 1-4 satisfy all ACs. Sandbox execution security surface deserves Phase 2 attention. |

---

## 4. Files to Change

| File | Change | Why |
|------|--------|-----|
| `CLAUDE.md` | Update with real commands, stack info, system reference | Currently "TBD" |
| `.claude/rules/stack.md` | Fill in resolved stack decisions | Currently "TBD" |
| `.claude/rules/conventions.md` | Fill in Python conventions | Currently placeholder |
| `.claude/rules/immutable.md` | Add discovered invariants as they emerge | Currently empty |
| `README.md` | Update after each phase | Currently "early stage" |
| `docs/SYSTEM.md` | Fill in architecture/domain model/constraints | Currently template |
| `.gitignore` | Expand for Python project (.rkp/local/, __pycache__, .venv, dist/, etc.) | Currently minimal |

## 5. Files to Create

### Project scaffolding
| File | Purpose |
|------|---------|
| `pyproject.toml` | Package definition, dependencies, tool config (hatchling) |
| `noxfile.py` | Task runner: lint, typecheck, test, quality |
| `.python-version` | Pin Python 3.12 |

### Source: Core domain (`src/rkp/core/`)
| File | Purpose |
|------|---------|
| `src/rkp/__init__.py` | Package root, version |
| `src/rkp/__main__.py` | `python -m rkp` entry |
| `src/rkp/core/types.py` | StrEnums: ClaimType, SourceAuthority (with corrected precedence), ReviewState, Sensitivity, RiskClass, EvidenceLevel, ArtifactOwnership |
| `src/rkp/core/models.py` | Frozen dataclasses: Claim (with freshness, projection_targets), Evidence, ClaimHistory, ManagedArtifact, EnvironmentProfile, ModuleEdge, Identity (repo/branch/worktree/session) |
| `src/rkp/core/errors.py` | Typed exception hierarchy |
| `src/rkp/core/config.py` | RkpConfig via pydantic-settings + YAML |
| `src/rkp/core/ids.py` | Content-addressable claim IDs, immutable after creation |
| `src/rkp/core/claim_builder.py` | Deterministic claim construction, merge/dedup engine, conflict detection |
| `src/rkp/core/security.py` | Safe parsing utilities, path traversal prevention, injection marker detection |

### Source: Store layer (`src/rkp/store/`)
| File | Purpose |
|------|---------|
| `src/rkp/store/database.py` | SQLite connection factory, PRAGMAs, migration runner, WAL checkpoint policy |
| `src/rkp/store/claims.py` | ClaimStore Protocol: CRUD, scope/applicability filtering, precedence ordering |
| `src/rkp/store/evidence.py` | Evidence chain storage/retrieval |
| `src/rkp/store/history.py` | Append-only audit trail |
| `src/rkp/store/artifacts.py` | Managed artifact tracking with ownership modes (imported-human-owned, managed-by-rkp, mixed-migration) |
| `src/rkp/store/overrides.py` | `.rkp/overrides/` serialization: read/write/merge strictyaml override files into claim state |
| `src/rkp/store/migrations/0001_init.sql` | Full schema: claims (with freshness, projection_targets, worktree_id), claim_evidence, claim_history, claim_applicability, managed_artifacts, environment_profiles (linked to commands), module_edges, session_log |

### Source: Git backend (`src/rkp/git/`)
| File | Purpose |
|------|---------|
| `src/rkp/git/backend.py` | GitBackend Protocol: repo_root, head, branch, worktree_id, list_tracked_files (including untracked via `--others --exclude-standard`), file_hash, diff_status |
| `src/rkp/git/cli_backend.py` | Git CLI implementation (default) |

### Source: Indexer / Extraction (`src/rkp/indexer/`)
| File | Purpose |
|------|---------|
| `src/rkp/indexer/orchestrator.py` | Extraction pipeline: file discovery → parse → extract → claim build → store |
| `src/rkp/indexer/parsers/python.py` | Python tree-sitter queries |
| `src/rkp/indexer/parsers/javascript.py` | JS/TS tree-sitter queries |
| `src/rkp/indexer/extractors/conventions.py` | Naming, test placement, imports, type annotations, docstrings |
| `src/rkp/indexer/extractors/commands.py` | Build/test/lint/format from configs with evidence levels and risk classes |
| `src/rkp/indexer/extractors/prerequisites.py` | Runtimes, tools, services, env vars from configs/Dockerfiles/CI |
| `src/rkp/indexer/extractors/ci_evidence.py` | GitHub Actions: commands, runtimes, services, env, OS, matrix |
| `src/rkp/indexer/extractors/boundaries.py` | Module detection, import-based dependency edges, test locations |
| `src/rkp/indexer/extractors/guardrails.py` | Permission/restriction claim extraction from configs, CI, instruction files |
| `src/rkp/indexer/extractors/conflicts.py` | Declared-vs-inferred mismatch detection |
| `src/rkp/indexer/extractors/docs_evidence.py` | Checked-in-docs parser: README, docs/ with command blocks, ADRs |
| `src/rkp/indexer/config_parsers/pyproject.py` | pyproject.toml (tomllib) |
| `src/rkp/indexer/config_parsers/package_json.py` | package.json |
| `src/rkp/indexer/config_parsers/makefile.py` | Makefile targets (regex) |
| `src/rkp/indexer/config_parsers/dockerfile.py` | Dockerfile (dockerfile-parse) |
| `src/rkp/indexer/config_parsers/docker_compose.py` | docker-compose.yml (yaml.safe_load) |
| `src/rkp/indexer/config_parsers/github_actions.py` | GitHub Actions workflows |
| `src/rkp/indexer/config_parsers/version_files.py` | .python-version, .nvmrc, .tool-versions |

### Source: Importer (`src/rkp/importer/`)
| File | Purpose |
|------|---------|
| `src/rkp/importer/engine.py` | Import orchestration |
| `src/rkp/importer/parsers/agents_md.py` | AGENTS.md → claims |
| `src/rkp/importer/parsers/claude_md.py` | CLAUDE.md → claims |
| `src/rkp/importer/parsers/copilot.py` | copilot-instructions.md + .instructions.md + copilot-setup-steps.yml → claims |
| `src/rkp/importer/parsers/cursor.py` | .cursor/rules → claims |

### Source: Projection (`src/rkp/projection/`)
| File | Purpose |
|------|---------|
| `src/rkp/projection/engine.py` | Pure function: claims + adapter caps + policy → artifacts + excluded report + overflow report |
| `src/rkp/projection/capability_matrix.py` | Host capability descriptors per host |
| `src/rkp/projection/sensitivity.py` | Single enforcement point for sensitivity filtering |
| `src/rkp/projection/budget.py` | Context budget tracking and overflow routing |
| `src/rkp/projection/adapters/base.py` | BaseAdapter Protocol |
| `src/rkp/projection/adapters/agents_md.py` | AGENTS.md generator |
| `src/rkp/projection/adapters/claude_md.py` | CLAUDE.md + .claude/rules/ + .claude/skills/ generator |
| `src/rkp/projection/adapters/copilot.py` | copilot-instructions.md + .instructions.md + copilot-setup-steps.yml generator |
| `src/rkp/projection/adapters/cursor.py` | .cursor/rules generator (Alpha) |
| `src/rkp/projection/adapters/windsurf.py` | .windsurf/rules generator (Alpha) |
| `src/rkp/projection/adapters/skills.py` | Agent Skills (SKILL.md) cross-host generator |

### Source: Graph, Server, CLI, Quality
_(Same as build research §2.3 — see Appendix B for full directory structure.)_

| File | Purpose |
|------|---------|
| `src/rkp/graph/repo_graph.py` | SQLite edges + in-memory adjacency maps |
| `src/rkp/server/mcp.py` | FastMCP instance with lifespan, stdio transport |
| `src/rkp/server/tools.py` | All MCP tool implementations |
| `src/rkp/server/resources.py` | MCP resource implementations |
| `src/rkp/server/response.py` | Response envelope: status, supported/unsupported_reason, data, warnings, provenance, freshness |
| `src/rkp/cli/app.py` | Typer app, composition root |
| `src/rkp/cli/commands/*.py` | init, review, apply, refresh, status, import_, preview, audit, doctor, serve, purge |
| `src/rkp/cli/ui/*.py` | tables, diffs, review_flow, progress |
| `src/rkp/quality/harness.py` | Quality harness runner |
| `src/rkp/quality/fixtures.py` | Fixture repo evaluation |
| `src/rkp/quality/conformance.py` | Round-trip validation per adapter |
| `src/rkp/quality/leakage.py` | Sensitivity leakage tests |

### Tests + Docs
| File | Purpose |
|------|---------|
| `tests/conftest.py` | Shared fixtures: tmp_repo, populated_db, claim_factory |
| `tests/fixtures/{simple_python,simple_js,with_agents_md,with_ci,with_conflicts,with_drift}/` | Curated fixture repos with `expected_claims.json` |
| `tests/{unit,integration,property,snapshot}/` | Test directories by type |
| `docs/architecture.md` | System boundaries, data flow, extension seams |
| `docs/decisions.md` | Append-only ADR log |

---

## 6. Milestone Outline

### Design principles for this milestone structure

1. **Vertical slices**: Every milestone after M1 produces end-to-end user-visible value.
2. **Security before trust surfaces**: Safe parsing and path traversal in M1. Full hardening before import.
3. **Quality from the start**: Every milestone with extraction includes fixture tests with expected claims. Formal harness consolidates before any adapter is labeled GA/Beta.
4. **No forward-referencing verification**: Each milestone's verification criteria depend only on capabilities that exist at that point.
5. **Adapter maturity is earned, not declared**: Adapters start as "preview." GA/Beta promotion requires passing conformance harness.

---

### Phase 1: Prove the Architecture (M1–M3)

_Goal: Get from zero to a working end-to-end vertical slice — config → claims → AGENTS.md preview → MCP query — as fast as possible, so architectural blockers surface early._

- [x] **M1: Scaffolding + domain model + schema + security foundations**
  - pyproject.toml with all dependencies, tool configs (ruff, pyright, pytest, hatch)
  - noxfile.py with lint, typecheck, test sessions
  - `src/rkp/core/types.py` — all StrEnums. **Corrected**: `DECLARED_IMPORTED_UNREVIEWED` at precedence 3.5 (below `executable-config`/`ci-observed` at 3, above `checked-in-docs` at 4). `ArtifactOwnership` enum: `imported-human-owned`, `managed-by-rkp`, `mixed-migration`.
  - `src/rkp/core/models.py` — frozen dataclasses. Claim model includes: `freshness` (last_validated, revalidation_trigger, stale flag), `projection_targets` (JSON list), `worktree_id`, `session_id`. EnvironmentProfile as top-level object per PRD amendment P0 #3.
  - `src/rkp/core/ids.py` — claim IDs are `SHA-256(claim_type:scope:content)` truncated to 16 hex, prefixed `claim-`. **Immutable after creation**: edits change content but not ID. Re-extraction uses (claim_type, scope, content_similarity) matching against existing claims, not just ID.
  - `src/rkp/core/claim_builder.py` — deterministic claim construction: create claims from extractor output, deduplicate against existing, detect conflicts. This is the "Claim Plane" per build research §2.1.
  - `src/rkp/core/security.py` — safe parsing utilities (`yaml.safe_load` enforcement, path traversal prevention via `pathlib.Path.resolve()` + repo root containment, injection marker scanning). These ship with the foundation, not as a late milestone.
  - `src/rkp/core/errors.py`, `config.py`
  - `src/rkp/store/database.py` — SQLite connection factory, PRAGMAs (WAL, busy_timeout=5000, cache_size=-64000, foreign_keys, mmap_size=256MB), migration runner (`PRAGMA user_version`), WAL checkpoint policy (checkpoint at shutdown, short-lived read transactions).
  - `src/rkp/store/migrations/0001_init.sql` — **complete** schema: claims (with freshness fields, projection_targets, worktree_id), claim_evidence (with evidence_level), claim_history, claim_applicability, managed_artifacts (with ownership_mode), environment_profiles (linked to commands via claim_id), module_edges (with repo_id, branch), session_log.
  - `src/rkp/store/claims.py` — basic CRUD + scope filtering + precedence ordering. FTS5 deferred.
  - `src/rkp/store/evidence.py`, `history.py`
  - `.rkp/overrides/` format design: one strictyaml file per override, self-contained entries for merge-friendliness. Design documented in ADR; implementation in M9.
  - CI: GitHub Actions (lint + typecheck + test, macOS + ubuntu, Python 3.12)
  - `docs/decisions.md` — ADRs: storage strategy, git backend, parser envelope, adapter maturity, overrides format, claim ID stability, imported claims precedence
  - `docs/architecture.md` — 4-plane architecture, data flow, key boundaries
  - Update `.claude/rules/stack.md`, `.claude/rules/conventions.md`, `.gitignore`
  - **Verification**: `nox -s lint typecheck test` passes. Core types instantiate. Claim ID generation is deterministic. Claim CRUD stores/retrieves with full fidelity. Path traversal prevention blocks escapes. Safe YAML enforcement tested.
  - **AC coverage**: AC-15 (no cloud dependency by design), partial AC-14 (data boundary design)

- [x] **M2: First vertical slice — config → claims → AGENTS.md preview → MCP tool**
  - [x] Step 1 — Config parsers + command extractor + orchestrator → verify: `pytest tests/unit/test_config_parsers.py tests/unit/test_commands_extractor.py tests/integration/test_orchestrator.py -v`
  - [x] Step 2 — Projection engine (sensitivity, budget, capability, engine, adapters) → verify: `pytest tests/snapshot/ tests/unit/test_sensitivity.py tests/unit/test_budget.py -v`
  - [x] Step 3 — MCP server (response, mcp, tools) → verify: `pytest tests/integration/test_mcp_contract.py -v`
  - [x] Step 4 — CLI (app, preview, serve) → verify: `pytest tests/integration/test_cli.py -v`
  - [x] Step 5 — Full verification → verify: `ruff check src tests && ruff format --check src tests && pyright && pytest`
  Commit: "feat: M2 first vertical slice — config→claims→AGENTS.md→MCP"
  - `src/rkp/indexer/config_parsers/pyproject.py` + `package_json.py` — two config parsers only
  - `src/rkp/indexer/extractors/commands.py` — command extraction with evidence levels (discovered, prerequisites-extracted) and risk classes (safe-readonly through destructive)
  - `src/rkp/indexer/orchestrator.py` — minimal: parse config files → extract commands → build claims → store
  - `src/rkp/projection/engine.py` — projection core: claims + adapter caps → artifacts + excluded/overflow reports
  - `src/rkp/projection/capability_matrix.py` — AGENTS.md capabilities only for now
  - `src/rkp/projection/sensitivity.py` — sensitivity filter (single enforcement point, from day one)
  - `src/rkp/projection/budget.py` — context budget tracking (32KiB for AGENTS.md)
  - `src/rkp/projection/adapters/base.py` + `agents_md.py` — minimal AGENTS.md: validated commands section, thin-by-default, generation header with provenance, deterministic output
  - `src/rkp/server/mcp.py` — FastMCP server with lifespan (open DB, load claims)
  - `src/rkp/server/response.py` — response envelope (status, supported/unsupported_reason, data, warnings, provenance)
  - `src/rkp/server/tools.py` — `get_validated_commands` tool only (with `readOnlyHint: true`, proper response envelope)
  - `src/rkp/cli/app.py` — Typer app, composition root
  - `src/rkp/cli/commands/preview.py` — `rkp preview --host codex`
  - `src/rkp/cli/commands/serve.py` — `rkp serve`
  - `tests/fixtures/simple_python/` — first fixture repo with pyproject.toml, expected_claims.json
  - First snapshot test: known claims → expected AGENTS.md output
  - First MCP contract test: in-memory client, get_validated_commands
  - First sensitivity leakage test (basic)
  - **Verification**: `rkp preview --host codex` produces a non-empty AGENTS.md preview from a Python repo's pyproject.toml. MCP tool returns validated commands. Sensitivity filter blocks local-only claims from projection. Snapshot test passes.
  - **AC coverage**: Partial AC-1 (first useful output path), AC-6 (get_validated_commands), partial AC-13 (provenance), partial AC-18 (thin projection)

- [x] **M3: Git backend + tree-sitter + Python convention extraction**
  - [x] Step 1 — Git backend + tree-sitter parser + convention extractor + fixture files → verify: `ruff check src/rkp/git src/rkp/indexer/parsers src/rkp/indexer/extractors/conventions.py && pyright src/rkp/git src/rkp/indexer/parsers src/rkp/indexer/extractors/conventions.py`
  - [x] Step 2 — Extend orchestrator + AGENTS.md projection + MCP tool + CLI → verify: `ruff check src/rkp/indexer/orchestrator.py src/rkp/projection/adapters/agents_md.py src/rkp/server && pyright src/rkp/indexer/orchestrator.py src/rkp/projection/adapters/agents_md.py src/rkp/server`
  - [x] Step 3 — All tests (unit, integration, snapshot, MCP contract) → verify: `pytest tests/ -v`
  - [x] Step 4 — Full verification → verify: `ruff check src tests && ruff format --check src tests && pyright && pytest`
  Commit: "feat: M3 git backend + tree-sitter + Python convention extraction"
  - **Verification**: Conventions extracted from Python fixture repo match expected claims with >=80% precision. `get_conventions` returns scoped conventions with confidence and evidence. `rkp preview` includes extracted conventions.
  - **AC coverage**: AC-4 (get_conventions), AC-12 (incremental via git blob OID comparison), partial AC-2 (source authority + confidence on claims)

---

### Phase 2: Widen Extraction + Full Projection (M4–M8)

_Goal: Full extraction pipeline, all P0 adapters (preview maturity), complete MCP contract, and core CLI commands._

- [x] **M4: JS/TS parsing + CI evidence + prerequisites + environment profiles**
  - [x] Step 1 — JS/TS parser + 5 config parsers (makefile, dockerfile, docker_compose, github_actions, version_files)
  - [x] Step 2 — CI evidence extractor + prerequisite extractor + environment profiles + extend conventions for JS/TS
  - [x] Step 3 — Extend orchestrator + MCP get_prerequisites tool
  - [x] Step 4 — Test fixtures + all tests (unit, integration, contract)
  - [x] Step 5 — Full verification
  Commit: "feat: M4 JS/TS parsing, CI evidence, prerequisites, environment profiles"
  - **Verification**: Commands from pyproject.toml, package.json, Makefile, and GitHub Actions extracted with correct evidence levels. Prerequisites aggregated into environment profiles. CI evidence cross-referenced. `get_prerequisites` returns structured profiles.
  - **AC coverage**: AC-7 (get_prerequisites with CI evidence), AC-25 (GitHub Actions parsed), partial AC-6 (extended evidence levels)

- [x] **M5: Module boundaries + checked-in-docs evidence + conflict detection**
  - [x] Step 1 — RepoGraph (done) (Protocol + SqliteRepoGraph) + boundary extractor + docs evidence extractor + conflict detector → verify: `ruff check src/rkp/graph src/rkp/indexer/extractors/boundaries.py src/rkp/indexer/extractors/docs_evidence.py src/rkp/indexer/extractors/conflicts.py && pyright src/rkp/graph src/rkp/indexer/extractors/boundaries.py src/rkp/indexer/extractors/docs_evidence.py src/rkp/indexer/extractors/conflicts.py`
  - [x] Step 2 — Extend orchestrator + MCP tools (get_module_info, get_conflicts)
  - [x] Step 3 — Test fixtures (extend simple_python, simple_js; create with_conflicts) + all tests (319 pass)
  - [x] Step 4 — Full verification (ruff, format, pyright, pytest — all clean)
  Commit: "feat: M5 module boundaries, docs evidence, conflict detection"
  - **Verification**: Module boundaries correctly identified. Import-based dependencies match manual inspection. Checked-in-docs evidence extracted with correct authority. Conflicts surfaced where declared and inferred diverge.
  - **AC coverage**: AC-5 (get_module_info), partial AC-2 (checked-in-docs authority tier active), AC-16 (unsupported areas reported explicitly)

- [x] **M6: CLAUDE.md adapter + skills + guardrail extraction/projection**
  - [x] Step 1 — Infrastructure: capability matrix (add Claude), budget tracker (optional hard_budget_bytes), pyproject security tools, guardrail extractor
  - [x] Step 2 — Skills adapter + Claude.md adapter
  - [x] Step 3 — Orchestrator (guardrails phase) + MCP tools + CLI preview
  - [x] Step 4 — All tests (372 pass, 0 fail)
  - [x] Step 5 — Full verification (ruff, format, pyright, pytest — all clean)
  Commit: "feat: M6 CLAUDE.md adapter, skills, guardrail extraction/projection"
  - **AC coverage**: AC-9 (get_guardrails with enforceable output), AC-8 (CLAUDE.md preview), partial AC-18 (skills for detailed content)

- [x] **M7: Full MCP server contract + response completeness**
  - [x] Step 1 — Response envelope audit: fix to_dict() (always include unsupported_reason, warnings), add make_partial/unsupported/error helpers, parameterize index_version
  - [x] Step 2 — Source allowlist config: SourceAllowlist model in config.py, enforce_allowlist() filter in tools.py
  - [x] Step 3 — Tool updates: pagination (cursor/limit) + detail_level (terse/normal/detailed) on get_conventions, get_validated_commands, get_conflicts, get_guardrails; fix get_instruction_preview unsupported response
  - [x] Step 4 — New tools: get_preflight_context, get_repo_overview, get_claim, refresh_index; refactor mcp.py (eliminate tool duplication via _register_tools); create resources.py (6 MCP resources)
  - [x] Step 5 — Tests: 9 new test files (envelope, pagination, detail_levels, preflight, overview, claim, refresh, allowlist, resources) + updated 4 existing test files for new response shape. 444 total pass (372 existing + 72 new)
  - [x] Step 6 — Full verification: ruff check, ruff format, pyright strict, pytest — all clean
  Commit: "feat: M7 full MCP server contract, pagination, detail levels, resources"
  - **AC coverage**: AC-3 (MCP server responds to all tools), AC-4/5/6/7/8/9 (all tool completeness), AC-13 (provenance on every response), AC-16 (explicit unsupported status)

- [x] **M8: CLI init + preview + status + doctor + serve**
  - [x] Step 1 — Refactor composition root (app.py → lazy DB/git), create UI utilities (output, tables, progress, diffs) → verify: `ruff check src/rkp/cli && pyright src/rkp/cli`
  - [x] Step 2 — Implement `rkp doctor`, `rkp init`, `rkp status` commands + extend `rkp serve` and `rkp preview` → verify: `ruff check src/rkp/cli && pyright src/rkp/cli`
  - [x] Step 3 — Integration tests for all CLI commands (init, status, doctor, serve, preview) → verify: `pytest tests/integration/test_cli_init.py tests/integration/test_cli_status.py tests/integration/test_cli_doctor.py tests/integration/test_cli_serve.py tests/integration/test_cli.py -v`
  - [x] Step 4 — Full verification → verify: `ruff check src tests && ruff format --check src tests && pyright && pytest`
  Commit: "feat: M8 CLI init + preview + status + doctor + serve"
  - **Verification**: `rkp init` produces useful output on fixture repos. `rkp preview` shows host-specific projections. `rkp status` reports correctly for what exists (index health, pending reviews). `rkp doctor` validates all prerequisites including Git.
  - **AC coverage**: Partial AC-1 (init produces non-template output), AC-15 (runs without cloud)

---

### Phase 3: Governance + Trust + Import (M9–M12)

_Goal: Complete the human governance loop, harden security before import, implement import/drift, and add Copilot adapter._

- [x] **M9: Review + governance + overrides persistence**
  - [x] Step 1 — Override model + store (src/rkp/store/overrides.py): Override dataclass, OverrideStore Protocol, FileSystemOverrideStore with strictyaml serialization, sensitivity enforcement, apply_overrides → verify: `uv run ruff check src/rkp/store/overrides.py && uv run pyright src/rkp/store/overrides.py`
  - [x] Step 2 — Review flow UI + review command (src/rkp/cli/ui/review_flow.py, src/rkp/cli/commands/review.py): Rich Panel claim display, interactive keyboard actions, $EDITOR integration, --approve-all batch mode, --type/--scope/--state filters, declaration prompts → verify: `uv run ruff check src/rkp/cli/commands/review.py src/rkp/cli/ui/review_flow.py && uv run pyright src/rkp/cli/commands/review.py src/rkp/cli/ui/review_flow.py`
  - [x] Step 3 — Apply + purge commands (src/rkp/cli/commands/apply.py, src/rkp/cli/commands/purge.py): diff preview, review-state filtering, confirmation, artifact tracking, purge with audit trail → verify: `uv run ruff check src/rkp/cli/commands/apply.py src/rkp/cli/commands/purge.py && uv run pyright src/rkp/cli/commands/apply.py src/rkp/cli/commands/purge.py`
  - [x] Step 4 — Integration: update init.py (load overrides after extraction), update app.py (register review/apply/purge), update projection engine (review-state filtering for apply vs preview) → verify: `uv run ruff check src/rkp/cli/ src/rkp/projection/ && uv run pyright src/rkp/cli/ src/rkp/projection/`
  - [x] Step 5 — Tests: unit tests (overrides, projection review-state), integration tests (review, apply, purge CLI), full governance lifecycle test → verify: `uv run pytest tests/ -v`
  Commit: "feat: M9 review + governance + overrides persistence"
  - **Verification**: Review workflow persists decisions correctly. Overrides round-trip: write → clone on new machine → `rkp init` → same approved/suppressed state. Apply writes expected files with correct content. Purge hard-deletes and logs. Audit trail captures all actions. Declaration prompts surfaced and answerable.
  - **AC coverage**: AC-10 (no write without review), AC-11 (full correction workflow including declaration prompts), AC-17 (audit trail + purge), AC-23 (version-controlled overrides, regenerable local state)

- [x] **M10: Security hardening**
  - [x] Step 1 — Extend `src/rkp/core/security.py`: InjectionFinding/SecretFinding models, scan_for_injection() with severity/code-block-allowlisting, scan_for_secrets() with regex+entropy, redact_secrets(). Create `src/rkp/server/response_filter.py` for MCP response scanning → verify: `uv run ruff check src/rkp/core/security.py src/rkp/server/response_filter.py && uv run pyright src/rkp/core/security.py src/rkp/server/response_filter.py`
  - [x] Step 2 — Integrate scanning into orchestrator (post-extraction, pre-store) and MCP response path (decorator on all tool handlers in mcp.py) → verify: `uv run ruff check src/rkp/indexer/orchestrator.py src/rkp/server/mcp.py && uv run pyright src/rkp/indexer/orchestrator.py src/rkp/server/mcp.py`
  - [x] Step 3 — Unit tests: test_injection_detection.py, test_secret_detection.py, test_response_filter.py → verify: `uv run pytest tests/unit/test_injection_detection.py tests/unit/test_secret_detection.py tests/unit/test_response_filter.py -v`
  - [x] Step 4 — Integration tests: test_sensitivity_enforcement.py, test_allowlist_enforcement.py, test_data_boundary.py → verify: `uv run pytest tests/integration/test_sensitivity_enforcement.py tests/integration/test_allowlist_enforcement.py tests/integration/test_data_boundary.py -v`
  - [x] Step 5 — Full verification: all 519+ existing tests pass + new tests, ruff, pyright → verify: `uv run ruff check src tests && uv run ruff format --check src tests && uv run pyright && uv run pytest`
  Commit: "feat: M10 security hardening — injection defense, secret detection, response filtering"
  - **Verification**: No injection markers pass through to MCP responses (with allowlisting for legitimate content). Path traversal blocked. Secrets detected and flagged. Sensitivity filter never leaks. Source allowlists enforced.
  - **AC coverage**: AC-14 (data boundary verified), AC-24 (sensitivity field enforced, leakage tested)

- [ ] **M11: Import + artifact ownership + drift detection**
  - `src/rkp/importer/engine.py` — import orchestration: discover instruction files → parse → create `declared-imported-unreviewed` claims (precedence 3.5, **below** executable-config) → run extraction in parallel → surface conflicts → present unified review
  - `src/rkp/importer/parsers/agents_md.py` + `claude_md.py` + `copilot.py` — import parsers for AGENTS.md, CLAUDE.md, copilot-instructions.md, copilot-setup-steps.yml (per PRD §11 supported import sources)
  - Import parsing: deterministic (frontmatter, code blocks, globs) + heuristic (heading classification, bullet extraction, command detection). LLM-assisted deferred.
  - Artifact ownership modes (per build research §3.7): `imported-human-owned` (imported but not managed), `managed-by-rkp` (regenerated after review), `mixed-migration` (transitioning, explicit diffs/warnings). Ownership mode persists on `managed_artifacts` table and governs drift/apply behavior.
  - `src/rkp/store/artifacts.py` — (extend) drift detection: content drift (file hash differs from expected), new unmanaged files, missing files. Hash comparison uses same normalization as generation.
  - Drift reconciliation: absorb (update claim from manual edit → creates declared-policy claim), reject (regenerate from canonical model), suppress (stop managing artifact)
  - `src/rkp/cli/commands/import_.py` — `rkp import [--source path]`
  - Extend `rkp status` with drift reporting
  - `tests/fixtures/with_agents_md/`, `tests/fixtures/with_drift/` — fixture repos
  - **Verification**: Imported files produce claims at correct authority. Conflicts surfaced between imported and extracted. Ownership modes govern behavior correctly: imported-human-owned files not overwritten, managed files regenerable, mixed-migration shows diffs. Drift correctly detected and reconcilable. Round-trip fidelity >=90%.
  - **AC coverage**: AC-21 (import AGENTS.md and CLAUDE.md), AC-22 (drift detection), AC-20 (partial: evidence-triggered revalidation via drift)

- [ ] **M12: Copilot adapter (Beta)**
  - `src/rkp/projection/adapters/copilot.py` — copilot-instructions.md, `.github/instructions/**/*.instructions.md` (path-scoped with `applyTo`), `copilot-setup-steps.yml` (validate: single job named `copilot-setup-steps`, max 59 min timeout, supported keys only)
  - MCP tool allowlist generation for Copilot (explicit allowlists of read-only tools per build research §8.8)
  - **Do NOT rely on resources/prompts** for Copilot coding agent flows (tools-only host)
  - Copilot-specific conformance tests (YAML shape validation + constraint checking)
  - Guardrail projection: Copilot agent tool config (enforceable), custom agent tool scoping
  - **Verification**: copilot-instructions.md projection is correct. Setup-steps.yml passes constraint validation. Tool allowlist generated correctly. Path-scoped .instructions.md files have correct `applyTo`. `get_instruction_preview` for copilot includes all surfaces.
  - **AC coverage**: AC-8 (copilot preview projection — "Beta" pending conformance harness)

---

### Phase 4: Quality + Ship (M13–M16)

_Goal: Formal quality measurement, adapter maturity promotion, remaining features, and release._

- [ ] **M13: Quality harness + trace capture + adapter maturity promotion**
  - `src/rkp/quality/harness.py` — quality harness runner
  - `src/rkp/quality/fixtures.py` — fixture repo evaluation: load expected_claims.json, measure precision/recall
  - `src/rkp/quality/conformance.py` — export conformance: automated round-trip validation per adapter
  - `src/rkp/quality/leakage.py` — sensitivity leakage tests across all adapters
  - Drift detection correctness tests against fixture repos with known edits
  - Import fidelity tests (import → claims → project → diff against original)
  - 250k LOC performance benchmark: `rkp init` completes within 5 minutes on a representative large repo
  - MCP trace capture: log queries, responses, timestamps (local-only, opt-in anonymized sharing per PRD §8.3)
  - Nox session: `nox -s quality`
  - **Adapter maturity promotion**: Only after this milestone passes do adapters earn their maturity labels:
    - AGENTS.md + CLAUDE.md: promote to **GA** if conformance + drift + leakage pass
    - Copilot: promote to **Beta** if conformance passes with documented gaps
    - Cursor/Windsurf: remain **Alpha (export-only)** until M15
  - **Verification**: Extraction precision >=80%. Export conformance >=95% for GA adapters. Zero sensitivity leakage. 250k LOC benchmark within 5 minutes. Trace capture producing logs.
  - **AC coverage**: AC-1 (250k LOC verified), AC-19 (quality harness complete), AC-24 (leakage tested), AC-26 (trace capture)

- [ ] **M14: Refresh + audit + stale-claim revalidation**
  - `src/rkp/cli/commands/refresh.py` — `rkp refresh`: re-analyze repo, present diff of what changed in claim model
  - Stale-claim revalidation: evidence-triggered (file changed → claim flagged), branch-aware (validate against current branch), drift-aware (managed artifact edited → affected claims flagged), time-based fallback (90 days default, configurable)
  - `src/rkp/cli/commands/audit.py` — `rkp audit [--claim-id X] [--scope path]`
  - Extend `rkp status` with staleness indicators
  - **Verification**: Refresh correctly identifies changed claims. Stale claims flagged on evidence change. Branch switch detected and handled. Audit trail queryable by claim and scope.
  - **AC coverage**: AC-20 (evidence-triggered + branch-aware + drift-aware revalidation)

- [ ] **M15: Cursor/Windsurf adapters (Alpha) + path-scoped refinement**
  - `src/rkp/projection/adapters/cursor.py` — .cursor/rules export (alwaysApply + glob-scoped)
  - `src/rkp/projection/adapters/windsurf.py` — .windsurf/rules export (always_on + glob-scoped)
  - `src/rkp/importer/parsers/cursor.py` — .cursor/rules import
  - Path-scoped convention refinement: per-scope analysis (not just global), directory-level projection
  - Alpha adapter conformance tests
  - **Verification**: Cursor and Windsurf exports generate valid formats. Path-scoped rules correctly projected per host. Alpha conformance tests pass.
  - **AC coverage**: AC-8 (extended host coverage)

- [ ] **M16: Documentation + release prep**
  - Update README.md (installation, quickstart, commands, support envelope, trust model)
  - Fill docs/SYSTEM.md (real architecture, domain model, constraints)
  - Create docs/claim-model.md, docs/host-adapters.md, docs/security.md, docs/quality-harness.md
  - MkDocs Material setup + GitHub Pages
  - PyPI release pipeline: trusted publishing (OIDC) via GitHub Actions, tag-triggered
  - Towncrier changelog setup
  - SBOM generation (CycloneDX)
  - License headers on all source files
  - **Verification**: `uvx repo-knowledge-plane init` works from PyPI. Docs render. Changelog generates.
  - **AC coverage**: AC-14 (data boundary documented)

---

## 7. Acceptance Criteria Coverage Map

Every AC must have a clear milestone. If it doesn't, it's a plan gap.

| AC | Description | Primary milestone | Verified by |
|----|-------------|-------------------|-------------|
| AC-1 | `uvx rkp init` <5 min on 250k LOC | M13 | 250k LOC benchmark |
| AC-2 | Claims distinguished by source authority | M3, M5 | Fixture tests + checked-in-docs tier |
| AC-3 | MCP server responds to all tools | M7 | Full contract test suite |
| AC-4 | get_conventions with evidence | M3 | Fixture tests |
| AC-5 | get_module_info | M5 | Fixture tests |
| AC-6 | get_validated_commands | M2 | First vertical slice test |
| AC-7 | get_prerequisites with CI evidence | M4 | CI fixture tests |
| AC-8 | get_instruction_preview for GA+Beta | M6 (Claude), M7 (all), M12 (Copilot) | Snapshot tests |
| AC-9 | get_guardrails enforceable | M6 | Guardrail projection tests |
| AC-10 | No write without review | M9 | Apply workflow tests |
| AC-11 | Full correction workflow | M9 | Declaration prompt + purge tests |
| AC-12 | Incremental <2s | M3 | Performance test |
| AC-13 | Provenance on every response | M2 (first), M7 (complete) | Contract tests |
| AC-14 | No data off machine + documented | M10, M16 | Security tests + docs |
| AC-15 | No cloud dependency | M1 | By design |
| AC-16 | Explicit unsupported status | M5, M7 | Envelope support test |
| AC-17 | Audit trail + purge | M9 | Purge + audit tests |
| AC-18 | Thin always-on, skills for detail | M2 (first), M6 (skills) | Snapshot tests |
| AC-19 | Quality harness passes all fixtures | M13 | Harness run |
| AC-20 | Evidence-triggered revalidation | M14 | Staleness tests |
| AC-21 | Import AGENTS.md + CLAUDE.md | M11 | Import fixture tests |
| AC-22 | Drift detection | M11 | Drift fixture tests |
| AC-23 | .rkp/ version-controlled | M9 | Override round-trip test |
| AC-24 | Sensitivity filtering | M2 (filter), M10 (hardened), M13 (harness) | Leakage tests |
| AC-25 | CI definitions parsed | M4 | CI fixture tests |
| AC-26 | Trace capture | M13 | Trace output test |

---

## 8. Testing Strategy

### Per-milestone testing

Every extraction milestone includes fixture repos with `expected_claims.json`. Every projection milestone includes snapshot (syrupy) tests. Every MCP milestone includes in-memory contract tests. No milestone ships without passing `nox -s lint typecheck test`.

| Phase | Test types | Key targets |
|-------|-----------|-------------|
| M1 | Unit, Property | Core types, claim CRUD, ID determinism, path traversal, safe YAML |
| M2 | Unit, Snapshot, Contract, Security | End-to-end slice, projection, MCP tool, sensitivity filter |
| M3 | Unit, Fixture, Contract | Parser output, convention precision/recall, get_conventions |
| M4 | Fixture, Contract | CI evidence, prerequisites, env profiles, get_prerequisites |
| M5 | Fixture, Contract | Module detection, docs evidence, conflicts, graph ops |
| M6 | Snapshot, Contract | CLAUDE.md + rules + skills, guardrail projection, get_guardrails |
| M7 | Contract | All MCP tools, response envelope, pagination, unsupported behavior |
| M8 | Integration | CLI end-to-end: init, preview, status, doctor |
| M9 | Integration | Review flow, apply, purge, override persistence round-trip |
| M10 | Security | Injection, traversal, secrets, leakage, data boundary |
| M11 | Integration, Roundtrip | Import fidelity, ownership modes, drift detection/reconciliation |
| M12 | Snapshot, Conformance | Copilot projection, setup-steps validation, tool allowlist |
| M13 | Meta, Performance | Quality harness measures correctly, 250k LOC benchmark |
| M14 | Integration | Refresh, staleness, audit queries |
| M15 | Snapshot | Cursor/Windsurf export, path-scoped projection |
| M16 | Smoke | Release pipeline, docs render |

### Nox sessions

```
nox -s lint        # ruff check + ruff format --check
nox -s typecheck   # pyright strict
nox -s test        # pytest with coverage
nox -s quality     # quality harness (M13+)
nox -s benchmark   # pytest-benchmark for performance
nox -s ci          # all of the above
```

---

## 9. Migration & Rollback

`.rkp/local/` (SQLite DB) is regenerable from repo + `.rkp/overrides/`. Delete and `rkp init` to rebuild. Human decisions in `.rkp/overrides/` are version-controlled via git.

- **Schema changes**: Forward-only numbered SQL files in `src/rkp/store/migrations/`. `PRAGMA user_version` tracks version. Each migration wrapped in transaction.
- **Projected files**: `rkp review` to fix claims, `rkp apply` to regenerate. Diff preview prevents blind overwrites.
- **API stability**: MCP tool names and parameters are the public API. Breaking changes require major version bump.

---

## 10. Manual Setup Tasks

| Task | Required before | Description |
|------|----------------|-------------|
| **Resolve pre-coding decisions (§3)** | M1 | Package name, license, overrides format, applicability vocabulary, platform scope |
| **Python 3.12 installed** | M1 | Verify in dev environment and CI |
| **uv installed** | M1 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Git installed** | M1 | Required external dependency; `rkp doctor` validates |
| **Set up GitHub repo settings** | M1 | Branch protection, required CI checks |
| **Verify SQLite FTS5 support** | M1 | Python's bundled SQLite should have it; verify in CI |
| **Create initial fixture repos** | M2 | Curate test fixtures with expected claims |
| **PyPI trusted publishing** | M16 | Configure OIDC for GitHub Actions → PyPI |
| **GitHub Pages setup** | M16 | For MkDocs hosting |

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **tree-sitter-language-pack API breaks** | Medium | Blocks parsing | Pin strictly. Thin wrapper. Verify QueryCursor API in M3. |
| **FastMCP v3 breaking changes** | Medium | Blocks MCP | Pin strictly. Thin abstraction in `server/mcp.py`. |
| **Convention extraction precision too low** | Medium | Trust collapse | Conservative thresholds (95%). Quality harness. Flag weak inferences for review. |
| **Instruction file import parsing inaccurate** | High | Distrust import | Start with structured elements only. Accept "partially parsed." Surface unparseable honestly. |
| **Claim ID drift under re-extraction** | Medium | Approved claims "resurrect" | IDs immutable after creation. Re-extraction matches by (type, scope, similarity), not just hash. ADR documents strategy. |
| **Schema churn from deferred fields** | Medium | Rework after M2 | Complete schema in M1 (identity, freshness, env profiles, evidence levels). Migration system from day one. |
| **Overrides persistence design wrong** | Medium | Team-sharing breaks | Design in M1 ADR. strictyaml format. Self-contained files for merge-friendliness. Implement in M9 with round-trip test. |
| **Imported claims outrank build truth** | High | Wrong agent behavior | Precedence 3.5 (below executable-config). Only promoted to `declared-reviewed` after human review. |
| **Performance cliffs on large repos** | Low | Bad first impression | File exclusion before parsing. Batch writes. 250k LOC benchmark in M13. |
| **GA labeling before conformance** | High | False confidence | Adapters start as "preview." GA/Beta requires M13 conformance harness passing. |
| **Security after import** | High | Untrusted input | Security fundamentals in M1. Full hardening (M10) before import (M11). |
| **Copilot validation insufficient** | Medium | Broken setup-steps | Constraint validation beyond actionlint: job naming, timeout, supported keys. |
| **Scope creep** | High | Delayed MVP | Strict milestone exit criteria. Each independently verifiable. |

---

## 12. Open Questions (Remaining)

Pre-coding decisions (§3) are resolved. These remain genuinely open but do not block M1:

1. **Container runtime for Phase 2 verification**: Podman (rootless, preferred) vs Docker vs both?
2. **Default staleness window**: 90 days for time-based fallback. Appropriate for design partners?
3. **MkDocs vs simpler docs**: Is full MkDocs Material justified for M16, or is a simple docs/ directory sufficient until then?
4. **Telemetry beyond trace capture**: OpenTelemetry (GenAI semantic conventions, opt-in, local-first) — implement in Phase 1 or defer to Phase 2?

---

## Appendix A: Key Dependency Versions

```
python >= 3.12, < 3.14
fastmcp >= 3.1.0, < 4.0.0              # v3.1.1 verified; Apache-2.0
typer[all] >= 0.15.0, < 1.0.0          # v0.24.1 verified; includes Rich
tree-sitter >= 0.25.0, < 1.0.0         # v0.25+ required for QueryCursor API
tree-sitter-language-pack >= 0.13.0     # pre-compiled grammars, MIT/Apache-2.0
pydantic >= 2.0.0, < 3.0.0
pydantic-settings >= 2.7.0, < 3.0.0
structlog >= 25.0.0
pyyaml >= 6.0.0
strictyaml >= 1.7.0
dockerfile-parse >= 2.0.0
ruff >= 0.9.0                           # dev
pyright >= 1.1.400                      # dev
pytest >= 8.0.0                         # dev
pytest-asyncio >= 0.24.0               # dev (MCP tests are async)
hypothesis >= 6.0.0                     # dev
syrupy >= 4.0.0                         # dev
pytest-cov >= 6.0.0                     # dev
pytest-benchmark >= 5.0.0              # dev
nox >= 2024.0.0                         # dev
```

**Note**: `fastmcp` depends on the official `mcp` SDK. Import `from mcp.types import ToolAnnotations, TextContent` for protocol types. Do NOT install `mcp` separately.

## Appendix B: Directory Structure Reference

```
repo-knowledge-plane/
    src/rkp/
        __init__.py, __main__.py
        core/
            types.py, models.py, errors.py, config.py,
            ids.py, claim_builder.py, security.py
        store/
            database.py, claims.py, evidence.py, history.py,
            artifacts.py, overrides.py
            migrations/0001_init.sql
        git/
            backend.py, cli_backend.py
        indexer/
            orchestrator.py
            parsers/python.py, javascript.py
            extractors/
                conventions.py, commands.py, prerequisites.py,
                ci_evidence.py, boundaries.py, guardrails.py,
                conflicts.py, docs_evidence.py
            config_parsers/
                pyproject.py, package_json.py, makefile.py,
                dockerfile.py, docker_compose.py,
                github_actions.py, version_files.py
        importer/
            engine.py
            parsers/agents_md.py, claude_md.py, copilot.py, cursor.py
        projection/
            engine.py, capability_matrix.py, sensitivity.py, budget.py
            adapters/
                base.py, agents_md.py, claude_md.py, copilot.py,
                cursor.py, windsurf.py, skills.py
        graph/repo_graph.py
        server/
            mcp.py, tools.py, resources.py, response.py
        cli/
            app.py
            commands/
                init.py, review.py, apply.py, refresh.py,
                status.py, import_.py, preview.py, audit.py,
                doctor.py, serve.py, purge.py
            ui/tables.py, diffs.py, review_flow.py, progress.py
        quality/
            harness.py, fixtures.py, conformance.py, leakage.py
    tests/
        conftest.py
        fixtures/{simple_python,simple_js,with_agents_md,
                  with_ci,with_conflicts,with_drift}/
        unit/, integration/, property/, snapshot/
    docs/
        architecture.md, decisions.md, claim-model.md,
        host-adapters.md, security.md, quality-harness.md
    .rkp/
        config.yaml           # checked in
        overrides/             # checked in (strictyaml)
        local/                 # gitignored (SQLite, cache)
    pyproject.toml, noxfile.py, .python-version
    .github/workflows/ci.yml
```

## Appendix C: Critical Invariants

1. **No instruction file written without human review and explicit approval.** MCP exposes previews only; CLI exposes `apply` after review.
2. **No repo content transmitted off local machine by RKP itself.** Data boundary with host agents documented.
3. **Sensitivity filtering enforced at a single point, just before output.** Both projection and MCP.
4. **MCP tools are read-only** (no file/repo modification). `refresh_index` modifies internal index only and is marked `readOnlyHint: false`.
5. **Projected output is deterministic** for the same effective claim state.
6. **All logging uses stderr.** stdout reserved for MCP protocol.
7. **YAML parsed with safe_load() (repo) or strictyaml (.rkp/).** Never `yaml.load()`.
8. **Claims carry provenance on every response.** Index version, repo HEAD, branch, timestamp, confidence, source authority, applicability, review state.
9. **Extractors never know how hosts consume data. Adapters never infer claims.** Strict plane separation.
10. **Active verification is opt-in with explicit per-category consent.** Default is passive analysis.
11. **Imported claims do not outrank executable configuration until reviewed.** `DECLARED_IMPORTED_UNREVIEWED` at precedence 3.5.
12. **Claim IDs are immutable after creation.** Edits change content, not ID.
13. **Adapter maturity is earned via conformance harness, not declared at implementation time.**

## Appendix D: Phase 2+ Seams (Design Now, Implement Later)

These interfaces should exist in Phase 1 code but not be implemented:

1. **`GitBackend` Protocol** — Phase 2 adds optional pygit2 backend
2. **`RepoGraph` interface** — Phase 2 adds optional rustworkx accelerator
3. **Parser registry** — Phase 2 adds Go, Java, Rust grammars
4. **Adapter registry** — new hosts via BaseAdapter Protocol
5. **Transport abstraction** — Phase 2 adds Streamable HTTP for remote MCP
6. **Sandbox verification seam** — `rkp verify` stub exists; Phase 2 implements containerized runner
7. **Temporal coupling / hotspot seam** — `git/coupling.py`, `hotspots.py` are Phase 3 placeholders
8. **CI outcome ingestion seam** — Phase 2 adds CI results (pass/fail/flaky) beyond config parsing

## Appendix E: Verified API Patterns

### tree-sitter v0.25+ (QueryCursor API)
```python
from tree_sitter import Query, QueryCursor
from tree_sitter_language_pack import get_language, get_parser

language = get_language("python")
parser = get_parser("python")
tree = parser.parse(source_bytes)
query = Query(language, '(function_definition name: (identifier) @func_name)')
cursor = QueryCursor(query)
captures = cursor.captures(tree.root_node)  # dict[str, list[Node]]
```

### FastMCP v3.1 (lifespan + tools + testing)
```python
from fastmcp import FastMCP, Client, Context
from fastmcp.server.lifespan import lifespan

@lifespan
async def app_lifespan(server):
    db = open_database()
    try:
        yield {"db": db}
    finally:
        db.close()

mcp = FastMCP("rkp", lifespan=app_lifespan)

@mcp.tool(annotations={"readOnlyHint": True})
def get_conventions(ctx: Context, path_or_symbol: str) -> dict:
    db = ctx.lifespan_context["db"]
    ...

# Testing (in-memory, no subprocess):
async def test_tool(server: FastMCP):
    async with Client(server) as client:  # MUST be in test body, NOT fixture
        result = await client.call_tool("get_conventions", {"path_or_symbol": "src/"})
```

### Typer v0.24 (composition root)
```python
import typer
from dataclasses import dataclass

app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)

@dataclass
class AppState:
    db: Database
    git: GitBackend

@app.callback()
def main(ctx: typer.Context, repo: str = typer.Option(".", envvar="RKP_REPO")):
    ctx.obj = AppState(db=open_db(repo), git=CliGitBackend(repo))
```
