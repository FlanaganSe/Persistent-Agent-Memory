# Repo Knowledge Plane — Product Requirements Document

_v3.0 — 2026-03-18. Revised from v2.0 after structural review. Research base: `docs/research.md`._

---

## 1. Product Summary

Repo Knowledge Plane (RKP) is a persistent, agent-neutral intelligence layer for software repositories. It extracts verified operational context — environment prerequisites, validated commands, conventions, architecture boundaries, scoped rules, and declared-vs-inferred conflicts — from a repository's code, configuration, and history. It serves that knowledge through MCP so any coding agent or developer tool can query the same evidence-backed substrate without developers pasting context into prompts.

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
| **Windsurf** | Transport choice, tool toggles, tool caps | Windsurf-only configuration |
| **Devin** | Product-native memory, DeepWiki | Devin-only. Not structured for other agents |

The consequences:
1. **Duplication**: Teams maintain copilot-instructions.md AND CLAUDE.md AND AGENTS.md AND .cursor/rules with overlapping, potentially contradictory content
2. **Drift**: When a convention changes, it must be updated in N places — or agents get stale guidance
3. **No governance**: Most instruction surfaces have no review workflow, no provenance, no confidence signals. Inferred memories mix with declared policies
4. **No portability**: Switching or adding an agent means recreating context from scratch
5. **Mixed evidence on value**: A Jan 2026 study found AGENTS.md associated with lower runtime and token use, but a Feb 2026 study found repo context files often _reduced_ task success and _increased_ inference cost by 20%+ when they imposed unnecessary requirements. The difference is quality: thin, verified, frequently-relevant context helps; verbose, stale, or over-constraining context hurts

Meanwhile, AGENTS.md is present in 60,000+ repositories with no tooling to generate or maintain it from actual codebase analysis. But generating instruction files is not the product — it is one delivery surface among many.

---

## 3. Vision & Positioning

MCP is now an industry standard under the Linux Foundation's Agentic AI Foundation (AAIF), co-sponsored by Anthropic, OpenAI, Google, AWS, and Microsoft. AGENTS.md is also stewarded by AAIF. These are the converging, vendor-neutral interfaces the product builds on.

### Non-negotiable properties

| Property | Why non-negotiable |
|---|---|
| **Cross-agent** | Value compounds when the same context is available to multiple agents — workstation-first in MVP, with cloud/remote agents addressed by deployment extension |
| **Persistent** | Knowledge must survive sessions. Six months of accumulated understanding remains available |
| **Local-first** | No cloud required, zero-procurement adoption. Note: RKP itself keeps data local by default; what host agents do with queried data follows their own retention policies |
| **Evidence-backed** | Every derived claim has provenance, source authority, timestamps, and confidence. Declared facts distinguished from inferred heuristics with explicit precedence |
| **Governable** | Inferred claims can be corrected, suppressed, or tombstoned. Instruction file writes require human review. Provenance is auditable |
| **Identity-aware** | Repo, branch, worktree, and session identity are first-class in the data model — not assumed to be single/static |
| **Infrastructure, not persona** | Not a new "AI teammate" — quietly improves work done through existing tools |

### What "cross-agent" means concretely

| Agent | Deployment model | MCP support | MVP compatible |
|---|---|---|---|
| Claude Code (local) | Workstation | stdio, tools + resources | **Yes** |
| Codex CLI/IDE | Workstation | stdio, tools + resources | **Yes** |
| Cursor | Workstation | stdio, tools + resources | **Yes** |
| Windsurf | Workstation | stdio, SSE, Streamable HTTP | **Yes** |
| Copilot coding agent | GitHub Actions environment | Tools only (no resources, no prompts) | **Partial** — tools work, resources don't |
| Codex cloud | OpenAI cloud | Remote MCP | **No** — requires managed deployment |
| Devin | VM / remote MCP | Remote MCP | **No** — requires managed deployment |

**MVP deployment target: local/workstation agents.** Cloud/remote agent support requires a managed deployment story (Phase 2+). However, the core data model does not assume a single machine, single worktree, or single session — it is designed so remote deployment is an operational change, not a data model rewrite.

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

### Repositioned wedge: Verified operational context + thin always-on guidance + host-native projection

The wedge is **not** "generate AGENTS.md." Adjacent scaffolding already exists: Claude Code has `/init` for CLAUDE.md, GitHub says Copilot coding agent can generate `copilot-instructions.md`. And the research is mixed on value — thin, verified, frequently-relevant context helps; verbose or over-constraining context hurts.

The opportunity is: **extract the non-inferable operational context that agents need but cannot safely reconstruct from the code alone, keep always-on guidance deliberately thin, and project into host-native surfaces including skills and playbooks where appropriate.** That means:

1. **Environment prerequisites and validated commands** — what's needed to build/test/lint, discovered from config, with prerequisites and optional sandbox verification
2. **Thin always-on conventions** — only non-inferable, high-confidence, frequently-relevant rules in root instruction files
3. **Host-native skill/playbook projection** — detailed procedures, validation recipes, and environment-specific workflows projected as skills (Claude Code, Copilot, Codex) or on-demand MCP queries, not crammed into always-on files
4. **Declared vs. inferred conventions** — separated with evidence, confidence, and source authority
5. **Path-scoped rules** — which constraints apply where, with precedence
6. **Coarse module boundaries** — what depends on what, tied to actionable context (scoped rules, test locations, valid commands per module)
7. **Declared-vs-inferred conflicts** — where the docs say one thing and the code does another
8. **Enforceable guardrails** — security-sensitive workflows projected as permission/tool restrictions where the host supports them, advisory text everywhere else

The instruction files (AGENTS.md, copilot-instructions.md, .cursor/rules) are one delivery surface. Skills and playbooks are another. MCP queries are a third. The product is the verified operational context underneath, projected faithfully through a host capability matrix that models all of these surfaces.

### Why this wedge, not PR-risk intelligence

1. **Most universal immediate problem.** Every agent rediscovers conventions because instruction surfaces are incomplete, stale, or over-stuffed.
2. **Fastest path to trust.** Convention synthesis produces useful output from the current snapshot and modest history. Risk predictions too early damage trust faster than they create value.
3. **Self-distributing artifacts.** Generated instruction files are visible in-repo, useful to anyone, naturally attributable.
4. **Builds the right substrate.** Accurate synthesis requires parsing, boundary detection, convention inference, and MCP with provenance — the foundation for every subsequent capability.
5. **Lower technical risk.** Risk prediction requires runtime data (CI outcomes, test coverage, historical failures) that most repos don't make easily available. Convention synthesis works from what's already in the repo.
6. **Measurable from day one.** With a built-in eval harness, the product can demonstrate whether its context actually improves agent task success.

PR-risk intelligence is strategically critical but second-act. It depends on richer outcome data and calibration.

### First useful output in under five minutes

A developer runs `uvx repo-knowledge-plane init` and within five minutes receives:

- Discovered build/test/lint commands with prerequisites (runtimes, tools, services, env vars needed)
- A draft instruction artifact — deliberately thin: only non-inferable, high-confidence, frequently-relevant rules
- Detailed procedures flagged for skill/playbook projection where the host supports it
- Low-confidence items flagged for human confirmation
- A diff-style review flow — no instruction file is written until the human approves
- MCP tools queryable for conventions, modules, prerequisites, and architecture boundaries

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
| **precedence** | How this claim interacts with conflicting claims |
| **projection_targets** | Which host surfaces this should project to |
| **review_state** | unreviewed / approved / edited / suppressed / tombstoned |
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
| **environment-prerequisite** | Runtime, tool, service, OS, env var, or network requirement for a command | copilot-setup-steps.yml, README, or structured MCP response |
| **validated-command** | Build/test/lint/format command with verification level | Structured MCP response, instruction file reference |
| **permission/restriction** | Tool restrictions, sandbox requirements, security-sensitive operation flags | Claude Code permissions, Copilot agent tool config, advisory text |
| **module-boundary** | Architecture boundary, dependency relationship, ownership hint | Structured MCP response, instruction file reference |
| **conflict** | Declared-vs-inferred mismatch, stale evidence | Structured MCP response, review queue |

### Source authority hierarchy

Claims are not just "declared" or "inferred." They have explicit source authority that determines precedence:

| Authority level | Source | Precedence (highest first) |
|---|---|---|
| **human-override** | Human correction via `rkp review` | 1 (highest) |
| **declared-policy** | Explicit rules in AGENTS.md, CLAUDE.md, .cursor/rules, README | 2 |
| **executable-config** | CI config, package.json scripts, Makefile targets, pyproject.toml | 3 |
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
| **Human re-approval** | Freshness reset |
| **Time-based expiry** | After configurable window (default 90 days) with no revalidation trigger, claim marked stale |

### Review states

| State | Meaning |
|---|---|
| **unreviewed** | Machine-generated, not yet seen by human |
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
| **Validated command discovery** | Discover build, test, lint, format commands from config files. Report verification level per command (see §8.1) |
| **Thin instruction projection** | Generate deliberately thin always-on instruction artifacts. Only non-inferable, high-confidence, frequently-relevant rules. Detailed procedures flagged for skill projection or on-demand query |
| **Skill/playbook projection** | For hosts that support skills (Claude Code, Copilot, Codex): project detailed procedures and validation workflows as host-native skills. For other hosts: surface via MCP query |
| **Guardrail projection** | Security-sensitive operations projected as enforceable permission/tool restrictions where host supports them (Claude Code permissions, Copilot agent tool config). Advisory text for hosts without enforcement |
| **Host capability matrix** | Model the full agent configuration surface per host: always-on rules, scoped rules, skills, environment config, permissions, size constraints. Project faithfully per host |
| **Coarse module mapping** | Top-level module/package detection, path-to-module mapping, import-based dependency edges within the support envelope. Tied to actionable context: scoped rules, test locations, valid commands per module |
| **Correction and governance** | Human can approve, edit, suppress, or tombstone any claim. Override workflow for bad inferences. Evidence-triggered + branch-aware stale-claim revalidation. Audit trail |
| **MCP server** | Stable surface of tools (primary) and resources via MCP stdio transport |
| **Provenance** | Source authority, timestamp, extraction version, confidence, freshness basis, and review state on every claim |
| **Execution policy** | Passive-analysis mode (default) and opt-in active-verification mode. See §8.2 |
| **Downstream eval harness** | Built-in measurement of whether RKP context helps or harms agent task success. See §8.3 |

### 8.1 Validated command verification levels

"Validated" is not binary. Commands have a verification level:

| Level | Meaning | How achieved |
|---|---|---|
| **discovered** | Found in a config file (package.json, Makefile, pyproject.toml, CI config) | Static parsing |
| **prerequisites-extracted** | Required runtimes, tools, services, env vars identified | Cross-referencing config, CI definitions, Dockerfiles |
| **environment-profiled** | Full environment contract assembled: what's needed to run this command | Aggregation of prerequisite sources |
| **sandbox-verified** | Command executed successfully in an isolated environment | Opt-in active mode: sandboxed execution (container/worktree). Only with explicit human consent |

P0 ships levels 1-3 (discovery through environment profiling) for all discovered commands. Level 4 (sandbox verification) is opt-in with explicit consent per-command.

### 8.2 Execution policy

The product wants to verify that build/test/lint commands actually work. But verification means executing arbitrary repo code. This requires an explicit trust model.

| Mode | Description | Default |
|---|---|---|
| **Passive analysis** | Only static parsing and cross-referencing. No command execution. No side effects. | **Default** |
| **Active verification** | Execute discovered commands in sandboxed isolation. Requires explicit opt-in per command category. | Opt-in |

Active verification controls:

| Control | Description |
|---|---|
| **Per-category consent** | User explicitly opts in to verifying build, test, lint, or format commands separately |
| **Sandbox isolation** | Commands run in a container or clean worktree, never in the user's working tree |
| **Secret/network controls** | No access to user secrets or network by default. Configurable allowlists |
| **Source trust levels** | Only commands from trusted sources (package.json scripts, Makefile targets, CI config) are eligible for execution. Arbitrary scripts require explicit approval |
| **Timeout and resource limits** | Execution capped by time and resource usage |
| **Evidence recording** | Execution result (success/failure, output, duration) recorded as claim evidence |

_Assumption [A11]: Most MVP value comes from passive analysis (levels 1-3). Active verification is a differentiator but must not be required for basic functionality._

### 8.3 Downstream eval harness

If the product alters what agents see before they act, you must measure whether it helps or harms. Evaluation is not a Phase 4 optimization — it ships with MVP.

**Mandatory early metrics:**

| Metric | What it measures | Method |
|---|---|---|
| **Task success delta** | Does agent task success change with RKP context vs without? | A/B trace comparison on design-partner repos |
| **Bad-instruction rate** | How often does RKP-generated guidance lead to incorrect agent behavior? | Sampled evaluation by pilot tech leads |
| **Command verification precision** | Do discovered commands actually work? | Execute in sandbox (where opted in); manual spot-check (where not) |
| **Projection correctness** | Is the projected instruction file / skill faithful to the canonical model for each host? | Automated round-trip validation |
| **Correction burden** | How much human effort is needed to fix RKP output? | Track corrections / total claims over time |
| **Token/runtime overhead** | Does RKP context increase agent inference cost? | Measure token count and response time with/without RKP |

**Eval trace capture:**
- MCP server logs queries, responses, and timestamps
- Design-partner agents optionally capture task outcome (success/failure/correction) associated with RKP query context
- Eval traces are local-only by default; opt-in anonymized sharing for aggregate analysis

### What is explicitly deferred

| Deferred capability | Why deferred | Phase |
|---|---|---|
| Impact graphs for diffs | Requires reliable semantic dependency edges beyond tree-sitter syntax extraction; too aggressive for P0 | Phase 2 |
| Test recommendation | Infeasible at useful precision without runtime coverage or CI outcome data | Phase 2-3 |
| Reviewer recommendation | GitHub already has suggested reviewers + CODEOWNERS; weak differentiation | Cut from MVP |
| Composite risk score | Uncalibrated scores risk trust collapse | Phase 3-4 |
| Cloud/remote agent deployment | Requires managed service, not just local daemon. But core data model is remote-ready | Phase 2+ |
| Multi-repo graph federation | Enterprise feature | Phase 3+ |
| CI/test outcome ingestion | Enables impact/test features but adds integration complexity to MVP | Phase 2 |
| Vector/semantic search | Initial value is structural understanding, not semantic retrieval | Phase 2+ |
| Autonomous code modification | Must never modify code based on inferred rules | Never (P0 constraint) |
| Deep cross-language semantics | Requires compiler/LSP/SCIP integration per language | Phase 2+ (per language) |
| Merge gating | High-stakes pass/fail decisions require calibration trust | Phase 4 |
| Change coupling / temporal analysis | Valuable but requires grounding in outcomes or well-defined coupling models before it's trustworthy | Phase 3 |

### Core user flows

**Flow 1 — Repository bootstrap:**
Tech lead runs `uvx repo-knowledge-plane init`. Product analyzes the repo within the support envelope. Presents a draft: thin always-on rules, scoped rules, and skills/playbooks separated. Tech lead approves, edits, or suppresses individual claims. Approved artifacts are written (instruction files, skills where host supports them). MCP server starts.

**Flow 2 — Agent preflight:**
Before editing code in a scope, agent calls `get_conventions` or `get_module_info` via MCP. Receives repo-specific constraints, prerequisite info, scoped rules, and guardrails without the user pasting them into a prompt.

**Flow 3 — Convention review and correction:**
Tech lead reviews inferred claims periodically. Suppresses incorrect inferences. Adds declared rules the product missed. Corrections persist and improve future synthesis. Evidence-triggered alerts surface claims that need re-review.

**Flow 4 — Instruction refresh:**
After significant codebase changes, tech lead runs `preview_instruction_update`. Reviews a diff of what changed in the canonical model. Approves updates to instruction artifacts and skills.

**Flow 5 — Eval check:**
Tech lead runs `rkp eval` to see whether RKP context is helping: task success delta, correction burden, bad-instruction rate. Uses this to tune which claims are active, suppressed, or need editing.

---

## 9. MCP Surface

### Design principles

1. **Tools-first.** Every critical read must be available as a tool, not only as a resource. This ensures compatibility with all MCP hosts, including Copilot coding agent (tools-only).
2. **No write operations as MCP tools.** Instruction file generation is preview-only in MCP. File writes require a human-reviewed apply step in the CLI.
3. **Provenance on every response.** Index version, repo HEAD, generation timestamp, confidence, source authority, review state.
4. **Graceful degradation.** If a query touches areas outside the support envelope, the response says so explicitly rather than fabricating confidence.

### Tools (primary surface)

| Tool | Parameters | Purpose |
|---|---|---|
| `get_conventions` | `path_or_symbol`, `include_evidence` | Return relevant rules for a path, symbol, or module. Source authority and confidence included |
| `get_module_info` | `path_or_symbol` | Module boundaries, dependencies, ownership hints, test locations, related paths, applicable scoped rules |
| `get_prerequisites` | `command_or_scope` | Environment prerequisites for a command or scope: runtimes, tools, services, env vars, OS, verification level |
| `get_validated_commands` | `scope` | Build, test, lint, format commands with source, verification level, and prerequisite summary |
| `get_repo_overview` | — | Languages, build/test entrypoints, module map, indexing status, support envelope coverage |
| `get_instruction_preview` | `consumer` | Preview what would be projected for a target consumer (`agents-md`, `copilot`, `cursor`, `claude`) including instruction files AND skills/playbooks |
| `get_guardrails` | `path_or_scope` | Security-sensitive operations, permission restrictions, tool constraints. Enforceable where host supports; advisory where not |
| `get_conflicts` | `path_or_scope` | Declared-vs-inferred conflicts, stale claims, suppressed inferences |
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
| `rkp init` | Bootstrap: analyze repo, present draft for review, write approved artifacts |
| `rkp review` | Interactive review of claims: approve, edit, suppress, tombstone |
| `rkp apply` | Write approved instruction artifacts and skills to disk after human review |
| `rkp refresh` | Re-analyze and present diff of what changed |
| `rkp status` | Show index health, staleness, support envelope coverage, correction stats |
| `rkp eval` | Show eval metrics: task success delta, correction burden, bad-instruction rate |
| `rkp verify` | Opt-in: run sandbox verification of discovered commands |
| `rkp audit` | Query the audit trail for a claim or scope |
| `rkp purge` | Hard-delete tombstoned claims (for data removal requirements); requires confirmation and logs the purge |

### Example: get_conventions

```json
// Request
{ "tool": "get_conventions",
  "arguments": { "path_or_symbol": "src/payments", "include_evidence": true } }

// Response
{
  "scope": "src/payments",
  "claims": [
    { "id": "claim-001",
      "content": "Do not call payment providers directly from API handlers",
      "claim_type": "always-on-rule",
      "source_authority": "declared-policy",
      "source": "docs/architecture.md",
      "confidence": 1.0,
      "review_state": "approved",
      "freshness": { "last_validated": "2026-03-15", "trigger": "evidence-file-unchanged" }
    },
    { "id": "claim-042",
      "content": "Provider adapters live under src/payments/providers/*",
      "claim_type": "scoped-rule",
      "source_authority": "inferred-high",
      "confidence": 0.89,
      "evidence": ["src/payments/providers/stripe.py", "src/payments/providers/adyen.py"],
      "review_state": "unreviewed",
      "freshness": { "last_validated": "2026-03-17", "trigger": "evidence-files-unchanged" }
    }
  ],
  "conflicts": [],
  "envelope_coverage": "full",
  "provenance": { "index_version": "2026-03-17T18:22:00Z", "repo_head": "abc1234", "branch": "main" }
}
```

---

## 10. Host Capability Matrix

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

| Host | Always-on | Path-scoped | Skills | Environment | Permissions | Size constraint |
|---|---|---|---|---|---|---|
| **AGENTS.md** (Codex) | Root file | Directory-level files | Codex skills (Agent Skills standard) | AGENTS.md `setup` section | Advisory in rules | 32 KiB combined |
| **CLAUDE.md** (Claude Code) | Root file | Directory-level files + .claude/rules/ | Claude Code skills (Agent Skills standard) | CLAUDE.md or skill | settings.json permissions, subagent config | Keep short (~200 lines) |
| **Copilot** | copilot-instructions.md (also reads AGENTS.md + CLAUDE.md) | .instructions.md files | Copilot skills + custom agents | copilot-setup-steps.yml | Agent tool config, custom agent tool scoping | Unknown |
| **Cursor** | .cursor/rules | Path-scoped rules | N/A | Advisory in rules | N/A | Per-rule targeting |

### Projection rules

1. Always-on rules → root instruction file for that host. **Keep thin**: only non-inferable, high-confidence, frequently-relevant claims. Research (ETH Zurich, Feb 2026) shows repository overviews specifically provide zero navigation reduction despite being universally included in LLM-generated files — omit them from always-on content
2. Path-scoped rules → host-specific scoped files where supported, annotations in root file where not
3. Detailed procedures and validation workflows → skills/playbooks where host supports them, on-demand MCP queries where not
4. Environment prerequisites → host-native environment config (copilot-setup-steps.yml, etc.) where supported, structured MCP response everywhere
5. Security guardrails → enforceable permissions/restrictions where host supports them, advisory text where not
6. If projected content exceeds host size constraints, prioritize: human-override > declared-policy > high-confidence inferred > low-confidence inferred. Move overflow to skills or on-demand
7. Each projected file includes a generation header with provenance and a "do not edit directly — corrections go through `rkp review`" notice
8. The canonical claim model is the source of truth; projected artifacts are derived

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
| **Purge** | Hard-delete tombstoned claims (for data removal requirements); requires confirmation, logged | CLI |

### Instruction file safety

- **No instruction file is written without human review.** The MCP surface exposes previews; the CLI exposes `apply` after review.
- Instruction file writes produce a diff for review, not a silent overwrite.
- Generated files include a provenance header linking to evidence.
- Skill/playbook generation follows the same review-then-apply workflow.

### Stale-claim revalidation

Primary mechanism: **evidence-triggered and branch-aware revalidation**.

- When a claim's evidence changes (file modified, config updated, convention-violating code merged), the claim is flagged for revalidation.
- Claims are validated against evidence on the **current branch**, not just the default branch.
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
| Eval harness ships with MVP | Cannot wait to measure whether the product helps or harms |

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
| **1. Verified context + faithful projection + eval** | Months 0-3 | Local indexing, convention extraction, prerequisite extraction, validated commands (levels 1-3), thin instruction projection, skill/playbook projection, guardrail projection, correction workflow, MCP tools, eval harness | First useful output; cross-agent distribution; measurable impact from day one |
| **2. Active verification + cloud deployment + semantic enrichment** | Months 3-6 | Sandbox command verification (level 4), optional LSP/SCIP enrichment, deeper dependency edges, CI/test outcome ingestion hooks, remote/managed deployment via Streamable HTTP | Verified commands; broader agent reach; semantic accuracy |
| **3. Behavioral layer** | Months 6-9 | Git history mining: hotspots, change coupling (grounded in CodeScene-style temporal coupling), contributor concentration. Path history with outcomes. Runtime data ingestion (coverage, test outcomes) | Longitudinal intelligence beyond snapshot; moat data |
| **4. Risk scoring & advanced eval** | Months 9-12 | Calibrated risk scores, outcome feedback loop, advanced agent evaluation, test recommendation with precision targets | Trustworthy forward-looking risk; measurable improvement loops |

### Phase 1 exit criteria

All P0 acceptance criteria met. 3+ design partners using the product with at least one agent. Correction workflow exercised. Eval harness producing task success delta measurements. Instruction artifacts accepted after review by 70%+ of partners.

### Phase 2 prerequisites

- Design-partner signal on which languages to add next
- At least one design partner willing to share CI/test outcome data
- Clear demand signal for cloud agent support (from which partners, which agents)
- Phase 1 eval data showing positive task success delta

---

## 15. Success Metrics

### 90-day (activation, trust, and measurable impact) — leading indicators

| Metric | Target | Measurement |
|---|---|---|
| Time to first useful output | < 5 min median | Instrumented from `init` to first approved artifact |
| Instruction artifact acceptance | ≥ 70% accept with light edits | Manual review in design-partner cohort |
| Convention query accuracy | ≥ 80% correct in spot checks | Sampled evaluation by pilot tech leads |
| Task success delta (with vs without RKP) | Positive; ≥ 5% improvement | Eval harness A/B traces on design-partner repos |
| Bad-instruction rate | < 10% of projected claims lead to incorrect agent behavior | Sampled evaluation by pilot tech leads |
| Command verification precision | ≥ 90% of discovered commands are actually valid | Sandbox verification (where opted in) + manual spot-check |
| Projection correctness | ≥ 95% of projected instructions are faithful to canonical model | Automated round-trip validation |
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

### What we explicitly do NOT promise at 6 months

- Test recommendation precision (no runtime data yet)
- Regression prediction (no calibration data yet)
- System-level DORA metric improvements (not attributable at this stage)

### 12-month (system improvement) — outcome metrics

| Metric | Target | Measurement |
|---|---|---|
| Escaped regression reduction | ≥ 15% vs pre-adoption baseline | Pilot repos with CI outcome tracking |
| PR cycle time reduction | ≥ 20% for AI-assisted changes | Open to merge, end-to-end |
| Test recommendation precision | ≥ 0.70 | Requires Phase 3 runtime data ingestion |
| Agent task quality lift | ≥ 15% first-pass acceptance | Controlled with/without RKP |

---

## 16. Competitive Landscape

### Honest positioning

"Shared intelligence layer" alone is not a moat in March 2026. Sourcegraph 7.0 explicitly calls itself "the intelligence layer for developers and AI agents." Potpie positions itself as "codebase-to-knowledge-graph infrastructure for agents" ($2.2M pre-seed, Feb 2026). The differentiation must be more specific.

**RKP's specific differentiation: portable verified repo context with source authority, thin-by-default instruction projection, host-native skill/guardrail projection, human governance, environment prerequisite modeling, and measurable downstream eval.**

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
5. **Eval-driven quality** — measurable proof that the context helps, not just vibes
6. **Host-native projection quality** — faithful projection to instruction files, skills, guardrails, and environment configs per host

---

## 17. Go-to-Market & Pricing

**Distribution:** Open-source core via `uvx`. MCP registry listing for agent ecosystem discoverability. Used _from within_ existing tools.

**Viral artifact:** Generated instruction files and skills — visible in-repo, useful to anyone, naturally attributable. But the product value is the verified substrate and faithful projection, not the artifact.

**Adoption loop:** Tech lead installs locally → reviews and approves artifacts → team sees value from better agent behavior → eval data confirms improvement → platform team standardizes → organization purchases.

| Tier | Price | Includes |
|---|---|---|
| Individual (OSS) | Free | Full local analysis, synthesis, MCP server, correction workflow, eval harness |
| Team | ~$20-35/active dev/month | Shared config, cross-member conventions, telemetry, team correction workflow |
| Enterprise | Custom | SSO, policy, audit, air-gapped, multi-repo admin, managed deployment for cloud agents |

"Active dev" = committed in last 90 days.

Pitch: not "pay for more AI" but "infrastructure that makes AI tools you already bought safer and more effective — and proves it with eval data."

_Assumption [A6]: If local-first usage alone captures most value, monetization leans on coordination, governance, and evaluation features._

---

## 18. Risks & Mitigations

| Risk | Category | Mitigation |
|---|---|---|
| Polyglot parsing quality inconsistent | Technical | Explicit launch support envelope; surface unsupported areas; parser quality scoring |
| Inferred conventions wrong but sound authoritative | Technical/Trust | Source authority hierarchy; correction workflow as P0; confidence thresholds; "needs confirmation" flag; eval harness measures bad-instruction rate |
| Cold start on sparse-history repos | Technical | First wedge valuable from current snapshot alone; history signals added opportunistically |
| Large repos exceed performance targets | Technical | Incremental indexing; warm graph; Rust acceleration path; scope filters |
| Provenance gaps or stale data | Technical | Evidence-triggered + branch-aware revalidation; version every extraction; timestamp every resource; prefer incomplete-but-current |
| Tree-sitter insufficient for promised analysis | Technical | Honest about what tree-sitter provides; optional LSP/SCIP enrichment; don't promise compiler-grade accuracy |
| Dismissed as "just an AGENTS.md generator" | Product | Instruction files are one delivery surface; differentiate on verified context, skill projection, correction, eval, and cross-host projection |
| Overlap blur with Sourcegraph/Potpie | Product | Differentiate on behavioral signals, governance, skill/guardrail projection, and eval — not on graph/search |
| Instruction artifacts reduce agent performance | Product | Thin-by-default; skill projection for detailed content; eval harness measures task success delta; allow suppression |
| Command verification executes malicious code | Security | Passive-by-default; explicit opt-in per category; sandboxed execution; no secrets/network by default |
| MCP trust boundary exploited | Security | No write operations in MCP; read-only by default; source allowlists; audit trail |
| "No data leaves machine" claim misleading | Trust | Clarify boundary: RKP is local-only; host agents have their own retention policies; document explicitly |
| Buyer-user divergence | Commercial | Free tier for pull; governance as paid expansion |
| Incumbents absorb shallow features | Commercial | Accelerate toward longitudinal data, trust calibration, cross-agent neutrality, eval proof |

---

## 19. Acceptance Criteria (P0)

| # | Criterion |
|---|---|
| AC-1 | `uvx repo-knowledge-plane init` produces a non-template instruction artifact with repo-specific validated commands (with prerequisites), thin conventions, and module boundaries within 5 min on a 250k LOC Python repo |
| AC-2 | Generated content distinguishes claims by source authority level with evidence references and confidence scores |
| AC-3 | MCP server starts via stdio and responds to all documented tool calls |
| AC-4 | `get_conventions` returns scoped conventions with source authority, confidence, evidence, and review state for a given path |
| AC-5 | `get_module_info` returns boundary, dependency, and test location info for a top-level module within the support envelope |
| AC-6 | `get_validated_commands` returns build/test/lint commands with source, verification level, and prerequisite summary |
| AC-7 | `get_prerequisites` returns environment requirements (runtimes, tools, services, env vars) for a command or scope |
| AC-8 | `get_instruction_preview` returns faithful host-specific projection for at least AGENTS.md, CLAUDE.md, and copilot-instructions.md — including skill/playbook projection where host supports it |
| AC-9 | `get_guardrails` returns security-sensitive operations with enforceable restrictions for hosts that support them |
| AC-10 | No instruction file or skill is written without human review and explicit approval via CLI |
| AC-11 | Correction workflow: user can approve, edit, suppress, and tombstone claims via `rkp review` |
| AC-12 | Incremental index update completes in < 2 seconds for a single-file change |
| AC-13 | All MCP responses include provenance (index version, repo HEAD, branch, timestamp, confidence, source authority, review state) |
| AC-14 | No repository content transmitted off the local machine by RKP itself; data boundary with host agents documented |
| AC-15 | Product runs without any cloud service dependency |
| AC-16 | Queries touching areas outside the support envelope return explicit "unsupported" status, not fabricated confidence |
| AC-17 | Audit trail records source authority, evidence, extraction version, and human corrections for each claim. Tombstoned claims retain evidence |
| AC-18 | Projected always-on instruction files are thin: only non-inferable, high-confidence, frequently-relevant claims. Detailed procedures project to skills or on-demand |
| AC-19 | Eval harness captures query traces and produces task success delta, bad-instruction rate, and correction burden metrics |
| AC-20 | Claims are revalidated on evidence-change triggers and branch context, not just time-based expiry |

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
| A11 | Most MVP value comes from passive analysis (levels 1-3) | Design partners consistently want sandbox verification before anything else |
| A12 | Thin-by-default instructions perform better than verbose ones | Eval data shows verbose instructions have higher task success |
| A13 | Skill/playbook projection adds value over instruction-file-only | Design partners don't use skill-capable hosts |

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
| D9 | Local/workstation agents are MVP deployment target | Cloud agents require managed deployment — Phase 2+ |
| D10 | Cut `recommend_reviewers` from MVP | GitHub suggested reviewers + CODEOWNERS already serve this; weak differentiation |
| D11 | Expand canonical model beyond instruction files | Agent behavior in 2026 is controlled by files + skills + environment + permissions + profiles. Model must cover the full surface for faithful projection |
| D12 | Thin-by-default instruction projection | Research shows verbose context files can hurt agent performance. Always-on files carry only non-inferable, high-confidence, frequently-relevant rules. Details → skills or on-demand |
| D13 | Source authority hierarchy replaces binary declared/inferred | human-override > declared-policy > executable-config > checked-in-docs > inferred-high > inferred-low. Needed for precedence and conflict resolution |
| D14 | Evidence-triggered + branch-aware revalidation as primary freshness mechanism | Time-based expiry (90 days) is fallback only. GitHub validates memories against cited code on current branch; RKP should do the same |
| D15 | Tombstone by default, hard delete only via explicit purge | Audit trail integrity for regulated environments. Delete-and-audit is contradictory; tombstone-and-audit is consistent |
| D16 | Validated commands split into verification levels | "Validated" is not binary. Levels: discovered → prerequisites-extracted → environment-profiled → sandbox-verified. P0 ships levels 1-3; level 4 is opt-in |
| D17 | Passive analysis by default, active verification opt-in | Executing repo commands is arbitrary code execution. Requires explicit consent, sandbox isolation, and trust controls |
| D18 | Eval harness ships with MVP, not Phase 4 | If the product alters what agents see, must measure impact from day one. Cannot wait 9 months to learn it's harmful |
| D19 | Identity model (repo/branch/worktree/session) first-class from day one | Avoids data model rewrite for multi-worktree, multi-branch, and remote deployment |
| D20 | Cut `find_prior_changes` from MVP; replace with path history in Phase 3 | "Similar historical changes" is hard to make trustworthy without semantic grounding. Phase 3 adds grounded temporal coupling and path history with outcomes |
| D21 | Guardrail projection as a P0 capability | Security constraints should be enforceable where hosts support them (permissions, tool restrictions), not just advisory text |
| D22 | Target Agent Skills open standard for skill projection | Claude Code and Codex both support the Agent Skills standard (agentskills.io). Cross-platform skill format is emerging. Copilot does not yet support it but reads AGENTS.md and CLAUDE.md |
| D23 | Omit repository overviews from always-on instruction content | ETH Zurich study (Feb 2026): repository overviews provide zero reduction in agent navigation steps despite being in 100% of LLM-generated files. Overviews cause over-compliance without benefit |

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
| Q9 | Eval trace sharing: what anonymization is sufficient for aggregate analysis? | Must not leak proprietary code patterns |
| Q10 | MCP App (ChatGPT, Claude, VS Code) as governance UI — how soon? | CLI-first for MVP; App-ready is lower effort than custom web UI |

---

## 22. What Changed from v2.0 and Why

This section documents the material changes from PRD v2.0, the reasoning behind each, and what criticism was accepted vs. rejected.

### Changes accepted from structural review

| Change | Reasoning |
|---|---|
| **Expanded canonical model beyond instruction files** | v2.0's instruction primitive model (always-on / path-scoped / nearest-override / on-demand / size constraints) only modeled file behavior. In 2026, agent behavior is controlled through instruction files, skills, environment configs, permissions, and agent profiles. The canonical model now covers the full configuration surface for faithful projection |
| **Reframed problem statement from "zero-state" to "fragmented and non-portable"** | "Each agent session starts from zero" was a strong line in 2024-2025. In 2026, Copilot Memory, Claude Code auto memory, and Codex Team Config all provide some persistence. The real problem is fragmentation, vendor lock-in, and lack of governance across these partial solutions |
| **Thin-by-default instruction projection** | Research shows instruction files can hurt agent performance when they impose unnecessary requirements. Always-on files now carry only thin, high-confidence, frequently-relevant rules. Detailed procedures project as skills or on-demand queries |
| **Added skill/playbook projection** | Copilot, Claude Code, and Codex all support skills as on-demand procedural workflows. This is the right surface for detailed procedures, not always-on instruction files |
| **Added guardrail projection** | Claude Code supports permissions, Copilot supports agent tool configuration. Security constraints should project as enforceable restrictions where possible, not just advisory text |
| **Split validated commands into verification levels** | "Validated" was under-specified. Now explicit levels: discovered → prerequisites-extracted → environment-profiled → sandbox-verified. P0 ships passive analysis (levels 1-3); sandbox verification is opt-in |
| **Added environment prerequisite extraction** | Commands need environment contracts: runtimes, tools, services, env vars, OS. GitHub's copilot-setup-steps.yml exists precisely for this reason. Prerequisite extraction is a P0 capability |
| **Added execution policy with passive-by-default mode** | v2.0 said "validated commands" without addressing that verification means executing arbitrary repo code. Now explicit: passive analysis by default, active verification opt-in with sandbox isolation |
| **Replaced binary declared/inferred with source authority hierarchy** | "Declared vs inferred" is not enough for precedence resolution. Now: human-override > declared-policy > executable-config > docs > inferred-high > inferred-low |
| **Evidence-triggered + branch-aware revalidation** | 90-day time-based expiry was the primary mechanism. Now evidence-change and branch context are primary; time-based is fallback |
| **Replaced hard delete with tombstone + explicit purge** | v2.0 said "delete removes a claim and its evidence" while promising audit trail for regulated environments. Contradictory. Now: tombstone retains evidence for audit; purge is explicit with confirmation |
| **Moved eval harness to Phase 1 (MVP)** | v2.0 put evaluation in Phase 4 (months 9-12). If the product alters what agents see, measuring impact is not optional and cannot wait 9 months |
| **Cut `find_prior_changes` from MVP** | "Similar historical changes" is hard to make trustworthy without richer semantics. Replaced with grounded temporal coupling and path history in Phase 3 |
| **Added identity model (repo/branch/worktree/session)** | v2.0 implicitly assumed single repo, single worktree. Data model now carries identity from day one to avoid schema migration when adding multi-worktree or remote support |
| **Clarified data boundary for local-first claim** | v2.0 said "no repository content leaves the machine." True for RKP, but host agents have their own retention policies. Boundary is now documented explicitly |

### Criticism evaluated but not fully accepted

| Suggestion | What we took / what we pushed back on |
|---|---|
| **"Dual deployment (local + remote) from day one"** | Took: identity model and data model are remote-ready from day one. Pushed back: building and operating a remote deployment for MVP is premature for a startup. Commercial wedge remains local-first |
| **"Coarse module mapping is not a differentiator"** | Took: don't over-invest in graph features. Pushed back: module mapping is valuable when tied to actionable context (scoped rules, test locations, commands). Kept but scoped to what's actionable |
| **"MCP Apps makes web UI lower effort than implied"** | Took: added to open questions as near-term governance UI option. Pushed back: CLI-first is correct for MVP launch; App-readiness doesn't mean App-required |
| **"HTTP transport is already easy via FastMCP"** | Took: acknowledged FastMCP Streamable HTTP in stack. Pushed back: the hard part is not transport but state/sync/session management for remote deployments. Phase 2+ |
| **"Sourcegraph is already the intelligence layer"** | Sourcegraph pivoted away from neutrality — dropped Cody Free/Pro, Amp is their own agent. Their code graph is static references only. RKP's behavioral signals, skill projection, governance, and eval are orthogonal |

---

_End of PRD v3.0._
