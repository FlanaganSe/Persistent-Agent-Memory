"""MCP contract tests: FastMCP in-memory client."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "mcp_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_mcp_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    """DB with some claims for testing."""
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    from dataclasses import replace

    claim1 = builder.build(
        content="pytest",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
    )
    claim1 = replace(claim1, risk_class=RiskClass.TEST_EXECUTION)
    store.save(claim1)

    claim2 = builder.build(
        content="ruff check .",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=0.95,
        evidence=("pyproject.toml",),
    )
    claim2 = replace(claim2, risk_class=RiskClass.SAFE_READONLY)
    store.save(claim2)

    return mcp_db


def _extract_text(result: object) -> str:
    """Extract text from a CallToolResult."""
    # FastMCP returns CallToolResult with .content list of TextContent
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    # Fallback for different API versions
    return str(result)


@pytest.mark.asyncio
async def test_get_validated_commands(populated_mcp_db: sqlite3.Connection) -> None:
    """get_validated_commands returns correct envelope."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands_tool", {"scope": "**"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        assert response["supported"] is True
        assert isinstance(response["data"], list)
        assert len(response["data"]) == 2
        assert "provenance" in response


@pytest.mark.asyncio
async def test_empty_repo_returns_ok(mcp_db: sqlite3.Connection) -> None:
    """Empty repo returns ok with empty data."""
    from fastmcp import Client

    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands_tool", {"scope": "**"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        assert response["data"] == []


@pytest.mark.asyncio
async def test_provenance_fields(populated_mcp_db: sqlite3.Connection) -> None:
    """Provenance fields present on response."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands_tool", {})
        text = _extract_text(result)
        response = json.loads(text)
        provenance = response["provenance"]
        assert "index_version" in provenance
        assert "repo_head" in provenance
        assert "branch" in provenance
        assert "timestamp" in provenance


@pytest.mark.asyncio
async def test_command_fields(populated_mcp_db: sqlite3.Connection) -> None:
    """Each command has expected fields."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands_tool", {})
        text = _extract_text(result)
        response = json.loads(text)
        for cmd in response["data"]:
            assert "id" in cmd
            assert "command" in cmd
            assert "risk_class" in cmd
            assert "evidence_level" in cmd
            assert "source" in cmd
            assert "confidence" in cmd
