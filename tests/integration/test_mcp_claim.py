"""get_claim tests — single claim detail with evidence chain and history."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from fastmcp import Client

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Evidence
from rkp.core.types import ClaimType, EvidenceLevel, RiskClass, SourceAuthority
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations
from rkp.store.evidence import SqliteEvidenceStore
from rkp.store.history import SqliteHistoryStore


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "claim_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_db(mcp_db: sqlite3.Connection) -> tuple[sqlite3.Connection, str]:
    """Returns (db, claim_id) with evidence and history."""
    store = SqliteClaimStore(mcp_db)
    ev_store = SqliteEvidenceStore(mcp_db)
    hist_store = SqliteHistoryStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    claim = builder.build(
        content="Use pytest for all tests",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
    )
    claim = replace(claim, risk_class=RiskClass.TEST_EXECUTION)
    store.save(claim)

    # Add evidence record
    ev_store.save(
        Evidence(
            claim_id=claim.id,
            file_path="pyproject.toml",
            file_hash="sha256abc",
            extraction_version="0.1.0",
            line_start=10,
            line_end=15,
            evidence_level=EvidenceLevel.DISCOVERED,
        )
    )

    # Add history record
    hist_store.record(
        claim_id=claim.id,
        action="created",
        content_after=claim.content,
        actor="system",
        reason="Initial extraction",
    )

    return mcp_db, claim.id


@pytest.mark.asyncio
async def test_get_claim_found(populated_db: tuple[sqlite3.Connection, str]) -> None:
    """Known claim_id returns full detail."""
    db, claim_id = populated_db
    server = create_server(db=db)
    async with Client(server) as client:
        result = await client.call_tool("get_claim", {"claim_id": claim_id})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "ok"
        data = response["data"]
        assert data["id"] == claim_id
        assert data["content"] == "Use pytest for all tests"
        assert data["claim_type"] == "validated-command"


@pytest.mark.asyncio
async def test_get_claim_evidence_chain(
    populated_db: tuple[sqlite3.Connection, str],
) -> None:
    """Claim response includes evidence chain."""
    db, claim_id = populated_db
    server = create_server(db=db)
    async with Client(server) as client:
        result = await client.call_tool("get_claim", {"claim_id": claim_id})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]

        assert "evidence_chain" in data
        assert len(data["evidence_chain"]) == 1
        ev = data["evidence_chain"][0]
        assert ev["file_path"] == "pyproject.toml"
        assert ev["extraction_version"] == "0.1.0"
        assert ev["line_start"] == 10
        assert ev["line_end"] == 15
        assert ev["evidence_level"] == "discovered"


@pytest.mark.asyncio
async def test_get_claim_review_history(
    populated_db: tuple[sqlite3.Connection, str],
) -> None:
    """Claim response includes review history."""
    db, claim_id = populated_db
    server = create_server(db=db)
    async with Client(server) as client:
        result = await client.call_tool("get_claim", {"claim_id": claim_id})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]

        assert "review_history" in data
        assert len(data["review_history"]) == 1
        hist = data["review_history"][0]
        assert hist["action"] == "created"
        assert hist["actor"] == "system"


@pytest.mark.asyncio
async def test_get_claim_freshness(
    populated_db: tuple[sqlite3.Connection, str],
) -> None:
    """Claim response includes freshness assessment."""
    db, claim_id = populated_db
    server = create_server(db=db)
    async with Client(server) as client:
        result = await client.call_tool("get_claim", {"claim_id": claim_id})
        text = _extract_text(result)
        response = json.loads(text)
        data = response["data"]

        assert "freshness" in data
        assert "stale" in data["freshness"]
        assert "last_validated" in data["freshness"]


@pytest.mark.asyncio
async def test_get_claim_not_found(mcp_db: sqlite3.Connection) -> None:
    """Unknown claim_id returns error status."""
    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_claim", {"claim_id": "claim-nonexistent"})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "error"
        assert "Claim not found" in response["data"]["error"]
