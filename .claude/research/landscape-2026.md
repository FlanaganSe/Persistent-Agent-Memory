# Coding Agent Instruction/Configuration Surface Landscape (March 2026)

Research date: 2026-03-18. Sources: official documentation, arxiv papers, vendor blogs, web search.

---

## 1. GitHub Copilot

### Instruction Surfaces (as of March 2026)

| Surface | Location | Scope | Details |
|---|---|---|---|
| **copilot-instructions.md** | `/.github/copilot-instructions.md` | Repo-wide | Applies to coding agent, Copilot Chat, and code review. Org-level instructions serve as fallback. |
| **Path-scoped instructions** | `/.github/instructions/**/*.instructions.md` | Per file pattern | YAML frontmatter with `applyTo: "glob"` targets specific file patterns. |
| **Custom agents** | `/.github/agents/CUSTOM-AGENT-NAME.md` | Per agent | Markdown files with YAML frontmatter specifying name, description, prompt, tools, and MCP servers. Also definable at org/enterprise level in `.github-private` repo. |
| **copilot-setup-steps.yml** | `/.github/workflows/copilot-setup-steps.yml` | Repo-wide | GitHub Actions workflow for pre-installing dependencies in ephemeral environment. Supports steps, permissions, runs-on (Ubuntu/Windows/self-hosted), services, snapshot, timeout. Must be on default branch. |
| **MCP servers** | Per custom agent or repo-level | Per agent or repo | GitHub and Playwright MCP servers enabled by default. Custom agents can scope specific MCP servers. |
| **Copilot Memory** | Repo-specific, auto-created | Per repo | Repository-specific memories with citations to code locations. Validated against current codebase on retrieval. Auto-deleted after 28 days; refreshed on successful use. Currently limited to coding agent, code review, and CLI. |
| **AGENTS.md / CLAUDE.md** | Workspace root | Repo-wide | Copilot auto-discovers and loads AGENTS.md and CLAUDE.md instruction files (announced March 2026 for JetBrains). |
| **Agent hooks** | Settings-based | Per event | Public preview (March 2026): custom commands at key points during agent sessions. |

**Key facts**: Copilot's instruction surface is now the most layered. Memory is Copilot-only and ephemeral (28-day TTL). Copilot coding agent runs in GitHub's sandboxed environment -- MCP resources and prompts are not available, only tools. Custom agents are the most composable unit. copilot-setup-steps.yml is unique (no other platform has first-class "agent environment" config). Copilot now reads AGENTS.md AND CLAUDE.md AND its own copilot-instructions.md.

---

## 2. Claude Code

### Instruction Surfaces (as of March 2026)

| Surface | Location | Scope |
|---|---|---|
| **CLAUDE.md** (project) | `./CLAUDE.md` or `./.claude/CLAUDE.md` | Project-wide, shared via VCS |
| **CLAUDE.md** (user) | `~/.claude/CLAUDE.md` | All projects for this user |
| **CLAUDE.md** (managed policy) | System paths (e.g., macOS: `/Library/Application Support/ClaudeCode/CLAUDE.md`) | All users on machine. Cannot be excluded. |
| **CLAUDE.md** (subdirectory) | `path/to/subdir/CLAUDE.md` | Loaded on-demand when files in subdir are accessed |
| **Rules** | `.claude/rules/*.md` | Per topic, optionally path-scoped via `paths:` frontmatter |
| **User rules** | `~/.claude/rules/*.md` | All projects, lower priority than project rules |
| **Skills** | `.claude/skills/<name>/SKILL.md` | Per skill, on-demand. Progressive disclosure. Support `context: fork`, `allowed-tools`, `model`, argument substitution, dynamic context via shell injection. |
| **Subagents** | `.claude/agents/<name>.md` | Per agent. Frontmatter: tools, disallowedTools, model, permissionMode, maxTurns, skills, mcpServers, hooks, memory (user/project/local), background, isolation (worktree). |
| **Auto memory** | `~/.claude/projects/<project>/memory/MEMORY.md` | Per project, machine-local. First 200 lines loaded every session. |
| **Hooks** | Settings-based | Lifecycle events: PreToolUse, PostToolUse, Stop, SubagentStart, SubagentStop, InstructionsLoaded. |
| **Settings** | Managed > User > Project > Local layers | Permissions, sandbox, env vars, claudeMdExcludes, hooks. |
| **MCP servers** | `.mcp.json`, settings, or inline in subagent frontmatter | Per project or per subagent. |
| **Plugins** | External packages | Provide agents, skills, and rules. Security-restricted. |
| **Agent teams** | Multi-session | Multiple agents with independent contexts. |
| **Imports** | `@path/to/file` in CLAUDE.md | Expand external files, max depth 5. |

**Key facts**: Most extensible platform as of March 2026. Subagent system is the most configurable (per-agent model, tools, permissions, hooks, skills, MCP, memory, isolation). 200-line soft limit on CLAUDE.md for adherence. Hooks provide deterministic control bypassing LLM decisions. Memory is machine-local with no cross-machine sync.

---

## 3. OpenAI Codex

### Instruction Surfaces (as of March 2026)

| Surface | Location | Scope |
|---|---|---|
| **AGENTS.md** | Root and directory-level | Layered from root to CWD. `AGENTS.override.md` for temporary overrides. Combined 32 KiB default cap. |
| **Skills** | `.agents/skills/<name>/SKILL.md` | Hierarchy: repo > user > admin > system. Optional `agents/openai.yaml` for UI metadata, invocation policy, tool dependencies. |
| **config.toml** | `~/.codex/config.toml` (user) or `.codex/config.toml` (project) | Model, sandbox_mode, approval_policy, permissions, features, MCP servers, profiles. |
| **Subagents** | `~/.codex/agents/` or `.codex/agents/` | TOML files. Built-in: default, worker, explorer. max_threads=6, max_depth=1. |
| **Profiles** | `profiles.<name>` in config.toml | Per-profile overrides for any config key. |

**Key facts**: AGENTS.md has a hard 32 KiB combined size limit. Skills follow the same Agent Skills open standard as Claude Code. Sandbox modes are explicit configuration. Override mechanism for temporary instruction replacement.

---

## 4. MCP Specification (2025-03-26)

Current standard, stewarded by AAIF (Linux Foundation). Key features:
- **Transports**: stdio, Streamable HTTP (new default for remote, replacing SSE), SSE (legacy).
- **Authorization**: OAuth 2.1 framework (new). Server Metadata Discovery, Dynamic Client Registration, session management.
- **Tool annotations**: Enhanced (read-only, destructive, etc.) but treated as untrusted unless from trusted server.
- **Security**: Advisory only ("SHOULD" not "MUST"). No protocol-level enforcement.
- **New**: JSON-RPC batching, audio content, enhanced progress updates.

**Key fact for PRD**: Security is advisory, not enforced. RKP's "no write operations via MCP" and "read-only by default" are stronger guarantees than the spec requires.

---

## 5. Research on Instruction File Effectiveness

### Study 1: arxiv 2601.20404 (January 2026, Lulla et al.)

**Scope**: 10 repos, 124 PRs, single agent (Codex/gpt-5.2-codex), small tasks (<=100 LOC).
**Finding**: AGENTS.md reduces median runtime by 28.64% (p<0.05) and median output tokens by 16.58% (p<0.05). Task completion unchanged.
**Limitations**: Single agent. Small tasks only. No correctness evaluation.

### Study 2: arxiv 2602.11988 (February 2026, Gloaguen et al., ETH Zurich)

**Scope**: 4 agent-model pairs, 2 benchmarks (SWE-bench Lite + novel AGENTbench with 138 tasks).
**Findings**:
- LLM-generated context files: performance drops in 5/8 settings (-0.5% to -2% success). Cost increase +20-23%. Reasoning tokens +14-22%.
- Developer-written files: marginal improvement (~+4% success), but cost +19%.
- Repository overviews: zero reduction in agent navigation steps despite being in 100% of LLM-generated files.
- Tool mention effect: if a tool is named in context file, agent usage increases dramatically.
- When docs removed, LLM-generated context files improve by +2.7% -- suggesting they duplicate existing docs.

**Recommendation**: Omit LLM-generated files. Human-written files should describe only minimal, non-inferable requirements.

### Reconciliation

The studies are not contradictory. Study 1: AGENTS.md makes agents navigate faster (fewer tokens). Study 2: despite faster navigation, agents don't resolve tasks more successfully, and extra instructions trigger unnecessary thoroughness that increases cost. **Agents follow instructions too literally** -- comprehensive guidance causes over-compliance.

---

## 6. FastMCP (v2.14.5, February 2026)

Mature Python MCP SDK. Supports: stdio, Streamable HTTP (since v2.3), SSE, SSE Polling, Memory/docket, Redis transports. OAuth 2.1 with multiple providers. Pluggable middleware, storage backends, server composition.

**Relevance**: Confirmed as appropriate stack choice for PRD. stdio trivial for MVP. Remote transport and OAuth available for Phase 2+.

---

## 7. Competitors

### Sourcegraph 7.0
Self-described "intelligence layer for developers and AI agents." Deep Search via MCP, cross-repo semantic understanding, SCIP-based code navigation. Dropped Cody Free/Pro; Amp is their own agent. **Differentiator from RKP**: Static references/search only. No behavioral signals, convention synthesis, instruction projection, or governance.

### Potpie
Codebase-to-knowledge-graph (Neo4j). CrewAI-powered RAG agents. $2.2M pre-seed (Feb 2026). **Differentiator from RKP**: Not MCP-native. Own agent suite. No behavioral signals, correction/governance, or host-aware projection.

### CodeScene
Temporal coupling via commit co-occurrence, developer proximity, and ticket references. Configurable thresholds. **Differentiator from RKP**: Human-dashboard-oriented, retrospective. No real-time agent consumption. No MCP. No instruction synthesis. Strong methodology for Phase 3 behavioral layer.

---

## 8. Agent Skills Standard Convergence

Both Claude Code and Codex now support the Agent Skills open standard (agentskills.io). SKILL.md files with YAML frontmatter, optional scripts/references/assets. Cross-platform skill format is emerging. GitHub Copilot does not yet support it but reads AGENTS.md and CLAUDE.md.

**Implication for PRD**: Skills as a delivery surface alongside instruction files is a new opportunity not in the original PRD. A skill like `get-repo-context` could work on both Claude Code and Codex.

---

## 9. Summary: What the Research Validates and Refutes

### Validated

1. **Context files make agents faster** (Study 1): -28.6% runtime, -16.6% tokens. Less exploration.
2. **LLM-generated context files hurt task success** (Study 2): -3% success, +20%+ cost.
3. **Human-written files provide marginal benefit** (Study 2): +4% success, +19% cost. Only non-inferable details help.
4. **Repository overviews are waste** (Study 2): No navigation reduction despite universal inclusion.
5. **Instruction surfaces are proliferating** (all platforms): Complexity of faithful projection is increasing.
6. **Agent Skills standard is converging** (Claude Code + Codex).

### Refuted/Complicated

1. **"Just generate AGENTS.md" is a product**: Both studies argue against comprehensive generation. Value is in minimal, verified, non-inferable context.
2. **"More context is better"**: Directly contradicted. More triggers over-compliance.
3. **"Copilot Memory solves cross-session context"**: 28-day TTL, Copilot-only, no governance.

### Uncertain

1. Whether findings generalize beyond Python.
2. Whether instruction file value changes with repo complexity.
3. Whether validated commands alone justify a product.
4. Whether Agent Skills standard will be adopted by Copilot.

---

## 10. Implications for PRD

| PRD Decision | Supported? | Notes |
|---|---|---|
| Verified operational context as wedge | **Yes, strongly** | Study 2: raw generation harmful. Minimal, verified context is only beneficial content. |
| Validated command discovery as P0 | **Yes** | Explicitly recommended as highest-value content by ETH Zurich team. |
| Convention synthesis with declared/inferred separation | **Partially** | Scoped, non-inferable rules valuable. Comprehensive summaries are not. |
| Host capability matrix | **Yes** | March 2026 shows even more divergence (Copilot hooks, Claude skills/subagents/plugins, Codex profiles). |
| 32 KiB size constraint (Codex) | **Confirmed** | Default `project_doc_max_bytes`. |
| Tools-first MCP for Copilot | **Confirmed** | Copilot coding agent is sandboxed, tools only. |
| Keep instruction files thin and scoped | **Yes, strongly** | Both studies penalize verbose files. Claude Code docs: target under 200 lines. |
| Review-then-apply (no auto-write) | **Yes** | LLM-generated files without review degrade performance. |
| Local-first workstation agents for MVP | **Yes** | All three platforms support local MCP stdio. |
| Skills as potential delivery surface | **New opportunity** | Agent Skills standard converging across Claude Code and Codex. |
