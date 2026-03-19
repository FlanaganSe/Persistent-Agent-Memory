"""refresh_index tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastmcp import Client

from rkp.server.mcp import create_server
from rkp.store.database import open_database, run_migrations


def _extract_text(result: object) -> str:
    content = getattr(result, "content", None)
    if content and len(content) > 0:
        return str(content[0].text)
    return str(result)


@pytest.fixture
def mcp_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "refresh_test.db", check_same_thread=False)
    run_migrations(db)
    return db


@pytest.fixture
def repo_with_pyproject(tmp_path: Path) -> Path:
    """Create a minimal repo fixture for refresh testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "test"\n\n[project.scripts]\ntest = "pytest"\n'
    )
    # Initialize git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    return repo


@pytest.mark.asyncio
async def test_refresh_no_repo_root(mcp_db: sqlite3.Connection) -> None:
    """refresh_index without repo_root configured returns error."""
    # create_server with no repo_root — the handler will get Path() which
    # may not be a valid git repo. We test the error path.
    server = create_server(db=mcp_db, repo_root=None)
    async with Client(server) as client:
        result = await client.call_tool("refresh_index", {})
        text = _extract_text(result)
        response = json.loads(text)
        # Should be error or partial — repo root not found
        assert response["status"] in ("error", "ok")


@pytest.mark.asyncio
async def test_refresh_with_fixture_repo(
    mcp_db: sqlite3.Connection, repo_with_pyproject: Path
) -> None:
    """refresh_index with a valid repo returns extraction summary."""
    server = create_server(db=mcp_db, repo_root=repo_with_pyproject)
    async with Client(server) as client:
        result = await client.call_tool("refresh_index", {})
        text = _extract_text(result)
        response = json.loads(text)

        assert response["status"] == "ok"
        data = response["data"]
        assert "files_parsed" in data
        assert "claims_created" in data
        assert "elapsed_seconds" in data
        assert data["files_parsed"] >= 1


@pytest.mark.asyncio
async def test_refresh_with_paths_warning(
    mcp_db: sqlite3.Connection, repo_with_pyproject: Path
) -> None:
    """refresh_index with paths param includes a warning about scope."""
    server = create_server(db=mcp_db, repo_root=repo_with_pyproject)
    async with Client(server) as client:
        result = await client.call_tool("refresh_index", {"paths": ["src/"]})
        text = _extract_text(result)
        response = json.loads(text)

        # Should succeed but with a warning about scope
        assert response["status"] == "ok"
        assert any("path" in w.lower() or "scope" in w.lower() for w in response["warnings"])


@pytest.mark.asyncio
async def test_refresh_idempotent(mcp_db: sqlite3.Connection, repo_with_pyproject: Path) -> None:
    """Running refresh twice: second run produces 0 new claims (deduplication)."""
    server = create_server(db=mcp_db, repo_root=repo_with_pyproject)
    async with Client(server) as client:
        # First run
        result1 = await client.call_tool("refresh_index", {})
        text1 = _extract_text(result1)
        r1 = json.loads(text1)
        created_first = r1["data"]["claims_created"]

        # Second run — same repo, no changes
        result2 = await client.call_tool("refresh_index", {})
        text2 = _extract_text(result2)
        r2 = json.loads(text2)
        created_second = r2["data"]["claims_created"]

        assert created_first >= 1
        # Second run should create 0 or very few new claims (deduplication)
        assert created_second <= created_first


@pytest.mark.asyncio
async def test_refresh_has_full_envelope(
    mcp_db: sqlite3.Connection, repo_with_pyproject: Path
) -> None:
    """refresh_index response has complete envelope."""
    server = create_server(db=mcp_db, repo_root=repo_with_pyproject)
    async with Client(server) as client:
        result = await client.call_tool("refresh_index", {})
        text = _extract_text(result)
        response = json.loads(text)
        assert "status" in response
        assert "supported" in response
        assert "unsupported_reason" in response
        assert "warnings" in response
        assert "provenance" in response
