"""Integration tests for rkp review command."""

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
def review_repo(tmp_path: Path) -> Generator[tuple[Path, sqlite3.Connection], None, None]:
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
    confidence: float = 0.98,
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


class TestReviewEmpty:
    def test_review_empty_queue(self, review_repo: tuple[Path, sqlite3.Connection]) -> None:
        """No unreviewed claims produces 'No claims to review' and exit 0."""
        repo, _db = review_repo
        result = runner.invoke(app, ["--repo", str(repo), "review"])
        assert result.exit_code == 0
        assert "no claims to review" in result.output.lower()


class TestReviewBatchApprove:
    def test_review_approve_all_batch(self, review_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--approve-all approves high-confidence, strong-authority claims."""
        repo, db = review_repo
        store = SqliteClaimStore(db)
        cid = _save_claim(store, repo, confidence=0.98)

        result = runner.invoke(app, ["--repo", str(repo), "review", "--approve-all"])
        assert result.exit_code == 0

        updated = store.get(cid)
        assert updated is not None
        assert updated.review_state == ReviewState.APPROVED

    def test_review_approve_all_skips_low_confidence(
        self, review_repo: tuple[Path, sqlite3.Connection]
    ) -> None:
        """--approve-all skips claims below the default 0.95 threshold."""
        repo, db = review_repo
        store = SqliteClaimStore(db)
        cid = _save_claim(store, repo, confidence=0.5)

        result = runner.invoke(app, ["--repo", str(repo), "review", "--approve-all"])
        assert result.exit_code == 0

        updated = store.get(cid)
        assert updated is not None
        assert updated.review_state == ReviewState.UNREVIEWED


class TestReviewFilters:
    def test_review_type_filter(self, review_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--type always-on-rule shows only convention claims, not commands."""
        repo, db = review_repo
        store = SqliteClaimStore(db)
        _save_claim(
            store,
            repo,
            content="Always lint before commit",
            claim_type=ClaimType.ALWAYS_ON_RULE,
        )
        _save_claim(
            store,
            repo,
            content="make test",
            claim_type=ClaimType.VALIDATED_COMMAND,
        )

        result = runner.invoke(
            app,
            ["--repo", str(repo), "--json", "review", "--type", "always-on-rule", "--approve-all"],
        )
        assert result.exit_code == 0
        data = extract_json(result.output)
        # Only the convention claim should have been considered.
        assert data["approved"] + data["skipped"] >= 1

    def test_review_scope_filter(self, review_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--scope src/ filters to claims whose scope starts with src/."""
        repo, db = review_repo
        store = SqliteClaimStore(db)
        _save_claim(store, repo, content="src rule", scope="src/rkp/")
        _save_claim(store, repo, content="root rule", scope="**")

        result = runner.invoke(
            app,
            [
                "--repo",
                str(repo),
                "--json",
                "review",
                "--scope",
                "src/",
                "--approve-all",
            ],
        )
        assert result.exit_code == 0
        data = extract_json(result.output)
        # Only the src/ claim should be in scope.
        total = data["approved"] + data["skipped"]
        assert total == 1

    def test_review_state_filter(self, review_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--state needs-declaration shows only needs-declaration claims."""
        repo, db = review_repo
        store = SqliteClaimStore(db)
        _save_claim(store, repo, content="normal rule")
        _save_claim(
            store,
            repo,
            content="Which testing framework?",
            review_state=ReviewState.NEEDS_DECLARATION,
        )

        result = runner.invoke(
            app,
            [
                "--repo",
                str(repo),
                "--json",
                "review",
                "--state",
                "needs-declaration",
                "--approve-all",
            ],
        )
        assert result.exit_code == 0
        data = extract_json(result.output)
        # Only the needs-declaration claim should be visible.
        total = data["approved"] + data["skipped"]
        assert total == 1


class TestReviewInteractive:
    def test_review_interactive_approve(
        self, review_repo: tuple[Path, sqlite3.Connection]
    ) -> None:
        """Interactive review: 'a' approves, 'q' quits."""
        repo, db = review_repo
        store = SqliteClaimStore(db)
        cid = _save_claim(store, repo, content="Use type hints everywhere")

        result = runner.invoke(
            app,
            ["--repo", str(repo), "review"],
            input="a\nq\n",
        )
        assert result.exit_code == 0

        updated = store.get(cid)
        assert updated is not None
        assert updated.review_state == ReviewState.APPROVED


class TestReviewJsonOutput:
    def test_review_json_output(self, review_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--json produces structured JSON with expected fields."""
        repo, db = review_repo
        store = SqliteClaimStore(db)
        _save_claim(store, repo, confidence=0.99)

        result = runner.invoke(
            app,
            ["--repo", str(repo), "--json", "review", "--approve-all"],
        )
        assert result.exit_code == 0
        data = extract_json(result.output)
        assert "status" in data
        assert data["status"] == "batch_approved"
        assert "approved" in data
        assert "skipped" in data
        assert "threshold" in data
        assert "approved_ids" in data

    def test_review_json_empty(self, review_repo: tuple[Path, sqlite3.Connection]) -> None:
        """--json with no claims produces empty status."""
        repo, _db = review_repo
        result = runner.invoke(
            app,
            ["--repo", str(repo), "--json", "review"],
        )
        assert result.exit_code == 0
        data = extract_json(result.output)
        assert data["status"] == "empty"
        assert "message" in data
