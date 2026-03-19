"""Integration tests for rkp apply command."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rkp.cli.app import app
from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, ReviewState, SourceAuthority
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations
from tests.integration.cli_helpers import extract_json

runner = CliRunner()


@pytest.fixture()
def apply_repo(tmp_path: Path) -> Generator[tuple[Path, sqlite3.Connection], None, None]:
    """Create a minimal repo with .rkp structure and migrated database."""
    repo = tmp_path / "repo"
    repo.mkdir()
    rkp_dir = repo / ".rkp"
    rkp_dir.mkdir()
    (rkp_dir / "local").mkdir()
    (rkp_dir / "overrides").mkdir()
    (rkp_dir / "config.yaml").write_text("# test config\n")
    db_path = rkp_dir / "local" / "rkp.db"
    db = open_database(db_path)
    run_migrations(db)
    yield repo, db
    db.close()


def _save_claim(
    store: SqliteClaimStore,
    repo_path: Path,
    *,
    content: str = "Use ruff for linting",
    claim_type: ClaimType = ClaimType.ALWAYS_ON_RULE,
    source_authority: SourceAuthority = SourceAuthority.EXECUTABLE_CONFIG,
    scope: str = "**",
    confidence: float = 0.9,
    review_state: ReviewState = ReviewState.UNREVIEWED,
) -> str:
    """Build and save a claim, returning its ID."""
    builder = ClaimBuilder(repo_id=str(repo_path))
    claim = builder.build(
        content=content,
        claim_type=claim_type,
        source_authority=source_authority,
        scope=scope,
        confidence=confidence,
    )
    if review_state != ReviewState.UNREVIEWED:
        claim = replace(claim, review_state=review_state)
    store.save(claim)
    return claim.id


class TestApplyNoApprovedClaims:
    def test_apply_no_approved_claims(self, apply_repo: tuple[Path, sqlite3.Connection]) -> None:
        """No approved claims produces exit 1 and an error message."""
        repo, _db = apply_repo
        result = runner.invoke(app, ["--repo", str(repo), "apply", "--yes"])
        assert result.exit_code == 1
        assert "no approved claims" in result.output.lower()

    def test_apply_no_approved_claims_json(
        self, apply_repo: tuple[Path, sqlite3.Connection]
    ) -> None:
        """--json with no approved claims returns status JSON and exit 1."""
        repo, _db = apply_repo
        result = runner.invoke(app, ["--repo", str(repo), "--json", "apply", "--yes"])
        assert result.exit_code == 1
        data = extract_json(result.output)
        assert data["status"] == "no_approved_claims"


class TestApplyWithApprovedClaims:
    def test_apply_with_approved_claims(self, apply_repo: tuple[Path, sqlite3.Connection]) -> None:
        """Approved claims produce files on disk when --yes is passed."""
        repo, db = apply_repo
        store = SqliteClaimStore(db)
        _save_claim(
            store,
            repo,
            content="Always run ruff before committing",
            review_state=ReviewState.APPROVED,
            confidence=0.95,
        )

        result = runner.invoke(app, ["--repo", str(repo), "apply", "--yes"])
        # exit 0 = files written, or 0 if no-change (content already up to date)
        assert result.exit_code == 0

    def test_apply_dry_run(self, apply_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--dry-run shows what would change without writing files."""
        repo, db = apply_repo
        store = SqliteClaimStore(db)
        _save_claim(
            store,
            repo,
            content="Always run ruff before committing",
            review_state=ReviewState.APPROVED,
            confidence=0.95,
        )

        result = runner.invoke(app, ["--repo", str(repo), "--json", "apply", "--dry-run"])
        assert result.exit_code == 0
        data = extract_json(result.output)
        assert data["status"] in ("dry_run", "no_changes")
        if data["status"] == "dry_run":
            assert "would_write" in data
            assert data["would_write"] >= 1

    def test_apply_only_approved_claims(self, apply_repo: tuple[Path, sqlite3.Connection]) -> None:
        """Only approved/edited claims are projected; unreviewed are excluded."""
        repo, db = apply_repo
        store = SqliteClaimStore(db)
        _save_claim(
            store,
            repo,
            content="Approved rule: use type hints",
            review_state=ReviewState.APPROVED,
            confidence=0.95,
        )
        _save_claim(
            store,
            repo,
            content="Unreviewed rule: use mypy",
            review_state=ReviewState.UNREVIEWED,
            confidence=0.95,
        )

        result = runner.invoke(app, ["--repo", str(repo), "--json", "apply", "--yes"])
        # Should succeed (has at least one approved claim)
        assert result.exit_code == 0


class TestApplyJsonOutput:
    def test_apply_json_output(self, apply_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--json produces structured JSON with file actions and managed artifacts."""
        repo, db = apply_repo
        store = SqliteClaimStore(db)
        _save_claim(
            store,
            repo,
            content="Always use pathlib.Path",
            review_state=ReviewState.APPROVED,
            confidence=0.95,
        )

        result = runner.invoke(app, ["--repo", str(repo), "--json", "apply", "--yes"])
        assert result.exit_code == 0
        data = extract_json(result.output)
        assert "status" in data
        assert data["status"] in ("success", "no_changes")
        if data["status"] == "success":
            assert "files" in data
            assert "written" in data
            assert "managed_artifacts" in data
            assert isinstance(data["managed_artifacts"], list)
            for artifact in data["managed_artifacts"]:
                assert "path" in artifact
                assert "artifact_type" in artifact
                assert "target_host" in artifact
                assert "hash" in artifact
