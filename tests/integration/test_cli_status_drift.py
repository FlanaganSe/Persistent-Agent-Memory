"""Integration tests for drift reporting in rkp status."""

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
```
"""


def _setup_repo_with_import(tmp_path: Path) -> Path:
    """Create a repo, init, and import AGENTS.md so drift detection has data."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Create a minimal Python file so init works
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n", encoding="utf-8")

    # Create AGENTS.md
    (repo / "AGENTS.md").write_text(_AGENTS_MD_CONTENT, encoding="utf-8")

    # Run init to create .rkp/ and database
    result = runner.invoke(app, ["--repo", str(repo), "init"])
    assert result.exit_code in (0, 1), f"init failed: {result.output}"

    # Run import to register AGENTS.md as a managed artifact
    result = runner.invoke(app, ["--repo", str(repo), "import"])
    assert result.exit_code in (0, 1), f"import failed: {result.output}"

    return repo


class TestStatusNoDrift:
    """Status on repo with no drift does not mention DRIFTED."""

    def test_no_drift_output(self, tmp_path: Path) -> None:
        repo = _setup_repo_with_import(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "status"])

        assert result.exit_code in (0, 1)
        assert "DRIFTED" not in result.output

    def test_no_drift_json(self, tmp_path: Path) -> None:
        repo = _setup_repo_with_import(tmp_path)
        result = runner.invoke(app, ["--repo", str(repo), "--json", "status"])

        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert data["managed_files"]["drifted"] == 0


class TestStatusWithDrift:
    """Status on repo with drifted file shows drift warning."""

    def test_drifted_file_shown(self, tmp_path: Path) -> None:
        repo = _setup_repo_with_import(tmp_path)

        # Modify the managed AGENTS.md
        (repo / "AGENTS.md").write_text(
            "# AGENTS.md\n\n## Conventions\n\n- TOTALLY DIFFERENT CONTENT\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--repo", str(repo), "status"])
        assert result.exit_code in (0, 1)
        assert "DRIFTED" in result.output or "drifted" in result.output.lower()

    def test_drifted_file_json(self, tmp_path: Path) -> None:
        repo = _setup_repo_with_import(tmp_path)

        # Modify the managed AGENTS.md
        (repo / "AGENTS.md").write_text(
            "# AGENTS.md\n\n## Conventions\n\n- TOTALLY DIFFERENT CONTENT\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["--repo", str(repo), "--json", "status"])
        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert data["managed_files"]["drifted"] > 0
        assert len(data["drift_details"]) > 0
        assert data["drift_details"][0]["path"] == "AGENTS.md"


class TestStatusNewUnmanaged:
    """Status on repo with new unmanaged file shows detection."""

    def test_new_unmanaged_detected(self, tmp_path: Path) -> None:
        repo = _setup_repo_with_import(tmp_path)

        # Create a CLAUDE.md that was NOT imported (unmanaged)
        (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n- Use type hints\n", encoding="utf-8")

        result = runner.invoke(app, ["--repo", str(repo), "status"])
        assert result.exit_code in (0, 1)
        output_lower = result.output.lower()
        assert "unmanaged" in output_lower or "not tracked" in output_lower

    def test_new_unmanaged_json(self, tmp_path: Path) -> None:
        repo = _setup_repo_with_import(tmp_path)

        # Create a CLAUDE.md that was NOT imported
        (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n- Use type hints\n", encoding="utf-8")

        result = runner.invoke(app, ["--repo", str(repo), "--json", "status"])
        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        assert data["managed_files"]["new_unmanaged"] > 0
