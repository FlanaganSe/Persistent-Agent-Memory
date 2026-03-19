# Installation

## Requirements

- Python 3.12 or 3.13
- Git available on `PATH`
- SQLite with FTS5 support
- Best-tested on macOS and Linux

Use `rkp doctor` after install to verify the environment actually works on the current machine.

## Install from PyPI

```bash
pip install repo-knowledge-plane
```

## Install with `uv`

```bash
uv tool install repo-knowledge-plane
```

For one-off execution without a persistent tool install:

```bash
uvx --from repo-knowledge-plane rkp doctor
```

## Install for local development

```bash
git clone https://github.com/seanflanagan/repo-knowledge-plane.git
cd repo-knowledge-plane
uv pip install ".[dev]"
```

## Verify the install

```bash
rkp doctor
```

Expected checks:

- Python version is supported
- Git is installed
- SQLite FTS5 is available
- tree-sitter runtime is available

## What installation does not do

- It does not initialize a repo for RKP use.
- It does not write any instruction files.
- It does not start the MCP server.

Those happen after install with `rkp init`, `rkp apply`, and `rkp serve`.
