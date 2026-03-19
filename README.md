# Repo Knowledge Plane

Extract once, govern centrally, project everywhere for AI coding agents.

Repo Knowledge Plane (RKP) is a local-first CLI and MCP server that turns repo evidence into durable operational knowledge for coding agents. It extracts conventions, validated commands, prerequisites, module boundaries, and guardrails from code, config, CI, docs, and imported instruction files, then projects that knowledge into host-native agent surfaces.

The problem it solves is simple: coding agents are stateless, and teams end up hand-maintaining overlapping files like `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, and `copilot-instructions.md`. RKP gives you one governed source of truth instead of a pile of drifting copies.

## What RKP Is For

- Teams using multiple coding agents on the same repository
- Repos that need evidence-backed commands, conventions, and guardrails
- Technical leads who want human review before agent-visible instructions are written
- Local-first workflows where repo knowledge stays on disk and under version control

## What RKP Is Not

- Not a hosted SaaS control plane
- Not a generic code search or wiki generator
- Not a replacement for CI, code review, or secrets management
- Not a promise that every agent host has equal feature maturity

## Core Workflow

```text
repo evidence -> claims -> human governance -> host projections + MCP queries
```

1. `rkp init` indexes the repository and creates `.rkp/`.
2. `rkp review` approves, edits, suppresses, or tombstones claims.
3. `rkp apply --host ...` writes reviewed instruction artifacts.
4. `rkp serve` exposes the same governed knowledge over MCP.

## Guarantees That Matter

- `stdout` is reserved for MCP protocol and machine-readable output; diagnostics go to `stderr`.
- Sensitivity filtering is enforced at output boundaries.
- `rkp apply` only writes approved or edited claims.
- Imported claims do not silently outrank executable config.
- Projection output is deterministic for the same claim set.
- Local-only claims do not get written into checked-in overrides.
- MCP is read-only except for the intentional `refresh_index` write path.

## Adapter Surface Today

| Host | Current output | Status |
|---|---|---|
| Codex | `AGENTS.md` | GA-eligible in the quality harness |
| Claude Code | `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`, `.claude/settings-snippet.json` | GA-eligible in the quality harness |
| GitHub Copilot | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `.github/workflows/copilot-setup-steps.yml`, `.copilot-tool-allowlist.json` | Beta |
| Cursor | `.cursor/rules/` | Alpha |
| Windsurf | `.windsurf/rules/` | Alpha |

RKP as a product is still alpha. “GA-eligible” here means the adapter passes the current conformance/leakage/drift harness, not that the overall project is production-finished.

## Install

```bash
pip install repo-knowledge-plane
```

Or with `uv`:

```bash
uv tool install repo-knowledge-plane
```

## Five-Minute Start

```bash
cd your-repo
rkp doctor
rkp init
rkp status
rkp preview --host claude
rkp review --approve-all --threshold 0.95
rkp apply --host claude --yes
rkp serve
```

Already have instruction files?

```bash
rkp init
rkp import
rkp review
rkp apply --host codex --yes
```

`rkp init` comes first even for import-heavy repos, because it creates the checked-in `.rkp/config.yaml` and local index layout the rest of the workflow expects.

## Demo Path

The cleanest demo is:

1. `rkp doctor`
2. `rkp init`
3. `rkp preview --host codex`
4. `rkp review --approve-all --threshold 0.95`
5. `rkp apply --host claude --yes`
6. `rkp serve`
7. Query `get_preflight_context` or `get_instruction_preview` from an MCP client

See [docs/demo.md](docs/demo.md) for a scripted walkthrough.

## Local Development

```bash
uv pip install ".[dev]"
uv run nox -s lint
uv run nox -s typecheck
uv run nox -s test
uv run nox -s quality
uv run nox -s docs
uv build
```

The default `nox` sessions now include docs, and `nox -s ci` runs lint, typecheck, tests, quality, and docs.

## Status and Scope

`0.1.0` is a serious alpha/demo release: the architecture is intentional, the claim/governance model is real, and the adapter quality harness is meaningful. What is not done yet is equally important: no hosted control plane, no sandbox verification pipeline, no remote MCP transport story, and no claim that every host surface is equally mature.

## Recommended Next Features

- Claim-backed change impact and blast-radius queries
- Better repo overview fidelity from populated evidence tables
- Stronger import round-trip coverage for more host formats
- Streamable HTTP MCP transport once the local stdio path is stable
- Optional sandbox verification for high-value commands

## Documentation

- [Getting started](docs/getting-started/quickstart.md)
- [Demo walkthrough](docs/demo.md)
- [Host adapters](docs/host-adapters.md)
- [CLI reference](docs/reference/cli.md)
- [Configuration](docs/reference/configuration.md)
- [Development guide](docs/development.md)
- [Testing guide](docs/testing.md)
- [Distribution notes](docs/distribution.md)

## License

Apache-2.0
