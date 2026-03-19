"""MCP contract tests for Copilot: get_instruction_preview, get_guardrails."""

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
    db = open_database(tmp_path / "mcp_copilot_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_mcp_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    """DB with claims for Copilot projection."""
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    # Command claim
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

    # Environment prerequisite
    env = builder.build(
        content="Python 3.12",
        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=(".python-version",),
    )
    store.save(env)

    # Guardrail
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

    # Convention
    conv = builder.build(
        content="Use snake_case for function names",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.95,
        applicability=("all",),
    )
    store.save(conv)

    return mcp_db


@pytest.mark.asyncio
class TestMCPCopilotPreview:
    async def test_instruction_preview_copilot(self, populated_mcp_db: sqlite3.Connection) -> None:
        """get_instruction_preview for 'copilot' returns all artifact types."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "copilot"})
            text = _extract_text(result)
            data = json.loads(text)

            assert data["status"] == "ok"
            files = data["data"]["files"]

            # All 4 artifact types
            assert ".github/copilot-instructions.md" in files
            assert ".github/workflows/copilot-setup-steps.yml" in files
            assert ".copilot-tool-allowlist.json" in files

    async def test_instruction_preview_includes_validation(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_instruction_preview includes setup-steps validation status."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "copilot"})
            text = _extract_text(result)
            data = json.loads(text)

            overflow = data["data"]["overflow_report"]
            assert "setup_steps_validation" in overflow
            assert overflow["setup_steps_validation"]["valid"] is True

    async def test_instruction_preview_includes_provenance(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_instruction_preview includes projection decision provenance."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_instruction_preview", {"consumer": "copilot"})
            text = _extract_text(result)
            data = json.loads(text)

            overflow = data["data"]["overflow_report"]
            assert "decisions" in overflow


@pytest.mark.asyncio
class TestMCPCopilotGuardrails:
    async def test_guardrails_copilot_enforcement(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_guardrails with Copilot context includes correct enforcement metadata."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_guardrails", {"host": "copilot"})
            text = _extract_text(result)
            data = json.loads(text)

            assert data["status"] == "ok"
            items = data["data"]["items"]
            assert len(items) > 0

            # Find the destructive guardrail
            destructive = [i for i in items if "destructive" in i.get("content", "").lower()]
            assert len(destructive) > 0

            item = destructive[0]
            assert "copilot" in item["enforceable_on"]
            assert item["enforcement_mechanism"] == "tool-allowlist"

    async def test_guardrails_default_enforcement(
        self, populated_mcp_db: sqlite3.Connection
    ) -> None:
        """get_guardrails without host shows claude enforcement by default."""
        from fastmcp import Client

        server = create_server(db=populated_mcp_db)
        async with Client(server) as client:
            result = await client.call_tool("get_guardrails", {})
            text = _extract_text(result)
            data = json.loads(text)

            items = data["data"]["items"]
            destructive = [i for i in items if "destructive" in i.get("content", "").lower()]
            assert len(destructive) > 0

            item = destructive[0]
            # Both claude and copilot should be in enforceable_on
            assert "claude" in item["enforceable_on"]
            assert "copilot" in item["enforceable_on"]
            # Default enforcement mechanism (no host specified)
            assert item["enforcement_mechanism"] == "settings.json permissions.deny"
