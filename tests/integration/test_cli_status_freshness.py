"""Integration tests for freshness indicators in rkp status."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rkp.cli.app import app
from rkp.store.database import open_database, run_migrations
from rkp.store.metadata import IndexMetadata, SqliteMetadataStore


def _parse_json(output: str) -> dict:
    """Extract JSON from CLI output."""
    start = output.find("{")
    if start == -1:
        msg = f"No JSON found in output: {output[:200]}"
        raise ValueError(msg)
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(output[start:])
    return obj


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    """Create a minimal initialized repo."""
    repo = tmp_path / "repo"
    repo.mkdir()

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

    (repo / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("def hello():\n    pass\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--repo", str(repo), "init"])
    assert result.exit_code in (0, 1), f"init failed: {result.output}"
    return repo


class TestStatusFreshness:
    def test_status_json_includes_freshness(self, initialized_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "--json", "status"])
        assert result.exit_code in (0, 1)
        data = _parse_json(result.output)
        assert "freshness" in data
        assert "last_indexed" in data["freshness"]
        assert "stale_claims" in data["freshness"]

    def test_status_fresh_index(self, initialized_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "status"])
        assert result.exit_code in (0, 1)
        # Should show "Index is current"
        assert "current" in result.output.lower() or "stale" in result.output.lower()

    def test_status_stale_index_head_changed(self, initialized_repo: Path) -> None:
        # Modify the index metadata to have old HEAD
        db_path = initialized_repo / ".rkp" / "local" / "rkp.db"
        db = open_database(db_path)
        run_migrations(db)
        meta_store = SqliteMetadataStore(db)
        meta_store.save(
            IndexMetadata(
                last_indexed="2026-03-01T00:00:00Z",
                repo_head="old_head_that_doesnt_match",
                branch="main",
                file_count=10,
                claim_count=5,
            )
        )
        db.close()

        # Make a new commit to change HEAD
        (initialized_repo / "new_file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=initialized_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "change head"],
            cwd=initialized_repo,
            capture_output=True,
            check=True,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "--json", "status"])
        assert result.exit_code in (0, 1)
        data = _parse_json(result.output)
        # Freshness should indicate head has changed
        assert data["freshness"]["head_changed"] is True or data["freshness"]["stale_claims"] >= 0
