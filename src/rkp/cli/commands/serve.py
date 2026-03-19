"""rkp serve — start the MCP server."""

from __future__ import annotations

import typer

from rkp.server.mcp import mcp


def serve(
    ctx: typer.Context,
) -> None:
    """Start the MCP server (stdio transport)."""
    mcp.run()
