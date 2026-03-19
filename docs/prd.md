# Repo Knowledge Plane — Product Requirements Document

_v4.0 — 2026-03-18. Revised from v3.0 after external review and critique. Research base: `docs/research-product.md`, `docs/research-build.md`._

---

## 1. Product Summary

Repo Knowledge Plane (RKP) is a persistent, agent-neutral intelligence layer for software repositories. It extracts verified operational context — environment prerequisites, validated commands with CI evidence, conventions, architecture boundaries, scoped rules, and declared-vs-inferred conflicts — from a repository's code, configuration, CI definitions, and history. It serves that knowledge through MCP so any coding agent or developer tool can query the same evidence-backed substrate without developers pasting context into prompts.

RKP also meets teams where they are: it imports existing instruction files (AGENTS.md, CLAUDE.md, .cursor/rules), enriches them with extracted evidence, detects drift when managed artifacts are manually edited, and projects reviewed output faithfully into every major agent's native configuration surface — instruction files, skills, environment configs, and permissions. Human review decisions are version-controlled in a checked-in `.rkp/` directory so they're shareable across machines and team members.

It is developer infrastructure — comparable to CI or observability — not another coding assistant. The positioning is: **"Portable, verified repo context for every coding agent."**

---

## 2. Problem Statement

AI coding tools have created a coordination and quality problem that scales with adoption.

### The evidence, stated honestly

**DORA 2024** (39,000 respondents): 75% of developers perceive individual productivity gains from AI. At the system level, more AI adoption correlated with better documentation quality, code quality, and review speed — but also with 1.5% lower delivery throughput and 7.2% reduced delivery stability. The causal story is not "AI makes teams slower"; it is that AI increases batch size, and larger batches are riskier and harder to review.

**METR 2025**: Experienced developers using AI took 19% longer on tasks while estimating a 20% speedup. However, METR's Feb 2026 update notes later data is noisy and likely biased downward, because developers and tasks with the highest expected AI uplift increasingly self-select out of no-AI experiments. The perception gap is real; the magnitude is uncertain.

**GitClear 2024-2025** (211M changed lines): Code churn rose from 5.5% to 7.9%, copy-pasted code from 8.3% to 12.3%, refactoring dropped by over 60%, and code clone occurrence rose eightfold. This is the most durable signal: AI increases velocity on local tasks while reducing structural maintenance.

**Structural argument**: Even if individual task speed improves, AI increases variance, coordination drift, and hidden quality tax — unless the repo has trusted, persistent operational context that agents can query before they work.

### The root cause — fragmented, ungoverned, non-portable context

The problem is no longer that agents have zero persistence. It is that persistence is **fragmented, vendor-specific, unevenly governed, and not portable**.

Every major platform has built its own partial solution:

| Platform | Persistence mechanism | Limitation |
|---|---|---|
| **GitHub Copilot** | Repository memory (auto-generated, branch-aware, 28-day TTL), copilot-instructions.md, path-scoped .instructions.md files, custom agents, skills | Copilot-only. Memory is auto-managed, not human-governed. No portability to other agents |
| **Claude Code** | CLAUDE.md hierarchy, .claude/rules/, settings, permissions/sandboxing, skills, subagents, auto memory | Claude Code-only. Rich but fragmented across many surfaces. No portability |
| **OpenAI Codex** | AGENTS.md layering (root to CWD), skills, Team Config | Codex-only. Skills deprecated custom prompts. No cross-agent sharing |
| **Cursor** | .cursor/rules (path-scoped), project context | Cursor-only. Rules are Cursor-specific format |
| **Windsurf** | Transport choice, tool toggles, tool caps, rules, skills, manual workflows | Windsurf-only configuration |
| **Devin** | Product-native memory, DeepWiki | Devin-only. Not structured for other agents |

The consequences:
1. **Duplication**: Teams maintain copilot-instructions.md AND CLAUDE.md AND AGENTS.md AND .cursor/rules with overlapping, potentially contradictory content
2. **Drift**: When a convention changes, it must be updated in N places — or agents get stale guidance
3. **No governance**: Most instruction surfaces have no review workflow, no provenance, no confidence signals. Inferred memories mix with declared policies
4. **No portability**: Switching or adding an agent means recreating context from scratch
5. **Quality matters more than quantity**: A Jan 2026 study found AGENTS.md associated with lower runtime and token use, but a Feb 2026 study found repo context files often _reduced_ task success and _increased_ inference cost by 20%+ when they imposed unnecessary requirements. The difference is quality and relevance: thin, verified, frequently-relevant context helps; verbose, stale, irrelevant, or over-constraining context hurts

Meanwhile, AGENTS.md is present in 60,000+ repositories with no tooling to generate or maintain it from actual codebase analysis. But generating instruction files is not the product — it is one delivery surface among many. And raw instruction generation is already commodity: Claude Code's `/init` generates CLAUDE.md, Copilot can generate copilot-instructions.md, Codex can scaffold AGENTS.md. The real opportunity is evidence-backed extraction, human governance, relevance-aware projection, and cross-agent portability.

---

## 3. Vision & Positioning

MCP is now an industry standard under the Linux Foundation's Agentic AI Foundation (AAIF), co-sponsored by Anthropic, OpenAI, Google, AWS, and Microsoft. AGENTS.md is also stewarded by AAIF. These are the converging, vendor-neutral interfaces the product builds on.

### Non-negotiable properties

| Property | Why non-negotiable |
|---|---|
| **Cross-agent** | Value compounds when the same context is available to multiple agents — workstation-first in MVP, with hosted/background agents served via checked-in projected artifacts |
| **Persistent** | Knowledge must survive sessions. Six months of accumulated understanding remains available |
| **Local-first** | No cloud required, zero-procurement adoption. Note: RKP itself keeps data local by default; what host agents do with queried data follows their own retention policies |
| **Evidence-backed** | Every derived claim has provenance, source authority, timestamps, and confidence. Declared facts distinguished from inferred heuristics with explicit precedence |
| **Governable** | Inferred claims can be corrected, suppressed, or tombstoned. Instruction file writes require human review. Provenance is auditable. Human decisions are version-controlled |
| **Relevance-aware** | Context is not just true — it must be appropriate for the current scope, task, and host. Over-inclusion is as harmful as omission |
| **Identity-aware** | Repo, branch, worktree, and session identity are first-class in the data model — not assumed to be single/static |
| **Infrastructure, not persona** | Not a new "AI teammate" — quietly improves work done through existing tools |

### What "cross-agent" means concretely

| Agent | Deployment model | MCP support | Adapter maturity | MVP path |
|---|---|---|---|---|
| **Claude Code (local)** | Workstation | stdio, tools + resources | **GA** | Full MCP + projected CLAUDE.md + skills |
| **Codex CLI/IDE** | Workstation | stdio, tools + resources | **GA** | Full MCP + projected AGENTS.md + skills |
| **Copilot** | Workstation + GitHub Actions | Tools only (no resources, no prompts) | **Beta** | Tools via MCP; projected copilot-instructions.md, .instructions.md, copilot-setup-steps.yml |
| **Cursor** | Workstation | stdio, tools + resources | **Alpha (export)** | Projected .cursor/rules; MCP tools available but untested |
| **Windsurf** | Workstation | stdio, SSE, Streamable HTTP | **Alpha (export)** | Projected rules; MCP tools available but untested |
| **Copilot coding agent** | GitHub Actions ephemeral | Tools only | **Beta** | Reads projected AGENTS.md + copilot-setup-steps.yml from repo (no running RKP server needed) |
| **Codex cloud** | OpenAI cloud | Remote MCP | **Not supported** | Reads projected AGENTS.md from repo; managed MCP requires Phase 2+ |
| **Devin** | VM / remote MCP | Remote MCP | **Not supported** | Reads projected AGENTS.md from repo if available |

**MVP deployment target: local/workstation agents (Claude Code, Codex) with GA adapter quality.** Copilot at beta quality. Cursor/Windsurf at alpha/export-only until conformance is proven. Cloud/remote agent support via managed MCP serving requires Phase 2+. However, all agents — including hosted/background agents — benefit from the checked-in projected artifacts (AGENTS.md, CLAUDE.md, copilot-setup-steps.yml) without requiring a running RKP server. This is artifact-first remote support.

_Assumption [A1]: Workstation agents are sufficient for initial adoption. If design partners consistently require cloud agent support first, accelerate the remote deployment story._

---

## 4. Target Users & Persona Priority

| Persona | Job to be done | MVP role |
|---|---|---|
| **AI coding agent** | Before touching code, know how this repo works and what constraints matter | **Primary technical consumer** — every MCP design decision must work for machine consumption first |
| **Senior engineer / tech lead** | Make architectural intent and conventions legible for humans and agents; correct wrong inferences | **Primary human champion** — validates output, provides feedback, drives adoption |
| **Developer onboarding** | Become productive without violating invisible rules | Early beneficiary — benefits from Day 1 artifacts |
| **Platform / dev productivity team** | Provide one trusted repo intelligence layer for all approved agents | **Scaling buyer** — governance/fleet features are Phase 2+ |

**MVP priority call:** Optimize for the tech lead + agent pair. The tech lead has the strongest pain around stale conventions, can validate synthesized output, and can champion adoption without org-wide rollout. The agent is the highest-frequency consumer.

_Assumption [A2]: Reevaluate after first 5-10 design partners. If platform teams consistently sponsor deployment first, shift roadmap emphasis._

---

## 5. Initial Wedge Decision

### Repositioned wedge: Evidence-backed extraction + reviewed operational contract + relevance-aware projection

The wedge is **not** "generate AGENTS.md." Adjacent scaffolding already exists, and the research is clear: the problem is not quantity of context but quality, relevance, and governance. Thin, verified, frequently-relevant context helps; verbose or over-constraining context hurts.

The opportunity is: **extract the non-inferable operational context that agents need but cannot safely reconstruct from the code alone, make it reviewable and governable, and project it into host-native surfaces with relevance-awareness so the right context reaches the right agent at the right time.** That means:

1. **Environment prerequisites and validated commands** — what's needed to build/test/lint, discovered from config and CI definitions, with prerequisites, risk classification, and evidence levels
2. **Thin always-on conventions** — only non-inferable, high-confidence, frequently-relevant rules in root instruction files
3. **Host-native skill/playbook projection** — detailed procedures, validation recipes, and environment-specific workflows projected as skills (Claude Code, Copilot, Codex) or on-demand MCP queries, not crammed into always-on files
4. **Declared vs. inferred conventions** — separated with evidence, confidence, source authority, and applicability
5. **Path-scoped rules** — which constraints apply where, with precedence
6. **Coarse module boundaries** — what depends on what, tied to actionable context (scoped rules, test locations, valid commands per module)
7. **Declared-vs-inferred conflicts** — where the docs say one thing and the code does another
8. **Enforceable guardrails** — security-sensitive workflows projected as permission/tool restrictions where the host supports them, advisory text everywhere else
9. **Import and drift detection** — ingest existing instruction files, detect when managed artifacts diverge from the canonical model

The instruction files (AGENTS.md, copilot-instructions.md, .cursor/rules) are one delivery surface. Skills and playbooks are another. MCP queries are a third. The product is the verified operational context underneath, projected faithfully through a host capability matrix that models all of these surfaces.

### Why this wedge, not PR-risk intelligence

1. **Most universal immediate problem.** Every agent rediscovers conventions because instruction surfaces are incomplete, stale, or over-stuffed.
2. **Fastest path to trust.** Convention synthesis produces useful output from the current snapshot and modest history. Risk predictions too early damage trust faster than they create value.
3. **Self-distributing artifacts.** Generated instruction files are visible in-repo, useful to anyone, naturally attributable.
4. **Builds the right substrate.** Accurate synthesis requires parsing, boundary detection, convention inference, and MCP with provenance — the foundation for every subsequent capability.
5. **Lower technical risk.** Risk prediction requires runtime data (CI outcomes, test coverage, historical failures) that most repos don't make easily available. Convention synthesis works from what's already in the repo.
6. **Measurable from day one.** With a quality harness and design-partner evaluation, the product can demonstrate whether its context actually improves agent task success.

PR-risk intelligence is strategically critical but second-act. It depends on richer outcome data and calibration.

### First useful output in under five minutes

A developer runs `uvx repo-knowledge-plane init` and within five minutes receives:

- Discovered build/test/lint commands with prerequisites and CI evidence where available
- A draft instruction artifact — deliberately thin: only non-inferable, high-confidence, frequently-relevant rules
- Detailed procedures flagged for skill/playbook projection where the host supports it
- Low-confidence items and declaration prompts flagged for human confirmation
- A diff-style review flow — no instruction file is written until the human approves
- MCP tools queryable for conventions, modules, prerequisites, and architecture boundaries

For repos that already have instruction files: `rkp import` ingests existing AGENTS.md, CLAUDE.md, and .cursor/rules as declared-policy claims, enriches them with extracted evidence, and surfaces conflicts and gaps.

_Assumption [A3]: "Under five minutes" defined for single-repo local indexing, modern laptop, repos within the launch support envelope._

---

## 6. Launch Support Envelope

The PRD does not promise universal polyglot support. The launch support envelope is:

| Dimension | Supported at launch | Planned expansion |
|---|---|---|
| **Languages** | Python (+ pytest), JavaScript/TypeScript (+ npm/pnpm/yarn) | Go, Java, Rust — driven by design-partner demand |
| **Repo size** | Repos ≤ 250k LOC | Larger repos with incremental indexing improvements |
| **Build systems** | One dominant build graph per repo | Multi-build-system repos |
| **Source hosting** | Local git repos (any host) | GitHub/GitLab API integration for PR/CI metadata |
| **CI definitions** | GitHub Actions, common CI configs (read-only, for evidence) | GitLab CI, CircleCI, Jenkins — driven by demand |
| **Generated/vendor dirs** | Excluded by default | Configurable inclusion |
| **Monorepos** | Single-package or workspace repos with clear boundaries | Deep monorepo support with sub-project isolation |

### What happens outside the envelope

When the product encounters unsupported languages, oversized repos, or configurations it can't parse with confidence:

- It **says so explicitly** — "unable to extract conventions for `src/legacy_cpp/` (C++ not in launch envelope)"
- It degrades gracefully — still reports what it can from supported parts
- It never fabricates confidence for areas it can't analyze

_Assumption [A4]: Python + JS/TS covers the majority of design-partner repos. If Go or Java demand emerges in first 5 partners, accelerate those parsers._

---

## 7. Canonical Claim Model

This is the core data model. Every piece of knowledge RKP extracts or receives is a **claim** in this model. The model must be rich enough to faithfully project into any host's configuration surface — not just instruction files.

### Claim schema

Every claim carries:

| Field | Description |
|---|---|
| **id** | Stable identifier |
| **content** | The rule, convention, command, boundary, or constraint |
| **claim_type** | One of the canonical types (see below) |
| **source_authority** | Where this came from and how authoritative it is |
| **scope** | What paths, modules, or contexts this applies to |
| **applicability** | When this claim should be surfaced — relevance tags and conditions (e.g., `testing`, `ci`, `security`, `python`) that the projection engine uses to decide inclusion in always-on vs. on-demand surfaces. Claims without explicit applicability default to always-applicable within their scope |
| **precedence** | How this claim interacts with conflicting claims |
| **projection_targets** | Which host surfaces this should project to |
| **sensitivity** | `public` (safe for any instruction file), `team-only` (omit from public repo exports), `local-only` (never project to checked-in files). Default: `public` |
| **review_state** | unreviewed / needs-declaration / approved / edited / suppressed / tombstoned |
| **freshness** | Evidence basis, last validated, revalidation trigger |
| **confidence** | Numeric confidence for inferred claims; 1.0 for declared |
| **evidence** | What source artifacts support this claim |
| **provenance** | Extraction version, timestamp, repo HEAD at extraction |

### Claim types

| Type | Description | Projection target examples |
|---|---|---|
| **always-on-rule** | Repo-wide convention, always loaded | Root instruction file (AGENTS.md, CLAUDE.md, copilot-instructions.md) |
| **scoped-rule** | Convention for a specific path/module | Path-scoped instruction files, directory-level CLAUDE.md, .instructions.md |
| **skill/playbook** | Procedural workflow: multi-step recipe, validation procedure, detailed how-to. Projected using the Agent Skills open standard (agentskills.io) where supported | Claude Code skill, Codex skill (both support Agent Skills standard), Copilot skill, or on-demand MCP query |
| **environment-prerequisite** | Runtime, tool, service, OS, env var, or network requirement for a command or scope | copilot-setup-steps.yml, README, or structured MCP response |
| **validated-command** | Build/test/lint/format command with evidence level (§8.1) and risk classification | Structured MCP response, instruction file reference, copilot-setup-steps.yml |
| **permission/restriction** | Tool restrictions, sandbox requirements, security-sensitive operation flags | Claude Code permissions, Copilot agent tool config, advisory text |
| **module-boundary** | Architecture boundary, dependency relationship, ownership hint | Structured MCP response, instruction file reference |
| **conflict** | Declared-vs-inferred mismatch, stale evidence | Structured MCP response, review queue |

### Validated command risk classification

Commands carry a `risk_class` that informs how they're projected and whether they're eligible for verification:

| Risk class | Description | Examples |
|---|---|---|
| **safe-readonly** | No side effects; safe to run in any context | lint, typecheck, format --check |
| **safe-mutating** | Modifies files but not external state | format --write, codegen |
| **test-execution** | Runs tests; may require services or fixtures | test, e2e |
| **build** | Compiles or bundles; may require tools/resources | build, compile |
| **destructive** | Modifies external state or is irreversible | db:reset, deploy, clean |

### Source authority hierarchy

Claims are not just "declared" or "inferred." They have explicit source authority that determines precedence:

| Authority level | Source | Precedence (highest first) |
|---|---|---|
| **human-override** | Human correction via `rkp review` | 1 (highest) |
| **declared-policy** | Explicit rules in AGENTS.md, CLAUDE.md, .cursor/rules, README | 2 |
| **executable-config** | CI config, package.json scripts, Makefile targets, pyproject.toml | 3 |
| **ci-observed** | Commands and environments observed in CI definitions (GitHub Actions, etc.) | 3 (same tier as executable-config; CI configs are executable configs) |
| **checked-in-docs** | Architecture docs, ADRs, contributing guides | 4 |
| **inferred-high** | Pattern with strong evidence (e.g., 95%+ file consistency) | 5 |
| **inferred-low** | Pattern with weaker evidence | 6 (lowest) |

When claims conflict, higher authority wins. When authority is equal, more specific scope wins.

### Freshness model

Time-based expiry (default: 90 days) is the fallback, not the primary freshness mechanism.

| Trigger | Action |
|---|---|
| **Evidence file changed** | Claim flagged for revalidation; confidence reduced until revalidated |
| **Branch divergence** | Claims validated against evidence on the current branch, not just default branch |
| **Convention-violating code merged** | Claim flagged as potentially stale, surfaced in conflicts |
| **Managed artifact drift** | Projected file manually edited outside RKP — claim flagged for reconciliation |
| **Human re-approval** | Freshness reset |
| **Time-based expiry** | After configurable window (default 90 days) with no revalidation trigger, claim marked stale |

### Review states

| State | Meaning |
|---|---|
| **unreviewed** | Machine-generated, not yet seen by human |
| **needs-declaration** | The system detected information it cannot infer confidently and is prompting the human to declare it (e.g., "which Python version is canonical — 3.11 or 3.12?") |
| **approved** | Human confirmed accuracy |
| **edited** | Human modified content; provenance chain preserved |
| **suppressed** | Hidden from outputs; evidence retained for audit |
| **tombstoned** | Soft-deleted; evidence retained for audit trail. Hard deletion requires explicit `rkp purge` command with confirmation |

Note: there is no hard "delete" by default. For audit trail integrity and regulated environment support, suppressed and tombstoned claims retain their evidence chain. `rkp purge` exists for GDPR/data-removal requirements with explicit confirmation and audit logging of the purge itself.

---

## 8. MVP Scope (0-6 months)

### What ships (P0)

| Capability | Description |
|---|---|
| **Local indexing** | Persistent repo indexing from working tree + git history; tree-sitter parsing for supported languages; SQLite persistence; in-memory graph for fast queries; incremental updates; branch-aware (indexes against current branch, not just default) |
| **Convention synthesis** | Combines declared signals (AGENTS.md, README, lint/test config, docs) and inferred signals (naming patterns, test placement, import boundaries, error idioms). Declared and inferred remain separate with explicit source authority |
| **Environment prerequisite extraction** | For each discovered command: extract required runtimes, tools, services, env vars, OS assumptions, and network requirements from config files, CI definitions, Dockerfiles, and README |
| **Validated command discovery** | Discover build, test, lint, format commands from config files and CI definitions. Report evidence level and risk class per command (see §8.1) |
| **CI config evidence** | Parse CI definitions (GitHub Actions workflows, common CI configs) to extract: which commands are run, in what environments, with what services and runtimes. This is passive analysis (reading config files, not calling CI APIs or executing commands) and provides evidence for command validation and prerequisite extraction |
| **Import from existing instruction files** | `rkp import` reads existing AGENTS.md, CLAUDE.md, copilot-instructions.md, .cursor/rules, copilot-setup-steps.yml. Parses rules, commands, conventions, and environment requirements. Creates declared-policy claims with the original file as evidence. Presents imported claims for review using the same workflow as extraction. Surfaces conflicts between imported files and extracted evidence |
| **Thin instruction projection** | Generate deliberately thin always-on instruction artifacts. Only non-inferable, high-confidence, frequently-relevant rules. Detailed procedures flagged for skill projection or on-demand query. Applicability-aware: claims surfaced based on scope, relevance tags, and host capabilities |
| **Skill/playbook projection** | For hosts that support skills (Claude Code, Copilot, Codex): project detailed procedures and validation workflows as host-native skills. For other hosts: surface via MCP query |
| **Guardrail projection** | Security-sensitive operations projected as enforceable permission/tool restrictions where host supports them (Claude Code permissions, Copilot agent tool config). Advisory text for hosts without enforcement |
| **Host capability matrix** | Model the full agent configuration surface per host: always-on rules, scoped rules, skills, environment config, permissions, size constraints. Project faithfully per host with explicit adapter maturity tiers |
| **Coarse module mapping** | Top-level module/package detection, path-to-module mapping, import-based dependency edges within the support envelope. Tied to actionable context: scoped rules, test locations, valid commands per module |
| **Drift detection** | Detect when projected instruction files or skills have been manually edited outside of RKP. `rkp status` reports discrepancies. Options: absorb the manual edit (update the claim), reject it (regenerate the file), or suppress the claim. Also detects new instruction files that appeared outside of RKP management |
| **Correction and governance** | Human can approve, edit, suppress, or tombstone any claim. Override workflow for bad inferences. Evidence-triggered + branch-aware + drift-aware stale-claim revalidation. Audit trail |
| **Version-controlled human decisions** | Checked-in `.rkp/` directory containing RKP configuration and durable human decisions (overrides, suppressions, declarations). Team-shareable across machines. Local working state (index, evidence cache) stored in a local-only database, regenerable from repo + `.rkp/` |
| **MCP server** | Stable surface of tools (primary) and resources via MCP stdio transport |
| **Provenance** | Source authority, timestamp, extraction version, confidence, freshness basis, applicability, sensitivity, and review state on every claim |
| **Execution policy** | Passive-analysis mode (default) and opt-in active-verification mode. See §8.2 |
| **Quality harness** | Built-in measurement that RKP context is correct, safe, and useful. See §8.3 |

### 8.1 Validated command evidence levels

"Validated" is not binary. Commands accumulate evidence from multiple sources:

| Level | Meaning | How achieved |
|---|---|---|
| **discovered** | Found in a config file (package.json, Makefile, pyproject.toml) | Static parsing |
| **prerequisites-extracted** | Required runtimes, tools, services, env vars identified | Cross-referencing config, Dockerfiles, README |
| **ci-evidenced** | Command observed in CI configuration with environment details (runtimes, services, OS) | Parsing CI definitions (GitHub Actions, etc.) |
| **environment-profiled** | Full environment contract assembled from all available sources | Aggregation of prerequisite sources + CI evidence |
| **sandbox-verified** | Command executed successfully in an isolated environment | Opt-in active mode: sandboxed execution (container/worktree). Only with explicit human consent |

P0 ships levels 1-4 (discovery through environment profiling, including CI evidence) for all discovered commands. Level 5 (sandbox verification) is opt-in with explicit consent per-command.

### 8.2 Execution policy

The product wants to verify that build/test/lint commands actually work. But verification means executing arbitrary repo code. This requires an explicit trust model.

| Mode | Description | Default |
|---|---|---|
| **Passive analysis** | Only static parsing and cross-referencing. No command execution. No side effects. Includes CI config parsing. | **Default** |
| **Active verification** | Execute discovered commands in sandboxed isolation. Requires explicit opt-in per command category. | Opt-in |

Active verification controls:

| Control | Description |
|---|---|
| **Per-category consent** | User explicitly opts in to verifying build, test, lint, or format commands separately |
| **Risk-class gating** | Only commands classified as `safe-readonly` or `safe-mutating` are eligible by default. Higher risk classes require explicit per-command approval |
| **Sandbox isolation** | Commands run in a container or clean worktree, never in the user's working tree |
| **Secret/network controls** | No access to user secrets or network by default. Configurable allowlists |
| **Source trust levels** | Only commands from trusted sources (package.json scripts, Makefile targets, CI config) are eligible for execution. Arbitrary scripts require explicit approval |
| **Timeout and resource limits** | Execution capped by time and resource usage |
| **Evidence recording** | Execution result (success/failure, output, duration) recorded as claim evidence |

_Assumption [A11]: Most MVP value comes from passive analysis (levels 1-4). Active verification is a differentiator but must not be required for basic functionality._

### 8.3 Quality harness and measurement

If the product alters what agents see before they act, you must measure whether it helps or harms. The quality harness ships with MVP. Task success measurement is a design-partner research program, not a productized A/B system.

**Quality harness (ships in product):**

| Component | What it tests | Method |
|---|---|---|
| **Fixture repos** | Does RKP extract correctly on known codebases with known-good answers? | Curated test repos with expected claims. Extraction precision/recall measured per fixture |
| **Export conformance** | Is the projected instruction file / skill faithful to the canonical model for each host? | Automated round-trip validation per adapter |
| **Leakage tests** | Do `team-only` or `local-only` claims leak into public exports? | Automated check on every projection |
| **Drift tests** | Does drift detection correctly identify manual edits to managed artifacts? | Fixture repos with known edits |
| **Extraction precision** | How often are inferred claims correct? | Sampled evaluation by pilot tech leads |
| **Import fidelity** | Do imported instruction files round-trip correctly? | Import existing files, re-export, diff |

**Product metrics (tracked in product):**

| Metric | What it measures | Method |
|---|---|---|
| **Correction burden** | How much human effort is needed to fix RKP output? | Track corrections / total claims over time |
| **Bad-instruction rate** | How often does RKP-generated guidance lead to incorrect agent behavior? | Sampled evaluation by pilot tech leads |
| **Command evidence precision** | Do discovered commands actually work? | CI evidence cross-reference; sandbox verification where opted in; manual spot-check where not |
| **Token/runtime overhead** | Does RKP context increase agent inference cost? | Measure token count and response time with/without RKP |

**Trace capture infrastructure:**
- MCP server logs queries, responses, and timestamps
- Design-partner agents optionally capture task outcome (success/failure/correction) associated with RKP query context
- Traces are local-only by default; opt-in anonymized sharing for aggregate analysis

**Design-partner evaluation program (not productized):**
- Task success delta (with vs without RKP context) measured through design-partner studies on real tasks
- Studies run with design partners willing to do controlled comparisons
- Results inform product iteration but are not a productized metric in MVP

### What is explicitly deferred

| Deferred capability | Why deferred | Phase |
|---|---|---|
| Impact graphs for diffs | Requires reliable semantic dependency edges beyond tree-sitter syntax extraction; too aggressive for P0 | Phase 2 |
| Test recommendation | Infeasible at useful precision without runtime coverage or CI outcome data | Phase 2-3 |
| Reviewer recommendation | GitHub already has suggested reviewers + CODEOWNERS; weak differentiation | Cut from MVP |
| Composite risk score | Uncalibrated scores risk trust collapse | Phase 3-4 |
| Cloud/remote managed MCP serving | Requires managed service, not just local daemon. But core data model is remote-ready. Hosted agents are served via checked-in projected artifacts | Phase 2+ |
| Multi-repo graph federation | Enterprise feature | Phase 3+ |
| CI outcome ingestion | Ingesting CI _results_ (pass/fail/flaky) enables impact/test features but adds API integration complexity to MVP. CI _config_ parsing is P0 | Phase 2 |
| Vector/semantic search | Initial value is structural understanding, not semantic retrieval | Phase 2+ |
| Autonomous code modification | Must never modify code based on inferred rules | Never (P0 constraint) |
| Deep cross-language semantics | Requires compiler/LSP/SCIP integration per language | Phase 2+ (per language) |
| Merge gating | High-stakes pass/fail decisions require calibration trust | Phase 4 |
| Change coupling / temporal analysis | Valuable but requires grounding in outcomes or well-defined coupling models before it's trustworthy | Phase 3 |
| Public plugin/extension marketplace | Security story for third-party extensions is immature (2026 studies found widespread vulnerability and malicious-skill problems). Internal adapter architecture for parsers and exporters only. Host-native skill/workflow export is fine; public installable extension distribution is not | Never for MVP; reassess post-launch |

### Core user flows

**Flow 1 — Repository bootstrap (new repo):**
Tech lead runs `uvx repo-knowledge-plane init`. Product analyzes the repo within the support envelope. Presents a draft: thin always-on rules, scoped rules, and skills/playbooks separated. Low-confidence items and declaration prompts flagged. Tech lead approves, edits, or suppresses individual claims. Approved artifacts are written (instruction files, skills where host supports them). `.rkp/` directory created with config and human decisions. MCP server starts.

**Flow 2 — Repository bootstrap (existing instruction files):**
Tech lead runs `rkp import` on a repo that already has AGENTS.md, CLAUDE.md, etc. RKP ingests these as declared-policy claims, runs extraction to find additional evidence and gaps, surfaces conflicts between imported files and extracted evidence, and presents a unified review. On approval, projected files are updated and `.rkp/` captures the human decisions.

**Flow 3 — Agent preflight:**
Before editing code in a scope, agent calls `get_conventions` or `get_module_info` via MCP. Receives repo-specific constraints, prerequisite info, scoped rules, and guardrails without the user pasting them into a prompt.

**Flow 4 — Convention review and correction:**
Tech lead reviews inferred claims periodically. Suppresses incorrect inferences. Adds declared rules the product missed. Responds to declaration prompts. Corrections persist and improve future synthesis. Evidence-triggered alerts surface claims that need re-review.

**Flow 5 — Instruction refresh:**
After significant codebase changes, tech lead runs `preview_instruction_update`. Reviews a diff of what changed in the canonical model. Approves updates to instruction artifacts and skills.

**Flow 6 — Drift reconciliation:**
`rkp status` reports that AGENTS.md was manually edited (a teammate added a rule directly). Tech lead reviews the drift, chooses to absorb the edit (creating a new declared-policy claim) or regenerate the file from the canonical model.

---

## 9. MCP Surface

### Design principles

1. **Tools-first.** Every critical read must be available as a tool, not only as a resource. This ensures compatibility with all MCP hosts, including Copilot coding agent (tools-only).
2. **No write operations as MCP tools.** Instruction file generation is preview-only in MCP. File writes require a human-reviewed apply step in the CLI.
3. **Provenance on every response.** Index version, repo HEAD, generation timestamp, confidence, source authority, applicability, sensitivity, review state.
4. **Graceful degradation.** If a query touches areas outside the support envelope, the response says so explicitly rather than fabricating confidence.

### Tools (primary surface)

| Tool | Parameters | Purpose |
|---|---|---|
| `get_conventions` | `path_or_symbol`, `include_evidence`, `task_context` | Return relevant rules for a path, symbol, or module. Source authority and confidence included. Optional `task_context` (e.g., "testing", "refactoring") for applicability filtering |
| `get_module_info` | `path_or_symbol` | Module boundaries, dependencies, ownership hints, test locations, related paths, applicable scoped rules |
| `get_prerequisites` | `command_or_scope` | Environment prerequisites for a command or scope: runtimes, tools, services, env vars, OS, evidence level |
| `get_validated_commands` | `scope` | Build, test, lint, format commands with source, evidence level, risk class, and prerequisite summary |
| `get_repo_overview` | — | Languages, build/test entrypoints, module map, indexing status, support envelope coverage |
| `get_instruction_preview` | `consumer` | Preview what would be projected for a target consumer (`agents-md`, `copilot`, `cursor`, `claude`) including instruction files AND skills/playbooks |
| `get_guardrails` | `path_or_scope` | Security-sensitive operations, permission restrictions, tool constraints. Enforceable where host supports; advisory where not |
| `get_conflicts` | `path_or_scope` | Declared-vs-inferred conflicts, stale claims, suppressed inferences, drift discrepancies |
| `get_claim` | `claim_id` | Full detail on a single claim: content, evidence chain, review history, freshness |
| `refresh_index` | `paths` | Incrementally update knowledge after file changes |

### Resources (supplementary — not available on all hosts)

| URI | Purpose |
|---|---|
| `rkp://repo/overview` | Languages, build/test entrypoints, module map, indexing status |
| `rkp://repo/conventions` | Full convention set with confidence and evidence |
| `rkp://repo/conventions/{path}` | Path-scoped conventions |
| `rkp://repo/instructions/{consumer}` | Synthesized instruction content for a target consumer |
| `rkp://repo/architecture/modules` | Module and boundary summary with dependency hints |
| `rkp://repo/prerequisites` | Full environment prerequisite summary |

### CLI-only operations (not exposed via MCP)

| Command | Purpose |
|---|---|
| `rkp init` | Bootstrap: analyze repo, present draft for review, write approved artifacts, create `.rkp/` |
| `rkp import` | Ingest existing instruction files as declared-policy claims; surface conflicts with extracted evidence |
| `rkp review` | Interactive review of claims: approve, edit, suppress, tombstone, respond to declaration prompts |
| `rkp apply` | Write approved instruction artifacts and skills to disk after human review |
| `rkp refresh` | Re-analyze and present diff of what changed |
| `rkp status` | Show index health, staleness, support envelope coverage, correction stats, drift report |
| `rkp verify` | Opt-in: run sandbox verification of discovered commands |
| `rkp audit` | Query the audit trail for a claim or scope |
| `rkp purge` | Hard-delete tombstoned claims (for data removal requirements); requires confirmation and logs the purge |

### Example: get_conventions

```json
// Request
{ "tool": "get_conventions",
  "arguments": { "path_or_symbol": "src/payments", "include_evidence": true, "task_context": "testing" } }

// Response
{
  "scope": "src/payments",
  "task_context": "testing",
  "claims": [
    { "id": "claim-001",
      "content": "Do not call payment providers directly from API handlers",
      "claim_type": "always-on-rule",
      "source_authority": "declared-policy",
      "source": "docs/architecture.md",
      "confidence": 1.0,
      "applicability": ["all"],
      "review_state": "approved",
      "freshness": { "last_validated": "2026-03-15", "trigger": "evidence-file-unchanged" }
    },
    { "id": "claim-042",
      "content": "Provider adapters live under src/payments/providers/*",
      "claim_type": "scoped-rule",
      "source_authority": "inferred-high",
      "confidence": 0.89,
      "applicability": ["all"],
      "evidence": ["src/payments/providers/stripe.py", "src/payments/providers/adyen.py"],
      "review_state": "unreviewed",
      "freshness": { "last_validated": "2026-03-17", "trigger": "evidence-files-unchanged" }
    },
    { "id": "claim-107",
      "content": "Payment tests require STRIPE_TEST_KEY env var and use pytest-mock for provider isolation",
      "claim_type": "scoped-rule",
      "source_authority": "ci-observed",
      "confidence": 0.95,
      "applicability": ["testing"],
      "evidence": [".github/workflows/test.yml", "tests/payments/conftest.py"],
      "review_state": "approved",
      "freshness": { "last_validated": "2026-03-17", "trigger": "evidence-files-unchanged" }
    }
  ],
  "conflicts": [],
  "envelope_coverage": "full",
  "provenance": { "index_version": "2026-03-17T18:22:00Z", "repo_head": "abc1234", "branch": "main" }
}
```

---

## 10. Host Capability Matrix & Adapter Maturity

Different agents have fundamentally different configuration surfaces. A shared internal model must project faithfully to each — including surfaces beyond instruction files.

### Host configuration surface model

| Primitive | Description |
|---|---|
| **Always-on rules** | Repo-wide conventions loaded every session |
| **Path-scoped rules** | Rules for specific directories or file patterns |
| **Nearest-override rules** | Rules resolved by file-system proximity (closest wins) |
| **Skills / playbooks** | Procedural workflows, multi-step recipes, detailed how-tos — loaded on demand, not always |
| **Environment / bootstrap** | Runtime, tool, service, and configuration requirements |
| **Permissions / restrictions** | Tool restrictions, sandbox requirements, security constraints |
| **Agent profile / subagent hints** | Configuration for agent behavior, delegation, tool selection |
| **On-demand context** | Context loaded per-query rather than always present |
| **Size constraints** | Max combined instruction size a host will accept |

### Projection by host

| Host | Always-on | Path-scoped | Skills | Environment | Permissions | Size constraint | Adapter maturity |
|---|---|---|---|---|---|---|---|
| **AGENTS.md** (Codex) | Root file | Directory-level files | Codex skills (Agent Skills standard) | AGENTS.md `setup` section | Advisory in rules | 32 KiB combined | **GA** |
| **CLAUDE.md** (Claude Code) | Root file | Directory-level files + .claude/rules/ | Claude Code skills (Agent Skills standard) | CLAUDE.md or skill | settings.json permissions, subagent config | Keep short (~200 lines) | **GA** |
| **Copilot** | copilot-instructions.md (also reads AGENTS.md + CLAUDE.md) | .instructions.md files | Copilot skills + custom agents | copilot-setup-steps.yml | Agent tool config, custom agent tool scoping | Unknown | **Beta** |
| **Cursor** | .cursor/rules | Path-scoped rules | N/A | Advisory in rules | N/A | Per-rule targeting | **Alpha (export)** |
| **Windsurf** | Rules | Path-scoped rules | Skills, manual workflows | Advisory in rules | Tool toggles/caps | Unknown | **Alpha (export)** |

**Adapter maturity definitions:**
- **GA**: Full projection + import + drift detection + conformance tests. Supported and maintained.
- **Beta**: Projection works and is tested, but conformance coverage is incomplete. Supported with known gaps documented.
- **Alpha (export)**: Export-only projection. Files are generated but not actively tested against the host's actual behavior. Community feedback drives promotion.

### Projection rules

1. Always-on rules → root instruction file for that host. **Keep thin**: only non-inferable, high-confidence, frequently-relevant claims with broad applicability. Research (ETH Zurich, Feb 2026) shows repository overviews specifically provide zero navigation reduction despite being universally included in LLM-generated files — omit them from always-on content
2. Path-scoped rules → host-specific scoped files where supported, annotations in root file where not
3. Detailed procedures and validation workflows → skills/playbooks where host supports them, on-demand MCP queries where not
4. Environment prerequisites → host-native environment config (copilot-setup-steps.yml, etc.) where supported, structured MCP response everywhere
5. Security guardrails → enforceable permissions/restrictions where host supports them, advisory text where not
6. Applicability filtering → claims with narrow applicability tags (e.g., `testing`, `ci`) go to skills or on-demand, not always-on files
7. Sensitivity filtering → `team-only` claims omitted from exports targeting public repos; `local-only` claims never projected to checked-in files
8. If projected content exceeds host size constraints, prioritize: human-override > declared-policy > high-confidence inferred > low-confidence inferred. Move overflow to skills or on-demand
9. Each projected file includes a generation header with provenance and a "do not edit directly — corrections go through `rkp review`" notice
10. The canonical claim model is the source of truth; projected artifacts are derived

---

## 11. Governance and Correction (P0)

This is not optional polish. Once the product synthesizes context that agents use before they work, it becomes part memory layer, part policy layer. Governance ships at launch.

### Correction workflow

| Action | Description | Available in |
|---|---|---|
| **Approve** | Mark a claim as human-verified | CLI (`rkp review`), future: App UI |
| **Edit** | Modify a claim's content while preserving provenance chain | CLI |
| **Suppress** | Hide a claim from all outputs; evidence retained for audit | CLI |
| **Tombstone** | Soft-delete a claim; evidence retained for audit trail | CLI |
| **Declare** | Add a new declared rule that the product didn't discover | CLI |
| **Respond to declaration prompt** | Answer a question the system could not resolve by inference (e.g., "canonical Python version is 3.12") | CLI |
| **Purge** | Hard-delete tombstoned claims (for data removal requirements); requires confirmation, logged | CLI |

### Import workflow

`rkp import` reads existing instruction files and creates claims:

1. Parse each file for rules, commands, conventions, and environment requirements
2. Create claims with source_authority: `declared-policy` and the original file as evidence
3. Run extraction in parallel to find additional evidence and gaps
4. Surface conflicts between imported claims and extracted evidence (e.g., imported rule says "use pytest" but extracted evidence shows mocha in test config)
5. Present unified review: imported claims, extracted claims, and conflicts
6. On approval, the imported file's content is governed by RKP — future projections will include it

Supported import sources: AGENTS.md, CLAUDE.md, copilot-instructions.md, .cursor/rules, copilot-setup-steps.yml.

### Drift detection

RKP tracks the expected content of every managed artifact (instruction file, skill, environment config). `rkp status` detects:

- **Content drift**: A managed file was manually edited (content differs from what RKP would generate)
- **New unmanaged files**: An instruction file appeared that RKP didn't create (e.g., someone added .cursor/rules manually)
- **Missing files**: A managed file was deleted

For each drift instance, the user can:
- **Absorb**: Update the canonical model to match the manual edit (creates a declared-policy claim)
- **Reject**: Regenerate the managed file from the canonical model
- **Suppress**: Stop managing that specific artifact

### Instruction file safety

- **No instruction file is written without human review.** The MCP surface exposes previews; the CLI exposes `apply` after review.
- Instruction file writes produce a diff for review, not a silent overwrite.
- Generated files include a provenance header linking to evidence.
- Skill/playbook generation follows the same review-then-apply workflow.

### Version-controlled human decisions

Human decisions are the durable part of the product's state. They are stored in a checked-in `.rkp/` directory:

| Path | Contents | Checked in? |
|---|---|---|
| `.rkp/config.yaml` | RKP configuration: support envelope, thresholds, adapter settings, execution policy | Yes |
| `.rkp/overrides/` | Human declarations, suppressions, edits — the durable human decisions | Yes |
| `.rkp/local/` | SQLite database (index, full claim model, evidence cache, history) | No (`.gitignore`'d) |

The local database is a working cache — regenerable from the repository + `.rkp/` human decisions. When a new team member clones and runs `rkp init`, RKP reindexes the repo but loads existing human decisions from `.rkp/overrides/`, producing the same approved/suppressed claims.

### Stale-claim revalidation

Primary mechanism: **evidence-triggered, branch-aware, and drift-aware revalidation**.

- When a claim's evidence changes (file modified, config updated, convention-violating code merged), the claim is flagged for revalidation.
- Claims are validated against evidence on the **current branch**, not just the default branch.
- When managed artifacts are manually edited, affected claims are flagged for reconciliation.
- Stale claims are downgraded in confidence and surfaced in `get_conflicts`.
- Time-based expiry (configurable, default: 90 days) is the fallback for claims whose evidence hasn't been touched but may still be outdated.

### Audit trail

- Every claim records: source authority, what evidence produced it, when, by which extraction version, and any human actions taken (approve, edit, suppress, tombstone, purge).
- Audit trail is queryable via CLI (`rkp audit`).
- For regulated environments: tombstone + audit trail is the default. Hard deletion (`rkp purge`) is explicit, requires confirmation, and is itself audit-logged.

### Trust boundaries

- MCP tools are read-only by default. No tool modifies files, configuration, or repository state.
- The product never modifies code based on inferred rules.
- Source allowlists: configurable list of which file types, directories, and signal sources may influence generated instructions.
- **Execution boundary**: When active verification is enabled, command execution is sandboxed and never runs in the user's working tree. See §8.2.
- **Sensitivity boundary**: Claims marked `team-only` or `local-only` are filtered from public exports. See §7 claim schema.
- **Data boundary**: RKP itself keeps all data local by default. However, data queried through MCP and consumed by host agents follows those agents' own retention and transmission policies. This boundary is documented clearly, not hidden.

---

## 12. Identity Model

The data model does not assume one repo, one worktree, one session, one machine. These identities are first-class:

| Identity | Description | Why first-class |
|---|---|---|
| **Repo identity** | Unique repository (by remote URL or local path) | Multiple repos may share an RKP instance in future |
| **Branch identity** | Which branch claims are validated against | Claims may differ by branch; evidence freshness is branch-aware |
| **Worktree identity** | Which worktree the index was built from | Multiple worktrees of the same repo should not corrupt each other |
| **Session identity** | A logical agent work session | Eval traces and query context need session scoping |

For MVP, the common case is: one repo, one worktree, one session at a time. But the data model carries these identities from day one so that multi-worktree, multi-branch, and eventually remote deployment are operational changes, not schema migrations.

---

## 13. Architecture & Technical Constraints

### Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.12+ | Ecosystem leverage, fast iteration, statistical modeling path |
| MCP serving | FastMCP (Python MCP SDK) | Best agent host compatibility; Streamable HTTP support for future remote |
| Parsing | tree-sitter + `tree-sitter-language-pack` | Incremental, broad coverage, no build required |
| Git analysis | pygit2 | High-throughput local git operations |
| Graph algorithms | rustworkx | Compiled performance for traversals and coupling |
| Persistence | SQLite (WAL mode) | Simple distribution, low idle cost, sufficient for single-repo |
| Transport | MCP stdio (first) | Least operational complexity; Streamable HTTP path via FastMCP when needed |
| Distribution | `uvx` | Zero-dependency adoption path |
| Sandbox (active verify) | Container (podman/docker) or clean git worktree | Isolation for command verification |

### Key decisions

| Decision | Rationale |
|---|---|
| Local-first over cloud-first | Security trust, zero-infra adoption, works in sensitive repos |
| SQLite + in-memory graph over standalone graph DB | Simpler distribution, lower idle cost; query profile is short traversals |
| Incremental re-analysis over full re-index | Required to meet latency targets in active repos |
| Vector search deferred | Initial value is structural understanding, not semantic retrieval |
| Provenance and source authority mandatory on all claims | Part of the contract, not an implementation detail |
| Heuristic signals before ML scoring | Interpretable, debuggable, achievable without outcome training data |
| Tree-sitter is syntax, not semantics | Reliable for convention mining, module detection, import structure. Not sufficient for cross-file type resolution or call-graph completeness. Optional LSP/SCIP enrichment path for Phase 2+ |
| Tools-first MCP surface | Ensures compatibility with all hosts including tools-only hosts (Copilot coding agent) |
| No MCP write operations | Instruction file writes require human-reviewed CLI apply step |
| Passive analysis by default | Active verification (command execution) is opt-in with explicit consent |
| Identity-aware data model from day one | Avoids rewrite when adding branch/worktree/remote support |
| Quality harness ships with MVP | Cannot wait to measure whether the product helps or harms |
| CI config parsing is passive analysis | Reading CI definitions for evidence is not executing commands or calling APIs |
| `.rkp/` directory checked in | Human decisions are version-controlled and team-shareable. Local working state is regenerable |

### Semantic analysis: what tree-sitter can and cannot do

| Capability | Tree-sitter | Compiler/LSP/SCIP (Phase 2+) |
|---|---|---|
| File structure, symbol names, imports | Yes | Yes |
| Naming convention patterns | Yes | Yes |
| Test file location patterns | Yes | Yes |
| Import-based module dependencies | Yes (syntactic) | Yes (semantic) |
| Cross-file type resolution | No | Yes |
| Call-graph completeness | No | Yes |
| Build-tool-aware dependency graph | No | Yes |
| Runtime coverage mapping | No | Requires CI integration |

The product is honest about what tree-sitter provides. Within the launch envelope (Python + JS/TS), import-based dependency detection is reliable enough for coarse module mapping. For deeper semantic analysis, optional enrichment paths (LSP, SCIP indexers, coverage data) are Phase 2+.

### Performance targets

| Target | Value |
|---|---|
| Warm MCP query latency | < 500ms median for top-5 query types |
| Initial index (250k LOC repo, supported languages) | < 5 minutes |
| Incremental update (single file change) | < 2 seconds |
| Memory footprint (idle server) | < 200MB |

_Assumption [A5]: SQLite + in-memory graph sufficient for first year of single-repo use. If pilot repos exceed bounds, Rust core acceleration moves forward sooner._

---

## 14. Phased Roadmap

| Phase | Timeframe | Focus | Key unlock |
|---|---|---|---|
| **1. Verified context + faithful projection + quality harness** | Months 0-3 | Local indexing, convention extraction, prerequisite extraction, CI config evidence, validated commands (levels 1-4), thin instruction projection, skill/playbook projection, guardrail projection, import, drift detection, correction workflow, `.rkp/` version-controlled config, MCP tools, quality harness, trace capture | First useful output; cross-agent distribution; measurable quality from day one |
| **2. Active verification + cloud deployment + semantic enrichment** | Months 3-6 | Sandbox command verification (level 5), optional LSP/SCIP enrichment, deeper dependency edges, CI outcome ingestion (pass/fail/flaky), remote/managed deployment via Streamable HTTP, Copilot adapter GA promotion | Verified commands; broader agent reach; semantic accuracy |
| **3. Behavioral layer** | Months 6-9 | Git history mining: hotspots, change coupling (grounded in CodeScene-style temporal coupling), contributor concentration. Path history with outcomes. Runtime data ingestion (coverage, test outcomes) | Longitudinal intelligence beyond snapshot; moat data |
| **4. Risk scoring & advanced eval** | Months 9-12 | Calibrated risk scores, outcome feedback loop, task success evaluation from accumulated design-partner data, test recommendation with precision targets | Trustworthy forward-looking risk; measurable improvement loops |

### Phase 1 exit criteria

All P0 acceptance criteria met. 3+ design partners using the product with at least one agent (GA adapter). Import workflow exercised on at least 2 repos with existing instruction files. Correction workflow exercised. Quality harness passing on all fixture repos. Trace capture producing correction burden and bad-instruction rate measurements. Instruction artifacts accepted after review by 70%+ of partners.

### Phase 2 prerequisites

- Design-partner signal on which languages to add next
- At least one design partner willing to share CI outcome data (beyond CI config)
- Clear demand signal for cloud agent support (from which partners, which agents)
- Phase 1 quality harness passing; correction rate declining

---

## 15. Success Metrics

### 90-day (activation, trust, and quality) — leading indicators

| Metric | Target | Measurement |
|---|---|---|
| Time to first useful output | < 5 min median | Instrumented from `init` to first approved artifact |
| Instruction artifact acceptance | ≥ 70% accept with light edits | Manual review in design-partner cohort |
| Convention query accuracy | ≥ 80% correct in spot checks | Sampled evaluation by pilot tech leads |
| Bad-instruction rate | < 10% of projected claims lead to incorrect agent behavior | Sampled evaluation by pilot tech leads |
| Command evidence precision | ≥ 90% of discovered commands are actually valid | CI evidence cross-reference + manual spot-check |
| Export conformance | ≥ 95% of projected instructions are faithful to canonical model | Quality harness automated round-trip validation |
| Import fidelity | ≥ 90% of imported rules round-trip correctly | Quality harness import-export diff |
| Correction rate per inferred claim | Declining trend after first review cycle | Track corrections / total inferred claims over time |
| Token overhead | < 15% increase in agent token usage with RKP context | Measure with/without RKP on identical tasks |
| Agent preflight query adoption | ≥ 3 sessions/repo/week using RKP tools | MCP server call logs |

### 6-month (workflow impact) — attributable indicators

| Metric | Target | Measurement |
|---|---|---|
| PR review iteration reduction | 10-15% vs baseline | Pilot repos, normalized for volume |
| Onboarding time reduction | ≥ 25% to first accepted PR | New contributor cohort in pilot repos |
| Usefulness by supported ecosystem | ≥ 80% of supported-language queries rated useful | Partner feedback |
| Multi-agent usage | ≥ 30% of installs use 2+ agents with RKP | Connection telemetry |
| Task success delta | Positive signal from design-partner studies | Controlled with/without comparisons (design-partner program, not productized) |

### What we explicitly do NOT promise at 6 months

- Test recommendation precision (no runtime data yet)
- Regression prediction (no calibration data yet)
- System-level DORA metric improvements (not attributable at this stage)
- Statistically significant task success delta (sample size too small; directional signal is the goal)

### 12-month (system improvement) — outcome metrics

| Metric | Target | Measurement |
|---|---|---|
| Escaped regression reduction | ≥ 15% vs pre-adoption baseline | Pilot repos with CI outcome tracking |
| PR cycle time reduction | ≥ 20% for AI-assisted changes | Open to merge, end-to-end |
| Test recommendation precision | ≥ 0.70 | Requires Phase 3 runtime data ingestion |
| Agent task quality lift | ≥ 15% first-pass acceptance | Controlled with/without RKP (accumulated design-partner data) |

---

## 16. Competitive Landscape

### Honest positioning

"Shared intelligence layer" alone is not a moat in March 2026. Sourcegraph 7.0 explicitly calls itself "the intelligence layer for developers and AI agents." Potpie positions itself as "codebase-to-knowledge-graph infrastructure for agents" ($2.2M pre-seed, Feb 2026). The differentiation must be more specific.

**RKP's specific differentiation: evidence-backed extraction with source authority, relevance-aware thin-by-default instruction projection, host-native skill/guardrail projection, import-and-reconcile for existing instruction files, human governance with version-controlled decisions, environment prerequisite modeling with CI evidence, adapter maturity tiers for honest cross-host support, and measurable quality harness.**

| Competitor | Strength | Where RKP differentiates |
|---|---|---|
| **GitHub / Copilot** | Platform integration, 20M users, Copilot Memory, copilot-setup-steps.yml | Copilot context is GitHub-locked; no cross-agent neutrality. Memory is auto-managed, not human-governed. No portability |
| **Sourcegraph / Amp** | Semantic graph (SCIP), cross-repo search, MCP server | Static references only — no behavioral signals, no convention synthesis, no instruction projection. Dropped Cody Free/Pro; Amp is their own agent, not neutral substrate |
| **Cursor** | IDE-native context, fast iteration | Intelligence is a Cursor advantage, not portable. .cursor/rules is Cursor-only |
| **CodeScene** | Proven behavioral methodology (hotspots, temporal coupling) | Retrospective, human-dashboard oriented. Not real-time agent consumption. No MCP. No instruction synthesis |
| **Devin / Cognition** | Strong product-native memory, DeepWiki | Memory is Devin-scoped. DeepWiki is wiki-format for humans, not structured for agent injection |
| **Potpie** | Code knowledge graphs, AGENTS.md generation | Not MCP-native. Own agent suite. No behavioral signals. No correction/governance. No skill projection |

### False moats (table stakes)

- Having a graph database
- Having embeddings
- Having an MCP server
- Having a wiki/doc generator
- Raw AGENTS.md file generation
- "Intelligence layer" branding

### Real moats (compound over time)

1. **Longitudinal private repo data** — what happened after changes, accumulated over months
2. **Evidence graph quality** — linking conventions, boundaries, history, and outcomes correctly
3. **Governance and correction** — the product that earns correction feedback has the most accurate model
4. **Cross-agent neutrality** — switching cost rises as knowledge plane becomes shared substrate
5. **Quality-driven trust** — measurable proof from the quality harness that the context helps, not just vibes
6. **Host-native projection quality** — faithful, relevance-aware projection to instruction files, skills, guardrails, and environment configs per host
7. **Import-and-reconcile** — the product that meets teams where they are (existing instruction files) and governs them earns the right to be the single source of truth

---

## 17. Go-to-Market & Pricing

**Distribution:** Open-source core via `uvx`. MCP registry listing for agent ecosystem discoverability. Used _from within_ existing tools.

**Viral artifact:** Generated instruction files and skills — visible in-repo, useful to anyone, naturally attributable. But the product value is the verified substrate and faithful projection, not the artifact.

**Adoption loop:** Tech lead installs locally → imports existing instruction files → reviews and approves enriched artifacts → team sees value from better agent behavior → quality harness confirms improvement → platform team standardizes → organization purchases.

| Tier | Price | Includes |
|---|---|---|
| Individual (OSS) | Free | Full local analysis, synthesis, import, drift detection, MCP server, correction workflow, quality harness |
| Team | ~$20-35/active dev/month | Shared config, cross-member conventions, telemetry, team correction workflow |
| Enterprise | Custom | SSO, policy, audit, air-gapped, multi-repo admin, managed deployment for cloud agents |

"Active dev" = committed in last 90 days.

Pitch: not "pay for more AI" but "infrastructure that makes AI tools you already bought safer and more effective — and proves it with quality data."

_Assumption [A6]: If local-first usage alone captures most value, monetization leans on coordination, governance, and evaluation features._

---

## 18. Risks & Mitigations

| Risk | Category | Mitigation |
|---|---|---|
| Polyglot parsing quality inconsistent | Technical | Explicit launch support envelope; surface unsupported areas; parser quality scoring |
| Inferred conventions wrong but sound authoritative | Technical/Trust | Source authority hierarchy; correction workflow as P0; confidence thresholds; "needs confirmation" flag; quality harness measures bad-instruction rate |
| Cold start on sparse-history repos | Technical | First wedge valuable from current snapshot alone; history signals added opportunistically |
| Large repos exceed performance targets | Technical | Incremental indexing; warm graph; Rust acceleration path; scope filters |
| Provenance gaps or stale data | Technical | Evidence-triggered + branch-aware + drift-aware revalidation; version every extraction; timestamp every resource; prefer incomplete-but-current |
| Tree-sitter insufficient for promised analysis | Technical | Honest about what tree-sitter provides; optional LSP/SCIP enrichment; don't promise compiler-grade accuracy |
| CI config diversity exceeds parser coverage | Technical | Start with GitHub Actions (most common); degrade gracefully for unsupported CI systems; CI evidence is additive, not required |
| Dismissed as "just an AGENTS.md generator" | Product | Instruction files are one delivery surface; differentiate on evidence-backed extraction, import/reconcile, skill projection, correction, quality harness, and cross-host projection |
| Overlap blur with Sourcegraph/Potpie | Product | Differentiate on behavioral signals, governance, skill/guardrail projection, import, and quality measurement — not on graph/search |
| Instruction artifacts reduce agent performance | Product | Thin-by-default; applicability-aware projection; skill projection for detailed content; quality harness measures task impact; allow suppression |
| Import creates false sense of governance | Product | Import workflow explicitly surfaces conflicts between imported files and extracted evidence; imported claims go through the same review process |
| Command verification executes malicious code | Security | Passive-by-default; explicit opt-in per category; risk-class gating; sandboxed execution; no secrets/network by default |
| MCP trust boundary exploited | Security | No write operations in MCP; read-only by default; source allowlists; audit trail |
| Sensitive information leaks into public exports | Security | Sensitivity field on claims; leakage tests in quality harness; `team-only` and `local-only` filtering |
| "No data leaves machine" claim misleading | Trust | Clarify boundary: RKP is local-only; host agents have their own retention policies; document explicitly |
| Buyer-user divergence | Commercial | Free tier for pull; governance as paid expansion |
| Incumbents absorb shallow features | Commercial | Accelerate toward longitudinal data, trust calibration, cross-agent neutrality, quality proof |

---

## 19. Acceptance Criteria (P0)

| # | Criterion |
|---|---|
| AC-1 | `uvx repo-knowledge-plane init` produces a non-template instruction artifact with repo-specific validated commands (with prerequisites and CI evidence where available), thin conventions, and module boundaries within 5 min on a 250k LOC Python repo |
| AC-2 | Generated content distinguishes claims by source authority level with evidence references, confidence scores, and applicability tags |
| AC-3 | MCP server starts via stdio and responds to all documented tool calls |
| AC-4 | `get_conventions` returns scoped conventions with source authority, confidence, evidence, applicability, and review state for a given path. Optional `task_context` parameter filters by applicability |
| AC-5 | `get_module_info` returns boundary, dependency, and test location info for a top-level module within the support envelope |
| AC-6 | `get_validated_commands` returns build/test/lint commands with source, evidence level, risk class, and prerequisite summary |
| AC-7 | `get_prerequisites` returns environment requirements (runtimes, tools, services, env vars) for a command or scope, including CI-derived evidence where available |
| AC-8 | `get_instruction_preview` returns faithful host-specific projection for GA adapters (AGENTS.md, CLAUDE.md) and beta adapter (copilot-instructions.md) — including skill/playbook projection where host supports it |
| AC-9 | `get_guardrails` returns security-sensitive operations with enforceable restrictions for hosts that support them |
| AC-10 | No instruction file or skill is written without human review and explicit approval via CLI |
| AC-11 | Correction workflow: user can approve, edit, suppress, tombstone claims, and respond to declaration prompts via `rkp review` |
| AC-12 | Incremental index update completes in < 2 seconds for a single-file change |
| AC-13 | All MCP responses include provenance (index version, repo HEAD, branch, timestamp, confidence, source authority, applicability, review state) |
| AC-14 | No repository content transmitted off the local machine by RKP itself; data boundary with host agents documented |
| AC-15 | Product runs without any cloud service dependency |
| AC-16 | Queries touching areas outside the support envelope return explicit "unsupported" status, not fabricated confidence |
| AC-17 | Audit trail records source authority, evidence, extraction version, and human corrections for each claim. Tombstoned claims retain evidence |
| AC-18 | Projected always-on instruction files are thin: only non-inferable, high-confidence, frequently-relevant claims with broad applicability. Detailed procedures project to skills or on-demand |
| AC-19 | Quality harness passes on all fixture repos: extraction precision, export conformance, leakage tests, drift tests, import fidelity |
| AC-20 | Claims are revalidated on evidence-change triggers, branch context, and managed-artifact drift — not just time-based expiry |
| AC-21 | `rkp import` ingests existing AGENTS.md and CLAUDE.md as declared-policy claims, surfaces conflicts with extracted evidence, and presents unified review |
| AC-22 | `rkp status` detects drift in managed instruction files (content changes, new unmanaged files, missing files) and reports discrepancies |
| AC-23 | `.rkp/` directory contains version-controlled config and human overrides; local working state is in `.rkp/local/` (gitignored) and regenerable |
| AC-24 | Claims carry `sensitivity` field; `team-only` and `local-only` claims are filtered from public exports. Leakage test in quality harness validates this |
| AC-25 | CI definitions (GitHub Actions) are parsed for command evidence and environment details as part of passive analysis |
| AC-26 | Trace capture infrastructure logs MCP queries, responses, and timestamps for evaluation purposes |

---

## 20. Assumptions Register

| ID | Assumption | Revisit trigger |
|---|---|---|
| A1 | Workstation agents sufficient for initial adoption | Design partners consistently need cloud agent support |
| A2 | Tech lead is the right MVP champion | Platform teams sponsor first in 5-10 design partners |
| A3 | "Under 5 min" achievable within launch support envelope | Empirical testing on diverse repos |
| A4 | Python + JS/TS covers majority of design-partner repos | Go or Java demand in first 5 partners |
| A5 | SQLite + in-memory graph sufficient for first year single-repo use | Pilot repos exceed memory/latency bounds |
| A6 | Free-local / paid-team boundary captures enough value | Local-only usage delivers most value |
| A7 | Convention synthesis is right first wedge over PR-risk scoring | Early users consistently ask for risk first |
| A8 | Teams accept generated instructions in review-then-apply mode | Pilot teams immediately want auto-commit |
| A9 | Tree-sitter provides sufficient extraction for convention mining in supported languages | Convention accuracy below threshold |
| A10 | MCP stdio is right first transport | Major agent hosts require HTTP before adoption |
| A11 | Most MVP value comes from passive analysis (levels 1-4) | Design partners consistently want sandbox verification before anything else |
| A12 | Thin-by-default instructions perform better than verbose ones | Quality harness data shows verbose instructions have higher task success |
| A13 | Skill/playbook projection adds value over instruction-file-only | Design partners don't use skill-capable hosts |
| A14 | Most repos with existing instruction files will benefit from import+enrich over start-from-scratch | Design partners prefer starting fresh |
| A15 | GitHub Actions is sufficient CI config coverage for launch | Design partners primarily use GitLab CI or other systems |
| A16 | Two GA adapters (Claude Code + Codex) are sufficient for initial adoption | Design partners primarily use beta/alpha hosts |

---

## 21. Decisions Log

### Decided

| # | Decision | Rationale |
|---|---|---|
| D1 | Verified operational context as initial wedge, not raw AGENTS.md generation | Adjacent scaffolding exists; differentiate on verified, governed, host-projected context |
| D2 | Tech lead + agent pair as MVP priority | Strongest pain, best validation authority, bottom-up adoption |
| D3 | Defer composite risk score, impact graphs, and test recommendation | Require runtime/CI data or semantic analysis beyond tree-sitter; premature inclusion damages trust |
| D4 | Platform team features (governance at fleet scale, multi-repo) are Phase 2+ | MVP governance is single-repo correction workflow |
| D5 | Tools-first MCP surface | Ensures compatibility with all hosts including tools-only (Copilot coding agent) |
| D6 | No MCP write operations | Instruction file writes require human-reviewed CLI apply step. Safety-critical design decision |
| D7 | Explicit launch support envelope | Python + JS/TS, ≤ 250k LOC, single build graph. Honest about limits rather than promising universal support |
| D8 | Correction/governance workflow is P0 | Product synthesizes instructions agents obey; governance is mandatory, not follow-on |
| D9 | Local/workstation agents are MVP deployment target; hosted agents served via checked-in artifacts | Cloud agents require managed deployment — Phase 2+. But projected artifacts serve hosted agents without a running server |
| D10 | Cut `recommend_reviewers` from MVP | GitHub suggested reviewers + CODEOWNERS already serve this; weak differentiation |
| D11 | Expand canonical model beyond instruction files | Agent behavior in 2026 is controlled by files + skills + environment + permissions + profiles. Model must cover the full surface for faithful projection |
| D12 | Thin-by-default, applicability-aware instruction projection | Research shows verbose context files can hurt agent performance. Always-on files carry only non-inferable, high-confidence, frequently-relevant rules with broad applicability. Narrow-applicability claims → skills or on-demand |
| D13 | Source authority hierarchy replaces binary declared/inferred | human-override > declared-policy > executable-config/ci-observed > checked-in-docs > inferred-high > inferred-low. Needed for precedence and conflict resolution |
| D14 | Evidence-triggered + branch-aware + drift-aware revalidation as primary freshness mechanism | 90-day time-based expiry is fallback only. Evidence changes, branch context, and managed-artifact drift are primary triggers |
| D15 | Tombstone by default, hard delete only via explicit purge | Audit trail integrity for regulated environments. Delete-and-audit is contradictory; tombstone-and-audit is consistent |
| D16 | Validated commands carry evidence levels and risk classification | "Validated" is not binary. Evidence levels: discovered → prerequisites-extracted → ci-evidenced → environment-profiled → sandbox-verified. Risk classes: safe-readonly through destructive. P0 ships levels 1-4; level 5 is opt-in |
| D17 | Passive analysis by default, active verification opt-in | Executing repo commands is arbitrary code execution. Requires explicit consent, sandbox isolation, and trust controls |
| D18 | Quality harness ships with MVP; task success measurement is design-partner research | Cannot wait to measure quality. But productized A/B task success at 90 days is not achievable with 3-5 design partners. Ship the harness and trace capture; run task success studies as a research program |
| D19 | Identity model (repo/branch/worktree/session) first-class from day one | Avoids data model rewrite for multi-worktree, multi-branch, and remote deployment |
| D20 | Cut `find_prior_changes` from MVP; replace with path history in Phase 3 | "Similar historical changes" is hard to make trustworthy without semantic grounding. Phase 3 adds grounded temporal coupling and path history with outcomes |
| D21 | Guardrail projection as a P0 capability | Security constraints should be enforceable where hosts support them (permissions, tool restrictions), not just advisory text |
| D22 | Target Agent Skills open standard for skill projection | Claude Code and Codex both support the Agent Skills standard (agentskills.io). Cross-platform skill format is emerging. Copilot does not yet support it but reads AGENTS.md and CLAUDE.md |
| D23 | Omit repository overviews from always-on instruction content | ETH Zurich study (Feb 2026): repository overviews provide zero reduction in agent navigation steps despite being in 100% of LLM-generated files. Overviews cause over-compliance without benefit |
| D24 | Import existing instruction files as P0 (`rkp import`) | Meets teams where they are. Most repos already have some instruction files. Import accelerates adoption and creates immediate value by enriching existing content with extracted evidence |
| D25 | Drift detection for managed artifacts as P0 | Once RKP manages instruction files, it must detect when they're manually edited. Without drift detection, the canonical model silently diverges from the checked-in files, undermining the product's value |
| D26 | Version-controlled human decisions in `.rkp/` directory | Human decisions (overrides, suppressions, declarations) are the durable state that must survive across machines and team members. Local working state (index, cache) is regenerable. This is analogous to checking in `.eslintrc` |
| D27 | Applicability as a first-class claim property | The question "is this rule true?" is different from "should this rule be shown here?" Over-inclusion is as harmful as omission (Feb 2026 study: 20%+ inference cost increase from over-broad context). Applicability tags enable relevance-aware projection |
| D28 | CI config parsing as P0 evidence source (passive, read-only) | CI definitions are the strongest available evidence that commands work in specific environments. GitHub explicitly says agents discovering dependencies via trial and error is slow and unreliable. Parsing CI configs (not executing or calling APIs) is passive analysis with high evidence value |
| D29 | Risk classification for validated commands | Different commands have different safety profiles. Risk class informs projection decisions (safe commands in instruction files, destructive commands as guardrails) and verification eligibility |
| D30 | Explicit adapter maturity tiers (GA/Beta/Alpha) | Promising parity across all hosts is dishonest. MCP support varies: Copilot supports tools only (not resources/prompts), Cursor/Windsurf have different MCP surfaces. Explicit tiers set correct expectations and focus testing effort |
| D31 | Sensitivity field on claims (public/team-only/local-only) | Prevents leaking internal URLs, service names, or security configs into public instruction files. Simple flag with high safety value |
| D32 | No checked-in canonical contract format (repo-context.yaml) | Projected host-native files (AGENTS.md, CLAUDE.md, etc.) ARE the checked-in contract. Adding a new intermediate format creates a three-layer architecture and introduces a format no existing agent reads — contradicting the anti-fragmentation thesis |
| D33 | No public plugin/extension marketplace in MVP | 2026 empirical studies found widespread vulnerability and malicious-skill problems. Internal adapter architecture for parsers and exporters only. Host-native skill/workflow export is fine; public installable extension distribution is not |
| D34 | Needs-declaration review state for claims the system cannot infer | When RKP detects ambiguity it cannot resolve (e.g., conflicting Python version references), it surfaces a declaration prompt rather than guessing. This turns uncertainty into an actionable question for the human |

### Open

| # | Question | Notes |
|---|---|---|
| Q1 | Optimal default staleness window for time-based fallback? | Default 90 days; validate with design partners |
| Q2 | Minimum evidence chain before product shows explicit risk score? | Ties to Phase 4 readiness gate |
| Q3 | Should MVP include lightweight PR annotation surface? | Accelerates feedback but adds complexity; decide at Month 2 |
| Q4 | Which enrichment path first: LSP integration or SCIP indexers? | Depends on language demand from design partners |
| Q5 | First non-MCP surface: GitHub App, CLI workflow, or none? | |
| Q6 | Canonical pricing unit for multi-repo orgs: seat, repo, or protected surface? | |
| Q7 | Source allowlist defaults — which file types and directories are trusted sources for convention inference? | |
| Q8 | Container runtime for sandbox verification: podman, docker, or both? | Podman preferred (rootless); docker as fallback |
| Q9 | Trace sharing: what anonymization is sufficient for aggregate analysis? | Must not leak proprietary code patterns |
| Q10 | MCP App (ChatGPT, Claude, VS Code) as governance UI — how soon? | CLI-first for MVP; App-ready is lower effort than custom web UI |
| Q11 | Applicability tag vocabulary — should it be free-form or a controlled vocabulary? | Free-form is more flexible; controlled vocabulary is more consistent. Start free-form, standardize after design-partner usage patterns emerge |
| Q12 | `.rkp/overrides/` format — YAML, JSON, or something else? | YAML preferred for human readability; decide during implementation planning |

---

## 22. What Changed from v3.0 and Why

This section documents the material changes from PRD v3.0, the reasoning behind each, and what criticism was accepted vs. rejected.

### Changes accepted from external review

| Change | Reasoning |
|---|---|
| **Added `rkp import` as P0 capability** | Raw instruction generation is commodity in 2026. The product must meet teams where they are — most repos already have instruction files. Import accelerates adoption by ingesting existing AGENTS.md, CLAUDE.md, etc., enriching them with extracted evidence, and surfacing conflicts. Without import, adoption requires starting from scratch |
| **Added drift detection as P0 capability** | Once RKP manages instruction files, it must detect when they're edited outside the tool. Without drift detection, the canonical model silently diverges from checked-in files. This was identified as a gap in v3.0's governance story |
| **Added applicability as a first-class claim property** | v3.0 had `scope` (path relevance) and thin-by-default projection, but no mechanism to express when a claim should be surfaced beyond path. The Feb 2026 study showing 20%+ inference cost increase from over-broad context makes this critical. Applicability tags enable the projection engine to make relevance-aware decisions |
| **Added CI config parsing as P0 evidence source** | v3.0 deferred all CI-related work to Phase 2. But parsing CI _definitions_ (not outcomes) is passive analysis — reading config files the product already knows how to handle. CI configs are the strongest available evidence that commands work in specific environments. GitHub explicitly says agents discovering dependencies via trial and error is slow and unreliable |
| **Added risk classification for validated commands** | v3.0's verification levels were about evidence strength but didn't classify command safety. Risk class informs projection (safe commands in instructions, destructive commands as guardrails) and verification eligibility |
| **Added explicit adapter maturity tiers** | v3.0's host capability matrix implied varying support levels but didn't make maturity explicit. 2 GA (Claude Code, Codex), 1 beta (Copilot), alpha/export-only (Cursor, Windsurf) sets correct expectations and focuses testing effort |
| **Reframed eval harness as quality harness + design-partner studies** | v3.0's "task success delta" as a productized 90-day metric was not achievable with 3-5 design partners. Reframed: quality harness (fixture repos, conformance tests, leakage/drift tests) ships in product; task success measurement is a design-partner research program with trace capture infrastructure |
| **Added sensitivity field on claims** | v3.0 had no mechanism to prevent internal URLs, service names, or security configs from leaking into public instruction files. Simple flag with high safety value |
| **Added needs-declaration review state** | v3.0 had "low-confidence items flagged for confirmation" but no explicit mechanism for the system to surface questions it cannot answer by inference. Declaration prompts turn uncertainty into actionable human input |
| **Added `.rkp/` directory for version-controlled human decisions** | v3.0 stored everything in SQLite. If you cloned the repo on a new machine, you lost all human review work. Now: durable human decisions are checked in and team-shareable; local working state is regenerable |
| **Made hosted/background agent support explicit via projected artifacts** | v3.0 deferred all cloud/remote agent support to Phase 2+. The correction: hosted agents (Copilot coding agent, Codex cloud) already read checked-in instruction files. The projected artifacts ARE the remote support path for P0. Managed MCP serving remains Phase 2+ |
| **Added explicit non-goal: no public marketplace** | v3.0 didn't propose a marketplace, but making it explicit prevents scope creep. 2026 research on skill security problems reinforces this |

### Criticism evaluated but not accepted

| Suggestion | What we took / what we pushed back on |
|---|---|
| **"Narrow from knowledge plane to operational contract"** | Took: sharpened Phase 1 description to emphasize concrete deliverables. Pushed back: the product is more than a contract format. The extraction engine, convention synthesis, module mapping, and MCP serving are intelligence operations that make the contract evidence-backed rather than hand-written. Reducing the identity to "contract management" undersells the differentiation |
| **"Add repo-context.yaml as a checked-in canonical contract"** | Took: version-controlled human decisions in `.rkp/`, import workflow, drift detection. Pushed back: a new canonical YAML format that no existing agent reads creates a three-layer architecture (SQLite → YAML → host files) and introduces another file in a product whose thesis is anti-fragmentation. The projected host-native files (AGENTS.md, CLAUDE.md, etc.) ARE already checked in and reviewable. They are the contract |
| **"Merge command + prerequisite into execution recipe"** | Took: CI evidence as evidence source, risk classification. Pushed back: prerequisites have their own lifecycle and can be shared across commands (e.g., "Python 3.12 required" serves build, test, and lint). Keeping separate claim types is better data modeling. The user-facing presentation can bundle them into a "recipe" view without merging the internal types |
| **"De-scope module mapping from MVP"** | Pushed back: coarse module mapping tied to actionable context (scoped rules, test locations, commands per module) is achievable with tree-sitter import analysis and directly valuable. It's not a graph-heavy research project — it's practical path-to-module mapping that makes scoped rules possible |
| **"De-scope ownership hints from MVP"** | Pushed back: ownership hints are simple metadata on module-boundary claims derived from git blame — minimal implementation cost. They make module info more useful for agents deciding who to ask about a change |
| **"Replace broad sandbox-verified commands with only evidence-backed recipes"** | Took: CI evidence and risk classification reduce the need for sandbox verification. Pushed back: sandbox verification as an opt-in, consent-gated capability is a real differentiator. The PRD already treats it as opt-in, not default. Removing it removes a capability that some design partners will want |

---

_End of PRD v4.0._
