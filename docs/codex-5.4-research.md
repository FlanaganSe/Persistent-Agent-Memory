# Repo Knowledge Plane — Deep Build Research (Codex 5.4)

_Date: March 18, 2026_

## 0. Scope and method

This document is a build-focused research pass for implementing the product described in `docs/prd.md` with minimum rework risk.

Method:
- Read the current PRD in full and cross-checked it against the existing repo research.
- Verified current agent-host and MCP capabilities against primary sources as of March 18, 2026.
- Focused on decisions that materially affect correctness, portability, UX trust, install friction, and long-term maintainability.
- Optimized for a product that can be planned and built precisely, not for a vague strategic narrative.

Primary conclusion:

> The product should be built as a local-first, evidence-backed operational contract engine for repositories, with a strict claim model, thin host projections, and a first-class quality harness. The MVP should deliberately avoid heavy native dependencies, broad parser bundles, cloud-first assumptions, and speculative intelligence layers that cannot yet be measured.

This document is intentionally opinionated. Where the PRD is directionally right but implementation-risky, this document recommends narrower, safer choices.

---

## 1. Executive answer

## 1.1 What the product should actually become

The highest-value version of Repo Knowledge Plane is not “a smart repo graph” and not “a better instruction generator.”

It is:
- A governed evidence pipeline that turns repo reality into explicit claims.
- A reviewable operational contract for humans and agents.
- A projection engine that adapts that contract to each host’s real configuration surface.
- A local intelligence service that remains useful even when hosts, models, and agent UX change.

If it does those four things well, it becomes infrastructure.
If it tries to do too much too early, it becomes a brittle meta-tool that users stop trusting after the first few wrong high-confidence claims.

## 1.2 The main product decisions to lock now

Keep:
- Local-first architecture.
- Workstation-agent-first launch.
- Canonical claim model with provenance, review state, source authority, applicability, freshness, and sensitivity.
- Tools-first MCP surface.
- Human review before writing any instruction artifact.
- Thin-by-default projection strategy.

Change:
- Use the official Python MCP SDK as the protocol foundation. Treat FastMCP as optional convenience, not as architectural bedrock.
- Do not make `pygit2` the MVP git backend. Use the Git CLI as the default backend behind an abstraction layer.
- Do not make `rustworkx` a required MVP dependency. Start with SQLite-backed graph edges and small in-memory traversals.
- Do not ship the full `tree-sitter-language-pack` as the default parser strategy. Use curated grammars plus specialized config extractors.
- Treat Copilot as a real adapter target, but still not parity-level with Codex and Claude because its MCP surface is tools-only and more constrained.
- Treat generated host artifacts as managed outputs with import-and-review migration, not as files to blindly overwrite.

Defer:
- Vector search.
- Semantic call-graph claims.
- Remote multi-tenant deployment.
- Regression risk scoring that implies predictive validity before outcome data exists.
- “Universal host parity.” The market is moving too fast for that promise to be honest.

Cut from MVP expectations:
- Any implication that tree-sitter alone provides deep architecture truth.
- Any assumption that more extracted context is automatically better for agent outcomes.
- Any plan that depends on active verification before users already get value from passive analysis.

## 1.3 The build thesis in one sentence

Build a deterministic, reviewable claim engine first; everything else should be an adapter, projection, or enrichment around it.

---

## 2. PRD stress test

## 2.1 What the PRD gets right

The PRD is strong on the parts that matter most:
- It identifies the correct wedge: evidence-backed extraction plus reviewed operational contract plus relevance-aware projection.
- It treats provenance as part of the product, not implementation detail.
- It is correct that “cross-agent” means adapting to different host surfaces rather than pretending they are interchangeable.
- It is correct that tools-first MCP design is the compatibility floor.
- It is correct that passive analysis should come before active verification.
- It is correct that a quality harness must ship with the product.

Those are the right anchor decisions. They should survive.

## 2.2 Where the PRD is still too optimistic or too broad

### Stack optimism

The PRD stack is plausible, but two choices increase install and legal risk for limited MVP benefit:
- `pygit2`
- `rustworkx`

A third choice is too broad by default:
- `tree-sitter-language-pack`

A fourth choice is slightly mispositioned:
- FastMCP should not be treated as the core protocol dependency when the official MCP Python SDK exists.

### Host parity optimism

The PRD is careful overall, but the adapter framing can still imply more symmetry than exists.

Reality in March 2026:
- Codex has strong instruction layering, project config, skills, and MCP support.
- Claude Code has strong repo memory, settings, hooks, subagents, and MCP support.
- Copilot’s coding-agent surface is meaningful, but it is more constrained and different in important ways.
- Cursor and Windsurf are worth exporting to, but they should not drive the core model.

The internal model should be capability-driven, not host-averaged.

### Architecture ambition risk

The PRD is trying to serve three futures at once:
- local repo operating contract
- richer architecture and coupling intelligence
- future cloud or remote serving

That is acceptable only if the architecture isolates these futures cleanly. If not, the team will accidentally build Phase 2 concerns into Phase 1, increasing complexity before trust is earned.

## 2.3 What should be changed in the PRD now

Recommended changes to `docs/prd.md`:

1. Replace “FastMCP (Python MCP SDK)” with “official MCP Python SDK; FastMCP optional wrapper if justified.”
2. Replace “tree-sitter + tree-sitter-language-pack” with “tree-sitter core + curated grammars, plus specialized parsers for config and docs.”
3. Replace “pygit2” with “Git CLI backend by default; optional libgit2 backend later behind abstraction.”
4. Replace “rustworkx” with “SQLite edge store first; optional graph accelerator after profiling.”
5. Strengthen Copilot notes: tools-only MCP, constrained setup surface, lower parity.
6. Add explicit artifact-ownership modes: imported human-owned, managed-by-RKP, and mixed review migration.
7. Add explicit parser, licensing, and host-drift risk entries.
8. Add documentation and release-management requirements, not just technical acceptance criteria.

## 2.4 What should be removed from implied MVP scope

These items are not impossible. They are simply premature for the first serious buildout:
- Broad language support beyond the launch envelope.
- Deep semantic architecture inference.
- Universal remote-host support.
- Predictive risk scores presented as trustworthy before outcome loops exist.
- Full adapter conformance for fast-moving alpha surfaces.

---

## 3. Product strategy: where the real value comes from

## 3.1 The actual user value hierarchy

The product’s value will not come from “knowing more facts about the repo.”

It will come from reducing four kinds of failure:
- Wrong commands.
- Wrong assumptions about prerequisites and environment.
- Wrong assumptions about path-specific conventions and boundaries.
- Wrong host-specific projection of guidance.

Those are the failures that waste agent time, cause review friction, and destroy trust.

Everything else should be subordinate to that.

## 3.2 The best MVP wedge

The correct MVP wedge is:

> turn implicit repo operations into explicit, evidence-backed, host-appropriate working rules.

In practice that means:
- build, test, lint, and validation commands
- runtime and tool prerequisites
- path-scoped conventions that matter for correctness
- coarse module boundaries and test locations
- dangerous-operation guardrails
- faithful projection into Codex, Claude Code, and Copilot surfaces

This is more valuable than a generic “repo overview” because:
- agents already read code and docs badly but passably
- agents fail much more often on repo-specific operating constraints
- users will notice immediately when commands, prerequisites, and path rules are right

## 3.3 What users will pay for

Users will pay when the product:
- prevents wasted agent loops
- reduces manual instruction maintenance
- decreases incorrect or noisy generated guidance
- survives across tools and model changes
- gives tech leads a trustworthy review surface instead of a black box

Users will not pay for a fancier internal graph if it does not change these outcomes.

## 3.4 Product principle: optimize for trust before breadth

Every part of the product should honor one rule:

> a smaller number of correct, explicit, evidence-backed claims is more valuable than a larger number of plausible claims.

Operationally that means:
- default to “unsupported” over weak confidence
- default to “available on demand” over “always-on”
- default to “human review required” over silent mutation
- default to “show the evidence” over “just trust the model”

---

## 4. Recommended system architecture

## 4.1 Architecture shape

Use a five-plane architecture.

1. Discovery plane
- Repository walk, file classification, repo capabilities, support-envelope detection.
- No interpretation beyond what exists and what type it is.

2. Evidence plane
- Deterministic extractors that turn artifacts into evidence records.
- Examples: CI workflow extractor, command extractor, instruction importer, code convention miner, module-edge extractor.

3. Claim plane
- Builds canonical claims from evidence.
- Resolves conflicts.
- Assigns scope, applicability, freshness, confidence, review state, and source authority.

4. Projection plane
- Pure rendering from canonical claims into host-specific artifacts or previews.
- Includes overflow handling, capability filtering, and thin-content budgeting.

5. Serving and governance plane
- MCP tools.
- CLI review/apply/status/import/doctor operations.
- Drift detection, audit trail, local trace capture, and migration support.

This structure matters because it prevents the most expensive future bug class: mixing “we observed X” with “we concluded Y” and “we rendered Z” in the same implementation path.

## 4.2 One-way data discipline

Enforce this rule in code:
- extractors create evidence
- claim builders create claims
- adapters render projections
- writers apply reviewed artifacts

No extractor should directly write host artifacts.
No adapter should invent claims.
No CLI apply step should reinterpret evidence.

That one-way discipline is what keeps the system testable.

## 4.3 Suggested package layout

Recommended initial structure:

```text
src/repo_knowledge_plane/
  app/
    services/
    dto/
    errors.py
  cli/
    main.py
    commands/
  mcp/
    server.py
    tools/
  domain/
    evidence/
    claims/
    projection/
    review/
    capabilities/
  extractors/
    code/
    config/
    ci/
    instructions/
    commands/
  adapters/
    codex/
    claude/
    copilot/
    cursor/
    windsurf/
  storage/
    migrations/
    repositories/
    sqlite/
  git/
    backend.py
    cli_backend.py
  parsing/
    treesitter/
    yaml/
    markdown/
  evals/
    fixtures/
    harness/
    golden/
  observability/
  support/
```

Guiding rule:
- `domain/` should be nearly pure Python with minimal side effects.
- `extractors/`, `storage/`, `git/`, and `adapters/` are side-effect boundaries.

## 4.4 Internal API boundaries

Use explicit service interfaces for:
- repo scan and indexing
- evidence retrieval
- claim synthesis and merge
- projection rendering
- review queue generation
- artifact application
- drift detection
- support-envelope checks

The CLI and MCP server should call the same application services.
If those code paths diverge, the product will fork into two partially compatible systems.

---

## 5. Data model and storage design

## 5.1 Storage recommendation

Use SQLite in WAL mode as the canonical local store.

Reasons:
- excellent distribution profile for local-first software
- enough power for the MVP query profile
- good support for JSON, FTS5, strict tables, and recursive CTEs
- debuggable and inspectable for users and developers
- lower operational surface than a standalone graph or document database

This remains the correct storage choice.

## 5.2 Storage discipline

Use SQLite deliberately, not casually.

Required practices:
- WAL mode enabled by default.
- `STRICT` tables where possible.
- forward-only schema migrations
- schema version recorded in the DB and in trace output
- deterministic migration tests from empty DB and prior-version fixtures
- periodic checkpoint and compaction commands
- database health checks in `rkp doctor`

Recommended commands:
- `rkp doctor db`
- `rkp maintenance checkpoint`
- `rkp maintenance vacuum`
- `rkp maintenance integrity-check`

## 5.3 Recommended table families

Suggested table groups:

Repository state:
- `repo_identity`
- `repo_snapshot`
- `path_inventory`
- `scan_run`

Evidence:
- `evidence_item`
- `evidence_locator`
- `evidence_relationship`
- `extractor_run`

Claims:
- `claim`
- `claim_revision`
- `claim_evidence_link`
- `claim_status`
- `claim_tombstone`

Projection:
- `projection_target`
- `projection_preview`
- `projection_artifact`
- `projection_overflow`
- `artifact_drift_event`

Review and audit:
- `review_action`
- `override_record`
- `import_event`
- `freshness_event`

Query and evaluation:
- `tool_query_trace`
- `tool_response_trace`
- `fixture_expectation`
- `eval_run`

Graphs and module edges:
- `module_node`
- `module_edge`
- `path_scope`

## 5.4 Stable identity design

This is one of the easiest places to make a future-breaking mistake.

Claims need stable logical identities that survive evidence churn.

A claim ID should not be based only on file position.
A claim ID should be derived from:
- repo identity
- claim kind
- logical scope
- subject
- normalized predicate
- normalized value identity

Examples:
- `command:test:repo-root:pytest-default`
- `prereq:python:path:services/api:python-3.12`
- `convention:naming:path:src/foo:test-files-use-test_prefix`

If this identity model is sloppy, review state and overrides will become unusable.

## 5.5 Why not a graph database yet

Do not introduce Neo4j, JanusGraph, or a custom graph store in the MVP.

The actual P0 graph need is modest:
- module nodes
- import or dependency edges
- path relationships
- maybe a few ownership or test edges

SQLite plus recursive queries is enough.
The product does not need graph-database complexity before it has proven query patterns that justify it.

## 5.6 Search strategy

Use FTS5 for:
- notes
- evidence snippets
- doc fragments
- claim explanations

Do not add vector search in P0.
The product’s early value is structural and operational, not semantic similarity retrieval.

---

## 6. Parsing and extraction strategy

## 6.1 The parser strategy should be mixed, not monolithic

The product should not try to solve all extraction with one parser family.

Use three extractor classes:
- code extractors
- config extractors
- instruction/document extractors

That is cleaner, more accurate, and easier to test.

## 6.2 Code extraction

Recommended approach:
- tree-sitter core
- curated grammars only for launch-supported languages
- small wrapper layer that normalizes AST traversal outputs

Launch grammar set should be narrow:
- Python
- JavaScript
- TypeScript
- TSX if needed
- YAML and Markdown only if line-precise evidence from tree-sitter is materially better than specialized parsers

Do not default to the full `tree-sitter-language-pack` bundle.

Why:
- 170+ grammar bundling increases supply-chain surface and update churn.
- It encourages fake support breadth.
- It weakens the clarity of the support envelope.
- It creates more test burden than product value in P0.

Better pattern:
- ship curated default grammars
- make broader grammar support an optional extra later

## 6.3 Config extraction

Use specialized parsers for structured configuration.

Examples:
- `tomllib` for TOML
- a YAML parser with location support for CI and config evidence
- JSON parser for manifests
- line-oriented parser for `.env.example` style files if explicitly allowed in future
- dedicated parsing for `Dockerfile`, `Makefile`, `package.json`, `pyproject.toml`, `uv.lock`, `pnpm-workspace.yaml`, GitHub Actions workflows

This is better than trying to use tree-sitter for everything.

## 6.4 Instruction and documentation extraction

Use a Markdown-aware extractor for:
- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/` material that has operational relevance

Important rule:
- not all documentation should become claims

Only extract claims when the material is:
- operational
- repo-specific
- plausibly still current
- specific enough to guide work

Ignore or heavily down-rank:
- generic repository overview prose
- stale templates
- aspirational docs with no supporting evidence
- duplicated content across files

## 6.5 Convention extraction should prefer enforced rules over inferred style

This is a major product-quality issue.

The system should not spend trust budget on low-value style trivia when linters and formatters already enforce it.

Preferred convention hierarchy:
1. enforced by config or tooling
2. declared by checked-in instruction or policy file
3. strongly repeated across code samples
4. weakly inferred from examples

This means:
- if `ruff format` or Prettier clearly owns formatting, do not generate verbose style instructions
- if naming or test-location patterns are clearly enforced, summarize them tersely
- use always-on files for non-inferable conventions, not for restating toolchain defaults

## 6.6 Command extraction strategy

Command extraction should come from multiple evidence types:
- CI workflows
- task runners (`Makefile`, `justfile`, `package.json`, `pyproject.toml`, `noxfile.py`, `tox.ini`)
- existing instruction files
- docs with explicit command blocks
- optional user overrides

Evidence scoring should favor:
- commands executed in CI
- commands in canonical tool manifests
- commands declared in human-reviewed repo policy

Weak evidence:
- prose docs without corroboration
- shell snippets in issue templates or blog-like docs

## 6.7 Module and boundary extraction

Be honest about what “module boundary” means in P0.

P0 can reliably return:
- top-level packages or services
- import-based coarse dependencies
- likely test locations
- path boundaries from manifests and repo structure

P0 cannot honestly promise:
- semantically complete call graphs
- runtime dependency guarantees
- accurate architecture-layer intent without human or doc evidence

If the product is honest here, users will trust it more.

---

## 7. Git and repo-state strategy

## 7.1 Default backend recommendation: Git CLI

Use the Git CLI as the default MVP backend.

Why this is the better March 2026 choice:
- Git is already a real dependency in every target repo environment.
- It avoids native library and binary-distribution complexity.
- It reduces legal review friction versus `pygit2`.
- It is easier to reason about in support and debugging.
- It preserves the `uvx` adoption story better than introducing `libgit2` concerns early.

`pygit2` is not a bad library. It is simply not the best default dependency for a zero-friction local-first MVP.

## 7.2 Backend abstraction

Define a git backend interface now.

Required operations:
- get repo root
- get HEAD and branch identity
- list tracked files
- compute file hashes and diff status
- get file history summary
- read blame or change frequency if needed later
- create clean worktree for future active verification

This preserves the option to add:
- `pygit2` accelerator backend
- JGit backend someday if needed
- cached history miner

## 7.3 History-mining should stay light in Phase 1

Do not let history mining contaminate the MVP.

Phase 1 git use should primarily support:
- current repo identity
- branch/head provenance
- drift and freshness triggers
- optional simple change-frequency heuristics where cheap

Temporal coupling and hotspot analytics belong later, once the system’s current-state contract is trusted.

---

## 8. Graph and dependency strategy

## 8.1 Avoid mandatory graph-specialist dependencies in MVP

The PRD currently proposes `rustworkx`.

Recommendation:
- do not make it required in P0
- store graph edges in SQLite
- materialize small in-memory adjacency maps when needed
- profile real workloads before adding a compiled graph dependency

This is the right tradeoff because the P0 graph workload is not heavy enough to justify the extra install and maintenance surface.

## 8.2 What the graph actually needs to do in P0

P0 graph responsibilities:
- answer coarse dependency questions
- map paths to modules
- map modules to likely test directories
- support “what else is nearby or connected” for review and instruction projection

That is not a large-scale graph-computation problem.
It is a structured lookup problem.

## 8.3 Design the seam now for future enrichment

Even though P0 graph needs are modest, design the interfaces so Phase 2 can add:
- semantic edges from LSP or SCIP
- temporal co-change edges
- ownership and incident edges
- risk propagation traversals

Design the seam now, not the implementation now.

---

## 9. MCP server and protocol strategy

## 9.1 Protocol foundation

Use the official Python MCP SDK as the primary implementation substrate.

Why:
- it is the canonical protocol implementation path
- it reduces abstraction mismatch risk as the protocol evolves
- it gives cleaner control over tools, resources, prompts, and transport behavior
- it reduces dependence on convenience wrappers when exact protocol behavior matters

FastMCP can still be used if it materially speeds delivery, but it should remain an internal convenience choice, not the architectural source of truth.

## 9.2 Transport strategy

P0:
- stdio MCP only

Phase 2:
- add Streamable HTTP only when there is concrete remote demand

This remains the right sequence.

Important related decision:
- do not build a parallel REST API unless a real non-MCP consumer exists

The application service layer should be transport-agnostic.
The wire surface should stay small.

## 9.3 Tool design principles

Each tool response should include:
- `status`
- `supported` or `unsupported_reason`
- `data`
- `warnings`
- `provenance`
- `freshness`
- `review_state`

The tool surface should be narrow and boring.
That is a good thing.

## 9.4 Recommended tool additions

The PRD tool set is close, but two supporting tools would materially help trust and debugging:
- `explain_claim` or `get_claim_details`
- `doctor_support_envelope`

Why:
- users need to see why a claim exists and what evidence backs it
- users need to know early when the repo falls outside support assumptions

## 9.5 Response-size strategy

Host context windows and MCP tool surfaces still punish oversized responses.

Every tool should support:
- path scoping
- pagination or bounded result counts
- optional terse mode vs detailed mode
- optional inclusion of evidence snippets

Do not assume that because a tool call is “on demand,” bigger is better.

---

## 10. Host adapter strategy

## 10.1 Adapter philosophy

Adapters should be treated like product surfaces, not file writers.

Each adapter needs:
- a capability descriptor
- explicit projection rules
- overflow policy
- trust and warning policy
- conformance tests
- import behavior
- drift-detection logic

The core model should never be distorted to fit the weakest host.

## 10.2 Codex adapter

As of March 18, 2026, Codex provides one of the strongest target surfaces for this product.

Use in P0:
- root `AGENTS.md`
- nested `AGENTS.override.md` behavior or equivalent nearest guidance logic where appropriate
- `.agents/skills` for procedural workflows
- optional project `.codex/config.toml` projection help for MCP and policy setup

Important design implications from current Codex docs:
- keep always-on guidance small
- rely on layered locality
- move heavy procedures into skills
- account for project-doc byte limits and precedence behavior

This adapter should be GA in P0.

## 10.3 Claude Code adapter

Claude Code is also a strong P0 target.

Use in P0:
- `CLAUDE.md`
- path-scoped rule support where applicable
- skills or procedural guide projection
- settings-related guidance for permissions and behavior
- future-compatible mapping for hooks or subagents only when truly justified

Important implication:
- do not over-project to hooks or subagents early
- keep the first adapter focused on stable, high-value surfaces

This adapter should also be GA in P0.

## 10.4 Copilot adapter

Copilot matters, but it should not force the MVP architecture.

As of March 18, 2026, current GitHub docs indicate support for:
- repository instructions
- path-scoped instruction files
- skills
- coding-agent environment setup steps
- MCP integration for coding-agent workflows

But it remains meaningfully different:
- the surface is more constrained
- the setup environment is opinionated
- the MCP story is not parity with the stronger local-agent hosts

Design implications:
- tools-first is mandatory here
- do not rely on resources/prompts for core Copilot value
- validate setup-file generation before writing it
- keep adapter maturity below Codex and Claude until conformance coverage is proven

Recommendation:
- keep Copilot as Beta in P0
- support preview and reviewed projection
- test it aggressively, but do not let it reshape the canonical model

## 10.5 Cursor and Windsurf adapters

Cursor and Windsurf are worth supporting as export targets because users will ask for them.

But the right maturity in P0 is still:
- alpha
- export only
- clearly documented gaps
- no parity claim
- no import promise until behavior is better characterized

These hosts evolve quickly enough that premature parity claims will create maintenance pain.

## 10.6 Internal neutral projection model

Do not make `AGENTS.md` the canonical internal model.
Do not make `CLAUDE.md` the canonical internal model.

The canonical model should stay claim-based.

However, it is still useful to keep an internal neutral projection abstraction with fields like:
- always-on guidance blocks
- path-scoped rules
- playbook references
- environment/bootstrap directives
- restrictions or guardrails
- overflow and omission notes

This helps every adapter without turning any host format into the internal truth.

## 10.7 Host-specific constraints that should shape implementation

| Host | Recommended maturity | Important implementation constraints |
|---|---|---|
| Codex | GA | Layered `AGENTS.md` behavior, project `.codex/config.toml`, stdio and Streamable HTTP MCP, strong skill support, keep always-on guidance within practical size budgets |
| Claude Code | GA | `CLAUDE.md`, project settings, hooks and subagents exist but should not drive MVP shape, keep always-on guidance concise and procedural depth in skills |
| Copilot coding agent | Beta | Repository instructions and path-scoped instructions are real, but MCP is tools-only, remote OAuth MCP is not supported, environment setup is opinionated, and adapter behavior should be validated carefully |
| Cursor | Alpha export | Rules and MCP support exist, but treat as export-only until conformance coverage exists |
| Windsurf | Alpha export | Rules and MCP support exist, but treat as export-only until conformance coverage exists |

Important concrete notes:
- Codex should get first-class projection for `.agents/skills`, not only `AGENTS.md`.
- Claude Code should get first-class projection for `CLAUDE.md`, with later hooks or subagent integration only after the core flow is stable.
- Copilot adapter work must account for `.github/copilot-instructions.md`, `.github/instructions/**/*.instructions.md`, and `.github/workflows/copilot-setup-steps.yml`.
- Current GitHub docs indicate Copilot coding agent only supports MCP tools, not MCP resources or prompts.
- Current GitHub docs also indicate Copilot coding agent setup is centered on Ubuntu x64 GitHub Actions-backed environments, with ARC as the official self-hosted path.
- Cursor and Windsurf should not be used to justify complexity in the canonical model until they earn it through stable conformance tests.

---

## 11. Instruction projection strategy

## 11.1 Thin-by-default is not optional

The PRD is right here, and this decision should get even stricter.

Always-on content should include only:
- non-inferable repo-specific constraints
- high-confidence, broad-applicability claims
- critical validation commands
- dangerous-operation restrictions
- host usage hints that materially change behavior
- references to on-demand skills or playbooks

Exclude from always-on content:
- repo overviews
- generic architecture descriptions the agent can infer from files
- style rules already enforced by tooling
- large command catalogs
- speculative or weak-confidence conventions

## 11.2 Skills and playbooks are where detailed procedure belongs

Detailed workflows should project to skills or playbooks when the host supports them.

Examples of strong playbook candidates:
- how to validate Python changes in this repo
- safe workflow for touching CI configuration
- how to modify generated code
- how to work inside a risky subsystem
- migration workflow for a particular package area

This is a major value lever because it preserves thin always-on guidance while still retaining rich knowledge.

## 11.3 Artifact ownership modes

The product needs explicit ownership modes for generated files.

Recommended modes:
- `imported-human-owned`: existing file imported into claims, but not managed by RKP
- `managed-by-rkp`: file or managed sections may be regenerated after review
- `mixed-migration`: user is moving from human-owned to managed, with explicit diffs and warnings

Without this distinction, the product will either overwrite trusted files or become unable to evolve them.

## 11.4 Managed-file write policy

Recommended policy:
- never silently rewrite files
- preview exact diffs
- show omitted claims and why they were omitted
- include generation headers and provenance
- support no-op preview when nothing changed

If a host file contains unmanaged edits in a managed region, the system should:
- detect drift
- refuse blind overwrite
- surface reconciliation choices in review

---

## 12. CLI, review, and UX flows

## 12.1 The CLI is core product, not scaffolding

Users will trust or distrust the system primarily through the CLI review flow.

The CLI must feel like a governance tool, not like a codegen helper.

## 12.2 Recommended top-level commands

P0 command set should likely be:
- `rkp init`
- `rkp index`
- `rkp review`
- `rkp apply`
- `rkp import`
- `rkp preview`
- `rkp status`
- `rkp doctor`
- `rkp trace`

Possible later commands:
- `rkp verify`
- `rkp revalidate`
- `rkp export`
- `rkp explain`

## 12.3 `rkp init` flow

Recommended behavior:
1. detect support envelope and repo shape
2. detect existing managed and unmanaged instruction surfaces
3. run extraction and build initial claims
4. present a concise findings summary
5. generate previews for supported adapters
6. open or print the review queue

The first run should answer two user questions quickly:
- what did you learn?
- what are you proposing to write?

## 12.4 `rkp review` flow

This is the highest-leverage UX surface.

Recommended review buckets:
- high-confidence claims ready for approve
- conflicts requiring decision
- weak-confidence claims recommended for suppress or defer
- drift or artifact ownership issues
- unsupported areas and why

Each review item should show:
- proposed claim
- scope
- evidence summary
- source authority
- confidence
- freshness
- projected host impact

## 12.5 `rkp status` flow

This command should become the operational dashboard.

It should report:
- repo snapshot and head info
- index freshness
- drift in managed artifacts
- unsupported or partially supported areas
- pending review items
- stale claims or claims awaiting revalidation
- adapter state by host

## 12.6 `rkp doctor` flow

This is more important than it looks.

It should validate:
- required runtime/tooling availability
- SQLite features and DB health
- parser availability
- support-envelope matches
- MCP server boot health
- adapter prerequisites
- permissions and path issues

The product will be easier to adopt if users can quickly diagnose why something is not working.

---

## 13. Build tooling and library recommendations

## 13.1 Adopt / defer / avoid matrix

| Area | Adopt now | Defer | Avoid for MVP |
|---|---|---|---|
| Runtime | Python 3.12+ | 3.13 optimization work | Polyglot runtime |
| Packaging | `uv`, `uvx`, PyPI | Homebrew formula | Docker-first distribution |
| CLI | Typer + Rich | Textual TUI if demand emerges | bespoke CLI framework |
| MCP | official Python MCP SDK | FastMCP convenience wrapper | custom protocol stack |
| Storage | SQLite WAL + FTS5 + JSON | Postgres for remote mode | graph DB |
| DB access | hand-written SQL repositories | light query builder if pain emerges | heavy ORM-centered design |
| Code parsing | tree-sitter curated grammars | broader grammar pack extras | “all languages supported” claim |
| Config parsing | TOML/YAML/JSON native parsers | more manifest types | tree-sitter for every config |
| Git | Git CLI backend | optional `pygit2` backend | mandatory libgit2 dependency |
| Graph | SQLite edges + small in-memory traversals | optional accelerator | required `rustworkx` |
| Validation | pytest + hypothesis + golden fixtures | mutation testing | manual-only testing |
| Typing | `pyright` strict plus runtime boundary validation | mypy if ecosystem pressure | untyped domain core |
| Lint/format | Ruff | import-order tweaks only | split lint/format toolchain |
| Logging | structured JSON-capable logging | OTEL export | ad hoc prints everywhere |
| File watch | simple change detection or watcher abstraction | richer daemon mode | watch-heavy architecture in P0 |
| Sandbox verify | clean worktree seam | containerized runner in Phase 2 | active verification in P0 |

## 13.2 Recommended Python stack

Concrete recommendation:
- `typer`
- `rich`
- `pydantic` v2 at IO boundaries
- `ruff`
- `pyright`
- `pytest`
- `hypothesis`
- `pytest-cov`
- `pytest-benchmark`
- optional snapshot or golden testing utility

Internal style recommendation:
- use dataclasses or lightweight domain types internally
- use Pydantic at boundaries and persistence DTOs, not everywhere indiscriminately

## 13.3 Database access recommendation

Use repository-style modules with explicit SQL.

Why:
- SQLite-specific features matter here
- recursive CTEs and FTS are easier to reason about in SQL than through a thick ORM abstraction
- debugging and performance profiling are cleaner

A small helper layer is fine.
A central ORM should not dominate the architecture.

## 13.4 Optional extras packaging

Use optional extras from day one.

Example shape:
- `repo-knowledge-plane` base install
- `repo-knowledge-plane[dev]`
- `repo-knowledge-plane[full-parsers]`
- `repo-knowledge-plane[verify]`

This keeps the local-first adoption path light while preserving room for heavier capabilities later.

---

## 14. Deployment and distribution strategy

## 14.1 The best initial distribution path

For launch, the canonical install path should be:
- publish to PyPI
- run via `uvx repo-knowledge-plane`

Why this is best:
- lowest friction for a Python-based local tool
- no requirement to create standalone binaries immediately
- cross-platform enough for target workstation users
- consistent with local MCP server execution patterns

Recommended explicit support stance for Phase 1:
- support macOS and Linux first
- treat Windows as a later support target unless a design partner makes it mandatory
- test Python 3.12 first, then add 3.13 once the fixture and adapter surface is stable

Reason:
- shell behavior, path handling, file watching, and local-agent tooling are materially easier to make robust on macOS and Linux first
- a fake “cross-platform” claim early will create debugging churn precisely where the product needs trust

## 14.2 Do not make Docker the primary user install path

Docker is useful for:
- future sandboxed verification
- remote HTTP serving
- CI

Docker is not the best primary local install path for this product because:
- the product needs intimate local repo and filesystem access
- containerizing the whole local UX adds friction
- it complicates path and editor integration
- it undermines the “works in five minutes” wedge

## 14.3 Recommended release channels

Recommended release channels:
- PyPI as canonical package distribution
- GitHub Releases for changelogs, checksums, and release notes
- GHCR only when a remote or container reference deployment exists
- Homebrew later if real user demand emerges

## 14.4 Future remote deployment recommendation

Do not launch as shared multi-tenant SaaS.

If remote deployment becomes necessary, the first honest remote shape should be:
- single-tenant or bring-your-own-cloud
- OCI image distribution
- Streamable HTTP MCP endpoint
- repo data stored in tenant-controlled infrastructure

Recommended order:
1. ship local-first
2. ship OCI image + reference deployment
3. support single-tenant managed pilots
4. only then evaluate whether a shared service makes sense

Reason:
- trust boundary is central to the product
- repo intelligence is sensitive by default
- a premature shared SaaS posture creates privacy, auth, and retention complexity before core value is proven

## 14.5 Remote infrastructure recommendation when needed

When remote mode exists, prefer:
- OCI image in GHCR
- reference deployment for Kubernetes or a simple container platform
- minimal persistent service footprint
- SQLite only if single-instance and low scale; otherwise a clearly separated remote-mode storage plan

Do not let remote-mode architecture leak into the local-first core prematurely.

---

## 15. Documentation strategy

## 15.1 Documentation should be structured by decision horizon

Recommended docs split:
- `README.md`: install, quickstart, core commands, support envelope, trust model
- `docs/architecture.md`: system boundaries, data flow, extension seams, constraints
- `docs/decisions.md`: append-only ADR log or ADR index
- `docs/claim-model.md`: canonical claim schema and merge rules
- `docs/host-adapters.md`: host capability matrix and projection rules
- `docs/quality-harness.md`: fixture strategy, evals, conformance tests
- `docs/security.md`: local data boundary, leakage policy, remote risks
- `docs/ops.md`: DB lifecycle, migrations, release, rollback, support commands

## 15.2 The repo is currently missing important canonical docs

Two missing docs matter immediately:
- `docs/architecture.md`
- `docs/decisions.md`

Those should exist early.
They do not need to be verbose.
They do need to be authoritative.

## 15.3 Documentation style recommendation

Documentation should be:
- terse
- explicit about what is supported vs not supported
- written around invariants and operational behavior
- free of template filler

The system docs should explain:
- what the system guarantees
- what it refuses to guarantee
- what evidence each claim class depends on
- what happens when evidence conflicts

## 15.4 Dogfooding recommendation

This project should dogfood its own product carefully, not theatrically.

Recommended dogfooding sequence:
- use RKP to maintain its own `AGENTS.md` and `CLAUDE.md` only after the import and review flows are trustworthy
- use the project as one fixture repo, but never as the only fixture repo

This is useful, but it should not distort evaluation.

---

## 16. Testing, quality, and robustness strategy

## 16.1 The quality harness is the moat, not just a safety net

This product can only succeed if it can repeatedly prove three things:
- the extracted claims are good enough
- the projected artifacts are faithful and thin
- the system does not leak or overstate unsupported information

That means the quality harness is not secondary. It is part of the product.

## 16.2 Required test layers

Recommended test pyramid:

Unit tests:
- claim merge logic
- confidence scoring rules
- applicability filtering
- projection prioritization and overflow logic
- support-envelope checks

Parser and extractor tests:
- per extractor fixture inputs
- line-accurate evidence expectations
- malformed file behavior

Golden projection tests:
- canonical claims to host artifacts
- deterministic output snapshots
- overflow diagnostics

Round-trip tests:
- import existing instruction file
- synthesize claims
- project preview
- ensure expected round-trip fidelity or expected warning

CLI integration tests:
- temp repo fixtures
- end-to-end `init`, `review`, `preview`, `status`, `apply`

MCP contract tests:
- tool argument validation
- response envelope consistency
- unsupported behavior explicitness

Performance tests:
- cold index on fixture repos
- warm query latency
- incremental update timing

Security and leakage tests:
- ensure sensitive claim filtering works
- ensure local-only claims never escape to checked-in projections
- ensure tool responses honor sensitivity and support envelope

## 16.3 Fixture strategy

Build a real fixture portfolio early.

Suggested fixture set:
- small Python service repo
- JS/TS monorepo with workspaces
- mixed-language repo inside the support envelope
- repo with existing `AGENTS.md` and `CLAUDE.md`
- repo with noisy docs and conflicting evidence
- repo intentionally outside the support envelope

Fixtures should be curated, versioned, and stable.
This will matter more than nearly any individual library choice.

## 16.4 Property-based testing targets

Use property tests for:
- claim merge associativity and precedence behavior where applicable
- projection prioritization under size limits
- drift detection correctness under file mutations
- sensitivity filtering invariants
- idempotence of preview without evidence changes

## 16.5 Determinism requirements

Generated artifacts must be deterministic for the same effective claim state.

That means:
- stable ordering rules
- normalized whitespace
- normalized evidence display
- stable tie-breakers
- no timestamp noise inside managed content blocks unless explicitly needed in headers

Without determinism, drift detection and user trust degrade fast.

## 16.6 Robustness principles

Build the system to fail clearly.

Preferred failure modes:
- explicit unsupported
- stale-warning with usable partial answer
- preview unavailable because review conflict exists
- artifact write refused because of unmanaged drift

Avoid:
- silent fallback to low-quality guesses
- incomplete artifacts that look authoritative
- unsupported hosts appearing “mostly fine”

---

## 17. Security, privacy, and trust boundaries

## 17.1 Local-first must be a real property

The product promise that no repo content is transmitted off the local machine by RKP itself must remain true in MVP.

That requires discipline around:
- logs
- crash reports
- optional telemetry
- dependency behavior
- remote MCP experiments

Default posture:
- local-only
- no outbound transmission
- opt-in export only

## 17.2 Sensitive data policy

Claims need sensitivity classes that actually affect behavior.

Recommended classes:
- `public`
- `team-only`
- `local-only`

Examples:
- public: repo conventions safe for checked-in files
- team-only: internal workflows appropriate for private repos but not public exports
- local-only: machine-specific environment facts, secrets-adjacent operational details, local override behavior

Important rule:
- env var names may be claims
- env var values must never be claims

## 17.3 Host security mismatch

Different hosts expose different risk surfaces.

The projection engine must know:
- what is enforceable
- what is advisory only
- what should never be projected to checked-in artifacts

This is especially important for:
- dangerous shell operations
- networked MCP tool access
- local machine paths
- internal service endpoints

## 17.4 Remote MCP and future auth risk

If remote MCP arrives later, major security risks include:
- SSRF
- OAuth token handling
- redirect abuse
- server impersonation
- unwanted data retention

These should not be solved in P0.
They should be isolated as a Phase 2 remote-mode concern.

---

## 18. Project management and feature management

## 18.1 Organize delivery by vertical slices, not horizontal subsystems

This project can get lost if the team builds “the parser layer,” then “the database layer,” then “the adapters,” without proving user value.

Preferred milestone slices:
1. repo scan + command/prereq claims + review preview
2. host projection for Codex and Claude
3. import and drift detection
4. module map and path-scoped conventions
5. Copilot beta adapter
6. quality harness expansion and design-partner hardening

Each slice should produce a visible end-to-end capability.

## 18.2 Feature template recommendation

Every feature or milestone proposal should answer:
- user problem being reduced
- evidence classes affected
- claim classes affected
- adapter surfaces affected
- eval plan
- rollout risk
- what becomes easier later if this ships

That keeps the roadmap grounded.

## 18.3 Decision management

Adopt ADR discipline early.

Suggested immediate ADR topics:
- canonical storage and migration strategy
- git backend strategy
- parser support envelope
- artifact ownership modes
- adapter maturity policy
- remote deployment stance

## 18.4 Release process recommendation

Use a boring release process:
- trunk-based or short-lived branch workflow
- CI gates on lint, types, unit, integration, golden, and perf smoke
- tagged releases to PyPI through trusted publishing
- release notes with user-visible behavior changes and migration notes

## 18.5 Feature flags

Use feature flags sparingly, but do use them for:
- alpha adapters
- experimental extractors
- remote mode
- active verification
- broader parser extras

Do not use feature flags to hide core MVP instability indefinitely.

---

## 19. Product-level constraints and UX refinements

## 19.1 The product should optimize for agent usefulness, not documentation completeness

This is a subtle but critical point.

A repository can contain a lot of information that is true but not useful to put in front of an agent every session.

The product needs a concept of relevance stronger than truth.

Good always-on content is:
- highly reusable
- hard to infer from code alone
- likely to matter to many tasks
- compact

Good on-demand content is:
- precise
- evidence-backed
- task-specific

## 19.2 Add “why this matters” and “why this was omitted” explanations

Two UX capabilities will pay off quickly:
- explain why a claim was included in a projection
- explain why a claim was omitted from a projection

This prevents the system from feeling arbitrary.

## 19.3 Avoid pretending that more context is better

The product should explicitly reject a common anti-pattern:
- dumping lots of extracted context into always-on files

This looks intelligent and often performs worse.
The product should be opinionated against it.

## 19.4 Add support-envelope surfacing early

The system should say clearly when it is outside scope.

Examples:
- unsupported primary language
- repo too large for current profile
- monorepo shape only partially supported
- missing parser for key manifest
- host capability not implemented

This honesty is part of the UX.

## 19.5 Valuable early additions not fully emphasized in the PRD

High-value additions to prioritize early:
- `doctor` and support diagnostics
- claim explanation surface
- artifact ownership and migration state
- omitted-claim diagnostics
- deterministic diff previews
- no-op status reporting
- fixture pack and conformance suite from day one

These increase trust more than many “smarter” features would.

---

## 20. Unknown unknowns and hidden risks

## 20.1 Host behavior drift is a permanent risk

Docs are necessary but not sufficient.
Host behavior changes faster than most infrastructure products.

Mitigation:
- maintain a live adapter conformance suite using disposable sample repos
- version capability descriptors by date
- document known behavior deltas from official docs when observed

## 20.2 The system may overfit to fixture repos

This is a real risk for a product built around extraction precision.

Mitigation:
- keep fixtures diverse
- add design-partner shadow evaluations
- rotate in messy real repos
- test negative cases, not just “works on clean repos” cases

## 20.3 Claim identity and review-state drift can become a product-killer

If claim IDs shift too often, users lose trust because approved or suppressed claims seem to resurrect randomly.

Mitigation:
- design stable logical identities now
- test for identity stability across small repo changes
- record supersession relationships explicitly

## 20.4 Sensitive information can leak through innocuous-looking metadata

Even without secret values, risky leakage can happen through:
- internal hostnames
- local path conventions
- tool names tied to internal systems
- team-only operational playbooks

Mitigation:
- strict sensitivity filtering
- projection policy tests
- clear review warnings before writing checked-in artifacts

## 20.5 Large repos can create silent performance cliffs

Potential cliffs:
- parser memory use
- Markdown/doc explosion
- wide monorepo workspace graphs
- path-scoped convention extraction across enormous trees

Mitigation:
- file count and byte-budget safeguards
- incremental scan and caching
- configurable ignore rules
- support-envelope warnings before degraded behavior looks like success

## 20.6 Importing existing instruction files may be politically harder than technically hard

Users may trust their current `AGENTS.md` or `CLAUDE.md` more than the new system.

Mitigation:
- import without taking ownership by default
- show exact conflicts and evidence
- let users preserve human-owned content while adopting claim-backed previews gradually

## 20.7 The biggest product risk is not technical, it is trust collapse

One or two incorrect high-confidence claims can outweigh many correct low-friction wins.

Mitigation:
- conservative defaults
- visible evidence
- explicit unsupported states
- thin projections
- review-first writes

---

## 21. Recommended phased build plan

## 21.1 Phase 1A: core contract loop

Goal:
- prove the local-first claim engine and review loop work

Build:
- repo scan and support-envelope detection
- evidence storage and schema
- command and prerequisite extraction
- claim model and merge logic
- Codex and Claude preview projection
- `rkp init`, `rkp review`, `rkp preview`, `rkp status`
- first fixture repos and golden tests

Exit criteria:
- useful repo-specific previews on supported repos
- deterministic outputs
- evidence-backed command and prerequisite results

## 21.2 Phase 1B: import, drift, and path scope

Build:
- import existing instruction files as declared-policy claims
- path-scoped conventions
- managed artifact ownership modes
- drift detection
- no-op and omitted-claim diagnostics
- broader fixture coverage

Exit criteria:
- users can migrate from manual instruction files without losing trust
- drift is surfaced clearly

## 21.3 Phase 1C: Copilot beta adapter and module map hardening

Build:
- Copilot beta adapter
- module-node and edge model
- test-location inference
- stronger adapter conformance tests
- better diagnostics for unsupported conditions

Exit criteria:
- two GA adapters truly solid
- Copilot usable with documented limits

## 21.4 Phase 2: optional verification and remote seam

Build only after Phase 1 trust exists:
- active verification seam behind explicit consent
- clean worktree runner
- optional containerized verifier
- Streamable HTTP transport
- OCI reference deployment
- optional semantic enrichment seam

Do not bring this earlier unless design-partner evidence forces it.

---

## 22. Recommended immediate decisions

These decisions should be made before coding starts in earnest:

1. Confirm that the canonical package target is `docs/codex-5.4-research.md` and that research artifacts continue living under `docs/`.
2. Update the PRD stack lines for MCP, parsing, git, and graph choices.
3. Decide the artifact ownership model for imported instruction files.
4. Define the support envelope precisely for Phase 1.
5. Commit to a curated parser set for launch.
6. Commit to Git CLI backend first.
7. Commit to SQLite edge store first.
8. Create `docs/architecture.md` and `docs/decisions.md` before the implementation fans out.
9. Define the first fixture repo set and quality harness shape before building too many extractors.
10. Treat Codex and Claude as the only true GA targets for Phase 1 planning.

---

## 23. Recommended PRD edits in plain language

If the PRD is revised from this research, the revision should say, in plain language:

- the product is a local-first claim engine with host-specific projections
- the MVP optimizes for correct operational context, not maximal repo summarization
- the official MCP Python SDK is the protocol foundation
- Git CLI is the default git backend
- graph acceleration is optional and deferred
- broad parser bundles are not the default
- always-on files stay thin by policy
- imported instruction files remain human-owned until the user explicitly opts into managed ownership
- Codex and Claude are GA launch adapters; Copilot is beta; Cursor and Windsurf are export-only alpha
- the quality harness is a release gate, not a post-hoc measurement system

---

## 24. Source notes

Internal repo sources reviewed:
- `docs/prd.md`
- `docs/research.md`
- `docs/codex-5.3-research.md`
- `docs/SYSTEM.md`
- `.claude/rules/immutable.md`
- `.claude/rules/conventions.md`
- `.claude/rules/stack.md`

Primary external sources checked on March 18, 2026:
- OpenAI Codex docs: `AGENTS.md`, skills, MCP, config, and customization pages
- OpenAI API docs for MCP connectors and remote MCP guidance
- Anthropic Claude Code docs for memory, settings, MCP, hooks, and subagents
- GitHub Copilot docs for repository instructions, skills, coding-agent setup, and MCP extension
- Cursor docs for rules and MCP support
- Windsurf docs for custom rules and MCP support
- Model Context Protocol docs and Python SDK docs
- `agents.md` standard site
- FastMCP docs
- `tree-sitter-language-pack` README
- `pygit2` README and license text
- `rustworkx` README
- `uv` docs
- SQLite WAL and FTS5 docs

Useful URLs:
- https://developers.openai.com/codex/concepts/customization/#agents-guidance
- https://developers.openai.com/codex/guides/agents-md/#layer-project-instructions
- https://developers.openai.com/codex/skills/
- https://developers.openai.com/codex/mcp/
- https://developers.openai.com/codex/config-basic/#configuration-precedence
- https://developers.openai.com/codex/config-reference/#configtoml
- https://developers.openai.com/api/docs/guides/tools-connectors-mcp/
- https://developers.openai.com/api/docs/guides/your-data/#v1responses
- https://docs.anthropic.com/en/docs/claude-code/memory
- https://docs.anthropic.com/en/docs/claude-code/settings
- https://docs.anthropic.com/en/docs/claude-code/mcp
- https://docs.anthropic.com/en/docs/claude-code/hooks
- https://docs.anthropic.com/en/docs/claude-code/sub-agents
- https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-skills
- https://docs.cursor.com/context/rules
- https://docs.cursor.com/context/model-context-protocol
- https://docs.windsurf.com/windsurf/cascade/custom-rules
- https://docs.windsurf.com/windsurf/cascade/mcp
- https://modelcontextprotocol.io/docs/concepts/roots
- https://py.sdk.modelcontextprotocol.io/
- https://agents.md/
- https://gofastmcp.com/getting-started/quickstart
- https://raw.githubusercontent.com/Goldziher/tree-sitter-language-pack/master/README.md
- https://raw.githubusercontent.com/libgit2/pygit2/master/README.md
- https://raw.githubusercontent.com/Qiskit/rustworkx/main/README.md
- https://docs.astral.sh/uv/
- https://www.sqlite.org/wal.html
- https://www.sqlite.org/fts5.html
