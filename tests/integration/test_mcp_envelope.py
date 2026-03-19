"""Response envelope consistency tests — parameterized across ALL tools.

Verifies AC-13 (provenance on every response) and AC-3 (all tools respond).
"""

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

# All registered MCP tools and their minimal arguments
_TOOL_ARGS: list[tuple[str, dict]] = [
    ("get_validated_commands", {}),
    ("get_conventions", {"path_or_symbol": "**"}),
    ("get_prerequisites", {}),
    ("get_module_info", {"path_or_symbol": "nonexistent"}),
    ("get_conflicts", {}),
    ("get_guardrails", {}),
    ("get_instruction_preview", {"consumer": "codex"}),
    ("get_repo_overview", {}),
    ("get_claim", {"claim_id": "claim-does-not-exist"}),
    ("get_preflight_context", {"path_or_symbol": "src/"}),
]


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "envelope_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def populated_db(mcp_db: sqlite3.Connection) -> sqlite3.Connection:
    store = SqliteClaimStore(mcp_db)
    builder = ClaimBuilder(repo_id="test-repo", branch="main")
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


# --- Parameterized envelope tests ---


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,args", _TOOL_ARGS, ids=[t[0] for t in _TOOL_ARGS])
async def test_envelope_has_all_fields(
    populated_db: sqlite3.Connection, tool_name: str, args: dict
) -> None:
    """Every tool response has status, supported, unsupported_reason, data, warnings, provenance."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool(tool_name, args)
        text = _extract_text(result)
        response = json.loads(text)

        assert "status" in response, f"{tool_name}: missing 'status'"
        assert "supported" in response, f"{tool_name}: missing 'supported'"
        assert "unsupported_reason" in response, f"{tool_name}: missing 'unsupported_reason'"
        assert "data" in response, f"{tool_name}: missing 'data'"
        assert "warnings" in response, f"{tool_name}: missing 'warnings'"
        assert "provenance" in response, f"{tool_name}: missing 'provenance'"

        # Warnings is always a list
        assert isinstance(response["warnings"], list), f"{tool_name}: warnings not a list"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,args", _TOOL_ARGS, ids=[t[0] for t in _TOOL_ARGS])
async def test_provenance_has_all_fields(
    populated_db: sqlite3.Connection, tool_name: str, args: dict
) -> None:
    """Provenance always has index_version, repo_head, branch, timestamp."""
    server = create_server(db=populated_db)
    async with Client(server) as client:
        result = await client.call_tool(tool_name, args)
        text = _extract_text(result)
        response = json.loads(text)
        prov = response["provenance"]

        assert "index_version" in prov, f"{tool_name}: missing index_version"
        assert "repo_head" in prov, f"{tool_name}: missing repo_head"
        assert "branch" in prov, f"{tool_name}: missing branch"
        assert "timestamp" in prov, f"{tool_name}: missing timestamp"


# --- Empty DB tests ---

_TOOLS_EMPTY_OK: list[tuple[str, dict]] = [
    ("get_validated_commands", {}),
    ("get_conventions", {"path_or_symbol": "**"}),
    ("get_prerequisites", {}),
    ("get_conflicts", {}),
    ("get_guardrails", {}),
    ("get_repo_overview", {}),
    ("get_preflight_context", {"path_or_symbol": "src/"}),
    ("get_module_info", {"path_or_symbol": "anything"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,args", _TOOLS_EMPTY_OK, ids=[t[0] for t in _TOOLS_EMPTY_OK])
async def test_empty_db_returns_ok(mcp_db: sqlite3.Connection, tool_name: str, args: dict) -> None:
    """Empty DB returns status ok (not error) for read tools."""
    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool(tool_name, args)
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "ok", (
            f"{tool_name}: expected ok on empty DB, got {response['status']}"
        )


@pytest.mark.asyncio
async def test_get_claim_not_found(mcp_db: sqlite3.Connection) -> None:
    """get_claim with unknown ID returns error status."""
    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_claim", {"claim_id": "claim-nonexistent"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "error"


@pytest.mark.asyncio
async def test_instruction_preview_unsupported(mcp_db: sqlite3.Connection) -> None:
    """get_instruction_preview for unknown consumer returns unsupported."""
    server = create_server(db=mcp_db)
    async with Client(server) as client:
        result = await client.call_tool("get_instruction_preview", {"consumer": "unknown_host"})
        text = _extract_text(result)
        response = json.loads(text)
        assert response["status"] == "unsupported"
        assert response["supported"] is False
        assert response["unsupported_reason"] is not None
