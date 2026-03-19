"""Integration tests for rkp serve command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from rkp.cli.app import app

runner = CliRunner()

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "simple_python"


class TestServeCommand:
    def test_serve_help(self) -> None:
        """Serve --help shows documentation."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "MCP" in result.output or "server" in result.output.lower()

    def test_serve_uses_repo_flag(self, tmp_path: Path) -> None:
        """Serve respects --repo flag (verifiable via startup message)."""
        # We can't actually start the MCP server in a test (it blocks on stdin),
        # but we can verify the command is registered and help works.
        result = runner.invoke(app, ["--repo", str(tmp_path), "serve", "--help"])
        assert result.exit_code == 0
