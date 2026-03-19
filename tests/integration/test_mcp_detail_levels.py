"""Detail level tests — terse, normal, detailed rendering."""

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
    db = open_database(tmp_path / "detail_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    claim = builder.build(
        content="Use snake_case for all Python identifiers (95% consistency)",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.95,
        applicability=("all",),
        evidence=("src/core.py", "src/utils.py"),
    )
    store.save(claim)

    cmd = builder.build(
        content="pytest --cov",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
    )
    cmd = replace(cmd, risk_class=RiskClass.TEST_EXECUTION)
    store.save(cmd)

    return mcp_db


@pytest.mark.asyncio
async def test_terse_conventions(populated_db: sqlite3.Connection) -> None:
    """detail_level=terse returns minimal fields, content truncated."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"detail_level": "terse"})
        text = _extract_text(result)
        response = json.loads(text)
        item = response["data"]["items"][0]

        # Terse has these 4 fields
        assert "id" in item
        assert "content_preview" in item
        assert "claim_type" in item
        assert "confidence" in item

        # Terse does NOT have these
        assert "source_authority" not in item
        assert "scope" not in item
        assert "applicability" not in item


@pytest.mark.asyncio
async def test_normal_conventions(populated_db: sqlite3.Connection) -> None:
    """detail_level=normal (default) returns standard claim fields."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {})
        text = _extract_text(result)
        response = json.loads(text)
        item = response["data"]["items"][0]

        assert "id" in item
        assert "content" in item
        assert "claim_type" in item
        assert "source_authority" in item
        assert "confidence" in item
        assert "scope" in item
        assert "applicability" in item
        assert "review_state" in item


@pytest.mark.asyncio
async def test_detailed_conventions(populated_db: sqlite3.Connection) -> None:
    """detail_level=detailed returns all fields including evidence chain."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {"detail_level": "detailed"})
        text = _extract_text(result)
        response = json.loads(text)
        item = response["data"]["items"][0]

        assert "id" in item
        assert "content" in item
        assert "evidence" in item
        assert "stale" in item
        assert "last_validated" in item


@pytest.mark.asyncio
async def test_terse_commands(populated_db: sqlite3.Connection) -> None:
    """Terse commands have minimal fields."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands", {"detail_level": "terse"})
        text = _extract_text(result)
        response = json.loads(text)
        item = response["data"]["items"][0]

        assert "id" in item
        assert "content_preview" in item
        assert "claim_type" in item
        assert "confidence" in item
        # Terse commands should NOT have command-specific fields
        assert "command" not in item
        assert "risk_class" not in item


@pytest.mark.asyncio
async def test_normal_commands(populated_db: sqlite3.Connection) -> None:
    """Normal commands have command-specific fields."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands", {})
        text = _extract_text(result)
        response = json.loads(text)
        item = response["data"]["items"][0]

        assert "command" in item
        assert "risk_class" in item
        assert "evidence_level" in item
        assert "source" in item


@pytest.mark.asyncio
async def test_default_is_normal(populated_db: sqlite3.Connection) -> None:
    """No detail_level param defaults to normal."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_conventions", {})
        text = _extract_text(result)
        response = json.loads(text)
        item = response["data"]["items"][0]
        # Normal has content (not content_preview)
        assert "content" in item
        assert "content_preview" not in item
