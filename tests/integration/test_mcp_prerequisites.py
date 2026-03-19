"""MCP contract tests for get_prerequisites_tool."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastmcp import Client

from rkp.server.mcp import create_server
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "mcp_prereq_test.db", check_same_thread=False)
    run_migrations(db)
    return db


def _extract_text(result: object) -> str:
    """Extract text from a CallToolResult."""
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


class TestGetPrerequisites:
    @pytest.mark.asyncio
    async def test_get_prerequisites_empty(self, mcp_db: sqlite3.Connection) -> None:
        """Returns empty prerequisites and profiles on a fresh DB."""
        server = create_server(db=mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_prerequisites_tool", {})
            text = _extract_text(result)
            data = json.loads(text)
            assert data["status"] == "ok"
            assert data["data"]["prerequisites"] == []
            assert data["data"]["profiles"] == []
            assert "provenance" in data

    @pytest.mark.asyncio
    async def test_response_envelope(self, mcp_db: sqlite3.Connection) -> None:
        """Response has correct envelope structure."""
        server = create_server(db=mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_prerequisites_tool", {})
            text = _extract_text(result)
            data = json.loads(text)
            assert "status" in data
            assert "supported" in data
            assert "data" in data
            assert "provenance" in data
            # Provenance has expected fields
            provenance = data["provenance"]
            assert "index_version" in provenance
            assert "repo_head" in provenance
            assert "branch" in provenance
            assert "timestamp" in provenance

    @pytest.mark.asyncio
    async def test_data_structure(self, mcp_db: sqlite3.Connection) -> None:
        """Data contains prerequisites list and profiles list."""
        server = create_server(db=mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_prerequisites_tool", {})
            text = _extract_text(result)
            data = json.loads(text)
            inner = data["data"]
            assert isinstance(inner["prerequisites"], list)
            assert isinstance(inner["profiles"], list)
