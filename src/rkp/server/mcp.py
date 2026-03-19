"""FastMCP server instance with lifespan."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastmcp import Context, FastMCP

from rkp.server.tools import get_conventions, get_prerequisites, get_validated_commands
from rkp.store.database import open_database, run_migrations

logger = structlog.get_logger()


@asynccontextmanager
async def app_lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
    """Open SQLite database and prepare stores."""
    db_path = Path(".rkp/local/rkp.db")
    db = open_database(db_path, check_same_thread=False)
    run_migrations(db)
    logger.info("MCP server database ready", db_path=str(db_path))
    try:
        yield {"db": db}
    finally:
        db.close()
        logger.info("MCP server database closed")


mcp = FastMCP(
    "repo-knowledge-plane",
    version="0.1.0",
    instructions="Repo Knowledge Plane: verified operational context for this repository.",
    lifespan=app_lifespan,
)


@mcp.tool(annotations={"readOnlyHint": True})
def get_validated_commands_tool(
    ctx: Context,
    scope: str = "**",
) -> str:
    """Get validated build/test/lint commands with evidence and risk classification.

    Args:
        scope: Path scope filter (default: ** for all)

    Returns:
        JSON response with validated commands, their sources, evidence levels,
        and risk classifications.
    """
    db: sqlite3.Connection = ctx.lifespan_context["db"]
    response = get_validated_commands(db, scope=scope)
    return json.dumps(response.to_dict(), indent=2)


@mcp.tool(annotations={"readOnlyHint": True})
def get_conventions_tool(
    ctx: Context,
    path_or_symbol: str = "**",
    include_evidence: bool = False,
    task_context: str | None = None,
) -> str:
    """Get conventions for a path or symbol with source authority and confidence.

    Args:
        path_or_symbol: Path or symbol to scope conventions to (default: ** for all)
        include_evidence: Include evidence file references in response
        task_context: Filter by applicability (e.g., "testing", "build")

    Returns:
        JSON response with convention claims including source authority,
        confidence, applicability, and review state.
    """
    db: sqlite3.Connection = ctx.lifespan_context["db"]
    response = get_conventions(
        db,
        path_or_symbol=path_or_symbol,
        include_evidence=include_evidence,
        task_context=task_context,
    )
    return json.dumps(response.to_dict(), indent=2)


@mcp.tool(annotations={"readOnlyHint": True})
def get_prerequisites_tool(
    ctx: Context,
    command_or_scope: str | None = None,
) -> str:
    """Get environment prerequisites and profiles for a command or scope.

    Args:
        command_or_scope: A specific command name or path scope (default: all)

    Returns:
        JSON response with environment prerequisites structured as profiles:
        runtimes, tools, services, env vars, evidence level per prerequisite.
    """
    db: sqlite3.Connection = ctx.lifespan_context["db"]
    response = get_prerequisites(db, command_or_scope=command_or_scope)
    return json.dumps(response.to_dict(), indent=2)


def create_server(
    *,
    db: sqlite3.Connection | None = None,
    db_path: Path | None = None,
) -> FastMCP[Any]:
    """Create an MCP server, optionally with a pre-opened database.

    Used in testing to inject a database connection.
    """
    if db is not None:

        @asynccontextmanager
        async def test_lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
            yield {"db": db}

        test_server: FastMCP[Any] = FastMCP(
            "repo-knowledge-plane",
            version="0.1.0",
            instructions="Repo Knowledge Plane: verified operational context.",
            lifespan=test_lifespan,
        )

        @test_server.tool(name="get_validated_commands_tool", annotations={"readOnlyHint": True})
        def _test_get_validated_commands(  # pyright: ignore[reportUnusedFunction]
            ctx: Context,
            scope: str = "**",
        ) -> str:
            """Get validated build/test/lint commands with evidence and risk classification."""
            db_conn: sqlite3.Connection = ctx.lifespan_context["db"]
            response = get_validated_commands(db_conn, scope=scope)
            return json.dumps(response.to_dict(), indent=2)

        @test_server.tool(name="get_conventions_tool", annotations={"readOnlyHint": True})
        def _test_get_conventions(  # pyright: ignore[reportUnusedFunction]
            ctx: Context,
            path_or_symbol: str = "**",
            include_evidence: bool = False,
            task_context: str | None = None,
        ) -> str:
            """Get conventions for a path or symbol."""
            db_conn: sqlite3.Connection = ctx.lifespan_context["db"]
            response = get_conventions(
                db_conn,
                path_or_symbol=path_or_symbol,
                include_evidence=include_evidence,
                task_context=task_context,
            )
            return json.dumps(response.to_dict(), indent=2)

        @test_server.tool(name="get_prerequisites_tool", annotations={"readOnlyHint": True})
        def _test_get_prerequisites(  # pyright: ignore[reportUnusedFunction]
            ctx: Context,
            command_or_scope: str | None = None,
        ) -> str:
            """Get environment prerequisites and profiles."""
            db_conn: sqlite3.Connection = ctx.lifespan_context["db"]
            response = get_prerequisites(db_conn, command_or_scope=command_or_scope)
            return json.dumps(response.to_dict(), indent=2)

        return test_server

    return mcp
