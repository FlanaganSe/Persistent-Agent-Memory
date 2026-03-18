---
name: project_rkp_context
description: Core context for the Repo Knowledge Plane project — what it is, competitive position, and key technical decisions under consideration
type: project
---

Repo Knowledge Plane (RKP) is a persistent, agent-neutral intelligence layer for software repositories, exposed via MCP. The product sits below AI coding tools (Cursor, Claude Code, Copilot, etc.) as shared infrastructure they all consume.

Core value propositions:
1. Auto-generate and serve AGENTS.md from codebase analysis — no vendor does this today
2. Persistent cross-session, cross-tool repo memory (architecture, conventions, change history)
3. Change-impact graphs and merge-risk prediction
4. MCP server interface (Resources for context, Tools for queries) — agent-neutral

**Why:** The market is $5–7B today heading to $25–50B by 2030. Every agent reinvents context per-session; no persistent neutral layer exists. AGENTS.md is in 60,000+ repos but zero tools generate it from analysis.

**How to apply:** Frame all suggestions around agent-neutrality, MCP-native design, and AGENTS.md synthesis as the wedge use case. Potpie AI ($2.2M pre-seed, Feb 2026) is the closest competitor — differentiate on MCP-native + open/self-hostable + AGENTS.md generation.

Stack: TBD as of 2026-03-18. PRD exists at `.claude/plans/prd.md`. Research at `.claude/plans/research.md`.
