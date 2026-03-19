# Repo Knowledge Plane

Extract once, govern centrally, project everywhere for AI coding agents.

Repo Knowledge Plane (RKP) is a local-first repository intelligence layer for agent workflows. It extracts durable, evidence-backed operational knowledge from code, config, CI, docs, and imported instruction files, governs that knowledge through review, and projects it into host-native agent formats or MCP responses.

## Why it exists

Coding agents repeatedly rediscover repo context or guess it. Teams then compensate by hand-maintaining multiple instruction surfaces that drift over time. RKP centralizes that problem:

- extract once from the repo itself
- govern centrally through claims and review state
- project everywhere into the agent surfaces you actually use

## What works today

| Area | What you get |
|---|---|
| Extraction | Python, JavaScript, TypeScript, common build/config files, GitHub Actions, and checked-in docs |
| Governance | Review, edit, suppress, tombstone, audit trail, drift detection, freshness metadata |
| Projection | Codex, Claude Code, Copilot, Cursor, and Windsurf adapters with maturity tiers |
| Serving | MCP tools for conventions, commands, guardrails, prerequisites, previews, repo overview, and preflight context |

## Start here

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Demo walkthrough](demo.md)

## Important product truths

- RKP is an alpha product with strong architectural intent and meaningful verification.
- Adapter maturity is not uniform; Codex and Claude are currently the strongest surfaces.
- This is a local-first CLI and MCP tool, not a hosted control plane.
- Review gating and sensitivity filtering are part of the product story, not optional polish.

## Next reading

- [Host adapters](host-adapters.md)
- [CLI reference](reference/cli.md)
- [Configuration](reference/configuration.md)
- [Development guide](development.md)
- [Testing guide](testing.md)
