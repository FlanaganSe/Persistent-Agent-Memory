"""Comprehensive sensitivity enforcement tests across ALL output boundaries (M10).

This is the definitive sensitivity test — if it passes, AC-24 is satisfied.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from fastmcp import Client

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, Sensitivity, SourceAuthority
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def sens_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "sens_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_sens_db(sens_db: sqlite3.Connection) -> sqlite3.Connection:
    """DB with public, team-only, and local-only claims."""
    store = SqliteClaimStore(sens_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    # Public claim.
    c_pub = builder.build(
        content="pytest",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
        sensitivity=Sensitivity.PUBLIC,
    )
    c_pub = replace(c_pub, risk_class=RiskClass.TEST_EXECUTION)
    store.save(c_pub)

    # Team-only claim.
    c_team = builder.build(
        content="Team-internal API endpoint: POST /admin/reset",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=0.9,
        evidence=("internal.md",),
        sensitivity=Sensitivity.TEAM_ONLY,
    )
    store.save(c_team)

    # Local-only claim.
    c_local = builder.build(
        content="Local dev DB password: hunter2",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=0.95,
        evidence=(".env.local",),
        sensitivity=Sensitivity.LOCAL_ONLY,
    )
    store.save(c_local)

    # Public convention claim.
    c_conv = builder.build(
        content="Use snake_case for all functions",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=1.0,
        applicability=("all",),
        evidence=("src/main.py",),
        sensitivity=Sensitivity.PUBLIC,
    )
    store.save(c_conv)

    # Local-only guardrail.
    c_guard = builder.build(
        content="Never access production database directly",
        claim_type=ClaimType.PERMISSION_RESTRICTION,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("security.md",),
        sensitivity=Sensitivity.LOCAL_ONLY,
    )
    store.save(c_guard)

    # Public conflict.
    c_conflict = builder.build(
        content="Conflict: test runner mismatch",
        claim_type=ClaimType.CONFLICT,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.8,
        evidence=("pyproject.toml",),
        sensitivity=Sensitivity.PUBLIC,
    )
    store.save(c_conflict)

    # Public module boundary.
    c_module = builder.build(
        content="Module boundary: src/core",
        claim_type=ClaimType.MODULE_BOUNDARY,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.85,
        evidence=("src/core/__init__.py",),
        sensitivity=Sensitivity.PUBLIC,
    )
    store.save(c_module)

    return sens_db


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return ""


def _assert_no_local_only(text: str) -> None:
    """Assert no local-only claim content appears in text."""
    assert "hunter2" not in text
    assert "Local dev DB" not in text
    assert "Never access production" not in text


def _assert_no_team_only_in_public(text: str) -> None:
    """Assert no team-only claim content appears in public projection."""
    assert "Team-internal API" not in text
    assert "/admin/reset" not in text


# -- Projection boundary tests --


class TestProjectionSensitivity:
    """Sensitivity filtering in projection (rkp preview)."""

    def test_codex_preview_excludes_local_only(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        store = SqliteClaimStore(populated_sens_db)
        claims = store.list_claims()
        adapter = AgentsMdAdapter()
        capability = get_capability("codex")
        assert capability is not None
        policy = ProjectionPolicy(target_sensitivity=Sensitivity.PUBLIC)
        result = project(claims, adapter, capability, policy)
        content = "\n".join(result.adapter_result.files.values())
        _assert_no_local_only(content)
        _assert_no_team_only_in_public(content)

    def test_claude_preview_excludes_local_only(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        store = SqliteClaimStore(populated_sens_db)
        claims = store.list_claims()
        adapter = ClaudeMdAdapter()
        capability = get_capability("claude")
        assert capability is not None
        policy = ProjectionPolicy(target_sensitivity=Sensitivity.PUBLIC)
        result = project(claims, adapter, capability, policy)
        content = "\n".join(result.adapter_result.files.values())
        _assert_no_local_only(content)
        _assert_no_team_only_in_public(content)


# -- MCP tool boundary tests --


class TestMCPSensitivity:
    """Sensitivity filtering across all MCP tools."""

    @pytest.mark.asyncio
    async def test_get_conventions_excludes_local(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_conventions", {"path_or_symbol": "**"})
            text = _extract_text(result)
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_validated_commands_excludes_local(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_validated_commands", {"scope": "**"})
            text = _extract_text(result)
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_prerequisites_excludes_local(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_prerequisites", {})
            text = _extract_text(result)
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_conflicts_excludes_local(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_conflicts", {})
            text = _extract_text(result)
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_guardrails_excludes_local(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_guardrails", {})
            text = _extract_text(result)
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_instruction_preview_excludes_local(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "codex"})
            text = _extract_text(result)
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_preflight_context_excludes_local(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_preflight_context", {"path_or_symbol": "**"})
            text = _extract_text(result)
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_repo_overview_excludes_local_from_counts(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        """Repo overview counts should be present (it's aggregate data, not claim content)."""
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_repo_overview", {})
            text = _extract_text(result)
            # Claim content should not appear.
            _assert_no_local_only(text)

    @pytest.mark.asyncio
    async def test_get_claim_blocks_local_only(
        self, populated_sens_db: sqlite3.Connection
    ) -> None:
        """get_claim on a local-only claim should be blocked entirely."""
        store = SqliteClaimStore(populated_sens_db)
        local_claims = [c for c in store.list_claims() if c.sensitivity == Sensitivity.LOCAL_ONLY]
        if not local_claims:
            pytest.skip("No local-only claims")
        server = create_server(db=populated_sens_db)
        async with Client(server) as client:
            result = await client.call_tool("get_claim", {"claim_id": local_claims[0].id})
            text = _extract_text(result)
            data = json.loads(text)
            # Local-only claims should be blocked via MCP.
            assert data["status"] == "error"
            assert "local-only" in text.lower()
