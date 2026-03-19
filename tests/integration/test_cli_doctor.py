"""Integration tests for rkp doctor command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from rkp.cli.app import app
from tests.integration.cli_helpers import extract_json

runner = CliRunner()


class TestDoctorCommand:
    def test_doctor_all_pass(self) -> None:
        """Doctor on a healthy system should pass all checks."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "doctor"])
        assert result.exit_code == 0
        assert "\u2713" in result.output

    def test_doctor_json_mode(self) -> None:
        """Doctor with --json produces valid JSON with check results."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "--json", "doctor"])
        assert result.exit_code == 0
        data = extract_json(result.output)
        assert "checks" in data
        assert "summary" in data
        assert isinstance(data["checks"], list)
        assert data["summary"]["total"] > 0

    def test_doctor_checks_python_version(self) -> None:
        """Doctor verifies Python version."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "--json", "doctor"])
        data = extract_json(result.output)
        python_check = next(c for c in data["checks"] if c["name"] == "python")
        assert python_check["passed"] is True
        assert "Python" in python_check["message"]

    def test_doctor_checks_git(self) -> None:
        """Doctor verifies Git availability."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "--json", "doctor"])
        data = extract_json(result.output)
        git_check = next(c for c in data["checks"] if c["name"] == "git")
        assert git_check["passed"] is True

    def test_doctor_checks_sqlite(self) -> None:
        """Doctor verifies SQLite features."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "--json", "doctor"])
        data = extract_json(result.output)
        sqlite_check = next(c for c in data["checks"] if c["name"] == "sqlite")
        assert sqlite_check["passed"] is True

    def test_doctor_checks_tree_sitter(self) -> None:
        """Doctor verifies tree-sitter parsers."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "--json", "doctor"])
        data = extract_json(result.output)
        ts_check = next(c for c in data["checks"] if c["name"] == "tree_sitter")
        assert ts_check["passed"] is True

    def test_doctor_without_db(self, tmp_path: Path) -> None:
        """Doctor on a dir with no DB reports 'not initialized' but doesn't fail."""
        result = runner.invoke(app, ["--repo", str(tmp_path), "--json", "doctor"])
        assert result.exit_code in (0, 1)
        data = extract_json(result.output)
        db_check = next(c for c in data["checks"] if c["name"] == "database")
        assert "not initialized" in db_check["message"].lower() or db_check["passed"]

    def test_doctor_quiet_mode(self) -> None:
        """Doctor with --quiet suppresses non-error output."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "--quiet", "doctor"])
        assert result.exit_code == 0
        # Quiet mode: no checkmarks or summary in output.
        assert "\u2713" not in result.output
        assert "checks passed" not in result.output

    def test_doctor_checks_mcp(self) -> None:
        """Doctor verifies MCP server can be constructed."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = runner.invoke(app, ["--repo", str(fixture_path), "--json", "doctor"])
        data = extract_json(result.output)
        mcp_check = next(c for c in data["checks"] if c["name"] == "mcp")
        assert mcp_check["passed"] is True
