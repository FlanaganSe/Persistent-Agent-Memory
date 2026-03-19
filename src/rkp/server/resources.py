"""MCP resource implementations — thin wrappers around tool logic.

Resources are supplementary to tools. Not all hosts support resources
(e.g., Copilot does not), so every resource's data is also accessible
via a tool.
"""

from __future__ import annotations

import json
from typing import Any, cast

from fastmcp import Context, FastMCP

from rkp.server.response_filter import filter_response
from rkp.server.tools import (
    get_conventions,
    get_instruction_preview,
    get_prerequisites,
    get_repo_overview,
)


def _filter_and_serialize(data: Any) -> str:
    """Serialize resource data to JSON with response filtering applied."""
    if isinstance(data, dict):
        typed_data = cast(dict[str, Any], data)
        typed_data, _warnings = filter_response(typed_data, [])
    return json.dumps(data, indent=2)


def register_resources(server: FastMCP[Any]) -> None:
    """Register all MCP resources on the given server."""

    @server.resource("rkp://repo/overview")
    def repo_overview(ctx: Context) -> str:  # pyright: ignore[reportUnusedFunction]
        """Repository overview: languages, modules, indexing status."""
        resp = get_repo_overview(ctx.lifespan_context["db"])
        return _filter_and_serialize(resp.to_dict()["data"])

    @server.resource("rkp://repo/conventions")
    def all_conventions(ctx: Context) -> str:  # pyright: ignore[reportUnusedFunction]
        """All conventions with confidence and evidence."""
        resp = get_conventions(
            ctx.lifespan_context["db"],
            path_or_symbol="**",
            include_evidence=True,
            limit=500,
        )
        return _filter_and_serialize(resp.to_dict()["data"])

    @server.resource("rkp://repo/conventions/{path}")
    def scoped_conventions(ctx: Context, path: str) -> str:  # pyright: ignore[reportUnusedFunction]
        """Path-scoped conventions."""
        resp = get_conventions(
            ctx.lifespan_context["db"],
            path_or_symbol=path,
            include_evidence=True,
            limit=500,
        )
        return _filter_and_serialize(resp.to_dict()["data"])

    @server.resource("rkp://repo/instructions/{consumer}")
    def instructions_preview(ctx: Context, consumer: str) -> str:  # pyright: ignore[reportUnusedFunction]
        """Synthesized instruction content for a target consumer."""
        resp = get_instruction_preview(
            ctx.lifespan_context["db"],
            consumer=consumer,
        )
        return _filter_and_serialize(resp.to_dict()["data"])

    @server.resource("rkp://repo/architecture/modules")
    def module_architecture(ctx: Context) -> str:  # pyright: ignore[reportUnusedFunction]
        """Module and boundary summary with dependency hints."""
        db = ctx.lifespan_context["db"]
        from rkp.graph.repo_graph import SqliteRepoGraph

        try:
            graph = SqliteRepoGraph(db)
            modules = graph.get_modules()
            result = [
                {
                    "module": mod,
                    "dependencies": graph.get_dependencies(mod),
                    "dependents": graph.get_dependents(mod),
                    "test_locations": graph.get_test_locations(mod),
                }
                for mod in modules
            ]
            return _filter_and_serialize(result)
        except Exception:
            return json.dumps([])

    @server.resource("rkp://repo/prerequisites")
    def prerequisites(ctx: Context) -> str:  # pyright: ignore[reportUnusedFunction]
        """Full environment prerequisite summary."""
        resp = get_prerequisites(ctx.lifespan_context["db"])
        return _filter_and_serialize(resp.to_dict()["data"])
