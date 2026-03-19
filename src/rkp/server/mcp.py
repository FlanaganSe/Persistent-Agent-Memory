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

from rkp.server.tools import (
    get_conflicts,
    get_conventions,
    get_guardrails,
    get_instruction_preview,
    get_module_info,
    get_prerequisites,
    get_validated_commands,
)
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


@mcp.tool(annotations={"readOnlyHint": True})
def get_module_info_tool(
    ctx: Context,
    path_or_symbol: str,
) -> str:
    """Get module boundary info, dependencies, dependents, and test locations.

    Args:
        path_or_symbol: A file path or module name to look up

    Returns:
        JSON response with module boundary, dependency graph, test locations,
        and applicable scoped rules.
    """
    db: sqlite3.Connection = ctx.lifespan_context["db"]
    response = get_module_info(db, path_or_symbol=path_or_symbol)
    return json.dumps(response.to_dict(), indent=2)


@mcp.tool(annotations={"readOnlyHint": True})
def get_conflicts_tool(
    ctx: Context,
    path_or_scope: str = "**",
) -> str:
    """Get conflict claims where declared and inferred knowledge disagree.

    Args:
        path_or_scope: Path or scope filter (default: ** for all)

    Returns:
        JSON response with conflict claims including conflicting claim references
        and suggested resolution type.
    """
    db: sqlite3.Connection = ctx.lifespan_context["db"]
    response = get_conflicts(db, path_or_scope=path_or_scope)
    return json.dumps(response.to_dict(), indent=2)


@mcp.tool(annotations={"readOnlyHint": True})
def get_guardrails_tool(
    ctx: Context,
    path_or_scope: str = "**",
) -> str:
    """Get security guardrails and permission restrictions.

    Args:
        path_or_scope: Path or scope filter (default: ** for all)

    Returns:
        JSON response with guardrail claims, each indicating whether
        it is enforceable on specific hosts or advisory-only.
    """
    db: sqlite3.Connection = ctx.lifespan_context["db"]
    response = get_guardrails(db, path_or_scope=path_or_scope)
    return json.dumps(response.to_dict(), indent=2)


@mcp.tool(annotations={"readOnlyHint": True})
def get_instruction_preview_tool(
    ctx: Context,
    consumer: str = "codex",
) -> str:
    """Preview projected instruction artifacts for a target consumer.

    Args:
        consumer: Target host (codex, agents-md, claude)

    Returns:
        JSON response with all projected artifacts, provenance,
        and projection decision log.
    """
    db: sqlite3.Connection = ctx.lifespan_context["db"]
    response = get_instruction_preview(db, consumer=consumer)
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

        @test_server.tool(name="get_module_info_tool", annotations={"readOnlyHint": True})
        def _test_get_module_info(  # pyright: ignore[reportUnusedFunction]
            ctx: Context,
            path_or_symbol: str,
        ) -> str:
            """Get module boundary info, dependencies, dependents, and test locations."""
            db_conn: sqlite3.Connection = ctx.lifespan_context["db"]
            response = get_module_info(db_conn, path_or_symbol=path_or_symbol)
            return json.dumps(response.to_dict(), indent=2)

        @test_server.tool(name="get_conflicts_tool", annotations={"readOnlyHint": True})
        def _test_get_conflicts(  # pyright: ignore[reportUnusedFunction]
            ctx: Context,
            path_or_scope: str = "**",
        ) -> str:
            """Get conflict claims."""
            db_conn: sqlite3.Connection = ctx.lifespan_context["db"]
            response = get_conflicts(db_conn, path_or_scope=path_or_scope)
            return json.dumps(response.to_dict(), indent=2)

        @test_server.tool(name="get_guardrails_tool", annotations={"readOnlyHint": True})
        def _test_get_guardrails(  # pyright: ignore[reportUnusedFunction]
            ctx: Context,
            path_or_scope: str = "**",
        ) -> str:
            """Get security guardrails and permission restrictions."""
            db_conn: sqlite3.Connection = ctx.lifespan_context["db"]
            response = get_guardrails(db_conn, path_or_scope=path_or_scope)
            return json.dumps(response.to_dict(), indent=2)

        @test_server.tool(name="get_instruction_preview_tool", annotations={"readOnlyHint": True})
        def _test_get_instruction_preview(  # pyright: ignore[reportUnusedFunction]
            ctx: Context,
            consumer: str = "codex",
        ) -> str:
            """Preview projected instruction artifacts."""
            db_conn: sqlite3.Connection = ctx.lifespan_context["db"]
            response = get_instruction_preview(db_conn, consumer=consumer)
            return json.dumps(response.to_dict(), indent=2)

        return test_server

    return mcp
