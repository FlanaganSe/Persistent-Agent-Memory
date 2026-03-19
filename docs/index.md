# Repo Knowledge Plane

Portable, verified repo context for every coding agent.

AI coding agents are stateless. Every session, they rediscover your repo's conventions, build commands, architecture, and guardrails from scratch — or worse, they guess wrong. RKP fixes this by extracting a durable, evidence-backed knowledge model from your codebase and serving it to any agent via [MCP](https://modelcontextprotocol.io).

## The Problem

AI coding tools boost individual speed, but teams see more churn, more broken conventions, and more coordination drift. The root cause: agents lack persistent, verified operational context.

Meanwhile, every agent vendor has built its own instruction surface — `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `copilot-instructions.md`, `.windsurf/rules`. Teams maintain multiple overlapping, potentially contradictory files by hand.

RKP is the single source of truth. Extract once, project everywhere.

## How It Works

```
Your repo (code, config, CI)
        ↓
   rkp init          ← Extract claims from source code, configs, CI
        ↓
   rkp review        ← Human reviews: approve, edit, suppress
        ↓
   rkp apply         ← Generate instruction files for each agent
        ↓
   rkp serve         ← MCP server — agents query live context
```

## Where It Projects

| Agent | Output | Status |
|---|---|---|
| **Codex** | `AGENTS.md` + `.agents/skills/` | GA |
| **Claude Code** | `CLAUDE.md` + `.claude/rules/` + `.claude/skills/` | GA |
| **Copilot** | `copilot-instructions.md` + `copilot-setup-steps.yml` | Beta |
| **Cursor** | `.cursor/rules/` | Alpha |
| **Windsurf** | `.windsurf/rules/` | Alpha |

## Quick Start

```bash
pip install repo-knowledge-plane
cd your-repo
rkp init
rkp review
rkp apply --host claude
rkp serve
```

See the [Installation](getting-started/installation.md) and [Quick Start](getting-started/quickstart.md) guides for details.

## Design Principles

- **Local-first** — no cloud, no code leaves your machine
- **Evidence-backed** — every claim links to source evidence
- **Human-governed** — machines extract, humans decide
- **Agent-neutral** — one canonical model, projected to every agent's native format
- **Thin-by-default** — less is more in always-on instruction files
