"""Integration tests for rkp refresh command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rkp.cli.app import app
from rkp.store.database import open_database, run_migrations
from rkp.store.metadata import SqliteMetadataStore


def _parse_json(output: str) -> dict:
    """Extract JSON object from CLI output (may include log lines on stderr)."""
    # Find the start of the JSON object (first '{' at beginning of a line or in output)
    start = output.find("{")
    if start == -1:
        msg = f"No JSON found in output: {output[:200]}"
        raise ValueError(msg)
    # Parse from there — json.loads is tolerant of trailing content via raw_decode
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(output[start:])
    return obj


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    """Create a minimal initialized repo."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Init git
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

    # Create a pyproject.toml
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "test"\nversion = "0.1.0"\n\n'
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"
    )
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("def hello():\n    return 'hello'\n")

    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    # Run rkp init
    runner = CliRunner()
    result = runner.invoke(app, ["--repo", str(repo), "init"])
    assert result.exit_code in (0, 1), f"init failed: {result.output}"

    return repo


class TestRefreshCommand:
    def test_refresh_on_unchanged_repo(self, initialized_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "refresh"])
        # Exit 0 = no changes, exit 1 = changes found (fresh extraction creates dups)
        assert result.exit_code in (0, 1), f"refresh failed: {result.output}"

    def test_refresh_json_output(self, initialized_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "--json", "refresh"])
        assert result.exit_code in (0, 1)
        data = _parse_json(result.output)
        assert "status" in data
        assert "files_analyzed" in data
        assert "new_claims" in data
        assert "stale_claims" in data

    def test_refresh_dry_run(self, initialized_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            app, ["--repo", str(initialized_repo), "--json", "refresh", "--dry-run"]
        )
        assert result.exit_code in (0, 1)
        data = _parse_json(result.output)
        assert data["dry_run"] is True

    def test_refresh_on_non_initialized_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "bare"
        repo.mkdir()
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(repo), "refresh"])
        assert result.exit_code == 3

    def test_refresh_updates_index_metadata(self, initialized_repo: Path) -> None:
        db_path = initialized_repo / ".rkp" / "local" / "rkp.db"
        db = open_database(db_path)
        run_migrations(db)
        meta_store = SqliteMetadataStore(db)

        # Should have metadata from init
        meta = meta_store.load()
        assert meta is not None
        old_indexed = meta.last_indexed

        db.close()

        runner = CliRunner()
        runner.invoke(app, ["--repo", str(initialized_repo), "refresh"])

        db = open_database(db_path)
        run_migrations(db)
        meta_store = SqliteMetadataStore(db)
        meta = meta_store.load()
        assert meta is not None
        # Timestamp should be updated (or same if very fast)
        assert meta.last_indexed >= old_indexed
        db.close()

    def test_refresh_after_modifying_file(self, initialized_repo: Path) -> None:
        # Modify a source file
        (initialized_repo / "src" / "main.py").write_text(
            "def hello():\n    return 'modified'\n\ndef new_func():\n    pass\n"
        )
        subprocess.run(["git", "add", "."], cwd=initialized_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "modify"],
            cwd=initialized_repo,
            capture_output=True,
            check=True,
        )

        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "--json", "refresh"])
        assert result.exit_code in (0, 1)
        data = _parse_json(result.output)
        assert data["files_analyzed"] > 0
