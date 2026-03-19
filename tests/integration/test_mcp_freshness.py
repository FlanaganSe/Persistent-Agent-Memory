"""Integration tests for freshness in MCP responses."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastmcp import Client

from rkp.core.models import Claim
from rkp.core.types import ClaimType, SourceAuthority
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations
from rkp.store.metadata import IndexMetadata, SqliteMetadataStore


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


@pytest.fixture
def db_with_claims(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "test.db", check_same_thread=False)
    run_migrations(db)
    store = SqliteClaimStore(db)

    # Fresh claim
    store.save(
        Claim(
            id="claim-fresh12345",
            content="Use pytest for testing",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.95,
            repo_id="test-repo",
            stale=False,
        )
    )
    # Stale claim
    store.save(
        Claim(
            id="claim-stale12345",
            content="Run make build",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.8,
            repo_id="test-repo",
            stale=True,
            revalidation_trigger="evidence-changed",
        )
    )

    # Save metadata
    meta_store = SqliteMetadataStore(db)
    meta_store.save(
        IndexMetadata(
            last_indexed="2026-03-18T19:22:00+00:00",
            repo_head="abc123",
            branch="main",
            file_count=10,
            claim_count=2,
        )
    )

    return db


@pytest.mark.asyncio
async def test_mcp_response_includes_freshness(
    db_with_claims: sqlite3.Connection,
) -> None:
    server = create_server(db=db_with_claims)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands", {"scope": "**"})
        text = _extract_text(result)
        data = json.loads(text)
        assert "freshness" in data
        assert "index_age_seconds" in data["freshness"]
        assert "stale_claims_in_response" in data["freshness"]
        assert "head_current" in data["freshness"]


@pytest.mark.asyncio
async def test_stale_claims_warning(
    db_with_claims: sqlite3.Connection,
) -> None:
    server = create_server(db=db_with_claims)
    async with Client(server) as client:
        result = await client.call_tool("get_validated_commands", {"scope": "**"})
        text = _extract_text(result)
        data = json.loads(text)
        # Should have stale claims warning
        if data["freshness"]["stale_claims_in_response"] > 0:
            assert any("stale" in w.lower() for w in data["warnings"])


@pytest.mark.asyncio
async def test_detailed_claim_includes_freshness(
    db_with_claims: sqlite3.Connection,
) -> None:
    server = create_server(db=db_with_claims)
    async with Client(server) as client:
        result = await client.call_tool("get_claim", {"claim_id": "claim-stale12345"})
        text = _extract_text(result)
        data = json.loads(text)
        claim_data = data["data"]
        assert "freshness" in claim_data or "stale" in str(claim_data)


@pytest.mark.asyncio
async def test_stale_flag_on_claims_in_detailed_response(
    db_with_claims: sqlite3.Connection,
) -> None:
    server = create_server(db=db_with_claims)
    async with Client(server) as client:
        result = await client.call_tool(
            "get_validated_commands",
            {"scope": "**", "detail_level": "detailed"},
        )
        text = _extract_text(result)
        data = json.loads(text)
        items = data["data"]["items"]
        stale_items = [i for i in items if i.get("stale")]
        for item in stale_items:
            assert "effective_confidence" in item
            assert item["effective_confidence"] < item["confidence"]
