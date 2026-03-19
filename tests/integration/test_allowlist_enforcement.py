"""Source allowlist end-to-end enforcement tests (M10).

Validates that allowlists filter claims at extraction, MCP, and projection.
"""

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
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.server.mcp import create_server
from rkp.server.tools import enforce_allowlist
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def allowlist_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "allowlist_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_allowlist_db(allowlist_db: sqlite3.Connection) -> sqlite3.Connection:
    """DB with claims from various source authorities and directories."""
    store = SqliteClaimStore(allowlist_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    # Claim from executable-config (src/).
    c1 = builder.build(
        content="pytest",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
    )
    c1 = replace(c1, risk_class=RiskClass.TEST_EXECUTION)
    store.save(c1)

    # Claim from inferred-high (src/).
    c2 = builder.build(
        content="Use snake_case",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.95,
        evidence=("src/main.py",),
        applicability=("all",),
    )
    store.save(c2)

    # Claim from vendor/ directory.
    c3 = builder.build(
        content="vendor convention: use tabs",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_LOW,
        confidence=0.6,
        evidence=("vendor/lib/style.py",),
        applicability=("all",),
    )
    store.save(c3)

    # Claim from checked-in-docs.
    c4 = builder.build(
        content="Install Node 20",
        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
        source_authority=SourceAuthority.CHECKED_IN_DOCS,
        confidence=0.7,
        evidence=("README.md",),
        applicability=("all",),
    )
    store.save(c4)

    return allowlist_db


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return ""


class TestEnforceAllowlistDirect:
    """Direct unit tests for enforce_allowlist()."""

    def test_default_config_passes_everything(
        self, populated_allowlist_db: sqlite3.Connection
    ) -> None:
        store = SqliteClaimStore(populated_allowlist_db)
        claims = store.list_claims()
        filtered = enforce_allowlist(claims, SourceAllowlist())
        assert len(filtered) == len(claims)

    def test_none_allowlist_passes_everything(
        self, populated_allowlist_db: sqlite3.Connection
    ) -> None:
        store = SqliteClaimStore(populated_allowlist_db)
        claims = store.list_claims()
        filtered = enforce_allowlist(claims, None)
        assert len(filtered) == len(claims)

    def test_exclude_vendor_directory(self, populated_allowlist_db: sqlite3.Connection) -> None:
        store = SqliteClaimStore(populated_allowlist_db)
        claims = store.list_claims()
        allowlist = SourceAllowlist(allowed_directories=("src/**", "*.toml", "*.md"))
        filtered = enforce_allowlist(claims, allowlist)
        # vendor/ claim should be excluded.
        assert not any("vendor" in str(c.evidence) for c in filtered)
        assert len(filtered) < len(claims)

    def test_restrict_to_executable_config_only(
        self, populated_allowlist_db: sqlite3.Connection
    ) -> None:
        store = SqliteClaimStore(populated_allowlist_db)
        claims = store.list_claims()
        allowlist = SourceAllowlist(
            trusted_evidence_sources=("executable-config",),
        )
        filtered = enforce_allowlist(claims, allowlist)
        assert all(c.source_authority == SourceAuthority.EXECUTABLE_CONFIG for c in filtered)


class TestAllowlistViaMCP:
    """Allowlist enforcement through MCP tool calls."""

    @pytest.mark.asyncio
    async def test_custom_allowlist_filters_conventions(
        self, populated_allowlist_db: sqlite3.Connection
    ) -> None:
        config = RkpConfig(
            source_allowlist=SourceAllowlist(
                trusted_evidence_sources=("executable-config",),
            )
        )
        server = create_server(db=populated_allowlist_db, config=config)
        async with Client(server) as client:
            result = await client.call_tool("get_conventions", {"path_or_symbol": "**"})
            text = _extract_text(result)
            data = json.loads(text)
            # Only executable-config claims should appear.
            items = data["data"]["items"]
            for item in items:
                assert item["source_authority"] == "executable-config"

    @pytest.mark.asyncio
    async def test_default_allowlist_returns_all(
        self, populated_allowlist_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_allowlist_db)
        async with Client(server) as client:
            result = await client.call_tool("get_conventions", {"path_or_symbol": "**"})
            text = _extract_text(result)
            data = json.loads(text)
            items = data["data"]["items"]
            assert len(items) >= 2  # Should have multiple authorities.


class TestAllowlistInProjection:
    """Allowlist enforcement in projection output."""

    def test_projection_with_restricted_allowlist(
        self, populated_allowlist_db: sqlite3.Connection
    ) -> None:
        store = SqliteClaimStore(populated_allowlist_db)
        claims = store.list_claims()

        # Filter before projection (as tools.py does).
        allowlist = SourceAllowlist(
            trusted_evidence_sources=("executable-config",),
        )
        filtered = enforce_allowlist(claims, allowlist)

        adapter = AgentsMdAdapter()
        capability = get_capability("codex")
        assert capability is not None
        policy = ProjectionPolicy()
        result = project(filtered, adapter, capability, policy)
        content = "\n".join(result.adapter_result.files.values())
        # Inferred claims should not appear.
        assert "Use snake_case" not in content
        assert "vendor convention" not in content
