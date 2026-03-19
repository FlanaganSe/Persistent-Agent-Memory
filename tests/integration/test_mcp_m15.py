"""MCP contract tests for cursor/windsurf preview."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


def _extract_text(result: object) -> str:
    """Extract text from a CallToolResult."""
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "mcp_m15_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_mcp_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    """DB with claims suitable for cursor/windsurf projection."""
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    cmd = replace(
        builder.build(
            content="pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("pyproject.toml",),
        ),
        risk_class=RiskClass.TEST_EXECUTION,
    )
    store.save(cmd)

    conv = builder.build(
        content="Use snake_case for function names",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.95,
        applicability=("all",),
    )
    store.save(conv)

    guardrail = builder.build(
        content="Command `db:reset` is classified as destructive "
        "— require explicit confirmation before running",
        claim_type=ClaimType.PERMISSION_RESTRICTION,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        applicability=("destructive", "security"),
        evidence=("Makefile",),
    )
    store.save(guardrail)

    return mcp_db


@pytest.mark.asyncio
class TestMCPCursorPreview:
    async def test_instruction_preview_cursor_returns_files(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_instruction_preview for 'cursor' returns .cursor/rules/ files."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "cursor"})
            text = _extract_text(result)
            data = json.loads(text)

            assert data["status"] == "ok"
            files = data["data"]["files"]
            assert any(k.startswith(".cursor/rules/") for k in files)

    async def test_instruction_preview_cursor_has_provenance(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_instruction_preview for 'cursor' includes provenance decisions."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "cursor"})
            text = _extract_text(result)
            data = json.loads(text)

            overflow = data["data"]["overflow_report"]
            assert "decisions" in overflow


@pytest.mark.asyncio
class TestMCPWindsurfPreview:
    async def test_instruction_preview_windsurf_returns_files(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_instruction_preview for 'windsurf' returns .windsurf/rules/ files."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "windsurf"})
            text = _extract_text(result)
            data = json.loads(text)

            assert data["status"] == "ok"
            files = data["data"]["files"]
            assert any(k.startswith(".windsurf/rules/") for k in files)

    async def test_instruction_preview_windsurf_has_budget(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_instruction_preview for 'windsurf' includes budget usage."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "windsurf"})
            text = _extract_text(result)
            data = json.loads(text)

            overflow = data["data"]["overflow_report"]
            assert "windsurf_budget" in overflow
            budget = overflow["windsurf_budget"]
            assert "workspace_used" in budget
            assert "workspace_limit" in budget
            assert budget["workspace_used"] <= budget["workspace_limit"]

    async def test_instruction_preview_windsurf_has_provenance(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_instruction_preview for 'windsurf' includes provenance decisions."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "windsurf"})
            text = _extract_text(result)
            data = json.loads(text)

            overflow = data["data"]["overflow_report"]
            assert "decisions" in overflow
