"""MCP resource tests — thin wrappers around tool logic."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from fastmcp import Client

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.config import RkpConfig, SourceAllowlist
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "resource_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    store.save(
        builder.build(
            content="Use snake_case",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=1.0,
            applicability=("all",),
            evidence=("src/core.py",),
        )
    )

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
async def test_resource_overview(populated_db: sqlite3.Connection) -> None:
    """rkp://repo/overview returns valid JSON."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.read_resource("rkp://repo/overview")
        text = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        data = json.loads(text)
        assert "indexing_status" in data
        assert "claim_summary" in data


@pytest.mark.asyncio
async def test_resource_conventions(populated_db: sqlite3.Connection) -> None:
    """rkp://repo/conventions returns convention data."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.read_resource("rkp://repo/conventions")
        text = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        data = json.loads(text)
        assert "items" in data
        assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_resource_prerequisites(populated_db: sqlite3.Connection) -> None:
    """rkp://repo/prerequisites returns prerequisite data."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.read_resource("rkp://repo/prerequisites")
        text = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        data = json.loads(text)
        assert "prerequisites" in data
        assert "profiles" in data


@pytest.mark.asyncio
async def test_resource_modules(populated_db: sqlite3.Connection) -> None:
    """rkp://repo/architecture/modules returns module list."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.read_resource("rkp://repo/architecture/modules")
        text = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        data = json.loads(text)
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_resource_conventions_respect_allowlist(populated_db: sqlite3.Connection) -> None:
    """Resources should enforce the same allowlist boundary as tools."""
    config = RkpConfig(
        source_allowlist=SourceAllowlist(
            trusted_evidence_sources=("executable-config",),
        )
    )
    server = create_server(db=populated_db, config=config)
    async with Client(server) as client:
        result = await client.read_resource("rkp://repo/conventions")
        text = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        data = json.loads(text)

        assert data["items"] == []
