# Repo Knowledge Plane — Product Requirements Document

_v1.0 — 2026-03-18. Consolidated from three independent drafts against shared research base (`docs/research.md`)._

---

## 1. Product Summary

Repo Knowledge Plane is a persistent, agent-neutral intelligence layer for software repositories. It continuously derives conventions, architecture boundaries, change context, and memory from a repository's code and history, then serves that knowledge through MCP so any coding agent or developer tool can query the same evidence-backed substrate. It is developer infrastructure — comparable to CI or observability — not another coding assistant. The positioning is: **"The memory and risk infrastructure for every coding agent."**

---

## 2. Problem Statement

AI coding tools have created a productivity paradox. Developers feel faster and often are faster on local tasks, but system-level outcomes are degrading.

DORA 2024 reports that 75% of developers perceive individual productivity gains from AI, yet AI adoption correlates with a 1.5% decrease in delivery throughput and 7.2% reduction in delivery stability. METR 2025 found experienced developers using AI took 19% longer on tasks while estimating they were 20% faster; high-AI-adoption teams merged 98% more PRs while review time rose 91%. GitClear's 2024-2025 analysis of 211 million changed lines shows code churn rising from 5.5% to 7.9%, copy-pasted code from 8.3% to 12.3%, refactoring dropping by over 60%, and code clone occurrence rising eightfold.

The root cause is structural. Today's agents optimize the session — they reason from the current working tree and a transient context window. They do not know which boundaries matter, which conventions are followed, which modules are fragile, or what broke last time. Each ecosystem reinvents partial solutions: Cursor re-embeds per session, Copilot stores 28-day scoped memory, Devin maintains product-native memory that doesn't leave Devin. None are persistent, cross-tool, or grounded in the behavioral history of the repository. Meanwhile, AGENTS.md — present in 60,000+ repositories — has no tooling to generate or maintain it from actual codebase analysis.

The repo knowledge plane treats the repository as a system with memory, not just a prompt with files.

---

## 3. Vision & Positioning

MCP is now an industry standard under the Linux Foundation's Agentic AI Foundation (AAIF), co-sponsored by Anthropic, OpenAI, Google, AWS, and Microsoft, with 10,000+ servers in production. AGENTS.md is also stewarded by AAIF and consumed by all major coding agents. This means the protocol and instruction surface the product builds on are not speculative — they are the converging standard.

Any agent that speaks MCP should be able to ask: what rules govern this area, what architecture does this code sit inside, what is the likely impact of this change, and what prior outcomes should shape the next action.

| Property | Why non-negotiable |
|---|---|
| **Cross-agent** | Value compounds only when the same understanding is available to Codex, Claude Code, Cursor, Copilot, Devin, and internal tools |
| **Persistent** | Knowledge must survive beyond sessions — six months of accumulated understanding must remain available |
| **Local-first** | No cloud required, code never leaves the machine by default; zero-procurement adoption |
| **Evidence-backed** | Every derived answer has provenance, timestamps, and confidence; declared facts distinguished from inferred heuristics |
| **Infrastructure, not persona** | Not a new "AI teammate" — quietly improves work done through existing tools |

---

## 4. Target Users & Persona Priority

| Persona | Job to be done | MVP role |
|---|---|---|
| **AI coding agent** | Before touching code, know how this repo works and what constraints matter | **Primary technical consumer** — every MCP design decision must work for machine consumption first |
| **Senior engineer / tech lead** | Make architectural intent and conventions legible for humans and agents | **Primary human champion** — validates output, drives adoption, provides feedback loop |
| **Developer onboarding** | Become productive without violating invisible rules | Early beneficiary — benefits from Day 1 artifacts but not the validation authority |
| **Platform / dev productivity team** | Provide one trusted repo intelligence layer for all approved agents | **Scaling buyer** — purchases and deploys for org; governance/fleet features are Phase 2+ |
| **Engineering manager** | Improve throughput without hidden quality tax | Important once risk scoring ships and outcomes can be quantified |

**MVP priority call:** Optimize for the tech lead + agent pair. The tech lead has the strongest pain around stale conventions, can validate synthesized output, and can champion adoption without org-wide rollout. The agent is the highest-frequency consumer. The platform team is the long-term buyer, but forcing platform-scale governance into MVP would slow the wedge.

_Assumption [A1]: Reevaluate after first 5-10 design partners. If platform teams consistently sponsor deployment first, shift roadmap emphasis earlier toward governance._

---

## 5. Initial Wedge Decision

Two wedge options from research: AGENTS.md / convention synthesis, and PR-time risk intelligence. This PRD selects **convention synthesis first**.

1. **Most universal immediate problem.** Every agent rediscovers conventions because instruction surfaces are incomplete, stale, or absent. Tooling to generate AGENTS.md from analysis is nonexistent.
2. **Fastest path to trust.** Convention synthesis produces useful output from the current snapshot and modest history. Risk predictions too early damage trust faster than they create value.
3. **Self-distributing artifact.** A generated AGENTS.md is visible in the repo, useful to anyone who opens it, and naturally attributable — better GTM than a hidden index.
4. **Builds the right substrate.** Accurate synthesis requires parsing, boundary detection, convention inference, and MCP with provenance — the foundation for every subsequent capability.

PR-risk intelligence is strategically critical but second-act. It depends on richer outcome data and calibration.

### First useful output in under five minutes

A developer runs `uvx repo-knowledge-plane init` and within five minutes receives:
- A draft `AGENTS.md` with repo-specific build commands, inferred conventions (labeled), declared rules (labeled), module boundaries, and do/don't guidance
- Optional companion files for `.github/copilot-instructions.md` and Cursor rules
- MCP resources queryable for conventions, modules, and architecture boundaries
- Low-confidence items flagged for human confirmation

_Assumption [A2]: "Under five minutes" defined for single-repo local indexing, modern laptop, repos ≤ ~250k LOC, one dominant build system._

---

## 6. MVP Scope (0-6 months)

### What ships

| Capability | Description |
|---|---|
| **Local indexing** | Persistent repo indexing from working tree + git history; tree-sitter parsing; SQLite persistence; in-memory graph for fast queries; incremental updates |
| **Convention synthesis** | Combines declared signals (AGENTS.md, README, lint/test config, docs) and inferred signals (naming patterns, test placement, import boundaries, error idioms, command discovery); declared and inferred remain separate in data model and responses |
| **Instruction generation** | Generate and refresh: `AGENTS.md`, `.github/copilot-instructions.md`, `.cursor/rules` — all projected from the same canonical convention model |
| **Architecture summary** | Module detection, path-to-module mapping, dependency edges, test coverage hints, ownership/contributor inference |
| **Change context signals** | Impact graphs for a diff, prior similar changes, recommended tests, "known fragile area" hints from churn/coupling — presented as explanatory signals, not a composite risk score |
| **MCP server** | Stable surface of resources and tools via MCP stdio transport |
| **Provenance** | Source, timestamp, extraction version, confidence, and validity window on every derived claim |

### What is explicitly deferred

- Composite risk *score* (single number/level like "medium-high") — ships when calibration data supports it
- Multi-repo enterprise graph federation
- Cloud-hosted control plane or dashboard
- Incident-management ingestion
- Broad vector/semantic search as primary retrieval
- Autonomous code modification based on inferred rules
- Deep cross-language semantic analysis for every ecosystem
- Merge gating (high-stakes pass/fail decisions)

### Core user flows

**Flow 1 — Repository bootstrap:** Tech lead runs `uvx repo-knowledge-plane init`. Reviews generated instruction artifacts. Accepts or edits. Starts using MCP server from their preferred agent.

**Flow 2 — Agent preflight:** Before editing code in a scope, agent queries conventions and architecture boundaries. Receives repo-specific constraints without the user pasting them into a prompt.

**Flow 3 — Change-aware assistance:** Developer proposes a diff. Agent queries impacted modules, recommended tests, and prior similar changes to avoid blind edits and weak validation.

---

## 7. MCP Surface

### Resources

| URI | Purpose |
|---|---|
| `rkp://repo/overview` | Languages, build/test entrypoints, module map, indexing status |
| `rkp://repo/conventions` | Declared and inferred conventions with confidence and evidence |
| `rkp://repo/instructions/{consumer}` | Synthesized instruction content for a target consumer (`agents-md`, `copilot`, `cursor`) |
| `rkp://repo/architecture/boundaries` | Module and boundary summary with ownership and dependency hints |
| `rkp://repo/module/{module_id}` | Focused summary: boundaries, owners, tests, dependencies |
| `rkp://repo/change/{change_ref}/impact` | Computed impact summary for a diff or commit |

### Tools

| Tool | Parameters | Purpose |
|---|---|---|
| `synthesize_repo_instructions` | `scope`, `consumer`, `write_files` | Generate instruction artifacts from canonical knowledge |
| `get_conventions` | `path_or_symbol`, `include_evidence` | Return relevant rules for a path, symbol, or module |
| `explain_module` | `path_or_symbol` | Summarize module: boundaries, owners, tests, related paths |
| `get_impact_graph` | `change_ref`, `depth`, `include_tests`, `include_owners` | Structural impact for a commit, branch diff, or working-tree diff |
| `find_prior_changes` | `path_or_symbol`, `limit`, `include_failures` | Similar historical changes and linked outcomes |
| `recommend_tests` | `change_ref`, `confidence_threshold` | Suggested tests with confidence and evidence |
| `recommend_reviewers` | `change_ref`, `max_reviewers` | Likely reviewers from ownership and history |
| `refresh_index` | `paths` | Incrementally update knowledge after file changes |

Every response includes a `provenance` block (index version, repo HEAD, generation timestamp, confidence). Declared vs. inferred knowledge is always distinguished.

### Example: get_conventions

```json
// Request
{ "tool": "get_conventions",
  "arguments": { "path_or_symbol": "src/payments", "include_evidence": true } }

// Response
{
  "scope": "src/payments",
  "declared": [
    { "rule": "Do not call payment providers directly from API handlers",
      "source": "docs/architecture.md" }
  ],
  "inferred": [
    { "rule": "Provider adapters live under src/payments/providers/*",
      "confidence": 0.89,
      "evidence": ["src/payments/providers/stripe.py", "src/payments/providers/adyen.py"] }
  ],
  "provenance": { "index_version": "2026-03-17T18:22:00Z", "repo_head": "abc1234" }
}
```

### Example: get_impact_graph

```json
// Request
{ "tool": "get_impact_graph",
  "arguments": { "change_ref": "working_tree", "depth": 2,
                 "include_tests": true, "include_owners": true } }

// Response
{
  "change_ref": "working_tree",
  "touched_paths": ["src/repo_graph/indexer.py"],
  "affected_modules": [
    { "id": "repo_graph", "reason": "contains changed file" },
    { "id": "mcp_server", "reason": "imports repo_graph symbols" }
  ],
  "recommended_tests": [{ "id": "tests/test_indexer.py", "confidence": 0.87 }],
  "owners": [{ "name": "platform-infra", "confidence": 0.62 }],
  "change_signals": ["elevated recent churn in module", "change crosses module boundary"],
  "provenance": { "index_version": "2026-03-17T18:22:00Z", "repo_head": "abc1234" }
}
```

---

## 8. Architecture & Technical Constraints

### Stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.12+ | Ecosystem leverage, fast iteration, statistical modeling path |
| MCP serving | FastMCP (Python MCP SDK) | Best agent host compatibility |
| Parsing | tree-sitter + `tree-sitter-language-pack` (170+ grammars) | Incremental, broad coverage, no build required |
| Git analysis | pygit2 | High-throughput local git operations |
| Graph algorithms | rustworkx | Compiled performance for traversals and coupling |
| Persistence | SQLite (WAL mode) | Simple distribution, low idle cost, sufficient for single-repo |
| Transport | MCP stdio (first) | Least operational complexity |
| Distribution | `uvx` | Zero-dependency adoption path |

### Key decisions

| Decision | Rationale |
|---|---|
| Local-first over cloud-first | Security trust, zero-infra adoption, works in sensitive repos |
| SQLite + in-memory graph over standalone graph DB | Simpler distribution, lower idle cost; query profile is short traversals |
| Incremental re-analysis over full re-index | Required to meet latency targets in active repos |
| Vector search deferred | Initial value is structural understanding, not semantic retrieval |
| Provenance mandatory on all derived claims | Part of the contract, not an implementation detail |
| Heuristic signals before ML scoring | Interpretable, debuggable, achievable without outcome training data |

### Performance targets

| Target | Value |
|---|---|
| Warm MCP query latency | < 500ms median for top-5 query types |
| Initial index (250k LOC repo) | < 5 minutes |
| Incremental update (single file change) | < 2 seconds |
| Memory footprint (idle server) | < 200MB |

_Assumption [A3]: SQLite + in-memory graph sufficient for first year of single-repo use. If pilot repos exceed bounds, Rust core acceleration moves forward sooner._

---

## 9. Phased Roadmap

| Phase | Timeframe | Focus | Key unlock |
|---|---|---|---|
| **1. Convention synthesis** | Months 0-3 | Local indexing, convention extraction, instruction synthesis, MCP server | First useful output; cross-agent distribution via artifacts |
| **2. Semantic code graph** | Months 3-6 | Module detection, dependency edges, ownership inference, structural impact queries | Reliable structural understanding; change-aware guidance |
| **3. Behavioral layer** | Months 6-9 | Git history mining: hotspots, change coupling, contributor concentration, recurring patterns | Longitudinal intelligence beyond current snapshot; moat data |
| **4. Risk scoring & eval** | Months 9-12 | Calibrated risk scores, outcome feedback loop, agent evaluation framework | Trustworthy forward-looking risk; measurable improvement loops |

Phases overlap slightly in implementation (Phase 2 prep starts ~Month 2), but product milestones follow the sequence above.

---

## 10. Success Metrics

### 90-day (activation and trust)

| Metric | Target | Measurement |
|---|---|---|
| Time to first useful output | < 5 min median | Instrumented from `init` to first artifact |
| Instruction artifact acceptance | ≥ 70% accept with light edits | Manual review in design-partner cohort |
| Convention query accuracy | ≥ 80% correct in spot checks | Sampled evaluation by pilot tech leads |
| Agent preflight adoption | ≥ 50% of sessions invoke RKP | MCP server call logs |

### 6-month (workflow impact)

| Metric | Target | Measurement |
|---|---|---|
| PR review iteration reduction | 15-20% vs baseline | Pilot repos, normalized for volume |
| Onboarding time reduction | ≥ 25% to first accepted PR | New contributor cohort |
| Test recommendation precision | ≥ 0.70 | Evaluation against actual failures |
| Weekly active agent sessions | ≥ 3 sessions/repo/week | MCP telemetry |

### 12-month (system improvement)

| Metric | Target | Measurement |
|---|---|---|
| Escaped regression reduction | ≥ 20% vs pre-adoption baseline | Pilot repos with outcome tracking |
| PR cycle time reduction | ≥ 25% for AI-assisted changes | Open to merge, end-to-end |
| Multi-agent integration | ≥ 40% of installs use 2+ agents | Connection telemetry |
| Agent task quality lift | ≥ 15% first-pass acceptance | Controlled with/without RKP |

_Assumption [A4]: Design-partner data quality supports regression measurement without heavy manual labeling._

---

## 11. Competitive Differentiation

| Competitor | Strength | Structural limitation |
|---|---|---|
| **GitHub / Copilot** | Platform integration, user base | Incentive is GitHub lock-in, not cross-agent neutrality |
| **Cursor** | IDE-native context, fast iteration | Workflow ownership at editor layer; intelligence is a Cursor advantage, not portable |
| **Sourcegraph / Cody** | Semantic graph, cross-repo search | Weaker on behavioral risk and longitudinal agent memory |
| **CodeScene** | Proven behavioral methodology | Retrospective, human-dashboard oriented; not real-time agent consumption |
| **Devin** | Validates persistent memory value | Vertically integrated; not neutral substrate |
| **Potpie** | Code knowledge graphs, artifact gen ($2.2M pre-seed Feb 2026) | Closest structural competitor but not MCP-native, own agent suite, no AGENTS.md generation |

**False moats:** Graph database, embeddings, MCP server, AI-generated docs — table stakes.

**Real moats:** Longitudinal private repo data, evidence graph quality, cross-agent neutrality, calibrated risk signals teams trust, switching cost as the knowledge plane becomes the repo's living memory.

---

## 12. Go-to-Market & Pricing

**Distribution:** Open-source core via `uvx`. MCP registry listing for agent ecosystem discoverability. Used *from within* existing tools.

**Viral artifact:** Generated AGENTS.md — visible in-repo, useful to anyone, naturally attributable.

**Adoption loop:** Tech lead installs locally → generates artifacts → team sees value → platform team standardizes → organization purchases.

| Tier | Price | Includes |
|---|---|---|
| Individual (OSS) | Free | Full local analysis, synthesis, MCP server |
| Team | ~$20-35/active dev/month | Shared config, cross-member conventions, telemetry (active = committed in last 90 days) |
| Enterprise | Custom | SSO, policy, audit, air-gapped, multi-repo admin |

Pitch: not "pay for more AI" but "infrastructure that makes AI tools you already bought safer and more effective."

_Assumption [A5]: If local-first usage alone captures most value, monetization leans on coordination, governance, and evaluation features._

---

## 13. Risks & Mitigations

| Risk | Category | Mitigation |
|---|---|---|
| Polyglot parsing quality inconsistent | Technical | Supported language set; surface unsupported areas explicitly; parser quality scoring |
| Inferred conventions wrong but sound authoritative | Technical | Declared/inferred separation in every response; confidence thresholds; "needs confirmation" output |
| Cold start on sparse-history repos | Technical | First wedge valuable from current snapshot alone; history signals added opportunistically |
| Large repos exceed performance targets | Technical | Incremental indexing; warm graph; Rust acceleration path; scope filters |
| Provenance gaps or stale data | Technical | Version every extraction; timestamp every resource; prefer incomplete-but-current |
| Dismissed as "just an AGENTS.md generator" | Product | AGENTS.md is first delivery surface of broader intelligence layer; expose MCP queries Day 1 |
| Overlap blur with Copilot/Cursor/Sourcegraph | Product | Position as neutral infrastructure *underneath* existing tools |
| Buyer-user divergence | Commercial | Free tier for pull; governance as paid expansion |
| Incumbents absorb shallow features | Commercial | Accelerate toward longitudinal data, trust calibration, cross-agent neutrality |
| Risk score trust if shipped prematurely | Product | Defer composite score until calibration data exists; ship signals first |

---

## 14. Acceptance Criteria (P0)

| # | Criterion |
|---|---|
| AC-1 | `uvx repo-knowledge-plane init` produces a non-template AGENTS.md with repo-specific commands, conventions, and module boundaries within 5 min on a 250k LOC Python repo |
| AC-2 | Generated instructions distinguish declared from inferred rules with evidence references |
| AC-3 | MCP server starts via stdio and responds to all documented resource reads and tool calls |
| AC-4 | `get_conventions` returns scoped conventions with confidence and evidence for a given path |
| AC-5 | `get_impact_graph` returns affected modules, recommended tests, and change signals for a working-tree diff |
| AC-6 | `recommend_tests` returns ≥ 1 relevant test with confidence ≥ 0.5 for changes in tested modules |
| AC-7 | `explain_module` returns boundary, dependency, ownership, and test info for a top-level module |
| AC-8 | Incremental index update completes in < 2 seconds for a single-file change |
| AC-9 | All MCP responses include provenance (index version, repo HEAD, timestamp, confidence) |
| AC-10 | No repository content transmitted off the local machine by default |
| AC-11 | Product runs without any cloud service dependency |
| AC-12 | Companion instruction files can be generated from the same canonical model |

---

## 15. Assumptions Register

| ID | Assumption | Revisit trigger |
|---|---|---|
| A1 | Tech lead is the right MVP champion; platform team is scaling buyer | Platform teams sponsor first in 5-10 design partners |
| A2 | "Under 5 min" achievable for repos ≤ 250k LOC, one build system | Empirical testing on diverse repos |
| A3 | SQLite + in-memory graph sufficient for first year single-repo use | Pilot repos exceed memory/latency bounds |
| A4 | Design-partner data supports regression measurement without heavy manual labeling | First measurement cycle reveals insufficient baseline |
| A5 | Free-local / paid-team boundary captures enough value in team tier | Local-only usage delivers most value |
| A6 | Convention synthesis is right first wedge over PR-risk scoring | Early users consistently ask for risk first |
| A7 | Teams accept generated instructions in draft mode before auto-update | Pilot teams immediately want auto-commit |
| A8 | Tree-sitter provides sufficient extraction quality for supported languages | Convention accuracy below threshold for important language |
| A9 | MCP stdio is right first transport | Major agent hosts require SSE before adoption |
| A10 | Review friction, onboarding, and agent task quality are most compelling initial metrics | Buyers consistently ask for different metrics |

---

## 16. Open Questions & Decisions Needed

### Decided

| # | Decision | Rationale |
|---|---|---|
| D1 | Convention synthesis as initial wedge | Lower cold-start, self-distributing artifact, builds right substrate |
| D2 | Tech lead + agent pair as MVP priority | Strongest pain, best validation authority, bottom-up adoption |
| D3 | Defer composite risk score; ship individual signals | Uncalibrated scores risk trust collapse; signals are independently valuable |
| D4 | Platform team features (governance, fleet) are Phase 2+ | Forcing platform-scale governance into MVP would slow the wedge |

### Open

| # | Question | Notes |
|---|---|---|
| Q1 | Which repos and languages define launch support envelope? | Needs empirical validation |
| Q2 | Minimum evidence chain before product shows explicit risk score? | Ties to Phase 4 readiness gate |
| Q3 | Should MVP include lightweight PR annotation surface? | Accelerates feedback but adds complexity; decide at Month 2 |
| Q4 | How should inferred conventions be reconciled when they conflict with declared rules? | Recommendation: surface the conflict, declared as default |
| Q5 | What correction/deletion workflow for memory governance? | Regulated environments may need audit trail |
| Q6 | First non-MCP surface: GitHub App, CLI workflow, or none? | |
| Q7 | Canonical pricing unit for multi-repo orgs: seat, repo, or protected surface? | |
| Q8 | Evaluation harness for agent quality improvement without benchmark contamination? | |
| Q9 | Which human buyer owns budget first in lighthouse accounts? | Depends on design-partner findings |
