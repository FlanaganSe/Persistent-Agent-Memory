"""FastMCP server instance with lifespan and tool/resource registration."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import structlog
from fastmcp import Context, FastMCP

from rkp.core.config import RkpConfig
from rkp.server.response_filter import filter_response
from rkp.server.tools import (
    get_claim,
    get_conflicts,
    get_conventions,
    get_guardrails,
    get_instruction_preview,
    get_module_info,
    get_preflight_context,
    get_prerequisites,
    get_repo_overview,
    get_validated_commands,
    refresh_index,
)
from rkp.server.trace import TraceLogger, create_trace_logger
from rkp.store.database import open_database, run_migrations

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def app_lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
    """Open SQLite database and prepare stores for the production server."""
    config = RkpConfig()
    db_path = config.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = open_database(db_path, check_same_thread=False)
    run_migrations(db)
    trace_logger = create_trace_logger(
        config.repo_root or Path(),
        enabled=config.trace_enabled,
    )
    logger.info("MCP server database ready", db_path=str(db_path))
    try:
        yield {
            "db": db,
            "config": config,
            "repo_root": config.repo_root or Path(),
            "trace_logger": trace_logger,
        }
    finally:
        db.close()
        logger.info("MCP server database closed")


# ---------------------------------------------------------------------------
# Tool handler functions  (one per MCP tool)
#
# Each handler: Context → str (JSON).  Pure logic lives in tools.py.
# Handlers are registered once via _register_tools() on any FastMCP instance.
# ---------------------------------------------------------------------------


def _ctx_db(ctx: Context) -> sqlite3.Connection:
    return ctx.lifespan_context["db"]


def _ctx_config(ctx: Context) -> RkpConfig:
    return ctx.lifespan_context.get("config", RkpConfig())


def _ctx_repo_root(ctx: Context) -> Path | None:
    return ctx.lifespan_context.get("repo_root")


def _ctx_trace_logger(ctx: Context) -> TraceLogger | None:
    return ctx.lifespan_context.get("trace_logger")


def _json(resp: Any) -> str:
    """Serialize a ToolResponse to JSON, applying response filtering."""
    raw: dict[str, Any] = cast(dict[str, Any], resp.to_dict())
    data = raw.get("data")
    existing_warnings: list[str] = [str(w) for w in cast(list[Any], raw.get("warnings", []))]
    if isinstance(data, dict):
        _, updated_warnings = filter_response(cast(dict[str, Any], data), existing_warnings)
        raw["warnings"] = updated_warnings
    return json.dumps(raw, indent=2)


def _traced(
    ctx: Context,
    tool_name: str,
    arguments: dict[str, object],
    resp: Any,
    duration_ms: float,
) -> None:
    """Log a trace entry if trace capture is enabled. Never raises."""
    try:
        trace = _ctx_trace_logger(ctx)
        if trace is None:
            return
        raw = resp.to_dict() if hasattr(resp, "to_dict") else {}
        data = raw.get("data", {})
        claim_count = 0
        if isinstance(data, dict):
            items = data.get("items")
            if isinstance(items, list):
                claim_count = len(items)
        # Estimate size without full serialization to avoid errors on non-serializable types
        try:
            response_str = json.dumps(raw)
            size_bytes = len(response_str.encode("utf-8"))
        except (TypeError, ValueError):
            size_bytes = 0
        trace.log_call(
            tool_name=tool_name,
            arguments=arguments,
            response_status=str(raw.get("status", "ok")),
            response_claim_count=claim_count,
            response_size_bytes=size_bytes,
            duration_ms=duration_ms,
        )
    except Exception:
        logger.debug("Trace capture failed", tool_name=tool_name, exc_info=True)


# -- paginated / detail-level tools --


def _h_get_validated_commands(
    ctx: Context,
    scope: str = "**",
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
) -> str:
    """Get validated build/test/lint commands with evidence and risk classification."""
    start = time.perf_counter()
    resp = get_validated_commands(
        _ctx_db(ctx),
        scope=scope,
        limit=limit,
        cursor=cursor,
        detail_level=detail_level,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_validated_commands",
        {"scope": scope, "limit": limit},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


def _h_get_conventions(
    ctx: Context,
    path_or_symbol: str = "**",
    include_evidence: bool = False,
    task_context: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
) -> str:
    """Get conventions for a path or symbol with source authority and confidence."""
    start = time.perf_counter()
    resp = get_conventions(
        _ctx_db(ctx),
        path_or_symbol=path_or_symbol,
        include_evidence=include_evidence,
        task_context=task_context,
        limit=limit,
        cursor=cursor,
        detail_level=detail_level,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_conventions",
        {"path_or_symbol": path_or_symbol},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


def _h_get_conflicts(
    ctx: Context,
    path_or_scope: str = "**",
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
) -> str:
    """Get conflict claims where declared and inferred knowledge disagree."""
    start = time.perf_counter()
    resp = get_conflicts(
        _ctx_db(ctx),
        path_or_scope=path_or_scope,
        limit=limit,
        cursor=cursor,
        detail_level=detail_level,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_conflicts",
        {"path_or_scope": path_or_scope},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


def _h_get_guardrails(
    ctx: Context,
    path_or_scope: str = "**",
    host: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
) -> str:
    """Get security guardrails and permission restrictions."""
    start = time.perf_counter()
    resp = get_guardrails(
        _ctx_db(ctx),
        path_or_scope=path_or_scope,
        host=host,
        limit=limit,
        cursor=cursor,
        detail_level=detail_level,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_guardrails",
        {"path_or_scope": path_or_scope, "host": host},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


# -- non-paginated tools --


def _h_get_prerequisites(
    ctx: Context,
    command_or_scope: str | None = None,
) -> str:
    """Get environment prerequisites and profiles for a command or scope."""
    start = time.perf_counter()
    resp = get_prerequisites(
        _ctx_db(ctx),
        command_or_scope=command_or_scope,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_prerequisites",
        {"command_or_scope": command_or_scope},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


def _h_get_module_info(
    ctx: Context,
    path_or_symbol: str,
) -> str:
    """Get module boundary info, dependencies, dependents, and test locations."""
    start = time.perf_counter()
    resp = get_module_info(
        _ctx_db(ctx),
        path_or_symbol=path_or_symbol,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_module_info",
        {"path_or_symbol": path_or_symbol},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


def _h_get_instruction_preview(
    ctx: Context,
    consumer: str = "codex",
) -> str:
    """Preview projected instruction artifacts for a target consumer."""
    start = time.perf_counter()
    resp = get_instruction_preview(
        _ctx_db(ctx),
        consumer=consumer,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_instruction_preview",
        {"consumer": consumer},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


# -- new M7 tools --


def _h_get_repo_overview(ctx: Context) -> str:
    """High-level summary of the repository's structure and RKP's understanding."""
    start = time.perf_counter()
    resp = get_repo_overview(_ctx_db(ctx))
    _traced(ctx, "get_repo_overview", {}, resp, (time.perf_counter() - start) * 1000)
    return _json(resp)


def _h_get_claim(ctx: Context, claim_id: str) -> str:
    """Full detail on a single claim: evidence chain, review history, freshness."""
    start = time.perf_counter()
    resp = get_claim(_ctx_db(ctx), claim_id=claim_id)
    _traced(ctx, "get_claim", {"claim_id": claim_id}, resp, (time.perf_counter() - start) * 1000)
    return _json(resp)


def _h_get_preflight_context(
    ctx: Context,
    path_or_symbol: str,
    task_context: str | None = None,
    host: str | None = None,
    detail_level: str = "terse",
) -> str:
    """Get the minimum actionable bundle an agent needs before starting work."""
    start = time.perf_counter()
    resp = get_preflight_context(
        _ctx_db(ctx),
        path_or_symbol=path_or_symbol,
        task_context=task_context,
        host=host,
        detail_level=detail_level,
        allowlist=_ctx_config(ctx).source_allowlist,
    )
    _traced(
        ctx,
        "get_preflight_context",
        {"path_or_symbol": path_or_symbol},
        resp,
        (time.perf_counter() - start) * 1000,
    )
    return _json(resp)


def _h_refresh_index(
    ctx: Context,
    paths: list[str] | None = None,
) -> str:
    """Trigger incremental re-indexing after file changes."""
    start = time.perf_counter()
    resp = refresh_index(
        _ctx_db(ctx),
        repo_root=_ctx_repo_root(ctx),
        paths=paths,
    )
    _traced(ctx, "refresh_index", {"paths": paths}, resp, (time.perf_counter() - start) * 1000)
    return _json(resp)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

_READONLY = {"readOnlyHint": True}
_READWRITE = {"readOnlyHint": False}

# (handler_fn, tool_name, annotations)
_TOOL_DEFS: list[tuple[Any, str, dict[str, Any]]] = [
    (_h_get_validated_commands, "get_validated_commands", _READONLY),
    (_h_get_conventions, "get_conventions", _READONLY),
    (_h_get_conflicts, "get_conflicts", _READONLY),
    (_h_get_guardrails, "get_guardrails", _READONLY),
    (_h_get_prerequisites, "get_prerequisites", _READONLY),
    (_h_get_module_info, "get_module_info", _READONLY),
    (_h_get_instruction_preview, "get_instruction_preview", _READONLY),
    (_h_get_repo_overview, "get_repo_overview", _READONLY),
    (_h_get_claim, "get_claim", _READONLY),
    (_h_get_preflight_context, "get_preflight_context", _READONLY),
    (_h_refresh_index, "refresh_index", _READWRITE),
]


def _register_tools(server: FastMCP[Any]) -> None:
    """Register all MCP tools on the given server instance."""
    for handler, tool_name, tool_annotations in _TOOL_DEFS:
        server.tool(name=tool_name, annotations=tool_annotations)(handler)


# ---------------------------------------------------------------------------
# Resource registration
# ---------------------------------------------------------------------------


def _register_resources(server: FastMCP[Any]) -> None:
    """Register MCP resources. Thin wrappers around tool logic."""
    from rkp.server.resources import register_resources

    register_resources(server)


# ---------------------------------------------------------------------------
# Server factories
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "repo-knowledge-plane",
    version="0.1.0",
    instructions="Repo Knowledge Plane: verified operational context for this repository.",
    lifespan=app_lifespan,
)
_register_tools(mcp)
_register_resources(mcp)


def create_server(
    *,
    db: sqlite3.Connection | None = None,
    db_path: Path | None = None,
    config: RkpConfig | None = None,
    repo_root: Path | None = None,
) -> FastMCP[Any]:
    """Create an MCP server, optionally with a pre-opened database.

    Used in testing to inject a database connection without file I/O.
    """
    if db is not None:

        @asynccontextmanager
        async def test_lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
            cfg = config or RkpConfig()
            yield {
                "db": db,
                "config": cfg,
                "repo_root": repo_root or Path(),
                "trace_logger": create_trace_logger(
                    repo_root or Path(), enabled=cfg.trace_enabled
                ),
            }

        test_server: FastMCP[Any] = FastMCP(
            "repo-knowledge-plane",
            version="0.1.0",
            instructions="Repo Knowledge Plane: verified operational context.",
            lifespan=test_lifespan,
        )
        _register_tools(test_server)
        _register_resources(test_server)
        return test_server

    return mcp


def create_server_for_path(
    *,
    repo_root: Path,
    db_path: Path,
) -> FastMCP[Any]:
    """Create an MCP server wired to a specific repo path and DB.

    Used by ``rkp serve`` to respect the ``--repo`` flag rather than
    falling back to the module-level singleton's default paths.
    """

    @asynccontextmanager
    async def path_lifespan(server: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
        config = RkpConfig(repo_root=repo_root, db_path=db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = open_database(db_path, check_same_thread=False)
        run_migrations(db)
        logger.info("MCP server database ready", db_path=str(db_path))
        try:
            yield {"db": db, "config": config, "repo_root": repo_root}
        finally:
            db.close()
            logger.info("MCP server database closed")

    server: FastMCP[Any] = FastMCP(
        "repo-knowledge-plane",
        version="0.1.0",
        instructions="Repo Knowledge Plane: verified operational context for this repository.",
        lifespan=path_lifespan,
    )
    _register_tools(server)
    _register_resources(server)
    return server
