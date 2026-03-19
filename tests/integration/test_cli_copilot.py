"""CLI integration tests for Copilot projection."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rkp.cli.app import app
from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations

runner = CliRunner()


@pytest.fixture
def repo_with_claims(tmp_path: Path) -> Path:
    """Create a temporary repo with claims for Copilot projection."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / ".rkp" / "local").mkdir(parents=True)

    db_path = repo / ".rkp" / "local" / "rkp.db"
    db = open_database(db_path)
    run_migrations(db)

    store = SqliteClaimStore(db)
    builder = ClaimBuilder(repo_id=str(repo), branch="main")

    # Command
    cmd = replace(
        builder.build(
            content="pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("pyproject.toml",),
        ),
        risk_class=RiskClass.TEST_EXECUTION,
    )
    store.save(cmd)

    # Environment prerequisite
    env = builder.build(
        content="Python 3.12",
        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
    )
    store.save(env)

    # Convention
    conv = builder.build(
        content="Use snake_case for function names",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.95,
        applicability=("all",),
    )
    store.save(conv)

    db.close()
    return repo


class TestCLIPreviewCopilot:
    def test_preview_copilot_json(self, repo_with_claims: Path) -> None:
        """rkp preview --host copilot --json produces valid JSON with all artifacts."""
        result = runner.invoke(
            app,
            ["--repo", str(repo_with_claims), "--json", "preview", "--host", "copilot"],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        assert output["host"] == "copilot"
        assert ".github/copilot-instructions.md" in output["files"]
        assert ".github/workflows/copilot-setup-steps.yml" in output["files"]
        assert ".copilot-tool-allowlist.json" in output["files"]

    def test_preview_copilot_rich(self, repo_with_claims: Path) -> None:
        """rkp preview --host copilot shows Rich-formatted output."""
        result = runner.invoke(
            app,
            ["--repo", str(repo_with_claims), "preview", "--host", "copilot"],
        )
        assert result.exit_code == 0
        # Should contain copilot-instructions.md content
        assert "copilot-instructions.md" in result.stdout or "copilot" in result.stdout.lower()


class TestCLIApplyCopilot:
    def _approve_claims(self, repo: Path) -> None:
        """Approve all claims so apply works."""
        db_path = repo / ".rkp" / "local" / "rkp.db"
        db = open_database(db_path)
        db.execute("UPDATE claims SET review_state = 'approved'")
        db.commit()
        db.close()

    def test_apply_copilot_writes_files(self, repo_with_claims: Path) -> None:
        """rkp apply --host copilot writes files to correct .github/ locations."""
        self._approve_claims(repo_with_claims)

        result = runner.invoke(
            app,
            [
                "--repo",
                str(repo_with_claims),
                "--json",
                "apply",
                "--host",
                "copilot",
                "--yes",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        assert output["status"] == "success"

        # Check files exist at correct locations
        assert (repo_with_claims / ".github" / "copilot-instructions.md").exists()
        assert (repo_with_claims / ".github" / "workflows" / "copilot-setup-steps.yml").exists()
        assert (repo_with_claims / ".copilot-tool-allowlist.json").exists()

    def test_apply_copilot_respects_ownership(self, repo_with_claims: Path) -> None:
        """rkp apply respects imported-human-owned copilot-instructions.md."""
        self._approve_claims(repo_with_claims)

        # Create a human-owned artifact record
        db_path = repo_with_claims / ".rkp" / "local" / "rkp.db"
        db = open_database(db_path)
        db.execute(
            """INSERT INTO managed_artifacts
               (path, artifact_type, target_host, expected_hash, last_projected, ownership_mode)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ".github/copilot-instructions.md",
                "instruction-file",
                "copilot",
                "abc123",
                "2026-01-01",
                "imported-human-owned",
            ),
        )
        db.commit()
        db.close()

        # Create the existing file
        github_dir = repo_with_claims / ".github"
        github_dir.mkdir(exist_ok=True)
        (github_dir / "copilot-instructions.md").write_text("Human-written content\n")

        result = runner.invoke(
            app,
            [
                "--repo",
                str(repo_with_claims),
                "--json",
                "apply",
                "--host",
                "copilot",
                "--yes",
            ],
        )
        assert result.exit_code == 0

        # Human-owned file should NOT be overwritten
        content = (github_dir / "copilot-instructions.md").read_text()
        assert content == "Human-written content\n"
