"""get_repo_overview tests."""

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


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "overview_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    store = SqliteClaimStore(mcp_db)
    ev_store = SqliteEvidenceStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    # Convention (Python)
    conv = builder.build(
        content="Use snake_case",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=1.0,
        applicability=("all",),
        evidence=("src/core.py",),
    )
    store.save(conv)
    ev_store.save(
        Evidence(
            claim_id=conv.id,
            file_path="src/core.py",
            file_hash="abc123",
            extraction_version="0.1.0",
            evidence_level=EvidenceLevel.DISCOVERED,
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

    return mcp_db


@pytest.mark.asyncio
async def test_overview_on_empty_db(mcp_db: sqlite3.Connection) -> None:
    """Empty DB returns not_indexed status."""
    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_repo_overview", {})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        data = response["data"]
        assert data["indexing_status"] == "not_indexed"
        assert data["claim_summary"]["total"] == 0


@pytest.mark.asyncio
async def test_overview_on_populated_db(populated_db: sqlite3.Connection) -> None:
    """Populated DB returns complete overview with correct counts."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_repo_overview", {})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        data = response["data"]

        assert data["indexing_status"] == "complete"
        assert data["claim_summary"]["total"] == 2
        assert "always-on-rule" in data["claim_summary"]["by_type"]
        assert "validated-command" in data["claim_summary"]["by_type"]

        # Languages detected from evidence
        assert isinstance(data["languages"], list)

        # Entrypoints from commands
        assert "pytest" in data["build_test_entrypoints"]

        # Support envelope
        assert "supported_languages" in data["support_envelope"]


@pytest.mark.asyncio
async def test_overview_has_full_envelope(populated_db: sqlite3.Connection) -> None:
    """Overview response has complete envelope."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool("get_repo_overview", {})
        text = _extract_text(result)
        response = json.loads(text)
        assert "status" in response
        assert "supported" in response
        assert "unsupported_reason" in response
        assert "warnings" in response
        assert "provenance" in response
