"""MCP contract tests for M6: get_guardrails, get_instruction_preview."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, ReviewState, RiskClass, SourceAuthority
from rkp.server.mcp import create_server
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "mcp_m6_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_mcp_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    """DB with command + guardrail claims."""
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")

    # Command claims
    cmd = builder.build(
        content="pytest",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
    )
    cmd = replace(cmd, risk_class=RiskClass.TEST_EXECUTION)
    store.save(cmd)

    # Destructive command
    dest_cmd = builder.build(
        content="db:reset",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("Makefile",),
    )
    dest_cmd = replace(dest_cmd, risk_class=RiskClass.DESTRUCTIVE)
    store.save(dest_cmd)

    # Guardrail (restriction) claim
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

    # Advisory guardrail (non-enforceable)
    advisory = builder.build(
        content="CI runs security scan: `npm audit` — ensure changes pass",
        claim_type=ClaimType.PERMISSION_RESTRICTION,
        source_authority=SourceAuthority.CI_OBSERVED,
        confidence=0.9,
        applicability=("security",),
        evidence=(".github/workflows/ci.yml",),
    )
    store.save(advisory)

    # Convention claim
    conv = builder.build(
        content="Use snake_case for function names",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=1.0,
        applicability=("all",),
    )
    store.save(conv)

    hidden = builder.build(
        content="hidden-preview-command",
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("pyproject.toml",),
    )
    store.save(replace(hidden, review_state=ReviewState.SUPPRESSED))

    return mcp_db


def _extract_text(result: object) -> str:
    """Extract text from a CallToolResult."""
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


# --- get_guardrails tests ---


@pytest.mark.asyncio
async def test_get_guardrails_returns_correct_envelope(
    populated_mcp_db: sqlite3.Connection,
) -> None:
    """get_guardrails → correct envelope with enforceable/advisory distinction."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_guardrails", {"path_or_scope": "**"})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "ok"
        items = response["data"]["items"]
        assert isinstance(items, list)
        assert len(items) == 2  # destructive + advisory

        # Check enforceable/advisory distinction
        enforceable = [g for g in items if g["enforceable_on"]]
        advisory = [g for g in items if not g["enforceable_on"]]
        assert len(enforceable) == 1
        assert len(advisory) == 1
        assert "claude" in enforceable[0]["enforceable_on"]
        assert enforceable[0]["enforcement_mechanism"] == "settings.json permissions.deny"
        assert advisory[0]["enforcement_mechanism"] == "advisory text only"


@pytest.mark.asyncio
async def test_get_guardrails_empty_repo(mcp_db: sqlite3.Connection) -> None:
    """get_guardrails with no restrictions → ok, empty data."""
    from fastmcp import Client

    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_guardrails", {"path_or_scope": "**"})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "ok"
        assert response["data"]["items"] == []


@pytest.mark.asyncio
async def test_get_guardrails_scoped(populated_mcp_db: sqlite3.Connection) -> None:
    """get_guardrails scoped to path → correctly filtered."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_guardrails", {"path_or_scope": "src/payments/"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok"
        assert len(response["data"]["items"]) == 2


@pytest.mark.asyncio
async def test_get_guardrails_provenance(populated_mcp_db: sqlite3.Connection) -> None:
    """get_guardrails has provenance in response."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_guardrails", {})
        text = _extract_text(result)
        response = json.loads(text)
        assert "provenance" in response
        assert "timestamp" in response["provenance"]


# --- get_instruction_preview tests ---


@pytest.mark.asyncio
async def test_instruction_preview_claude(populated_mcp_db: sqlite3.Connection) -> None:
    """get_instruction_preview for 'claude' → CLAUDE.md + rules + skills + settings."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_instruction_preview", {"consumer": "claude"})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "ok"
        data = response["data"]
        assert data["consumer"] == "claude"
        assert "files" in data
        assert "CLAUDE.md" in data["files"]
        assert len(data["files"]["CLAUDE.md"]) > 0


@pytest.mark.asyncio
async def test_instruction_preview_codex(populated_mcp_db: sqlite3.Connection) -> None:
    """get_instruction_preview for 'codex' → AGENTS.md (preserved behavior)."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_instruction_preview", {"consumer": "codex"})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "ok"
        data = response["data"]
        assert data["consumer"] == "codex"
        assert "AGENTS.md" in data["files"]
        assert "hidden-preview-command" not in data["files"]["AGENTS.md"]


@pytest.mark.asyncio
async def test_instruction_preview_unsupported_consumer(
    populated_mcp_db: sqlite3.Connection,
) -> None:
    """Unsupported consumer returns unsupported status."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_instruction_preview", {"consumer": "unknown"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "unsupported"
        assert response["supported"] is False
        assert response["unsupported_reason"] is not None


@pytest.mark.asyncio
async def test_instruction_preview_provenance(populated_mcp_db: sqlite3.Connection) -> None:
    """Both tools have provenance in response."""
    from fastmcp import Client

    server = create_server(db=populated_mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_instruction_preview", {"consumer": "claude"})
        text = _extract_text(result)
        response = json.loads(text)
        assert "provenance" in response
        data = response["data"]
        assert "overflow_report" in data
