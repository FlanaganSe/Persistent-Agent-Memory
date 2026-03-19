# Development Guide

## Local setup

```bash
git clone https://github.com/seanflanagan/repo-knowledge-plane.git
cd repo-knowledge-plane
uv pip install ".[dev]"
```

## High-value commands

```bash
uv run nox -s lint
uv run nox -s typecheck
uv run nox -s test
uv run nox -s quality
uv run nox -s docs
uv run python -m rkp --json doctor
uv run python -m rkp --json preview --host codex
uv build
```

## Repo shape

The core layers are:

- `core/`: claim model, types, security, config
- `store/`: SQLite persistence and migrations
- `indexer/`: parsers and extractors
- `importer/`: existing instruction file ingestion
- `projection/`: host adapters and budgets
- `server/`: MCP handlers and response envelopes
- `cli/`: Typer entrypoints and Rich UX
- `quality/`: conformance/leakage/drift harness

## Common failure modes

- `status` before `init`: the repo is not initialized yet
- noisy self-indexing: add repo-local `discovery.exclude_dirs` in `.rkp/config.yaml`
- MCP protocol pollution: any new human/log output must stay on `stderr`
- docs drift: if the adapter output path changes, update README, docs, and tests together

## Design constraints worth re-reading

- adapters format claims, they do not infer them
- imported claims stay below executable config until review
- sensitivity filtering and governance are output-boundary concerns, not optional callers’ whims
- this repo is still evolving, so prefer focused improvements over framework-building
