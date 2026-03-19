"""Pagination tests — cursor-based, no duplicates, no gaps."""

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
    db = open_database(tmp_path / "pagination_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def db_with_many_claims(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    """Create 25 convention claims for pagination testing."""
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")
    for i in range(25):
        claim = builder.build(
            content=f"Convention rule #{i:03d}: use consistent naming",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.9,
            applicability=("all",),
            evidence=(f"src/file_{i}.py",),
        )
        store.save(claim)
    return mcp_db


@pytest.mark.asyncio
async def test_pagination_returns_limited_results(
    db_with_many_claims: sqlite3.Connection,
) -> None:
    """get_conventions(limit=10) returns exactly 10 items + next_cursor."""
    server = create_server(db=db_with_many_claims)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"limit": 10})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]
        assert len(data["items"]) == 10
        assert data["has_more"] is True
        assert data["next_cursor"] is not None
        assert data["total_count"] == 25


@pytest.mark.asyncio
async def test_pagination_follow_cursor_no_duplicates(
    db_with_many_claims: sqlite3.Connection,
) -> None:
    """Following cursors yields all items with no duplicates or gaps."""
    server = create_server(db=db_with_many_claims)
    async with Client(server) as client:
        all_ids: list[str] = []
        cursor = None

        for _ in range(10):  # safety limit
            args: dict = {"limit": 10}
            if cursor is not None:
                args["cursor"] = cursor
            result = await client.call_tool("get_conventions", args)
            text = _extract_text(result)
            response = json.loads(text)
            data = response["data"]

            all_ids.extend(item["id"] for item in data["items"])

            if not data["has_more"]:
                break
            cursor = data["next_cursor"]

        # All 25 items collected
        assert len(all_ids) == 25
        # No duplicates
        assert len(set(all_ids)) == 25


@pytest.mark.asyncio
async def test_pagination_limit_1(db_with_many_claims: sqlite3.Connection) -> None:
    """limit=1 works correctly — returns 1 item per page."""
    server = create_server(db=db_with_many_claims)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"limit": 1})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]
        assert len(data["items"]) == 1
        assert data["has_more"] is True
        assert data["total_count"] == 25


@pytest.mark.asyncio
async def test_pagination_limit_larger_than_total(
    db_with_many_claims: sqlite3.Connection,
) -> None:
    """limit larger than total → all items, has_more=false."""
    server = create_server(db=db_with_many_claims)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"limit": 100})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]
        assert len(data["items"]) == 25
        assert data["has_more"] is False
        assert data["next_cursor"] is None


@pytest.mark.asyncio
async def test_pagination_invalid_cursor(
    db_with_many_claims: sqlite3.Connection,
) -> None:
    """Invalid cursor returns empty results (cursor > all IDs)."""
    server = create_server(db=db_with_many_claims)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"cursor": "zzz-impossible-cursor"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        # All IDs are < "zzz-...", so cursor filter returns 0 items
        assert len(response["data"]["items"]) == 0


@pytest.mark.asyncio
async def test_pagination_on_validated_commands(
    mcp_db: sqlite3.Connection,
) -> None:
    """Pagination works on get_validated_commands too."""
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")
    for i in range(15):
        cmd = builder.build(
            content=f"cmd_{i:02d}",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("Makefile",),
        )
        cmd = replace(cmd, risk_class=RiskClass.SAFE_READONLY)
        store.save(cmd)

    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands", {"limit": 5})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]
        assert len(data["items"]) == 5
        assert data["has_more"] is True
        assert data["total_count"] == 15
