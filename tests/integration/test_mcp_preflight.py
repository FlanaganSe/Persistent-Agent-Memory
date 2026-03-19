"""get_preflight_context tests — bounded summary bundle."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from fastmcp import Client

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "preflight_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    # Convention
    store.save(
        builder.build(
            content="Use snake_case for function names",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=1.0,
            applicability=("all",),
            evidence=("src/core.py",),
        )
    )

    # Testing-specific convention
    store.save(
        builder.build(
            content="Tests use pytest fixtures",
            claim_type=ClaimType.SCOPED_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.9,
            applicability=("testing",),
            scope="tests/",
            evidence=("tests/conftest.py",),
        )
    )

    # Command
    cmd = builder.build(
        content="pytest",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
    )
    cmd = replace(cmd, risk_class=RiskClass.TEST_EXECUTION)
    store.save(cmd)

    # Guardrail
    store.save(
        builder.build(
            content="Do not run destructive commands without confirmation",
            claim_type=ClaimType.PERMISSION_RESTRICTION,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            applicability=("security",),
            evidence=("Makefile",),
        )
    )

    return mcp_db


@pytest.mark.asyncio
async def test_preflight_returns_bundle(populated_db: sqlite3.Connection) -> None:
    """get_preflight_context returns all expected sections."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_preflight_context", {"path_or_symbol": "src/"})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "ok"
        data = response["data"]
        assert "scoped_rules" in data
        assert "validated_commands" in data
        assert "guardrails" in data
        assert "environment" in data
        assert "unsupported_areas" in data
        assert "warnings" in data


@pytest.mark.asyncio
async def test_preflight_task_context_filtering(
    populated_db: sqlite3.Connection,
) -> None:
    """task_context='testing' filters conventions by applicability."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool(
            "get_preflight_context",
            {"path_or_symbol": "**", "task_context": "testing"},
        )
        text = _extract_text(result)
        response = json.loads(text)
        rules = response["data"]["scoped_rules"]
        # Should include both: "all" applicability + "testing" applicability
        assert len(rules) >= 1


@pytest.mark.asyncio
async def test_preflight_unknown_path(populated_db: sqlite3.Connection) -> None:
    """Unknown path returns available information, not error."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool(
            "get_preflight_context", {"path_or_symbol": "nonexistent/path"}
        )
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        # Still returns ** scoped rules
        data = response["data"]
        assert isinstance(data["scoped_rules"], list)


@pytest.mark.asyncio
async def test_preflight_bounded_response(populated_db: sqlite3.Connection) -> None:
    """Preflight response is bounded (not hundreds of items)."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_preflight_context", {"path_or_symbol": "**"})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]
        # Total items across all sections should be reasonable
        total = (
            len(data["scoped_rules"]) + len(data["validated_commands"]) + len(data["guardrails"])
        )
        assert total < 200  # bounded, not exhaustive


@pytest.mark.asyncio
async def test_preflight_default_terse(populated_db: sqlite3.Connection) -> None:
    """Default detail_level is terse for preflight."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_preflight_context", {"path_or_symbol": "**"})
        text = _extract_text(result)
        response = json.loads(text)
        rules = response["data"]["scoped_rules"]
        if rules:
            # Terse: has content_preview, not full content
            assert "content_preview" in rules[0]
            assert "source_authority" not in rules[0]


@pytest.mark.asyncio
async def test_preflight_empty_db(mcp_db: sqlite3.Connection) -> None:
    """Preflight on empty DB returns ok with empty sections."""
    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_preflight_context", {"path_or_symbol": "src/"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        data = response["data"]
        assert data["scoped_rules"] == []
        assert data["validated_commands"] == []
        assert data["guardrails"] == []
