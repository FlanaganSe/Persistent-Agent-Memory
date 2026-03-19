"""Integration tests for the CLI import command via typer.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from rkp.cli.app import app
from tests.integration.cli_helpers import extract_json

runner = CliRunner()

_AGENTS_MD_CONTENT = """\
# AGENTS.md

## Conventions

- Always use ruff for linting
- Never commit directly to main

## Commands

```bash
pytest tests/
ruff check .
```
"""


def _create_repo_with_init(tmp_path: Path, *, agents_md: bool = True) -> Path:
    """Create a temp repo, run init, and optionally add AGENTS.md."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Create a minimal Python file so init works
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n", encoding="utf-8")

    if agents_md:
        (repo / "AGENTS.md").write_text(_AGENTS_MD_CONTENT, encoding="utf-8")

    # Run init to create .rkp/ directory and database
    result = runner.invoke(app, ["--repo", str(repo), "init"])
    assert result.exit_code in (0, 1), f"init failed: {result.output}"

    return repo


class TestCliImportDiscovery:
    """rkp import on fixture shows discovery and summary."""

    def test_import_shows_discovery(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=True)
        result = runner.invoke(app, ["--repo", str(repo), "import"])

        # Should show discovered files or import summary
        assert result.exit_code in (0, 1)
        output_lower = result.output.lower()
        assert "discover" in output_lower or "import" in output_lower or "claim" in output_lower

    def test_import_shows_claims_count(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=True)
        result = runner.invoke(app, ["--repo", str(repo), "import"])

        assert result.exit_code in (0, 1)
        assert "claim" in result.output.lower()


class TestCliImportJsonMode:
    """rkp import --json produces valid JSON output."""

    def test_import_json_valid(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=True)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "import"])

        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert "status" in data
        assert "files_discovered" in data
        assert "claims_created" in data
        assert isinstance(data["files_discovered"], list)
        assert isinstance(data["claims_created"], int)

    def test_import_json_contains_files(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=True)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "import"])

        data = extract_json(result.output)
        assert len(data["files_discovered"]) > 0
        assert any("AGENTS.md" in f for f in data["files_discovered"])


class TestCliImportDryRun:
    """rkp import --dry-run shows what would happen."""

    def test_dry_run_shows_results(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=True)
        result = runner.invoke(app, ["--repo", str(repo), "import", "--dry-run"])

        assert result.exit_code in (0, 1)
        output_lower = result.output.lower()
        assert "dry run" in output_lower or "dry_run" in output_lower

    def test_dry_run_json_status(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=True)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "import", "--dry-run"])

        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert data["status"] == "dry_run"


class TestCliImportNoFiles:
    """rkp import on repo with no instruction files shows clear message."""

    def test_no_files_message(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=False)
        result = runner.invoke(app, ["--repo", str(repo), "import"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "no instruction files" in output_lower or "looking for" in output_lower

    def test_no_files_json(self, tmp_path: Path) -> None:
        repo = _create_repo_with_init(tmp_path, agents_md=False)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "import"])

        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert data["claims_created"] == 0
        assert any("No instruction files" in w for w in data.get("warnings", []))
