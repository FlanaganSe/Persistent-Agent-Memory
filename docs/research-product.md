# Repo Knowledge Plane — Product Research

_Consolidated 2026-03-18 from 5 research files. Single source of truth for product strategy, market context, competitive landscape, and planning guidance._

---

## 1. Product Identity

### Core thesis

The durable moat is not the agent UI. It is the **longitudinal private dataset** and the **evidence-backed models** built from temporal repo structure, PR/review outcomes, CI/test history, incidents and rollbacks, inferred and declared conventions, and agent trajectories. That is difficult for a stateless agent vendor to reproduce inside a single session.

### What the product actually is

A **local-first, evidence-backed, human-governed operational contract compiler for software repos**, with thin default context, strong environment modeling, strict trust boundaries, and host-specific projection quality as the central engineering discipline.

It is a 4-layer system:
1. **Observation layer**: Raw facts from code, configs, docs, CI definitions, git history, and imported instruction artifacts.
2. **Claim synthesis layer**: Converts observations into canonical claims with authority, confidence, scope, applicability, freshness, sensitivity, and evidence chains.
3. **Governance overlay**: Human declarations, edits, suppressions, tombstones, trust promotions, and review state from `.rkp/overrides`.
4. **Projection and query layer**: Compiles claims into host-native artifacts and answers MCP queries with relevance- and budget-aware summaries.

### What it is NOT

- Just code search, a wiki generator, an engineering metrics dashboard, an agent memory store, or a PR review bot. It is the layer underneath all of those.

### Positioning

**"Portable, verified repo context for every coding agent."**

Sold as **platform infrastructure** (like CI, observability, feature flags), not as "yet another coding assistant."

### Core queries it answers

- "What are the architectural boundaries here?"
- "What conventions does this team actually follow?"
- "What is the likely blast radius of this change?"
- "What broke the last three times this module changed?"
- "Which tests matter for this diff, and what is still unprotected?"
- "What instructions should any agent inherit before touching this area?"

---

## 2. Why This Category Exists Now

### Converging trends (2025-2026)

1. **Coding agents are mainstream.** GitHub Copilot (20M users), Cursor ($2B ARR), Codex, Claude Code, Devin, Amazon Q, GitLab Duo, Augment, Windsurf, and open-source agents are all shipping agentic workflows.

2. **MCP is a real interoperability standard.** Versioned spec through 2025-11-25 with formal governance, SDK tiering (TypeScript/Python/Go Tier 1), cross-vendor adoption (Anthropic, OpenAI, Google, Microsoft), and 8M+ server downloads.

3. **AGENTS.md is the instruction standard.** Donated to Linux Foundation's Agentic AI Foundation (December 2025). 60,000+ repos. Supported by Codex, Copilot, Cursor, Gemini CLI, Devin, Windsurf. No tool auto-generates and maintains it from codebase analysis — this is whitespace.

4. **Agent UX has advanced faster than agent memory.** Most tools still answer from a mix of current repo snapshots, local instructions, ad hoc indexes, and the current chat session.

5. **Research is shifting toward persistent experience.** SWE-Exp, EXPEREPAIR, Prometheus, MemoryAgentBench show persistent memory improves agent behavior. GraphCoder, CodexGraph, GraphRAG show graph retrieval beats naive text-only retrieval for code understanding.

### The productivity paradox

| Source | Finding |
|--------|---------|
| **DORA 2024** (39K respondents) | 75% report individual gains, but AI adoption associated with 1.5% decrease in delivery throughput and 7.2% reduction in delivery stability |
| **GitClear 2024** (211M lines) | Code churn +44%, copy/paste +48%, refactoring -60%; 2025 update: clone occurrence rose 8x vs pre-AI |
| **METR 2025** | AI increased task time by 19% for experienced devs (39pp perception gap); high AI adoption → 98% more PRs but 91% longer review time |
| **Context rot** (Chroma) | 30%+ accuracy drops for middle-of-context content across all frontier models |
| **JetBrains** (Dec 2025) | Smart context management outperforms raw context expansion |

**Structural argument**: Even if context windows scale infinitely, a knowledge plane solves different problems — persistence across sessions, structure (which parts matter for a given query), and history (git-mined patterns no context window can derive from current files alone).

### Developer time allocation

- **58–70% of developer time** is spent understanding existing code, not writing new code
- Read:write ratio: **7:1 to 200:1**
- **30–50% of time** debugging; actual new code writing: **<10% of work time**

**Implication**: AI tools today aggressively optimize the <10% (writing). A knowledge plane optimizes the 58–70% (understanding). This is the asymmetric opportunity.

---

## 3. Market Data & Sizing

### AI coding tool market

| Source | 2024/2025 | Forecast | CAGR |
|--------|-----------|----------|------|
| Grand View Research | $4.86B (2023) | $26B by 2030 | 27.1% |
| Market.us | $5.5B (2024) | $47.3B by 2034 | 24% |
| Mordor Intelligence | $7.37B (2025) | $23.97B by 2030 | 26.6% |
| Future Market Insights | $6.43B (2024) | $122B by 2035 | 30.7% |

Conservative midpoint: **$5–7B in 2024–2025, heading toward $25–50B by 2030–2034** at ~25% CAGR.

### Active user base

- **GitHub Copilot**: 20M cumulative users; 1.3M paid subscribers; 42% market share; 90% of Fortune 100
- **Cursor**: 18% market share; $2B ARR (Feb 2026)
- **Amazon Q Developer**: ~11% market share
- **Total**: ~27M developers actively using AI coding tools, scaling toward 50M+ by 2027

### TAM for a cross-tool knowledge layer

At $15–30/seat/month:
- TAM: $5–10B ARR at full penetration
- Realistic SAM (enterprise teams 10–500 engineers, 3+ AI tools): $500M–2B ARR in 3–5 years

---

## 4. Personas & Jobs To Be Done

### Persona 1: Developer joining a new codebase
- Average time to full productivity: **3–9 months** (cost: $75,000+ per onboarding over 6 months)
- With AI: 10th PR in 49 days vs 91 without (46% acceleration, still months)
- **Needs**: Persistent architectural rationale, convention awareness, fragile/high-churn module visibility

### Persona 2: Senior engineer / tech lead
- Architecture erosion is slow/invisible; agents don't know conventions without explicit context
- AI-generated code accelerates entropy (refactoring rate down 60%+ since 2021)
- **Needs**: Machine-readable architectural intent, drift detection, convention enforcement

### Persona 3: Engineering manager / VP Engineering
- Companies with significant tech debt spend **20–40% of dev budget** on poor code quality (McKinsey)
- Only 39% of developers trust AI-generated code, yet ~70% of code may be AI-generated
- **Needs**: Quantified risk scores for PRs, architecture health, justifiable tooling ROI

### Persona 4: Platform engineering / developer productivity team
- **Needs**: Cross-tool neutral intelligence layer, evaluation layer, governance

### Persona 5: AI coding agent as "user"
- No cross-session memory, no conventions in context, no regression risk awareness, no dependency semantics
- **Needs**: Persistent structured knowledge accessible via MCP tool calls

---

## 5. Competitive Landscape

### Market structure

| Layer | Who plays here | What they miss |
|-------|---------------|---------------|
| Code quality / behavioral analytics | CodeScene, Trunk.io | Not agent-serving; no cross-session memory |
| Static architecture recovery | SciTools Understand, Structure101, Lattix | No AI integration; read-only snapshots |
| AI coding agents with context | Augment Code, Cursor/Windsurf, Aider | Per-session, per-IDE; no durable knowledge layer |
| AI code review / risk | CodeRabbit, Graphite, Qodo, Snyk | Limited cross-system memory; partial view |
| Engineering intelligence | LinearB, Jellyfish, Swarmia, DX, Harness SEI | Weak agent-time retrieval |
| Agent memory / graph infra | Mem0, Zep/Graphiti | Not opinionated enough for repo intelligence |
| Internal developer portals | Backstage, Compass, Cortex, OpsLevel | Weak code-level change reasoning |
| Emerging code graph / MCP | Potpie, CodePrism, CodeCortex | Early, narrow language support, no risk modeling |

**No product is clearly a neutral, cross-agent persistent repo knowledge substrate.**

### Key competitor analysis

**CodeScene**: Behavioral code analysis (hotspots, change coupling, knowledge concentration). €18/active author/month. Closest methodological predecessor. Serves engineering managers, not AI agents. No MCP, no structured agent output, no cross-session memory.

**Sourcegraph / Amp**: Enterprise code search with SCIP-based deterministic graph traversal. 30% completion acceptance rate. Code graph is static-reference-only — no behavioral signals, no git history, no risk modeling. Potential MCP integration partner.

**Devin / Cognition**: Autonomous coding with strong product-native memory. Knowledge items by triggers. DeepWiki: 50,000+ repos. Memory is Devin-scoped, not a neutral substrate. No regression risk scoring from git history.

**GitHub Copilot**: Copilot Memory (repo-specific, 28-day retention, validates against current code). Coding agent runs in ephemeral GitHub Actions environments. MCP tools-only (not resources/prompts), no OAuth remote MCP. Microsoft benefits when teams are on GitHub; cross-tool neutrality is a strategic contradiction.

**Potpie**: Knowledge graph for code. Pulls from GitHub, Sentry, Jira, Notion. Generates AGENTS.md. $2.2M pre-seed (Feb 2026). 40M-line codebase customer cut root-cause analysis from ~1 week to ~30 minutes. Validates market exists. Differentiated by behavioral risk modeling.

**Augment Code**: 200K token Context Engine. Context Lineage adds recent commit history. Per-session context injection, not persistent architectural knowledge. Context Engine MCP is a direct integration target.

### Why incumbents won't build this

- **GitHub/Microsoft**: Optimizes for GitHub platform. Cross-tool neutrality conflicts with lock-in strategy.
- **Cursor**: Focused on editor UX. Cross-tool knowledge plane requires neutrality conflicting with Cursor's IDE goal.
- **Anthropic**: Sells model API. Claude Code is a thin CLI, not a platform. No persistent storage model.
- **Structural**: Any single tool that builds this becomes a knowledge plane for their tool only. A neutral MCP server becomes more valuable the more tools it connects.

### OSS landscape

- **OpenHands**: Strong open agent runtime; no neutral persistent cross-tool repo memory
- **Cline**: Strong IDE agent + MCP; memory/governance tool-local
- **Aider**: Tree-sitter repo map rebuilt per session; no persistence, no behavioral signals
- **Continue**: Source-controlled AI checks and CI enforcement; less shared long-horizon memory graph
- **MCP reference Memory server**: Knowledge-graph persistent memory; building block, not repo-specific
- **Graphiti (Zep)**: Temporal context graph; best-in-class design pattern
- **Mem0**: Generalized memory layer, not repo-specific

---

## 6. MCP Protocol & Interoperability

### MCP maturity (2024-2026)

- **Launch**: Anthropic, Nov 25, 2024
- **Spec cadence**: Dated releases through 2025-11-25 with multiple revisions
- **Governance**: Formalized working groups, SDK tiering (conformance tests Jan 23, 2026; tiering published Feb 23, 2026)
- **Cross-vendor**: OpenAI (May 2025), Codex, GitHub Copilot coding agent
- **Security**: 30 CVEs in 60 days across implementations (2026). Prompt injection and tool poisoning dominant. OWASP now has MCP Top 10.

### What MCP standardizes

- Host-client-server architecture with capability negotiation
- JSON-RPC + transports (stdio, Streamable HTTP replacing legacy SSE)
- Three primitives: **resources** (app-driven context), **tools** (model-invoked execution), **prompts** (user-controlled reusable templates)
- OAuth/OIDC auth guidance; in-protocol discovery with pagination; registry model (still preview)

### Limitations

- Authorization is optional → uneven security baseline
- Host behavioral divergence (approval semantics, tool filtering)
- Experimental task model (durable long-running analysis)
- MCP Apps (Jan 26, 2026): servers declare UI resources as sandboxed iframes — future governance UI path

### Adjacent standards

- **A2A (Agent2Agent)**: Agent-to-agent collaboration. v1.0.0 released Mar 12, 2026. Complementary to MCP.
- **ACP (Agent Client Protocol)**: Editor/client-to-agent runtime protocol. Active RFD cadence.
- **Practical**: MCP first, then bridge to A2A/ACP where demand appears.

---

## 7. AGENTS.md Ecosystem

- **What**: OpenAI released in August 2025 as an open standard. Markdown at repo root with build steps, test commands, coding conventions.
- **Governance**: Donated to AAIF (December 2025) alongside MCP and Goose. Backed by OpenAI, Anthropic, Google, Microsoft, Amazon, Bloomberg, Cloudflare.
- **Adoption**: 60,000+ open-source projects. Supported by all major agents.
- **Gap**: No tool auto-generates and keeps AGENTS.md current from codebase analysis. GitHub blog: most AGENTS.md files are incomplete or incorrect.
- **Critical finding**: Claude Code does NOT natively read AGENTS.md (open feature request #34235). Workaround: `@AGENTS.md` import syntax in CLAUDE.md. This strengthens the case for RKP projecting to CLAUDE.md directly.
- **Strategic value**: AGENTS.md generation is a visible, shareable artifact — viral vector for PLG (like Snyk's auto-PR).

---

## 8. Host Capability Matrix

### Instruction file size constraints

| Host | Size constraint |
|------|----------------|
| AGENTS.md (Codex) | 32 KiB combined (layered, nearest-file precedence) |
| CLAUDE.md | ~200 lines recommended; MCP tool schemas load every request |
| copilot-instructions.md | Not documented |
| .cursor/rules | 500 lines per rule recommended |
| Windsurf rules | 6K/rule global, 12K total workspace |
| SKILL.md | 500 lines, <5000 tokens recommended |
| Copilot custom agents | 30,000 characters max |

### Host-by-host strategy

**Codex / OpenAI** — Reference adapter (GA in P0)
- Cleanest target surface: layered AGENTS.md with nearest-file precedence, first-class skills with progressive disclosure
- Support: root AGENTS.md + nested overrides, `.agents/skills`, optional `.codex/config.toml`
- If something cannot be expressed cleanly in Codex's surfaces, it probably needs a better canonical representation

**Claude Code** — Strong GA adapter (GA in P0)
- Distinguished always-on (CLAUDE.md), on-demand skills, MCP servers, subagents, hooks
- Context discipline especially important: CLAUDE.md + MCP tool schemas load every request; skills are low-cost until used
- Support: CLAUDE.md, path-scoped rules, skills, permission projection
- Defer subagent/hook generation until base adapter is stable

**Copilot** — Beta in P0
- MCP **tools only** (no resources, no prompts). Agent uses available tools autonomously without approval.
- Copilot coding agent runs in ephemeral GitHub Actions environment via `copilot-setup-steps.yml`
- Setup constraints: single job named `copilot-setup-steps`, max timeout 59 min, non-zero exit doesn't fail agent
- Support order: `.github/copilot-instructions.md` → `.github/instructions/*.instructions.md` → `copilot-setup-steps.yml` → MCP tools → later: custom agent profiles
- Keep adapter security posture stricter than others

**Windsurf** — Alpha/export-only in P0
- Auto-scopes root and subdirectory AGENTS.md; separate rules, skills, workflows, memories, MCP
- Size-constrained: global rules 6K, workspace 12K

**Cursor** — Alpha/export-only in P0
- Rules and MCP support exist; treat as export-only due to security history (repo-provided `.cursor/mcp.json` vulnerability)

### Projection rules per host

| Host | Always-on file | Path-scoped | Skills | Env config | Permissions | Maturity |
|------|---------------|-------------|--------|------------|-------------|----------|
| Codex | Root AGENTS.md | Directory-level | Agent Skills | `setup` section | Advisory | **GA** |
| Claude | Root CLAUDE.md | .claude/rules/ with `paths` | SKILL.md in .claude/skills/ | CLAUDE.md or skill | settings.json | **GA** |
| Copilot | copilot-instructions.md | .instructions.md with `applyTo` | Custom agents | copilot-setup-steps.yml | Agent tool config | **Beta** |
| Cursor | .cursor/rules (alwaysApply) | .cursor/rules (globs) | N/A | Advisory | N/A | **Alpha** |
| Windsurf | .windsurf/rules (always_on) | .windsurf/rules (glob) | Workflows | Advisory | Tool toggles | **Alpha** |

---

## 9. PRD Amendments (Consolidated)

All research sources converged on these recommendations. Amendments marked with priority.

### P0 — Must address before planning

1. **Split "declared policy" into reviewed vs imported-unreviewed** — Imported instruction files should NOT automatically function as full-authority `declared-policy` until a human reviews them. Add `declared-reviewed` and `declared-imported-unreviewed` sub-levels. Otherwise `rkp import` can promote stale/low-quality instructions above actual build/test truth.

2. **Make context budget a first-class architectural constraint** — Every projection should track: hard budget, soft budget, included claims, omitted claims, omission reason, downgrade route taken. Not just adapter notes — central to the model and acceptance criteria.

3. **Promote "environment profile" to top-level object** — Commands should point to environment profiles, not carry prerequisites inline. Copilot and Codex cloud both have explicit environment setup surfaces. Makes remote support materially better.

4. **Executable supply-chain input trust rule** — "RKP does not import, generate, or activate repo-supplied MCP config, hook config, or script-backed skills by default." Those require a separate trust workflow with explicit allowlisting.

5. **Update Host Capability Matrix** — For Copilot coding agent: explicit "tools-only; no resources/prompts; no remote OAuth MCP." Add `copilot-setup-steps.yml` constraints and validation requirements.

### P1 — Important for implementation quality

6. **Add `get_preflight_context` summary tool** — Returns minimum actionable bundle for current task: scoped rules, validated commands, guardrails, environment profile, unsupported warnings. Keeps host context budgets manageable.

7. **Controlled core applicability vocabulary** — Not fully free-form in MVP. Core: `build, test, lint, format, docs, review, refactor, debug, security, ci, release, onboarding`. Plus optional custom tags.

8. **Projection decision provenance** — Every projected artifact explainable at claim level: why included, why excluded, why moved to skill, why downgraded for size, why filtered for sensitivity, which host capability forced the decision.

9. **Non-interactive CI check mode** — `rkp check` or `rkp status --ci`: drift checks, leakage checks, projection conformance, support-envelope warnings, stale-claim gating.

10. **Licensing/supply-chain section** — pygit2 GPLv2 linking exception considerations, tree-sitter grammar curation strategy.

11. **Storage operations section** — WAL checkpoint policy, DB maintenance commands.

12. **Adapter conformance release gate** — No GA promotion without conformance + drift + leakage tests passing.

### Confirmed PRD assumptions

| Assumption | Status |
|-----------|--------|
| A3: "Under 5 min" for 250k LOC | **Confirmed** — tree-sitter parses ~10-50 files/sec |
| A5: SQLite + in-memory graph sufficient | **Confirmed** — ~70-120MB for 250k LOC; query latency 10-35ms |
| A9: Tree-sitter sufficient for conventions | **Confirmed for high-confidence** — naming, imports, test patterns |
| A10: MCP stdio is right first transport | **Confirmed** — all target hosts support stdio |
| A15: GitHub Actions sufficient for launch | **Confirmed** — dominant CI system in target repos |

---

## 10. Academic Research Foundations

### Architecture recovery

- **Reflexion Method** (Murphy et al.): Human hypothesized architecture vs extracted source model. Requires expert input.
- **DSM-based recovery**: Dependency Structure Matrix — spectral partitioning groups files into layers/components from import/call deps.
- **ArchAgent** (arxiv 2601.13007): Static analysis + multi-level reference graphs + LLM synthesis. Up to 22K files. F1=0.966 vs DeepWiki's 0.860.
- **Hybrid clustering + LLM outperforms either approach alone.**

### Change impact analysis & defect prediction

- **Behavioral code analysis** (Tornhill/CodeScene): Hotspot detection (commit frequency × code complexity). Power law: 5-15% of files receive vast majority of commits. Files changed most frequently have **3-5x higher defect rates**.
- **Change coupling**: Co-commit patterns reveal hidden architectural dependencies. Score: `co_commits(A,B) / max(commits(A), commits(B))`.
- **JIT-BiCC** (2024): Code diffs + commit message semantics improve defect prediction.
- **Google Predictive Test Selection**: Catches >99.9% of regressions while running only ~33% of tests.
- **Meta DRS** (2025): Production evidence that diff risk scoring provides org-level gains.

### Convention extraction

- **Three approaches**: Frequency mining (FP-growth), statistical style inference (Naturalize), LLM-based extraction
- **Codified Context** (2602.20478): 57% of specialist agent specification content is domain knowledge. Three-tier knowledge infra reduces median agent runtime by 29%.
- Knowledge-to-code ratio: 24.2% (26,200 lines of context per 108,000 lines of application code)

### Cross-session memory

- **MemGPT**: Treats LLM context as RAM, external storage as disk. Three tiers.
- **A-Mem** (NeurIPS 2025): Zettelkasten-inspired. 2x improvement on multi-hop questions, 90% token reduction.
- **Zep/Graphiti** (2025): Bi-temporal knowledge graph. +18.5% accuracy, 90% latency reduction vs MemGPT.

### Software knowledge graphs

- **Graph4Code** (IBM): 1.3M Python files → 2.09B triples. Data flow across function calls.
- **GraphCoder**: Graph retrieval beats text-only RAG for code understanding.
- **CodexGraph**: Graph-augmented agent outperforms text-only.

### Key research papers

| Paper | Key Finding | Relevance |
|-------|------------|-----------|
| Codified Context (2602.20478) | 3-tier knowledge infra reduces agent runtime 29% | Direct product validation |
| ArchAgent (2601.13007) | F1=0.966 for architecture recovery | Recovery methodology |
| SWE-EVO (2512.18470) | 21% multi-file vs 65% single-file | Cross-file context is the bottleneck |
| A-Mem (2502.12110) | Zettelkasten memory: 2x multi-hop, 90% token reduction | Memory pattern |
| Graphiti (2501.13956) | Bi-temporal graph: +18.5% accuracy, -90% latency | Graph design pattern |
| Meta DRS | Diff risk scoring real org-level gains | Risk scoring validated at scale |
| ETH AGENTS.md eval (2602.11988) | Agents follow repo context even when it hurts | Over-compliance is the failure mode |
| Skill security (2601.10338) | Widespread vulns and confirmed malicious skills | Trust boundary is critical |
| GitClear 2024 | 8x clone increase, -60% refactoring | Convention enforcement needed |

---

## 11. Moats & Defensibility

### Real moats

1. **Longitudinal private outcome data**: What happened after changes matters more than the diff itself
2. **Evidence graph quality**: Linking PRs, tests, incidents, rollbacks, and boundaries correctly
3. **Calibration and trust**: A risk score people learn to trust is sticky
4. **Cross-agent neutrality**: Shared substrate underneath multiple agent tools → switching costs
5. **Governance**: Enterprise controls around lineage, retention, permissions, deletion, and audit
6. **Data flywheel**: More codebases → better heuristics and models
7. **Switching cost from accumulated knowledge**: 6 months of indexing = irreplaceable institutional knowledge
8. **Local-first as security moat**: 2/3 of enterprise security leaders considered banning AI code tools due to data exfiltration concerns

### False moats

Having a graph database, embeddings, an MCP server, a wiki generator, or a review bot. Those are table stakes or quickly copied.

---

## 12. Go-to-Market Strategy

### What makes dev tools go viral

1. **Friction-zero first value**: Install in 30 seconds, see something useful immediately
2. **Social exposure**: Tool outputs visible to others (like Snyk's auto-PR on public repos)
3. **CLI/IDE first**: Tools that live where developers work spread through word-of-mouth
4. **Open source core**: Trust, SEO, community, natural upgrade funnel
5. **MCP as distribution**: 8M+ server downloads; agents discover and use available tools directly

### Recommended GTM

1. **Open source core via `uvx` distribution** — zero-install friction, local-first
2. **MCP registry listing** — discoverability; agents may discover and use it directly
3. **AGENTS.md integration** — generate AGENTS.md as viral artifact: team adopts tool, tool generates AGENTS.md, others ask what generated it
4. **Bottom-up: individual → team → enterprise** — Snyk pincer model

### Pricing

| Product | Price |
|---------|-------|
| GitHub Copilot Business | $19/user/month |
| GitHub Copilot Enterprise | $39/user/month |
| Cursor Teams | $40/user/month |
| CodeRabbit Pro | $24/dev/month |
| CodeScene | €18/author/month |

**Recommendation**: Free individual (local-only, OSS) + per-seat team tier ($20/user/month) + enterprise (per-seat, SSO, audit, on-prem). Price on **protected engineering surface area**, not raw usage.

---

## 13. Risk Register (Consolidated)

### Hidden risks & failure modes

1. **Over-compliance, not hallucination, is the main failure mode.** The ETH AGENTS.md evaluation shows agents really do follow repo context — even when it makes tasks harder. The product's harm mode is "agent became too obedient to noisy instructions."

2. **Host drift may outpace repo drift.** Vendor surfaces change quickly. Adapter conformance is a permanent discipline, not a one-time task.

3. **Environment truth may matter more than convention truth for remote agents.** For Copilot coding agent and Codex cloud, a correct build/test environment is often more valuable than another page of instructions.

4. **Semantic drift is not always textual.** A manually edited instruction file may mean the same thing in different words. Drift resolution needs a semantic view, not just byte comparison.

5. **CI evidence is strongest where most annoying.** Reusable workflows, composite actions, matrix expansions, containers, and service definitions are precisely where command truth lives and where naïve parsers break.

6. **Trust collapse from 1-2 wrong high-confidence claims** can outweigh many correct low-friction wins. Conservative defaults, visible evidence, thin projections, review-first writes.

7. **Importing existing instruction files may be politically harder than technically hard.** Users may trust their current AGENTS.md more than the new system. Import without taking ownership by default.

8. **Claim identity drift can be a product-killer.** If claim IDs shift too often, approved/suppressed claims seem to resurrect randomly.

### Technical risks

| Risk | Mitigation |
|------|-----------|
| Polyglot normalization is hard | Tree-sitter + language-agnostic graph schema |
| Linking regressions to root-cause is noisy | Confidence scoring, evidence chains, conservative defaults |
| Freshness vs deep analysis tradeoff | Event-driven incremental recompute, staleness SLAs |
| GIL limits Python parallelism | Critical paths in compiled code (pygit2, rustworkx). Rust via PyO3 later. |
| FastMCP 3.x breaking changes | Pin strictly; wrap in thin abstraction |
| Grammar version changes break queries | Pin tree-sitter-language-pack; test against fixtures in CI |
| pygit2 licensing friction (GPLv2) | ADR + legal review + fallback Git CLI backend |
| Convention thresholds too aggressive/conservative | Make configurable; calibrate with design partners |
| SQLite WAL unbounded growth | Periodic checkpoint at shutdown; short-lived read transactions |
| Performance cliffs on large repos | File count/byte-budget safeguards, incremental scan, configurable ignore rules |

### Product risks

| Risk | Mitigation |
|------|-----------|
| Overlap perception with existing tools | Position as layer underneath |
| Noisy first output collapses trust | Explanation-first UX |
| Cold-start problem | Start with deterministic signals before ML |
| Fixture overfitting | Diverse fixtures + design-partner shadow evaluations + messy real repos |
| Metadata leakage | Strict sensitivity filtering + projection policy tests |

### Commercial risks

| Risk | Mitigation |
|------|-----------|
| Enterprises prefer extending GitHub/GitLab | Neutral positioning; ingest, don't replace |
| Pricing looks like tax on AI tools | Frame as infrastructure making existing tools more effective |
| Larger context windows make this unnecessary | Context rot evidence; persistence/structure ≠ window size |

---

## 14. Phased Strategy

### MVP phasing

**Phase 1A: Core contract loop** (weeks 1-6)
- Canonical claim model, precedence engine, SQLite schema, `.rkp/overrides` format
- Command/prerequisite extraction, evidence storage
- Codex and Claude preview projection
- `rkp init`, `rkp review`, `rkp preview`, `rkp status`
- First fixture repos and golden tests
- Exit: useful repo-specific previews on supported repos, deterministic outputs

**Phase 1B: Import, drift, path scope** (weeks 7-8)
- Import existing instruction files as declared-policy claims
- Path-scoped conventions, managed artifact ownership modes
- Drift detection, no-op and omitted-claim diagnostics
- Exit: users can migrate from manual instruction files without losing trust

**Phase 1C: Copilot beta and module map** (weeks 9-12)
- Copilot beta adapter, module-node and edge model
- Test-location inference, stronger adapter conformance tests
- Quality harness, security hardening, docs, design-partner onboarding
- Exit: two GA adapters truly solid, Copilot usable with documented limits

**Phase 2: Verification and remote seam** (post-12 weeks)
- Active verification with consent, clean worktree runner
- Streamable HTTP transport, OCI reference deployment
- Broader parser support, optional semantic enrichment

### What to keep, defer, cut

**Keep**: Coarse module mapping, CI config parsing, skills/playbook projection, drift detection, version-controlled human decisions, active verification as opt-in

**Defer**: Custom agent/subagent generation, ownership hints as surfaced MVP promise, vector search/embeddings, managed remote MCP service, composite risk score

**Cut entirely from MVP**: Importing/generating repo-supplied MCP config, importing third-party skills/plugins by default, any plugin marketplace, any default behavior that executes repo code outside explicit verification boundary

### Implementation sequencing philosophy

Organize by **vertical slices**, not horizontal tech buckets. A good slice: "GitHub Actions command evidence into Codex and Claude projection with review + tests." Not "parser week" and "MCP week." End-to-end truth faster.

---

## 15. What to build first (from all sources)

The initial wedge is **convention and instruction synthesis** (AGENTS.md auto-generation and multi-host projection). It's:
- Fastest to initial value
- Broadest adoption surface (every agent re-discovers conventions from scratch)
- 60,000+ repos using AGENTS.md with zero automated maintenance
- Natural viral vector (generated files are shareable artifacts)

Then layer **PR risk intelligence** as the differentiation and moat (behavioral code analysis, change impact, regression risk).

---

## 16. Source Index

### Standards & protocols
- [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/draft/basic/security_best_practices)
- [Agent Skills Specification](https://agentskills.io/specification)
- [AGENTS.md Specification](https://agents.md/)
- [A2A Protocol](https://github.com/a2aproject/A2A)
- [ACP Protocol](https://agentclientprotocol.com/get-started/introduction)

### Agent host docs
- [Codex AGENTS.md Guide](https://developers.openai.com/codex/guides/agents-md/)
- [Codex Skills](https://developers.openai.com/codex/skills/)
- [Codex MCP](https://developers.openai.com/codex/mcp/)
- [Codex Config Precedence](https://developers.openai.com/codex/config-basic/#configuration-precedence)
- [Claude Code Memory/CLAUDE.md](https://docs.anthropic.com/en/docs/claude-code/memory)
- [Claude Code Settings](https://docs.anthropic.com/en/docs/claude-code/settings)
- [Claude Code MCP](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [Copilot Custom Instructions](https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot)
- [Copilot MCP](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/extend-coding-agent-with-mcp)
- [Copilot Setup Steps](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment)
- [Cursor Rules](https://cursor.com/docs/context/rules)
- [Windsurf Rules](https://docs.windsurf.com/windsurf/cascade/custom-rules)
- [GitHub AGENTS.md Lessons](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)

### Market & metrics
- [DORA 2024 Report](https://dora.dev/research/2024/dora-report/)
- [GitClear 2024](https://www.gitclear.com/coding_on_copilot_data_shows_ais_downward_pressure_on_code_quality)
- [GitClear 2025](https://www.gitclear.com/ai_assistant_code_quality_2025_research)
- [METR Study](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)
- [Chroma Context Rot](https://research.trychroma.com/context-rot)
- [Stack Overflow 2025 AI Survey](https://survey.stackoverflow.co/2025/ai)

### Competitors
- [CodeScene](https://codescene.com/product/behavioral-code-analysis)
- [Sourcegraph Amp](https://sourcegraph.com/blog/why-sourcegraph-and-amp-are-becoming-independent-companies)
- [Devin DeepWiki](https://docs.devin.ai/work-with-devin/deepwiki)
- [Potpie](https://techfundingnews.com/the-startup-building-a-knowledge-graph-for-code-raises-2-2m-to-make-ai-agents-actually-useful/)
- [Augment Context Engine](https://www.augmentcode.com/context-engine)

### Academic
- [ArchAgent](https://arxiv.org/abs/2601.13007), [Codified Context](https://arxiv.org/abs/2602.20478), [SWE-EVO](https://arxiv.org/abs/2512.18470), [A-Mem](https://arxiv.org/abs/2502.12110), [Graphiti](https://arxiv.org/abs/2501.13956), [Meta DRS](https://engineering.fb.com/2025/08/06/developer-tools/diff-risk-score-drs-ai-risk-aware-software-development-meta/), [AGENTS.md eval](https://arxiv.org/abs/2602.11988), [Skill security](https://arxiv.org/abs/2601.10338), [MCP Security](https://www.heyuan110.com/posts/ai/2026-03-10-mcp-security-2026/)

---

_End of product research. See `docs/research-build.md` for implementation-level technical decisions._
