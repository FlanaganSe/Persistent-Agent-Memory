# Installation

## Requirements

- Python 3.12 or later
- Git (validated by `rkp doctor`)
- macOS or Linux (Windows support planned for Phase 2)

## Install from PyPI

```bash
pip install repo-knowledge-plane
```

Or use [uv](https://docs.astral.sh/uv/) for isolated execution:

```bash
uvx repo-knowledge-plane
```

## Install for Development

```bash
git clone https://github.com/seanflanagan/repo-knowledge-plane.git
cd repo-knowledge-plane
uv pip install ".[dev]"
```

## Verify Installation

```bash
rkp doctor
```

This checks:

- Python version (3.12+)
- Git installation and version
- SQLite FTS5 support
- tree-sitter availability

## Dependencies

RKP uses:

- **SQLite** (WAL mode, FTS5) for local storage
- **tree-sitter** for code parsing (Python, JS/TS)
- **FastMCP** for MCP server
- **Typer + Rich** for CLI
- **pydantic v2** for configuration validation
- **structlog** for structured logging
