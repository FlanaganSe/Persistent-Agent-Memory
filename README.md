# Repo Knowledge Plane

Persistent, agent-neutral intelligence layer for software repositories.

AI coding agents are stateless — every session, they rediscover your repo's conventions, architecture, and history from scratch. Repo Knowledge Plane fixes that by building a durable knowledge model of your codebase and serving it over [MCP](https://modelcontextprotocol.io) so any agent can query it.

## What it does

- Indexes your repo's code, git history, and project config
- Infers conventions, module boundaries, ownership, and architecture
- Generates and maintains `AGENTS.md` and other agent instruction files
- Serves structured repo knowledge via MCP (conventions, impact graphs, test recommendations)
- Runs locally — no cloud, no code leaves your machine

## Status

**Early stage.** Product requirements are a work in progress (see `.claude/plans/prd.md`). Stack and implementation are not yet finalized.

## License

TBD
