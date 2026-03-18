# Repo Knowledge Plane — Deep Build Research (Codex 5.3)

_Date: March 18, 2026_

## 0) Scope and method

This research is a build-focused technical blueprint for implementing `docs/prd.md` with minimum rework risk.

Method used:
- Grounded on the current PRD (`v4.0`, dated March 18, 2026) and existing internal research.
- Cross-checked against current primary docs for MCP, Codex, Copilot coding agent, Claude Code, SQLite, tree-sitter, uv, pygit2, and MCP SDKs.
- Emphasis on choices that improve correctness, portability, operational safety, and iteration speed.

This document is intentionally opinionated so downstream planning can be specific and executable.

## 1) Executive recommendations

### 1.1 Keep / change / cut summary

Keep:
- Local-first architecture and workstation-first MVP.
- Canonical claim model with provenance, review state, source authority, applicability, and sensitivity.
- Thin-by-default projection strategy.
- Tools-first MCP surface.
- Human review gate for writes.

Change:
- Treat Copilot coding agent as stronger than “beta export only”: it supports repo-level MCP tool integration now, but with hard constraints (tools-only, no resources/prompts, no remote OAuth MCP).
- Harden PRD around Copilot setup/environment realities (`copilot-setup-steps.yml` constraints, self-hosted runner implications, Windows firewall caveats).
- Add explicit package/license strategy for parser and git stack (pygit2 GPLv2 linking exception and tree-sitter language bundle supply-chain risk).
- Add a concrete storage lifecycle (WAL checkpoint policy, DB compaction, schema migration policy).

Cut or defer further:
- Any MVP dependency on resources/prompts in Copilot pathways (strictly tools for Copilot coding agent).
- Broad language parsing bundle at launch; use curated language parsers for Python + JS/TS only.
- Any assumption that hosted/remote agents will have equivalent MCP capabilities in Phase 1.

### 1.2 Recommended stack (March 2026)

- Runtime: Python 3.12+
- Packaging/distribution: `uv` + PyPI + `uvx repo-knowledge-plane`
- MCP layer: official MCP Python SDK (`mcp`, FastMCP high-level server)
- Parsing: tree-sitter core + curated grammar set (not full bundle by default)
- Git access: `pygit2` primary (fast path), with fallback mode strategy documented
- Graph algorithms: `rustworkx`
- Persistence: SQLite (WAL) + strict schema discipline + migration framework
- API/typing: Pydantic v2 + typed DTOs
- CLI UX: Typer + Rich
- Testing: pytest + property tests for extraction/conflict logic + fixture repos
- Quality harness: first-class subsystem, not “test folder only”

## 2) PRD delta analysis from current external docs

### 2.1 Copilot coding agent capability realities (important)

What current docs indicate:
- Copilot coding agent can use MCP **tools** from local and remote MCP servers.
- It does **not** support MCP resources or prompts.
- It does **not currently** support remote MCP servers that use OAuth.
- Tool use is autonomous (no per-call approval prompts once configured).

Implication:
- Your tools-first design is correct.
- For Copilot adapter design, resources/prompts should be treated as non-existent capability.
- Copilot MCP config must be tightly allowlisted (tool allowlist by default).

### 2.2 Copilot environment/setup constraints to encode

What docs indicate:
- Copilot environment customization is through `.github/workflows/copilot-setup-steps.yml`.
- Workflow must contain a single job named `copilot-setup-steps`.
- Only specific job settings are customizable; unsupported keys are ignored.
- `timeout-minutes` maximum is 59.
- Non-zero setup step exits do not fail the whole agent run; remaining setup steps are skipped.
- Self-hosted runners are supported, but integrated firewall compatibility constraints apply.
- Default environment is Ubuntu Linux; Windows is possible with caveats.

Implication:
- `rkp` projection for Copilot must validate to these constraints before writing files.
- P0 should include preflight validation rules for `copilot-setup-steps.yml` generation.

### 2.3 Codex capability realities to exploit

What official docs indicate:
- Codex supports stdio and Streamable HTTP MCP in CLI and IDE extension.
- Codex AGENTS discovery is layered with explicit precedence and default size limit (`project_doc_max_bytes`, default 32 KiB combined chain behavior in guidance docs).
- Codex supports repo-scoped `.codex/config.toml` (trusted projects), layered precedence, team config, rules, and skills.

Implication:
- Codex adapter should project more than `AGENTS.md`: include `.codex` team config patterns where useful.
- PRD should include explicit budgeting logic against Codex instruction size limits and directory-level override behavior.

### 2.4 MCP security and auth implications

What MCP docs indicate:
- Streamable HTTP is the current replacement for legacy HTTP+SSE pattern.
- HTTP transport auth guidance is OAuth-based; stdio auth should come from environment.
- Security guidance highlights SSRF, redirect validation, and network policy controls for MCP client/server integrations.

Implication:
- Your passive/local-first stance is correct.
- Add explicit SSRF/network policy hardening in Phase 2 remote mode requirements.
- For stdio-first MVP, keep auth simple (env + local process trust), but build interfaces that can enforce HTTP auth and allowlists later.

## 3) Product architecture recommendation

## 3.1 Architecture shape

Use a 4-plane architecture in one repo:

1. Extraction Plane
- Parsers for code/config/instruction files/CI workflows.
- Produces normalized evidence records.

2. Claim Plane
- Deterministic claim builders + conflict resolver + source authority ordering.
- Produces canonical claims with provenance and review metadata.

3. Projection Plane
- Host adapters (Codex, Claude, Copilot, Cursor, Windsurf).
- Pure function: `canonical_claims + adapter_caps + policy -> artifacts + warnings`.

4. Serving & Governance Plane
- MCP read tools.
- CLI review/apply/status/import/verify.
- Audit trail, drift detection, and freshness orchestration.

Reasoning:
- This cleanly isolates extraction bugs from projection bugs.
- Enables high-confidence adapter conformance tests.
- Makes “import existing files then reconcile” first-class rather than a side effect.

### 3.2 Data model boundaries

Keep three distinct stores:
- Evidence store (immutable-ish event/evidence records).
- Canonical claim state (current effective claim per claim_id + history).
- Projection artifacts state (expected rendered outputs + hash/signature for drift detection).

Avoid coupling:
- Do not recompute projection diffs by reparsing generated files.
- Keep projection snapshots in DB and compare to filesystem content hash.

## 4) Technical stack decisions and tradeoffs

### 4.1 Python + MCP SDK + uv

Why this is still best for MVP:
- MCP Python SDK is tier-1 and has complete primitives for tools/resources/prompts and transports.
- Python ecosystem is best fit for fast parser/eval iteration.
- `uv` and `uvx` provide fast install and no-global-env friction.

What to enforce:
- Lock Python minor version for production reproducibility.
- Ship reproducible lock strategy and pinned parser dependencies.
- Use `uv` workspace + explicit constraints file.

### 4.2 SQLite as local persistence

Why keep it:
- Excellent local-first distribution profile.
- WAL mode gives strong read/write concurrency for your pattern.
- Useful built-ins: JSON functions, FTS5, strict tables.

Required discipline:
- Define WAL checkpoint policy (automatic threshold + manual checkpoints during idle).
- Add DB health commands (`rkp doctor db`) and compaction operations.
- Schema migration policy with forward-only migrations and rollback rehearsal.

### 4.3 Parser strategy (tree-sitter)

Recommended:
- Keep tree-sitter core.
- For launch, do **curated grammars only** (Python, JS, TS + config grammars you need).
- Avoid full grammar mega-bundle in default install.

Why:
- Better supply-chain surface.
- Better reproducibility and faster parser update QA.
- Avoid license transitive surprises from broad language packs.

### 4.4 Git layer strategy

Use `pygit2` as performance path, but explicitly manage legal/runtime risk:
- `pygit2` is GPLv2 with linking exception; this may still trigger legal review concerns in some orgs.
- Keep a fallback git backend abstraction (e.g., shell/git CLI mode) for “no libgit2 native dep” environments.

Action:
- Add ADR early on licensing and binary distribution strategy.

### 4.5 Graph and traversal layer

Use `rustworkx` for core graph operations.

Guidance:
- Keep graph model minimal in P0 (module/package and import edges only).
- Do not over-model semantics before Phase 2 enrichment.
- Build traversal utility functions with strict complexity budgets and memoization.

## 5) Host adapter strategy (capabilities-driven)

Adapter contract:
- Each adapter defines supported primitives: `always_on`, `scoped_rules`, `skills`, `env`, `permissions`, `mcp_tools`, `mcp_resources`, `mcp_prompts`, `size_constraints`, `auth_constraints`.

Projection engine contract:
- Input: canonical claims + task context + adapter capability descriptor.
- Output: artifact set + excluded-claim report + overflow report + security warnings.

### 5.1 Codex adapter

Support in P0:
- `AGENTS.md` root + nested overrides.
- Optional `.codex/config.toml` templating assistance.
- Skill projection to `.agents/skills`.

Rules:
- Hard byte budgeting and truncation diagnostics.
- Prefer nearest-directory guidance for specialized rules.

### 5.2 Claude adapter

Support in P0:
- `CLAUDE.md` and `.claude` surfaces, including settings guidance and skills mapping.

Rules:
- Keep always-on concise.
- Push procedural detail to skills/playbooks.

### 5.3 Copilot adapter

Support in P0:
- `copilot-instructions.md`, `.instructions.md`, `copilot-setup-steps.yml`, MCP tool config.

Rules:
- Do not rely on resources/prompts for coding agent flows.
- Strong allowlist generation for MCP tools.
- Pre-validate setup workflow constraints (job name, keys, timeouts).

### 5.4 Cursor/Windsurf adapters

Support in P0:
- Export-focused, with conformance tests gated before claiming parity.

Rules:
- Keep explicit “alpha/export” messaging in CLI status and docs.
- Degrade gracefully when capability unknown or unstable.

## 6) Core product flows: exact behavior recommendations

### 6.1 `rkp init`

Recommended flow:
1. Scan support envelope and report unsupported segments first.
2. Build evidence index.
3. Generate draft claims with uncertainty flags.
4. Generate host previews.
5. Present unified review queue sorted by impact/risk.
6. Require explicit apply per artifact group.

Critical UX details:
- Diff-first review, never full-file wall-of-text first.
- Every claim shows “why surfaced now” and source authority.
- Claim edits must preserve provenance chain.

### 6.2 `rkp import`

Recommended flow:
1. Parse existing instruction/config/skills files as declared claims.
2. Run extraction in parallel.
3. Auto-cluster conflicts by scope and severity.
4. Require resolve action (`adopt`, `suppress`, `mark-needs-declaration`).

### 6.3 `rkp status`

Required sections:
- Index health and staleness triggers.
- Drift summary by artifact.
- Confidence and correction trends.
- Support envelope coverage and parser failure map.

### 6.4 `rkp verify` (opt-in active execution)

Minimum controls:
- Category-level opt-in + per-command escalation for higher risk classes.
- Sandboxed worktree/container only.
- Default deny for network and secrets.
- Time/resource limits.
- Structured execution evidence persisted per run.

## 7) Quality, testability, and robustness blueprint

### 7.1 Testing architecture

Layered tests:
- Unit: extractors, authority/precedence, projection filters, conflict resolver.
- Contract: MCP tool schemas and response invariants.
- Fixture integration: known repos with expected claims/projections.
- Adapter conformance: canonical model -> host artifact snapshot tests.
- Safety tests: leakage tests for sensitivity filtering.
- Drift tests: detect/absorb/reject paths.

### 7.2 Quality harness should be first-class package

Implement as `rkp_quality` subsystem with:
- Standardized fixture schema.
- Deterministic evaluation runner.
- Versioned scorecards over time.
- CI gating rules (block regressions above thresholds).

### 7.3 Reliability/SLOs

Recommended P0 SLOs:
- Warm query p50 < 500ms for top tools.
- Incremental refresh p95 < 3s for single-file change.
- Init success on envelope repos > 95%.
- Projection conformance for GA adapters > 95%.

## 8) Security and trust model hardening

### 8.1 Threat model to implement early

Threat classes:
- Instruction poisoning from untrusted files.
- MCP tool overreach/exfiltration.
- Secrets leakage in projected artifacts.
- Active verification command abuse.
- Remote MCP SSRF/token abuse in future phases.

### 8.2 Required controls in MVP

- Source allowlists for claim-generating inputs.
- Sensitivity labels enforced during projection.
- Secrets/path deny patterns by default.
- Read-only MCP tools by default for your own server.
- Explicit audit logs for all human overrides and apply actions.

### 8.3 Required controls for Phase 2 remote mode

- OAuth/token audience validation.
- Outbound request allowlists and SSRF protections.
- Redirect validation and metadata endpoint blocking.
- Per-tenant encryption and isolation model.

## 9) Documentation and project management system

### 9.1 Documentation architecture (recommended)

Create five doc tracks:
- Product: PRD, roadmap, milestones.
- Architecture: system overview, data model, boundaries, ADRs.
- Operations: install, upgrade, backup/restore, incident runbooks.
- Integrations: per-host adapter docs and known limitations.
- Contributor docs: dev setup, testing, quality harness, release process.

### 9.2 Required docs for first production candidate

- `docs/architecture.md` (missing; should be authoritative).
- `docs/decisions.md` or ADR directory with real decisions (currently absent).
- `docs/security.md` with threat model + controls + boundaries.
- `docs/evaluation.md` with quality harness methodology.

### 9.3 Feature management model

Use explicit lifecycle states:
- `experimental`
- `beta`
- `ga`
- `deprecated`

Each feature must declare:
- Owner
- Exit criteria
- Observability hooks
- Rollback plan

## 10) Deployment, distribution, and upgrade strategy

### 10.1 Local distribution (Phase 1)

Primary:
- Publish to PyPI.
- Install/run via `uvx repo-knowledge-plane`.

Secondary:
- `pipx` support.
- Homebrew formula only after cross-platform maturity.

### 10.2 Upgrade model

- Semantic versioning with strict migration docs.
- `rkp upgrade --dry-run` to detect schema/projection breaking changes.
- Keep projected file headers with generating version for drift/migration checks.

### 10.3 Enterprise path (Phase 2+)

- Managed Streamable HTTP deployment.
- Tenant-aware auth and policy controls.
- Keep local-first mode as permanent product path (not “legacy mode”).

## 11) UX and value maximization recommendations

### 11.1 UX principles

- Explainability before automation.
- Diffs before full rewrites.
- Progressive disclosure by default.
- Warn loudly on unsupported scopes rather than hiding uncertainty.

### 11.2 Value loops to instrument

- “Agent asked fewer environment/setup questions” loop.
- “Fewer review corrections due to missing repo conventions” loop.
- “Import + reconcile reduced instruction drift maintenance” loop.

### 11.3 Anti-patterns to avoid

- Bloated always-on context files.
- Silent overwrite behavior.
- Confidence inflation on inferred claims.
- Adapter parity claims without conformance evidence.

## 12) Unknown-unknowns and proactive discovery program

Run these as explicit research tracks in parallel with build:

1. Host behavior drift tracking
- Weekly adapter smoke tests against latest host versions.
- Snapshot capability matrix updates.

2. Parser correctness drift
- Nightly fixture replay across representative repos.
- Alert on extraction precision drops.

3. Supply-chain and license drift
- Dependency/license scanning at release boundaries.
- Policy check before adding new language grammars.

4. Context-effect regressions
- Track token/runtime overhead by adapter + task type.
- Regression gate for context bloat.

5. Security red-team path
- Prompt-injection and MCP overreach simulations quarterly.
- Verification sandbox escape tests.

## 13) Phased implementation blueprint

### Phase A (0-6 weeks): “Correct substrate”

Deliver:
- Canonical claim schema + precedence engine + persistence model.
- Extractors for commands/prereqs/conventions in launch envelope.
- Projection engine skeleton with Codex + Claude adapters.
- Review/apply/drift loop end-to-end.

Exit criteria:
- End-to-end on 3 internal repos with deterministic outputs.

### Phase B (6-12 weeks): “Trustable adapters”

Deliver:
- Copilot adapter with setup workflow validator and MCP tool allowlist generation.
- Import flow for AGENTS/CLAUDE/Copilot instruction surfaces.
- Quality harness v1 and fixture packs.

Exit criteria:
- Adapter conformance >= target.
- Safety leakage tests passing.

### Phase C (12-20 weeks): “Operational confidence”

Deliver:
- Active verification opt-in path.
- Extended conflict UX and declaration prompts.
- Operational docs and upgrade tooling.

Exit criteria:
- Design partner cohorts can run full bootstrap->review->apply->refresh cycle reliably.

## 14) High-risk items and mitigations

1. Risk: Licensing friction around pygit2/libgit2 in enterprise procurement.
- Mitigation: ADR + legal review + fallback backend option.

2. Risk: Grammar bundle supply-chain bloat and maintenance burden.
- Mitigation: Curated parsers in launch; opt-in grammar packs.

3. Risk: Copilot adapter behavior divergence from assumptions.
- Mitigation: Markdown API scraping tests + weekly capability validation.

4. Risk: Over-context harms agent quality.
- Mitigation: hard context budgets + applicability filtering + measurement in CI.

5. Risk: Drift between canonical model and projected files.
- Mitigation: hash-signature tracking + drift command + mandatory reconciliation paths.

## 15) Concrete PRD edits to make now

1. Update Host Capability Matrix notes:
- For Copilot coding agent: explicit “tools-only; no resources/prompts; no remote OAuth MCP.”

2. Expand Copilot section in P0:
- Add `copilot-setup-steps.yml` constraints and validation requirements.

3. Add licensing and supply-chain constraint section:
- `pygit2` license considerations.
- Tree-sitter grammar curation strategy.

4. Add storage operations section:
- WAL checkpoint policy and DB maintenance commands.

5. Add adapter conformance release gate:
- No GA promotion without conformance + drift + leakage tests.

6. Add explicit unknown-unknown program section:
- Host drift, parser drift, security red-team, context-regression monitoring.

## 16) Suggested planning outputs to generate next

From this research, planning should produce these files:

- `.plans/phase-a-implementation-plan.md`
- `.plans/adapter-conformance-plan.md`
- `.plans/quality-harness-spec.md`
- `.plans/security-threat-model.md`
- `.plans/data-model-adr-set.md`

Each should include owners, milestones, dependencies, and objective exit criteria.

## 17) Source index

Primary sources used for this research:

1. PRD and local project docs
- `docs/prd.md`
- `docs/research.md`

2. MCP specification and docs
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- https://modelcontextprotocol.io/specification/2025-11-25/server/resources
- https://modelcontextprotocol.io/specification/2025-11-25/server/prompts
- https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- https://modelcontextprotocol.io/docs/sdk

3. OpenAI Codex official docs
- https://developers.openai.com/codex/guides/agents-md/
- https://developers.openai.com/codex/concepts/customization/
- https://developers.openai.com/codex/mcp
- https://developers.openai.com/codex/config-basic#configuration-precedence
- https://developers.openai.com/codex/enterprise/admin-setup#step-4-standardize-local-configuration-with-team-config
- https://developers.openai.com/codex/rules/#create-a-rules-file
- https://developers.openai.com/codex/skills/#where-to-save-skills
- https://developers.openai.com/codex/integrations/github/#customize-what-codex-reviews

4. GitHub Copilot coding agent docs
- https://docs.github.com/en/copilot/concepts/agents/coding-agent/mcp-and-coding-agent
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment
- https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/use-the-github-mcp-server
- GitHub docs markdown API endpoints used for precise extraction:
  - `https://docs.github.com/api/article/body?pathname=/en/copilot/concepts/agents/coding-agent/mcp-and-coding-agent`
  - `https://docs.github.com/api/article/body?pathname=/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment`
  - `https://docs.github.com/api/article/body?pathname=/en/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp`

5. Anthropic Claude Code docs
- https://docs.anthropic.com/en/docs/claude-code/mcp
- https://docs.anthropic.com/en/docs/claude-code/settings
- https://docs.anthropic.com/en/docs/claude-code/memory

6. Core technical stack docs
- uv docs: https://docs.astral.sh/uv/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- tree-sitter docs: https://tree-sitter.github.io/tree-sitter/
- tree-sitter-language-pack: https://pypi.org/project/tree-sitter-language-pack/
- pygit2 docs: https://www.pygit2.org/
- rustworkx: https://pypi.org/project/rustworkx/
- SQLite docs: https://sqlite.org/docs.html
- SQLite WAL: https://sqlite.org/wal.html

## 18) Confidence notes

- High confidence: MCP transport/auth constraints, Codex layering/config behavior, Copilot coding agent constraints, SQLite/uv/tree-sitter fundamentals.
- Medium confidence: Cursor/Windsurf parity details due weaker documentation accessibility in this pass; keep alpha/export posture until adapter conformance confirms behavior.
- Medium confidence: Enterprise legal acceptance of pygit2; requires legal/procurement confirmation per target design partners.

