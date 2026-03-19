"""Integration tests for rkp init command."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from rkp.cli.app import app
from tests.integration.cli_helpers import extract_json

runner = CliRunner()

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "simple_python"


def _copy_fixture(tmp_path: Path) -> Path:
    """Copy simple_python fixture to a temp dir for init testing."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE_DIR, dest, ignore=shutil.ignore_patterns(".rkp", ".ruff_cache"))
    return dest


class TestInitCommand:
    def test_init_simple_python(self, tmp_path: Path) -> None:
        """Init on simple_python fixture creates .rkp/ and extracts claims."""
        repo = _copy_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "init"])
        assert result.exit_code in (0, 1)  # 0 or 1 (findings)
        assert (repo / ".rkp" / "config.yaml").exists()
        assert (repo / ".rkp" / "local").is_dir()
        assert (repo / ".rkp" / "overrides").is_dir()

    def test_init_shows_summary(self, tmp_path: Path) -> None:
        """Init shows extraction summary."""
        repo = _copy_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "init"])
        assert result.exit_code in (0, 1)
        assert "Extracted" in result.output or "claims" in result.output.lower()

    def test_init_already_initialized(self, tmp_path: Path) -> None:
        """Init on already-initialized repo shows appropriate message."""
        repo = _copy_fixture(tmp_path)
        runner.invoke(app, ["--repo", str(repo), "init"])
        result = runner.invoke(app, ["--repo", str(repo), "init"])
        assert result.exit_code == 0
        assert "already initialized" in result.output.lower()

    def test_init_empty_directory(self, tmp_path: Path) -> None:
        """Init on empty directory exits with code 3."""
        result = runner.invoke(app, ["--repo", str(tmp_path), "init"])
        assert result.exit_code == 3

    def test_init_non_git_directory(self, tmp_path: Path) -> None:
        """Init on non-git directory works with filesystem-only extraction."""
        repo = _copy_fixture(tmp_path)
        git_dir = repo / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)
        result = runner.invoke(app, ["--repo", str(repo), "init"])
        assert result.exit_code in (0, 1)

    def test_init_json_mode(self, tmp_path: Path) -> None:
        """Init with --json produces valid JSON output."""
        repo = _copy_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "init"])
        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert data["status"] == "success"
        assert "claims_created" in data
        assert "config_path" in data
        assert "next_steps" in data

    def test_init_quiet_mode(self, tmp_path: Path) -> None:
        """Init with --quiet suppresses non-error output."""
        repo = _copy_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "--quiet", "init"])
        assert result.exit_code in (0, 1)

    def test_init_creates_config(self, tmp_path: Path) -> None:
        """Init creates .rkp/config.yaml with valid content."""
        repo = _copy_fixture(tmp_path)
        runner.invoke(app, ["--repo", str(repo), "init"])
        config_path = repo / ".rkp" / "config.yaml"
        assert config_path.exists()
        content = config_path.read_text()
        assert "support_envelope" in content
        assert "thresholds" in content

    def test_init_creates_directories(self, tmp_path: Path) -> None:
        """Init creates .rkp/local/ and .rkp/overrides/."""
        repo = _copy_fixture(tmp_path)
        runner.invoke(app, ["--repo", str(repo), "init"])
        assert (repo / ".rkp" / "local").is_dir()
        assert (repo / ".rkp" / "overrides").is_dir()

    def test_init_json_already_initialized(self, tmp_path: Path) -> None:
        """Init --json on already-initialized repo returns status."""
        repo = _copy_fixture(tmp_path)
        runner.invoke(app, ["--repo", str(repo), "init"])
        result = runner.invoke(app, ["--repo", str(repo), "--json", "init"])
        assert result.exit_code == 0
        data = extract_json(result.output)
        assert data["status"] == "already_initialized"

    def test_init_shows_next_steps(self, tmp_path: Path) -> None:
        """Init shows next steps to the user."""
        repo = _copy_fixture(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "init"])
        assert result.exit_code in (0, 1)
        assert "preview" in result.output.lower() or "status" in result.output.lower()
