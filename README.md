# Repo Knowledge Plane

Portable, verified repo context for every coding agent.

AI coding agents are stateless. Every session, they rediscover your repo's conventions, build commands, architecture, and guardrails from scratch — or worse, they guess wrong. RKP fixes this by extracting a durable, evidence-backed knowledge model from your codebase and serving it to any agent via [MCP](https://modelcontextprotocol.io).

## The Problem

AI coding tools boost individual speed, but teams are seeing more churn, more broken conventions, and more coordination drift. The root cause: agents lack persistent, verified operational context.

Meanwhile, every agent vendor has built its own instruction surface — `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `copilot-instructions.md`, `.windsurf/rules`. Teams end up maintaining multiple overlapping, potentially contradictory files by hand. When conventions change, updates need to happen in N places.

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

**Claims** are the core abstraction: structured facts about your repo (conventions, commands, prerequisites, boundaries) with provenance, confidence scores, and source authority. A claim like "run `pytest` for tests" carries evidence of *where* that was found (CI config, pyproject.toml, etc.) and *how confident* the extraction is.

Human review is first-class. You approve what's right, fix what's wrong, suppress what's irrelevant. Your decisions are version-controlled in `.rkp/overrides/` and survive re-extraction.

## What It Extracts

| Claim Type | Example |
|---|---|
| Conventions | "Use frozen dataclasses for domain models" |
| Validated commands | "`nox -s test` — CI-evidenced, safe" |
| Prerequisites | "Requires Python 3.12+, Node 18+" |
| Guardrails | "Never run `rm -rf` on repo root" |
| Module boundaries | "src/payments → src/core (import dependency)" |
| Conflicts | "README says Jest, CI runs Vitest" |

Sources: Python/JS/TS code (via tree-sitter), `pyproject.toml`, `package.json`, `Dockerfile`, GitHub Actions, Makefile, and existing instruction files.

## Where It Projects

RKP translates your canonical claims into each agent's native format:

| Agent | Output | Status |
|---|---|---|
| **Codex** | `AGENTS.md` + `.agents/skills/` | GA |
| **Claude Code** | `CLAUDE.md` + `.claude/rules/` + `.claude/skills/` | GA |
| **Copilot** | `copilot-instructions.md` + `copilot-setup-steps.yml` | Beta |
| **Cursor** | `.cursor/rules/` | Alpha |
| **Windsurf** | `.windsurf/rules/` | Alpha |

Each projection respects the host's capabilities and size constraints. High-authority claims go in always-on files; detailed procedures go in skills. Sensitive claims (team-only, local-only) are filtered automatically.

## Quick Start

```bash
# Install
pip install repo-knowledge-plane
# or
uvx repo-knowledge-plane

# Initialize on your repo
cd your-repo
rkp init

# Review extracted claims
rkp review

# Preview what would be generated
rkp preview --host claude

# Write instruction files
rkp apply --host claude

# Start MCP server for agents
rkp serve
```

### Already have instruction files?

```bash
# Import existing AGENTS.md, CLAUDE.md, etc.
rkp import

# Review imported + extracted claims together
rkp review

# Re-project with unified governance
rkp apply --host codex
```

## CLI Reference

| Command | What it does |
|---|---|
| `rkp init` | Scan repo, extract claims, create `.rkp/` config |
| `rkp status` | Show index health, pending reviews, stale claims |
| `rkp review` | Interactively approve/edit/suppress claims |
| `rkp preview --host <target>` | Preview projected artifacts without writing |
| `rkp apply --host <target>` | Write instruction files to disk |
| `rkp import` | Ingest existing instruction files as claims |
| `rkp refresh` | Re-check evidence, flag stale claims |
| `rkp serve` | Start MCP server (stdio transport) |
| `rkp audit` | Query the governance audit trail |
| `rkp quality` | Run the quality harness (conformance, leakage, fidelity) |
| `rkp doctor` | Validate environment and repo setup |
| `rkp purge` | Delete local RKP data |

All commands accept `--repo <path>`, `--json`, `--verbose`, and `--quiet`.

## MCP Tools

When running `rkp serve`, agents can call these tools:

| Tool | Purpose |
|---|---|
| `get_conventions` | Scoped conventions with confidence and evidence |
| `get_validated_commands` | Build/test/lint commands with risk classification |
| `get_prerequisites` | Runtimes, tools, services, env vars needed |
| `get_guardrails` | Security restrictions and dangerous operations |
| `get_module_info` | Dependencies, dependents, test locations |
| `get_conflicts` | Where declared and inferred knowledge disagree |
| `get_instruction_preview` | What a specific agent would see |
| `get_repo_overview` | Languages, modules, claim statistics |
| `get_claim` | Full detail on a single claim |
| `get_preflight_context` | Minimum context bundle before editing |
| `refresh_index` | Trigger re-extraction |

All responses include freshness metadata — agents know if context is stale.

## Key Concepts

**Source authority hierarchy** — Not all knowledge is equal. A CI config (`executable-config`) outranks an inferred pattern (`inferred-low`). A human override outranks everything. RKP uses this hierarchy to resolve conflicts and prioritize what goes in size-limited instruction files.

**Thin-by-default projection** — Always-on instruction files contain only high-confidence, broadly applicable, non-inferable rules. Detailed content is pushed to skills/on-demand surfaces. This avoids overwhelming agents with noise.

**Drift detection** — RKP tracks the hash of every file it generates. If someone manually edits a managed file, `rkp status` flags the drift. You can absorb the edit (create a new claim), regenerate (overwrite), or suppress (stop managing that file).

**Sensitivity filtering** — Claims are tagged `public`, `team-only`, or `local-only`. Team-only and local-only claims never appear in exported instruction files or unauthenticated MCP responses.

## Repo Structure

```
.rkp/                          ← Checked into git
├── config.yaml                ← RKP settings (languages, thresholds)
├── overrides/                 ← Human governance decisions (approve, suppress, edit)
│   └── claim-abc123.yaml
└── local/                     ← Gitignored, regenerable
    └── rkp.db                 ← SQLite index (claims, evidence, history)
```

The `.rkp/overrides/` directory is the durable record of your team's decisions. The database is a cache — delete it and `rkp init` rebuilds from your repo + overrides.

## Development

```bash
# Setup
git clone <repo-url>
cd repo-knowledge-plane
uv pip install ".[dev]"

# Run checks
nox -s lint         # ruff check + format
nox -s typecheck    # pyright strict
nox -s test         # pytest
nox -s ci           # all of the above
```

**Requirements:** Python 3.12+, uv (recommended), git.

**Stack:** SQLite (WAL + FTS5), tree-sitter, FastMCP, Typer + Rich, structlog, pydantic v2, pytest + hypothesis + syrupy.

## Language Support

| Language | Extraction | Status |
|---|---|---|
| Python | tree-sitter + config parsers | Supported |
| JavaScript/TypeScript | tree-sitter + config parsers | Supported |
| Config files | pyproject.toml, package.json, Dockerfile, Makefile, GitHub Actions | Supported |
| Other languages | Graceful degradation (config-only extraction) | Partial |

## Design Principles

- **Local-first** — No cloud, no code leaves your machine. The database is a local SQLite file.
- **Evidence-backed** — Every claim links to source evidence. Nothing is asserted without provenance.
- **Human-governed** — Machines extract, humans decide. Approvals persist across re-extractions.
- **Agent-neutral** — One canonical model, projected to every agent's native format.
- **Thin-by-default** — Less is more. Only high-value context in always-on files.

## Status

**v0.1.0 — Early stage.** Core extraction, projection, and MCP serving work. The quality harness runs. Codex and Claude Code adapters are GA; Copilot is beta; Cursor and Windsurf are alpha/export-only.

## License

Apache-2.0
