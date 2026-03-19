# Distribution

RKP is a Python CLI plus MCP server. The minimum viable distribution story is intentionally lightweight.

## Recommended install paths

- `pip install repo-knowledge-plane`
- `uv tool install repo-knowledge-plane`
- `uvx --from repo-knowledge-plane rkp ...` for one-off use

## What is already in place

- Hatchling build backend
- console entry point: `rkp`
- MkDocs site for documentation
- Towncrier for changelog management
- PyPI release workflow triggered from version tags

## What this repo does not need right now

- a hosted control plane
- Kubernetes deployment manifests
- a container-first runtime model

## Release expectations

The release path should verify:

- tag version matches `pyproject.toml`
- changelog fragments render cleanly
- lint, typecheck, tests, quality, and docs all pass
- `uv build` succeeds

That is enough to make a Python CLI/MCP project credible without adding enterprise theater.
