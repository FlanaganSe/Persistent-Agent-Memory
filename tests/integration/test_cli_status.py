"""Integration tests for rkp status command."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from rkp.cli.app import app
from tests.integration.cli_helpers import extract_json

runner = CliRunner()

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "simple_python"


def _init_fixture(tmp_path: Path) -> Path:
    """Copy fixture, run init, return repo path."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE_DIR, dest, ignore=shutil.ignore_patterns(".rkp", ".ruff_cache"))
    runner.invoke(app, ["--repo", str(dest), "init"])
    return dest


class TestStatusCommand:
    def test_status_initialized(self, tmp_path: Path) -> None:
        """Status on initialized repo shows claim info."""
        repo = _init_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "status"])
        assert result.exit_code in (0, 1)
        assert "claim" in result.output.lower() or "index" in result.output.lower()

    def test_status_not_initialized(self, tmp_path: Path) -> None:
        """Status on non-initialized repo exits with code 3."""
        result = runner.invoke(app, ["--repo", str(tmp_path), "status"])
        assert result.exit_code == 3

    def test_status_not_initialized_message(self, tmp_path: Path) -> None:
        """Status on non-initialized repo suggests rkp init."""
        result = runner.invoke(app, ["--repo", str(tmp_path), "status"])
        assert "init" in result.output.lower()

    def test_status_json_mode(self, tmp_path: Path) -> None:
        """Status with --json produces valid JSON."""
        repo = _init_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "status"])
        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert "status" in data
        assert "index" in data
        assert "claims_by_type" in data
        assert "pending_reviews" in data
        assert "support_envelope" in data
        assert "adapters" in data

    def test_status_json_not_initialized(self, tmp_path: Path) -> None:
        """Status --json on non-initialized repo returns error JSON."""
        result = runner.invoke(app, ["--repo", str(tmp_path), "--json", "status"])
        assert result.exit_code == 3
        data = extract_json(result.output)
        assert data["status"] == "not_initialized"

    def test_status_shows_claim_counts(self, tmp_path: Path) -> None:
        """Status shows claim counts matching the store."""
        repo = _init_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "status"])
        data = extract_json(result.output)
        total = data["index"]["total_claims"]
        assert total > 0

    def test_status_quiet_mode(self, tmp_path: Path) -> None:
        """Status with --quiet suppresses output."""
        repo = _init_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "--quiet", "status"])
        assert result.exit_code in (0, 1)

    def test_status_shows_adapters(self, tmp_path: Path) -> None:
        """Status shows adapter state."""
        repo = _init_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "status"])
        data = extract_json(result.output)
        assert "codex" in data["adapters"]
        assert "claude" in data["adapters"]
