# Repo Knowledge Plane — Consolidated Research

_All research conducted 2026-03-17. Consolidated 2026-03-17._
_Sources: 7 research files + 2 agent memory files, deduplicated and critically synthesized._

---

## 1. Executive Summary

A **repo knowledge plane** is a persistent, agent-neutral intelligence substrate for software repositories. It is not another coding agent. It is the shared memory, risk, and architecture layer that sits underneath many agents: Codex, Claude Code, Cursor, Devin, GitHub Copilot, Augment, open-source agents, and internal tools.

### Core thesis

The durable moat is not the agent UI. It is the **longitudinal private dataset** and the **evidence-backed models** built from temporal repo structure, PR/review outcomes, CI/test history, incidents and rollbacks, inferred and declared conventions, and agent trajectories. That is difficult for a stateless agent vendor to reproduce inside a single session.

### Product frame

> A multi-tenant system that continuously ingests repository structure, change history, review history, test outcomes, incidents, architecture decisions, and team conventions; turns that into a temporal knowledge graph plus retrieval and scoring services; and exposes it through an MCP server so any coding agent or developer tool can query it.

### Positioning statement

**"The memory and risk infrastructure for every coding agent."**

This should be sold as **platform infrastructure** (like CI, observability, feature flags), not as "yet another coding assistant."

---

## 2. Why This Category Exists Now

### Converging trends (2025-2026)

1. **Coding agents are mainstream.** GitHub Copilot (20M users), Cursor ($2B ARR), Codex, Claude Code, Devin, Amazon Q, GitLab Duo, Augment, Windsurf, and open-source agents are all shipping agentic workflows.

2. **MCP is a real interoperability standard.** Versioned spec through 2025-11-25 with formal governance, SDK tiering (TypeScript/Python/Go Tier 1), cross-vendor adoption (Anthropic, OpenAI, Google, Microsoft), and 8M+ server downloads. It provides host-client-server architecture, JSON-RPC messaging, standard transports (stdio, Streamable HTTP), and OAuth-based auth.

3. **AGENTS.md is the instruction standard.** Donated to Linux Foundation's Agentic AI Foundation (December 2025). 60,000+ repos. Supported by Codex, Copilot, Cursor, Gemini CLI, Devin, Windsurf, and more. No tool auto-generates and maintains it from codebase analysis — this is whitespace.

4. **Agent UX has advanced faster than agent memory.** Most tools still answer from a mix of current repo snapshots, local instructions, ad hoc indexes, and the current chat session. That is structurally weak for organization-scale engineering work.

5. **Research is shifting toward persistent experience.** SWE-Exp, EXPEREPAIR, Prometheus, MemoryAgentBench show persistent memory improves agent behavior. GraphCoder, CodexGraph, GraphRAG show graph retrieval beats naive text-only retrieval for code understanding.

### The productivity paradox is real

**DORA 2024** (39,000 respondents):
- 75% of developers report individual productivity gains from AI
- Yet AI adoption was associated with **1.5% decrease in delivery throughput** and **7.2% reduction in delivery stability** at the system level
- Root cause: AI increases batch size (bigger changesets), and larger batches are riskier and harder to review

**GitClear 2024** (211M changed lines of code):
- Code churn rose from 5.5% to 7.9% (44% increase)
- Copy/pasted code rose from 8.3% to 12.3%
- Refactoring fell from 25% to under 10% (60%+ decline)
- 2025 update: code clone occurrence rose **eightfold** vs. pre-AI baseline

**METR 2025**:
- AI tooling **increased task completion time by 19%** for experienced developers — while those same developers estimated a 20% speedup (39pp perception gap)
- Teams with high AI adoption merge 98% more PRs, but **PR review time increases 91%**

**Context rot** (Chroma Research, 2025):
- Every frontier model shows performance degradation as context length increases
- 30%+ accuracy drops for middle-of-context content
- JetBrains (Dec 2025): smart context management outperforms raw context expansion

**Structural argument**: Even if context windows scale infinitely, a knowledge plane solves different problems — *persistence across sessions*, *structure* (knowing which parts matter for a given query), and *history* (git-mined patterns no context window can derive from current files alone).

Sources: [DORA 2024](https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report), [GitClear 2024](https://www.gitclear.com/coding_on_copilot_data_shows_ais_downward_pressure_on_code_quality), [GitClear 2025](https://www.gitclear.com/ai_assistant_code_quality_2025_research), [METR study](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), [Chroma context rot](https://research.trychroma.com/context-rot), [JetBrains context management](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)

---

## 3. Market Data & Sizing

### AI coding tool market

| Source | 2024/2025 Estimate | Forecast | CAGR |
|---|---|---|---|
| Grand View Research | $4.86B (2023) | $26B by 2030 | 27.1% |
| Market.us | $5.5B (2024) | $47.3B by 2034 | 24% |
| Mordor Intelligence | $7.37B (2025) | $23.97B by 2030 | 26.6% |
| Future Market Insights | $6.43B (2024) | $122B by 2035 | 30.7% |

Conservative midpoint: **$5–7B in 2024–2025, heading toward $25–50B by 2030–2034** at ~25% CAGR.

### Active user base

- **GitHub Copilot**: 20M cumulative users; 1.3M paid subscribers; 42% market share; 90% of Fortune 100
- **Cursor**: 18% market share; $2B ARR (Feb 2026, up from $100M ARR in 2024)
- **Amazon Q Developer**: ~11% market share
- **Total**: ~27M developers actively using AI coding tools, scaling toward 50M+ by 2027

### TAM for a cross-tool knowledge layer

A knowledge plane sits above individual coding tools. If priced at $15–30/seat/month:
- TAM: $5–10B ARR at full penetration
- Realistic SAM (enterprise teams 10–500 engineers, 3+ AI tools): $500M–2B ARR in 3–5 years

### Developer time allocation

- **58–70% of developer time** is spent understanding existing code, not writing new code
- Read:write ratio ranges from **7:1 to 200:1**
- Developers spend **30–50% of time debugging**
- Actual new code writing: **<10% of work time**

**Implication**: AI tools today aggressively optimize the <10% of time (writing code). A knowledge plane optimizes the 58–70% (understanding code). This is where the asymmetric opportunity sits.

Sources: [TechCrunch — Copilot 20M](https://techcrunch.com/2025/07/30/github-copilot-crosses-20-million-all-time-users/), [Sacra — Cursor](https://sacra.com/research/cursor-at-100m-arr/), [Stack Overflow 2025 AI](https://survey.stackoverflow.co/2025/ai)

---

## 4. Product Definition

### What a repo knowledge plane is

- **Persistent**: survives chat/session boundaries
- **Cross-agent**: queryable by Claude Code, Codex, Cursor, Devin, OSS agents, internal bots
- **Repository-aware**: understands structure, symbols, architecture boundaries, ownership, history, CI/test outcomes, incidents
- **Action-guiding**: returns recommendations and risk scores, not just retrieval snippets
- **Governed**: auditable provenance, policy controls, redaction scopes, access boundaries

### What it is NOT

- Just code search
- Just a wiki generator
- Just an engineering metrics dashboard
- Just an agent memory store
- Just a PR review bot

It is the layer underneath all of those.

### Shortest definition

> A temporal software knowledge graph + retrieval system + risk/eval engine + MCP serving layer.

### Core queries it answers

- "What are the architectural boundaries here?"
- "What conventions does this team actually follow?"
- "What is the likely blast radius of this change?"
- "What broke the last three times this module changed?"
- "Which tests matter for this diff, and what is still unprotected?"
- "What instructions should any agent inherit before touching this area?"

### Core entity model

- **Repository**: repo, branch, commit, tag, path, file, symbol, module, package, service
- **Change**: diff, PR, review comment, reviewer, merge, rollback, hotfix
- **Execution**: build, workflow, job, test target, test result, deployment, alert, incident
- **Organization**: team, owner, oncall, service catalog entry, policy, environment
- **Knowledge**: architecture boundary, convention, decision, instruction, quality rule, memory item, prior case
- **Agent**: agent run, model, skill, tool call, eval run, outcome

### Temporal relations

`depends_on`, `calls`, `contains`, `owned_by`, `tested_by`, `failed_in`, `caused`, `fixed_by`, `reviewed_by`, `violates`, `supersedes`, `similar_to`, `co_changes`

### Critical design principle

Every derived claim must retain: source system, timestamp and validity interval, extraction version, evidence URI, confidence score. Without provenance, the product becomes untrustworthy.

---

## 5. Jobs To Be Done & Personas

### Persona 1: Developer joining a new codebase

- Average time to full productivity: **3–9 months**
- Cost of one onboarding: **$75,000+** in lost productivity over 6 months
- With AI: 10th PR in 49 days vs. 91 without (46% acceleration, still months)
- **Needs**: Persistent, queryable architectural rationale. Convention awareness. Which modules are fragile/high-churn.

### Persona 2: Senior engineer / tech lead

- Architecture erosion is slow and invisible: "as-implemented" diverges from "as-intended"
- Convention enforcement requires manual review; agents don't know conventions without explicit context
- AI-generated code accelerates entropy: refactoring rate down 60%+ since 2021
- **Needs**: Machine-readable architectural intent. Drift detection. Convention enforcement.

### Persona 3: Engineering manager / VP Engineering

- McKinsey: companies with significant tech debt spend **20–40% of development budget** on poor code quality
- No reliable signal for "which PR will cause a regression?" — review bottleneck growing (91% increase per DORA)
- Only 39% of developers trust AI-generated code, yet ~70% of code may be AI-generated
- **Needs**: Quantified risk scores for PRs. Architecture health. Justifiable tooling ROI.

### Persona 4: Platform engineering / developer productivity team

- Provide a neutral intelligence layer usable by many agent vendors
- Reduce repeated reinvention of repo indexing and team conventions
- Measure which agent/model/skill combinations actually work in-house
- Enforce governance, auditability, and data isolation
- **Needs**: Cross-tool substrate. Evaluation layer. Governance.

### Persona 5: The AI coding agent as "user"

The novel, differentiated persona — the agent as a first-class consumer.
- No cross-session memory (each session starts from zero)
- No architectural conventions in context window
- No regression risk awareness (which files are high-churn, historically fragile)
- No dependency semantics (what else breaks if this file changes)
- **Needs**: Persistent structured knowledge accessible via MCP tool calls.

Sources: [DX — onboarding](https://getdx.com/blog/ai-cuts-developer-onboarding-time-in-half/), [DORA 2024](https://dora.dev/research/2024/dora-report/)

---

## 6. Competitive Landscape

### Market structure

The market is fragmented across distinct layers, each solving part of the problem:

| Layer | Who plays here | What they miss |
|---|---|---|
| Code quality / behavioral analytics | CodeScene, Trunk.io | Not agent-serving; no cross-session memory |
| Static architecture recovery | SciTools Understand, Structure101, Lattix | No AI integration; read-only snapshots |
| AI coding agents with context | Augment Code, Cursor/Windsurf, Aider | Per-session, per-IDE; no durable knowledge layer |
| AI code review / risk | CodeRabbit, Graphite, Qodo, Snyk | Limited cross-system memory; partial view |
| Engineering intelligence | LinearB, Jellyfish, Swarmia, DX, Harness SEI | Weak agent-time retrieval |
| Agent memory / graph infra | Mem0, Zep/Graphiti | Not opinionated enough for repo intelligence |
| Internal developer portals | Backstage, Compass, Cortex, OpsLevel | Weak code-level change reasoning |
| Emerging code graph / MCP | Potpie, CodePrism, CodeCortex | Early, narrow language support, no risk modeling |

**No product in this set is clearly a neutral, cross-agent persistent repo knowledge substrate.**

### Capability matrix (as of March 2026)

| Platform | Cross-session memory | Architectural understanding | Regression-risk prediction | Cross-tool interop |
|---|---|---|---|---|
| GitHub Copilot | **Strong** (repo-scoped) | Partial | Partial | Partial-Strong |
| Sourcegraph / Cody | Partial | **Strong** | Weak-Partial | **Strong** |
| Cursor | Partial | Partial-Strong | Partial | **Strong** |
| Devin / Cognition | **Strong** (product-native) | **Strong** | Partial | **Strong** |
| Windsurf / Codeium | Partial | **Strong** (RAG) | Weak-Partial | **Strong** |
| Graphite | Weak-Partial | Partial | Partial-Strong (PR-time) | Partial |

### Key competitor analysis

#### CodeScene

- **Core value**: Behavioral code analysis — git history mining for hotspots, change coupling, code health. Hybrid git mining + static metrics.
- **Methodology**: Hotspot analysis (commit frequency x code health), change coupling (co-commit patterns), knowledge concentration (bus factor), team coupling (Conway's Law violations).
- **Pricing**: €18/active author/month. Cloud and on-prem.
- **Limitations**: Retrospective only (no forward risk on proposed changes). Not agent-serving (no MCP, no structured output for agents). No cross-session memory for agents. No architectural semantic graph.
- **Framing**: Closest methodological predecessor. Serves engineering managers, not AI agents. Could be a data partner or the methodology to subsume and reposition agent-first.

#### Sourcegraph / Amp

- **Core value**: Enterprise code search with cross-repo navigation. Code graph from static analysis (cross-references, symbols, call sites).
- **Strategic shift**: Cody Free/Pro discontinued July 2025. Amp is the new agentic product. Cody Enterprise remains.
- **Normsky architecture**: Deterministic code graph traversal (SCIP-based) beats asking the LLM what to search. Pre-computed persistent context. 30% completion acceptance rate.
- **Limitations**: Code graph is static-reference-only — no behavioral signals, no git history analysis, no risk modeling. No persistent cross-session architectural memory.
- **Framing**: Potential MCP integration partner. Strong on retrieval and interoperability plumbing. Gap is durable memory + risk intelligence.

#### Devin / Cognition

- **Core value**: Autonomous coding with strong product-native memory. Knowledge items by triggers; repo/org/enterprise scopes. DeepWiki generates architecture diagrams/docs. 50,000+ repos indexed.
- **Limitations**: Memory is powerful but Devin-scoped, not a neutral substrate. DeepWiki is wiki-format for humans, not structured for agent injection. No regression risk scoring from git history.
- **Framing**: Demonstrates what mature persistent-memory coding looks like. Gap is neutrality: memory and risk portable across all coding-agent surfaces.

#### GitHub Copilot

- **Copilot Memory**: Repository-specific, stores with citations, validates against current code, 28-day retention unless revalidated.
- **Coding agent**: Runs in ephemeral GitHub Actions environments with hooks/skills/MCP.
- **Limitations**: MCP supports tools only (not resources/prompts), no OAuth remote MCP. No calibrated regression-risk product. Single-repo per task. Memory is Copilot-scoped.
- **Why they won't build this**: Microsoft benefits when teams are on GitHub. Cross-tool neutrality is a strategic contradiction.

#### Potpie

- **What it does**: Graphical representation of software ecosystems. Pulls from GitHub, Sentry, Jira, Notion. Generates AGENTS.md, system designs, release notes. $2.2M pre-seed (February 2026).
- **Performance**: Customer with 40M-line codebase cut root-cause analysis from ~1 week to ~30 minutes.
- **Gap**: Focuses on connecting tool ecosystem and generating documentation artifacts. Not focused on git-behavioral signals, change coupling, or regression risk prediction.
- **Framing**: Closest funded direct competitor in spirit. Validates market exists and is early-stage. Differentiated by behavioral risk modeling and real-time agent context.

#### Augment Code

- **Technical approach**: Semantic vector indexing. 200K token Context Engine. Context Lineage adds recent commit history.
- **Limitations**: Per-session context injection, not persistent architectural knowledge. No behavioral git analysis beyond commit summaries.
- **Framing**: Context Engine MCP is a direct integration target — knowledge plane feeds it enriched context Augment's vector index cannot derive.

### Why incumbents won't build this

- **GitHub/Microsoft**: Optimizes for the GitHub platform. Cross-tool neutrality conflicts with GitHub lock-in strategy.
- **Cursor**: Focused on editor UX. A cross-tool knowledge plane requires neutrality conflicting with Cursor's goal of being the preferred IDE.
- **Anthropic**: Sells model API. Claude Code is a thin CLI, not a platform. No persistent storage model.
- **Structural argument**: Any single tool that builds this becomes a knowledge plane for their tool only. A neutral MCP server becomes more valuable the more tools it connects. This is structurally difficult for incumbents to replicate without undermining their core strategy.

### OSS landscape

- **OpenHands**: Strong open agent runtime; no neutral persistent cross-tool repo memory.
- **Cline**: Strong IDE agent + MCP; memory/governance tool-local.
- **Aider**: Tree-sitter repo map rebuilt per session. No persistence, no behavioral signals.
- **Continue**: Source-controlled AI checks and CI enforcement; less shared long-horizon memory graph.
- **MCP reference Memory server**: Knowledge-graph persistent memory. Building block, not repo-specific.
- **Graphiti (Zep)**: Temporal context graph directly aligned with persistent agent memory. Best-in-class design pattern.
- **Mem0**: Generalized memory layer, not repo-specific.

Sources: [CodeScene](https://codescene.com/product/behavioral-code-analysis), [Sourcegraph Amp](https://sourcegraph.com/blog/why-sourcegraph-and-amp-are-becoming-independent-companies), [Devin DeepWiki](https://docs.devin.ai/work-with-devin/deepwiki), [Potpie funding](https://techfundingnews.com/the-startup-building-a-knowledge-graph-for-code-raises-2-2m-to-make-ai-agents-actually-useful/), [Augment Context Engine](https://www.augmentcode.com/context-engine)

---

## 7. MCP Protocol & Interoperability Standards

### MCP maturity (2024-2026)

- **Initial launch**: Anthropic, Nov 25, 2024
- **Spec cadence**: Dated releases through 2025-11-25 with multiple revisions
- **Governance**: Formalized working groups and SDK tiering (conformance tests Jan 23, 2026; tiering published Feb 23, 2026)
- **Cross-vendor adoption**: OpenAI Responses API MCP support (May 21, 2025), Codex MCP integration, GitHub Copilot coding agent MCP support

### What MCP standardizes

- Host-client-server architecture with isolation and capability negotiation
- Standard JSON-RPC message model and transports (stdio, Streamable HTTP)
- Three primitives: **resources** (app-driven context), **tools** (model-invoked execution), **prompts** (user-controlled reusable templates)
- Transport-level auth guidance (OAuth/OIDC)
- In-protocol discovery: `tools/list`, `resources/list`, `prompts/list` with pagination
- Registry model: `server.json` schema + OpenAPI registry API (still in preview)

### Limitations relevant to product design

- **Protocol-level security is not fully enforceable by spec alone.** Implementors must build consent/access controls.
- **Authorization is optional.** Creates uneven baseline security across servers.
- **Transport fragmentation.** Some hosts emphasize stdio + streamable HTTP, some still expose SSE.
- **Registry is still preview.** Explicit warnings about data resets/breaking changes.
- **Host behavioral divergence.** Approval semantics, tool filtering, and supported modes differ by host/runtime.
- **Experimental task model.** Useful for durable long-running analysis but currently marked experimental.

### Recommended MCP surface for the knowledge plane

**Resources** (durable, auditable knowledge artifacts):
- `rkp://tenant/repo/architecture/boundaries`
- `rkp://tenant/repo/conventions`
- `rkp://tenant/repo/decisions`
- `rkp://tenant/repo/module/{id}/history`
- `rkp://tenant/repo/change/{sha}/impact`

**Tools** (computed/interactive queries):
- `analyze_change_risk(change_ref, include_evidence)`
- `get_impact_graph(change_ref, depth, include_tests, include_owners)`
- `find_prior_regressions(module_or_symbol, timeframe)`
- `synthesize_repo_instructions(scope, consumer)`
- `recommend_tests(change_ref, confidence_threshold)`
- `explain_boundary_violation(diff_ref)`
- `record_outcome(assessment_id, observed_outcome)`

**Prompts** (repeatable workflows):
- "pre-merge risk review"
- "architecture conformance review"
- "module handoff summary"

### Trust and boundary controls (non-optional)

- Scope by roots/workspace boundaries
- Default to read-only toolsets; require explicit elevation for mutations
- Emit provenance on every answer (commit range, ADR, test evidence, confidence level)
- Separate trust tiers in responses (verified artifact vs inferred heuristic)
- Avoid token passthrough anti-patterns

### Adjacent interop standards

- **A2A (Agent2Agent)**: Agent-to-agent collaboration. Complementary to MCP. v1.0.0 released Mar 12, 2026.
- **ACP (Agent Client Protocol)**: Editor/client-to-agent runtime protocol. Active RFD cadence.
- **Practical takeaway**: MCP first, then bridge to A2A/ACP adapters where demand appears.

Sources: [MCP spec](https://modelcontextprotocol.io/specification/2025-11-25), [MCP announcement](https://www.anthropic.com/news/model-context-protocol), [OpenAI MCP](https://developers.openai.com/codex/mcp/), [A2A](https://github.com/a2aproject/A2A), [ACP](https://agentclientprotocol.com/get-started/introduction)

---

## 8. Academic Research Foundations

### 8.1 Architecture recovery

**Classical approaches**:
- **Reflexion Method** (Murphy et al.): Human specifies hypothesized architecture, tool extracts source model, compare for divergence. Requires expert input.
- **DSM-based recovery**: Dependency Structure Matrix algorithms (provider proximity, spectral partitioning) automatically group files into layers/components based on import/call dependencies. Lattix implements this.

**LLM-based approaches (2025-2026)**:
- **ArchAgent** (arxiv 2601.13007): Combines static analysis, multi-level reference graphs, and LLM synthesis. Handles up to 22,000 files. F1=0.966 vs DeepWiki's 0.860. Dependency context improves F1 by 0.07-0.11 points.
- **Enabling Architecture Traceability** (ICSA 2025): LLMs succeed at structural/stylistic elements but struggle with complex class relationships and design patterns.

**What's tractable now**:
- Dependency graph extraction via tree-sitter/CodeQL/LSP is solved for most languages
- DSM layering detection works reliably on JVM/C++ codebases
- LLM-assisted architecture summarization (ArchAgent pattern) achieves high F1 on file-to-component assignment
- **Hybrid clustering + LLM outperforms either approach alone**

### 8.2 Change impact analysis & defect prediction

**Behavioral code analysis** (Tornhill, CodeScene methodology):
- **Hotspot detection**: Files weighted by commit frequency x code complexity. Power law: 5-15% of files receive the vast majority of commits.
- **Change coupling**: Files that co-commit are temporally coupled, even without static import relationships. Reveals hidden architectural dependencies, distributed monolith patterns. Score: `co_commits(A,B) / max(commits(A), commits(B))`.
- **Knowledge distribution**: Author contribution mapping. Bus factor. Off-boarding risk.
- **Key finding**: Files changed most frequently have **3-5x higher defect rates**.

**JIT defect prediction**:
- JIT-BiCC (2024): Combining code diffs + commit message semantics improves prediction.
- SimCom++ (2024): Expert features + deep features are complementary.
- Random Forest and gradient boosting consistently outperform logistic regression.

**CI failure prediction**:
- LSTM-based models outperform traditional ML
- Atlassian (FSE 2024): Repository dimension is the single strongest predictor; 120 hours wasted build time per project per year
- Google's Predictive Test Selection: catches >99.9% of regressions while running only ~33% of tests

**Meta DRS** (2025): Production deployment evidence that diff risk scoring and risk-aware workflows provide concrete org-level gains in sensitive release windows.

### 8.3 Convention extraction

**Three approaches**:
1. **Frequency mining**: AST subtree/sequence mining (FP-growth). Tools like PMD encode known patterns.
2. **Statistical style inference**: Naturalize (Allamanis et al., 2014) — code has "naturalness" that can be statistically measured.
3. **LLM-based extraction**: LLMs describe naming conventions, error-handling patterns, architectural idioms from code samples. Conventions are describable in natural language, making them usable in agent contexts.

**Codified Context paper** (arxiv 2602.20478): 57% of specialist agent specification content is domain knowledge rather than behavioral instructions.

**What's tractable now**: Simple naming conventions via regex. Import pattern extraction. Error handling detection via AST. LLM-based convention summarization from sampled files.

**Still open**: Discovering unknown project-specific conventions. Convention conflict detection across contributors. Semantic convention extraction without documentation.

### 8.4 Software knowledge graphs

**Graph4Code** (IBM Research): Processes 1.3M Python files -> 2.09 billion triples. Represents data flow across function calls, not just AST structure.

**Recommended schema**:
- Nodes: Repository, File, Symbol, Commit, Test, CIBuild, Author
- Edges: IMPORTS, DEFINES, CALLS, CHANGED_IN, AUTHORED_BY, COVERS, CO_CHANGES

### 8.5 Cross-session memory for agents

**MemGPT** (2023, now Letta): Treats LLM context as RAM, external storage as disk. Three tiers: in-context core, archival (vector), recall (conversation).

**A-Mem** (NeurIPS 2025): Zettelkasten-inspired. Reduces token overhead from ~16,900 to ~1,200-2,500 tokens. 2x improvement on multi-hop questions.

**Zep/Graphiti** (2025): Temporal knowledge graph. Bi-temporal model: tracks both event time and ingestion time, with validity intervals on every edge. Hybrid search: cosine similarity + BM25 + BFS graph traversal. Outperforms MemGPT on Deep Memory Retrieval by 18.5% accuracy, 90% latency reduction.

**What coding agents do today**: Cursor re-embeds per session. Augment maintains persistent index but per-session context. Sourcegraph/Cody uses deterministic graph traversal (SCIP-based). CLAUDE.md/.cursorrules don't scale (Codified Context paper shows three-tier architecture reduces median agent runtime by 29%).

**What's most valuable to persist** (from Codified Context paper):
1. Project conventions and standards
2. Architectural decisions and constraints
3. Known failure modes and their resolutions
4. Domain knowledge (business logic, terminology)
5. File ownership and hotspot maps

Knowledge-to-code ratio: 24.2% (26,200 lines of context per 108,000 lines of application code).

### 8.6 Benchmark signals

| Finding | Source | Implication |
|---------|--------|-------------|
| GPT-5 achieves 21% on multi-file tasks vs 65% single-file | SWE-EVO (2024) | Persistent cross-file context is the bottleneck |
| -7.2% delivery stability from AI adoption | DORA (2024) | AI coding degrades architectural judgment |
| 29% reduction in agent runtime from knowledge infrastructure | Codified Context (2026) | Codified context works; the question is how to scale it |
| 8x increase in duplicate code blocks | GitClear (2024) | Convention enforcement needed for AI-generated code |
| Contamination risk in static benchmarks | SWE-bench Live (2025) | Evaluation must use in-house tasks with freshness-aware methodology |

**Key implication for the product**: If it includes agent evaluation, it needs in-house task sets, freshness-aware evaluation, contamination tracking, and economic/operational outcome metrics — not just patch success.

Sources: [ArchAgent](https://arxiv.org/abs/2601.13007), [Codified Context](https://arxiv.org/abs/2602.20478), [SWE-EVO](https://arxiv.org/abs/2512.18470), [A-Mem](https://arxiv.org/abs/2502.12110), [Graphiti](https://arxiv.org/abs/2501.13956), [Meta DRS](https://engineering.fb.com/2025/08/06/developer-tools/diff-risk-score-drs-ai-risk-aware-software-development-meta/), [SWE-bench Live](https://arxiv.org/abs/2505.23419)

---

## 9. Architecture & Technology Stack

### Decided constraints (from project decisions, 2026-03-17)

- **Local-first**: No cloud required. Code never leaves the machine.
- **Single binary or uvx distribution**: No Docker for users.
- **Incremental re-analysis on file change**
- **Sub-500ms query response**
- **MCP stdio transport**: Server process stays alive and holds full knowledge graph in memory between tool calls.

> **Note**: The research also explored an enterprise multi-tenant SaaS architecture (Go/Rust/Postgres/Kafka/Temporal). That is preserved in the "Enterprise-Scale Reference Architecture" section below for future reference but is NOT the current build path.

### Decided MVP stack

```
MCP layer:      mcp Python SDK (FastMCP), Python 3.12+
Parsing:        tree-sitter + tree-sitter-language-pack (170+ grammars)
Git analysis:   pygit2 (libgit2 bindings)
Graph storage:  SQLite (WAL mode) for persistence
Graph algos:    rustworkx (petgraph backend, 3-100x faster than NetworkX)
Vector (later): LanceDB + voyage-code-3 (deferred to post-MVP)
Distribution:   uvx
```

### Why this stack

1. **Query performance is proven sufficient.** `codebase-memory-mcp` (SQLite + tree-sitter, Go) achieves <1ms queries on Django (49k nodes, 196k edges).
2. **FastMCP makes MCP implementation near-zero-cost.** Decorator-based tool definition with auto-generated schemas.
3. **ML/embedding ecosystem matters.** Python is the natural home for future risk models.
4. **pygit2 + rustworkx delegate CPU work to compiled code**, mitigating Python overhead.
5. **uvx distribution**: Users run `uvx repo-knowledge-plane` and get a hermetic install.

### Production path

Rust core via PyO3 + maturin, keeping Python MCP surface. Validated pattern (Polars, HF tokenizers, Google Cloud MCP walkthrough).

### Code parsing pipeline

| Layer | Tool | What It Provides |
|-------|------|-----------------|
| Syntax | tree-sitter | Fast symbol extraction, AST patterns, file structure. Incremental re-parse. 170+ languages. |
| Semantics | SCIP indexers (optional) | Cross-file references, definitions, types. Requires full build. |
| Deep analysis | CodeQL (optional) | Data flow, taint analysis, security queries |
| Conventions | LLM over samples | Naming, patterns, idioms |

**Tree-sitter is the universal parser foundation.** SCIP/LSIF/LSP are enrichment layers only — they require full project builds and lack incremental indexing.

### Git analysis algorithms

- **Change coupling**: Walk commit graph, build co-occurrence matrix, normalize by individual file change frequency. O(n² files × m commits), manageable on sliding window.
- **File churn**: Count commits per file in time window. Weight by recency for decay.
- **Author/ownership**: git blame per file via libgit2. Expensive per-file but cacheable.
- **Performance**: For 100k+ commits, using pygit2 with DiffOptions (rename detection off, context lines 0) keeps diff time per commit to milliseconds.

### Graph storage rationale

For a 100k-file repo: ~500k–2M nodes, ~5M–20M edges. Fits in memory on modern hardware (8–16GB).

Access pattern: Bulk writes during initial build. Mostly reads with occasional incremental updates. Queries are short traversals (1–3 hops). This is a structured lookup workload, not a multi-hop graph traversal workload.

**Eliminated options**: Neo4j (JVM, ~500MB idle), Kuzu (abandoned October 2025), DGraph/ArangoDB (server processes). DuckPGQ interesting but research-stage. SurrealDB approaching readiness but proprietary query language.

### Incremental analysis

1. **Content-hash tracking**: Store SHA256 of each file at index time. On re-index, compare hashes. Only re-parse changed files.
2. **Tree-sitter incremental parsing**: Accepts old tree and byte range edits. Only modified subtree re-parsed.
3. **Graph update**: On file change — remove all nodes/edges from that file, re-parse, insert new. On git commit — recompute coupling scores for touched files.

### Enterprise-scale reference architecture (future)

For multi-tenant, enterprise SaaS deployment (not current build path):

1. **Control plane**: Tenant management, identity/auth, schema registry, policy engine
2. **Ingestion plane**: SCM connectors (GitHub/GitLab/Bitbucket), CI/CD connectors, code intelligence extractors, webhook-driven incremental ingest
3. **Storage plane**: Immutable event store, Postgres 18 + pgvector, OpenSearch, Kafka/Redpanda, artifact store
4. **Intelligence plane**: Architecture recovery, convention inference, change impact, risk estimation, test impact, case-based retrieval, evaluation services
5. **Serving plane**: MCP server, REST/GraphQL API, PR bot, CI gate actions, dashboard
6. **Governance plane**: Audit logs, OpenTelemetry, OPA, data retention/deletion, tenant isolation

Stack: Go (control plane, MCP server), Rust (parsing/indexing workers), Python (ML/risk models), Postgres + pgvector, OpenSearch, Kafka, Temporal.

---

## 10. MVP Definition & Phasing

### MVP scope (0-6 months)

**Inputs**:
- GitHub or GitLab repositories (1 SCM)
- PR and review history
- CI runs and test outcomes (GitHub Actions)
- Optional docs/ADRs/rules

**Outputs**:
- Impact graph for a diff
- Inferred local conventions for touched scope
- Prior similar changes and regressions
- Recommended tests and reviewers
- Evidence-backed risk summary
- AGENTS.md auto-generation and maintenance
- MCP resources and tools usable from Codex, Claude Code, Cursor, and internal scripts

**Risk model v1**: Heuristic ensemble — hotspot churn, owner spread, coupling, changed-surface, historical fail correlation. Hybrid statistical + rule features (not pure end-to-end LLM scoring).

**Success criteria**:
- Agents answer architecture/risk/history questions with verifiable evidence
- Measurable reduction in review iteration count and escaped regressions for pilot repos

### Explicitly deferred from MVP

- Full enterprise service graph
- Perfect cross-language semantics
- Generalized autonomous refactoring
- Broad incident-management intelligence
- Vendor-neutral procurement scorecards
- Vector search / semantic code search

### Phased expansion

#### Phase 1: Convention synthesis + PR intelligence (initial wedge)

Two competing wedge recommendations emerged from research:

**Wedge A — PR-time impact and regression intelligence**:
- Infer architectural boundaries and ownership
- Compute change impact and likely blast radius
- Retrieve prior regressions and failed changes
- Estimate calibrated regression risk with evidence
- Recommend tests, reviewers, and constraints
- *Rationale*: Attaches to existing workflow with clear pain. Measurable value. Requires building the underlying knowledge graph. Defensible if evidence quality is high.

**Wedge B — Convention and instruction synthesis (AGENTS.md auto-generator)**:
- Continuously read the repository and synthesize AGENTS.md, .cursor/rules, .github/copilot-instructions.md
- Serve via MCP. Keep updated as codebase evolves.
- *Rationale*: Directly addresses the most universal pain point (every agent re-discovers conventions from scratch). 60,000+ repos using AGENTS.md with zero automated maintenance tooling. Fast time to initial value. Natural integration point with every agent tool.

**Research recommendation**: Build the full platform (Phase 1-4) with **Wedge B as the initial delivery surface** — it's fastest to value and broadest adoption surface — then layer Wedge A as the differentiation and moat.

#### Phase 2: Semantic code graph

- Dependency graph and architectural structure (modules, ownership, import/call relationships)
- Provides the graph store foundation that later phases need

#### Phase 3: Behavioral layer (deepest moat)

- Git history mining: hotspot analysis, change coupling, knowledge concentration
- CodeScene's methodology repositioned agent-first
- Hardest technical layer

#### Phase 4: Risk scoring + agent evaluation

- Combine graph + behavioral signals to score proposed changes
- Forward-looking prediction
- Agent/model/skill comparison on internal tasks
- Memory governance and policy controls

---

## 11. Go-to-Market Strategy

### How comparable dev tools went to market

**Snyk (PLG + enterprise pincer)**:
- Free tier, no friction. Viral loop: auto-opens fix PRs on public repos — contributors see "Opened by Snyk."
- Bottom-up to enterprise via security/compliance buyer.
- Revenue: $343M ARR (2025).

**Sourcegraph**: Open-source code search → per-seat commercial → AI (Cody). Dropped Apache license in 2023.

**CodeScene**: Behavioral code analysis. Open-source community version. Commercial €18/author/month. €24.8M revenue (2023).

### What makes dev tools go viral

1. **Friction-zero first value**: Install in 30 seconds, see something useful immediately
2. **Social/collaborative exposure**: Tool outputs visible to others (like Snyk's auto-PR)
3. **CLI/IDE first**: Tools that live where developers work spread through word-of-mouth
4. **Open source core**: Trust, SEO, community, natural upgrade funnel
5. **MCP as distribution**: 8M+ server downloads. An MCP-native tool gets discovered by agents that browse available tools.

### Recommended GTM

1. **Open source core via `uvx` distribution** — zero-install friction, local-first
2. **MCP registry listing** — discoverability channel; agents may discover and use it directly
3. **AGENTS.md integration** — generate AGENTS.md files as a viral artifact: team adopts tool, tool generates AGENTS.md, other developers see the file, ask what generated it
4. **Bottom-up individual → team → enterprise** — following the Snyk pincer model

---

## 12. Commercial Framing & Pricing

### Likely buyers

- Platform engineering / internal developer platform teams
- Developer productivity teams
- Engineering excellence / quality teams
- Security engineering (positioned as change-risk reduction)
- CTO / VP Engineering sponsors

### What the buyer wants

Not "more AI." The buyer wants:
- Lower change failure rate
- Faster safe merges
- Better leverage from already-purchased coding agents
- Governance and evidence

### Pricing anchors

| Product | Model | Price |
|---|---|---|
| GitHub Copilot Business | Per seat | $19/user/month |
| GitHub Copilot Enterprise | Per seat | $39/user/month |
| Cursor Teams | Per seat | $40/user/month |
| CodeRabbit Pro | Per developer | $24/dev/month |
| CodeScene | Per active author | €18/author/month |
| Sourcegraph Enterprise | Per seat | $19/user/month |
| Snyk AppSec | Per seat, enterprise | ~$58/month |

### Recommended model

**Hybrid: free individual (local-only, OSS) + per-seat team tier ($20/user/month) + enterprise (per-seat, SSO, audit logs, on-prem)**

Pricing anchor: $20/user/month puts it at parity with Cursor and below Snyk, within established willingness-to-pay.

### Why pure usage pricing is risky

If the product is part of merge safety and engineering governance, teams will resent feeling punished for frequent use. Price on **protected engineering surface area**, not raw model usage.

---

## 13. Moats & Defensibility

### Real moats

1. **Longitudinal private outcome data**: What happened after changes matters more than the diff itself.
2. **Evidence graph quality**: Linking PRs, tests, incidents, rollbacks, and boundaries correctly.
3. **Calibration and trust**: A risk score people learn to trust is sticky.
4. **Cross-agent neutrality**: If the system becomes the shared substrate underneath multiple agent tools, switching costs rise.
5. **Governance**: Enterprise controls around lineage, retention, permissions, deletion, and audit.
6. **Data flywheel**: The tool that sees more codebases builds better heuristics and models.
7. **Switching cost from accumulated knowledge**: A tool that has indexed a codebase for 6 months has irreplaceable institutional knowledge.
8. **Local-first as security moat**: 2/3 of enterprise security leaders considered banning AI code tools due to data exfiltration concerns. Code never leaving the machine is a structural differentiator.

### False moats

- Having a graph database
- Having embeddings
- Having an MCP server
- Having a wiki generator
- Having yet another review bot

Those are table stakes or quickly copied.

---

## 14. Risks & Mitigations

### Technical risks

| Risk | Mitigation |
|------|-----------|
| Polyglot repo normalization is hard | Tree-sitter's 170+ grammars; language-agnostic graph schema |
| Linking regressions to root-cause is noisy | Confidence scoring, evidence chains, conservative defaults |
| Freshness vs. deep analysis tradeoff | Event-driven incremental recompute, staleness SLAs |
| Retrieval quality degrades without provenance | Provenance required on every derived claim |
| Memory poisoning from low-quality artifacts | Provenance, confidence scoring, human feedback loop |
| GIL limits Python parallelism | Critical paths delegated to compiled code (pygit2, rustworkx). Rust migration path via PyO3. |

### Product risks

| Risk | Mitigation |
|------|-----------|
| Perceived overlap with existing tools | Position as layer underneath, not replacement |
| Noisy first output collapses trust | Explanation-first UX (why, what evidence, what similar historical changes) |
| System can't explain itself with evidence | Provenance as core product, not backend detail |
| Cold-start problem | Start with deterministic signals (ownership/dependency/test history) before ML features |
| SCM/agent vendors absorb parts of market | Cross-tool neutrality and longitudinal private data as moats |

### Commercial risks

| Risk | Mitigation |
|------|-----------|
| Enterprises prefer extending GitHub/GitLab | Neutral positioning; ingest existing systems don't replace them |
| Deployment friction (broad repo access needed) | Start with single-repo local-first; expand to multi-repo |
| Pricing looks like tax on existing AI tools | Frame as infrastructure that makes existing tools more effective |
| One agent dominates (winner-take-all) | Current market fragmented (Cursor 18% vs Copilot 42%); even dominant agent benefits from persistent knowledge |
| Larger context windows make this unnecessary | Context rot evidence; persistence and structure solve different problems than window size |

---

## 15. Open Questions for PRD

### Buyer & wedge
1. Which buyer signs first: platform engineering, developer productivity, or reliability engineering?
2. Is the initial wedge PR review risk, convention/AGENTS.md synthesis, or repo onboarding?
3. What minimum evidence chain is required before users will trust risk outputs?

### Scope & integration
4. Which source systems are mandatory in V1: SCM only, SCM + CI, or SCM + CI + incidents?
5. How much cross-language semantic accuracy is actually needed in the first 6 months?
6. Should the first serving surface be MCP only, MCP + GitHub app, or MCP + dashboard?
7. Do you require air-gapped/on-prem from day one?

### Product design
8. How will memory correction, deletion, and human override work?
9. How will we separate static declared rules from inferred conventions?
10. What evidence format is required before an agent can auto-apply code changes?
11. How much can we infer automatically versus requiring human curation?
12. Which outputs should be read-only versus allowed to gate or trigger workflows?

### Metrics & evaluation
13. What is the right unit of value: repo, service, developer, or change?
14. What is the evaluation story for comparing models, prompts, and skills on customer data?
15. What data do we need to predict regression risk with usable calibration?
16. What does success look like after 90 days, 6 months, and 12 months?

### Go-to-market
17. Is the initial GTM developer-led (self-serve MCP server) or platform-led (enterprise deployment)?
18. Which repositories/languages are required for first lighthouse customers?

---

## 16. AGENTS.md Ecosystem

AGENTS.md deserves its own section because it is both a market signal and a product opportunity.

- **What it is**: OpenAI released AGENTS.md in August 2025 as an open standard — a README for AI agents. Markdown at repo root with build steps, test commands, coding conventions.
- **Governance**: Donated to Linux Foundation's Agentic AI Foundation (December 2025) alongside MCP and goose. Backed by OpenAI, Anthropic, Google, Microsoft, Amazon, Bloomberg, Cloudflare.
- **Adoption**: 60,000+ open-source projects. Supported by all major agents.
- **The gap**: No tool auto-generates and keeps AGENTS.md current from codebase analysis. Codex and Devin read AGENTS.md but do not produce it.
- **GitHub blog**: Lessons from 2,500+ repos shows most AGENTS.md files are incomplete or incorrect.
- **Strategic value**: AGENTS.md generation is a visible, shareable artifact — the exact kind of social/viral vector that drives PLG (like Snyk's auto-PR).

Sources: [agents.md](https://agents.md/), [GitHub blog](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/), [AAIF launch](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation)

---

## 17. Key Research Papers

| Paper | Date | Key Finding | Relevance |
|-------|------|-------------|-----------|
| Codified Context (2602.20478) | Feb 2026 | Three-tier knowledge infra reduces agent runtime 29% | Direct validation of the product concept |
| ArchAgent (2601.13007) | Jan 2025 | LLM + reference graphs: F1=0.966 for architecture recovery | Architecture recovery methodology |
| SWE-EVO (2512.18470) | Dec 2024 | GPT-5 achieves 21% on multi-file vs 65% single-file | Persistent cross-file context is the bottleneck |
| A-Mem (2502.12110) | NeurIPS 2025 | Zettelkasten memory: 2x on multi-hop, 90% token reduction | Memory architecture pattern |
| Graphiti/Zep (2501.13956) | Jan 2025 | Bi-temporal knowledge graph: +18.5% accuracy, -90% latency | Temporal graph design pattern |
| Meta DRS (eng blog) | Aug 2025 | Diff risk scoring provides real org-level gains | Risk scoring validated at scale |
| SWE-bench Live (2505.23419) | May 2025 | Contamination-resistant continuous evaluation | Evaluation methodology |
| JIT-BiCC (2410.12107) | Oct 2024 | Code diffs + commit semantics improve defect prediction | Risk model features |
| Moving Faster, Reducing Risk (2410.06351) | Oct 2024 | Risk gating captures incident-prone changes in production | Risk-aware workflow validation |
| GraphCoder (2406.07003) | Jun 2024 | Graph retrieval beats text-only RAG for code understanding | Hybrid retrieval validates graph approach |
| CodexGraph (2408.03910) | Aug 2024 | Graph-augmented agent outperforms text-only | Graph backbone not optional |
| RepoMod-Bench (2602.22518) | Feb 2026 | Scaling collapse on larger repos | Autonomy limits at scale |

---

## 18. Curated Source Index

### Standards & protocols
- [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Architecture](https://modelcontextprotocol.io/specification/2025-11-25/architecture)
- [MCP Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)
- [MCP SDKs](https://modelcontextprotocol.io/docs/sdk)
- [MCP SDK Tiering](https://modelcontextprotocol.io/community/sdk-tiers)
- [MCP Registry](https://modelcontextprotocol.io/registry/about)
- [MCP Anniversary Post](http://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/)
- [A2A Protocol](https://github.com/a2aproject/A2A)
- [ACP Protocol](https://agentclientprotocol.com/get-started/introduction)
- [AGENTS.md Specification](https://agents.md/)
- [SCIP Protocol](https://github.com/sourcegraph/scip)
- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/)

### Product & market
- [OpenAI Codex](https://openai.com/codex/)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview)
- [GitHub Copilot Coding Agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent)
- [GitHub Copilot Code Review](https://docs.github.com/en/copilot/concepts/agents/code-review)
- [GitHub Copilot Memory](https://docs.github.com/en/copilot/concepts/agents/copilot-memory)
- [Cursor Codebase](https://docs.cursor.com/chat/codebase)
- [Devin DeepWiki](https://docs.devin.ai/work-with-devin/deepwiki)
- [Sourcegraph/Amp Split](https://sourcegraph.com/blog/why-sourcegraph-and-amp-are-becoming-independent-companies)
- [Sourcegraph MCP Server](https://sourcegraph.com/changelog/sourcegraph-mcp-server)
- [Augment Context Engine](https://www.augmentcode.com/context-engine)
- [Windsurf Memories](https://docs.windsurf.com/windsurf/cascade/memories.md)
- [CodeScene Behavioral Analysis](https://codescene.com/product/behavioral-code-analysis)
- [CodeRabbit](https://docs.coderabbit.ai/overview/pull-request-review)
- [Graphite AI Reviews](https://graphite.com/docs/ai-reviews)
- [Potpie Funding](https://techfundingnews.com/the-startup-building-a-knowledge-graph-for-code-raises-2-2m-to-make-ai-agents-actually-useful/)

### Engineering metrics & market signals
- [DORA 2024 Report](https://dora.dev/research/2024/dora-report/)
- [DORA Metrics Guide](https://dora.dev/guides/dora-metrics/)
- [Stack Overflow 2025 AI Survey](https://survey.stackoverflow.co/2025/ai)
- [GitClear 2024 Report](https://www.gitclear.com/coding_on_copilot_data_shows_ais_downward_pressure_on_code_quality)
- [GitClear 2025 Update](https://www.gitclear.com/ai_assistant_code_quality_2025_research)
- [METR Study](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)
- [Chroma Context Rot](https://research.trychroma.com/context-rot)

### Memory & graph infrastructure
- [Mem0](https://mem0.ai/)
- [Graphiti/Zep](https://help.getzep.com/graphiti/getting-started/welcome)
- [Backstage](https://backstage.io/)
- [Neo4j Codebase Knowledge Graph](https://neo4j.com/blog/developer/codebase-knowledge-graph/)

### Implementation stack
- [tree-sitter Language Pack](https://github.com/Goldziher/tree-sitter-language-pack)
- [pygit2](https://www.pygit2.org/)
- [rustworkx](https://www.rustworkx.org/)
- [petgraph](https://docs.rs/petgraph/)
- [pgvector](https://github.com/pgvector/pgvector)
- [LanceDB](https://lancedb.com/)
- [voyage-code-3](https://blog.voyageai.com/2024/12/04/voyage-code-3/)
- [FastMCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [PyO3](https://pyo3.rs/)
- [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) (existence proof: Go + tree-sitter + SQLite, <1ms queries)

### GTM references
- [Snyk PLG Strategy](https://openviewpartners.com/blog/snyk-plg-strategy/)
- [DX Onboarding Study](https://getdx.com/blog/ai-cuts-developer-onboarding-time-in-half/)
- [GitHub AGENTS.md Lessons](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)

---

## 19. Conflicts & Decisions Logged

These are areas where research files gave conflicting recommendations. Decisions are noted where made.

| Topic | Conflict | Decision |
|-------|---------|----------|
| **Architecture** | Enterprise SaaS (Go/Postgres/Kafka) vs. local-first (Python/SQLite) | **Local-first decided.** Enterprise architecture preserved as future reference. |
| **Initial wedge** | PR regression intelligence vs. AGENTS.md auto-generation | **Not yet decided.** Research recommends AGENTS.md as faster-to-value initial delivery, with PR risk as the moat-building differentiation layer. |
| **Stack language** | Go vs. Rust vs. Python vs. hybrid | **Python MVP decided.** Rust production path via PyO3. |
| **Graph storage** | Neo4j vs. embedded graph DB vs. SQLite + in-memory graph | **SQLite + rustworkx decided.** Neo4j eliminated (JVM). Kuzu eliminated (abandoned). |
| **Vector search** | MVP requirement vs. deferred | **Deferred to post-MVP.** |
| **Pricing model** | Enterprise platform fee vs. OSS + per-seat hybrid | **Not yet decided.** Research favors OSS core + $20/seat team tier + enterprise. |

---

_End of consolidated research. This document supersedes all prior research files in `.plans/` and `.claude/plans/`._
