"""CLI integration tests for cursor/windsurf preview and apply."""

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
    """Create a temporary repo with claims for cursor/windsurf projection."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / ".rkp" / "local").mkdir(parents=True)

    db_path = repo / ".rkp" / "local" / "rkp.db"
    db = open_database(db_path)
    run_migrations(db)

    store = SqliteClaimStore(db)
    builder = ClaimBuilder(repo_id=str(repo), branch="main")

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

    conv = builder.build(
        content="Use snake_case for function names",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.INFERRED_HIGH,
        confidence=0.95,
        applicability=("all",),
    )
    store.save(conv)

    guardrail = builder.build(
        content="Command `db:reset` is classified as destructive "
        "— require explicit confirmation before running",
        claim_type=ClaimType.PERMISSION_RESTRICTION,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=1.0,
        evidence=("Makefile",),
    )
    store.save(guardrail)

    db.close()
    return repo


def _approve_claims(repo: Path) -> None:
    """Approve all claims so apply works."""
    db_path = repo / ".rkp" / "local" / "rkp.db"
    db = open_database(db_path)
    db.execute("UPDATE claims SET review_state = 'approved'")
    db.commit()
    db.close()


class TestCLIPreviewCursor:
    def test_preview_cursor_shows_rules(self, repo_with_claims: Path) -> None:
        """rkp preview --host cursor shows .cursor/rules/ files."""
        result = runner.invoke(
            app,
            ["--repo", str(repo_with_claims), "preview", "--host", "cursor"],
        )
        assert result.exit_code == 0
        assert ".cursor/rules/" in result.stdout or "cursor" in result.stdout.lower()

    def test_preview_cursor_json(self, repo_with_claims: Path) -> None:
        """rkp preview --host cursor --json produces valid JSON with cursor rules."""
        result = runner.invoke(
            app,
            ["--repo", str(repo_with_claims), "--json", "preview", "--host", "cursor"],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["host"] == "cursor"
        assert any(k.startswith(".cursor/rules/") for k in output["files"])


class TestCLIPreviewWindsurf:
    def test_preview_windsurf_shows_rules(self, repo_with_claims: Path) -> None:
        """rkp preview --host windsurf shows .windsurf/rules/ files."""
        result = runner.invoke(
            app,
            ["--repo", str(repo_with_claims), "preview", "--host", "windsurf"],
        )
        assert result.exit_code == 0
        assert ".windsurf/rules/" in result.stdout or "windsurf" in result.stdout.lower()

    def test_preview_windsurf_json_has_budget(self, repo_with_claims: Path) -> None:
        """rkp preview --host windsurf --json includes budget details."""
        result = runner.invoke(
            app,
            ["--repo", str(repo_with_claims), "--json", "preview", "--host", "windsurf"],
        )
        assert result.exit_code == 0
        output = json.loads(result.stdout)
        assert output["host"] == "windsurf"
        assert any(k.startswith(".windsurf/rules/") for k in output["files"])

        overflow = output["overflow_report"]
        assert "windsurf_budget" in overflow
        budget = overflow["windsurf_budget"]
        assert "workspace_used" in budget
        assert "workspace_limit" in budget


class TestCLIApplyCursor:
    def test_apply_cursor_writes_files(self, repo_with_claims: Path) -> None:
        """rkp apply --host cursor writes .cursor/rules/ files."""
        _approve_claims(repo_with_claims)

        result = runner.invoke(
            app,
            [
                "--repo",
                str(repo_with_claims),
                "--json",
                "apply",
                "--host",
                "cursor",
                "--yes",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        assert output["status"] == "success"

        cursor_rules = repo_with_claims / ".cursor" / "rules"
        assert cursor_rules.exists()
        rule_files = list(cursor_rules.glob("rkp-*.md"))
        assert len(rule_files) > 0


class TestCLIApplyWindsurf:
    def test_apply_windsurf_writes_files(self, repo_with_claims: Path) -> None:
        """rkp apply --host windsurf writes .windsurf/rules/ files."""
        _approve_claims(repo_with_claims)

        result = runner.invoke(
            app,
            [
                "--repo",
                str(repo_with_claims),
                "--json",
                "apply",
                "--host",
                "windsurf",
                "--yes",
            ],
        )
        assert result.exit_code == 0

        output = json.loads(result.stdout)
        assert output["status"] == "success"

        windsurf_rules = repo_with_claims / ".windsurf" / "rules"
        assert windsurf_rules.exists()
        rule_files = list(windsurf_rules.glob("rkp-*.md"))
        assert len(rule_files) > 0
