"""Integration tests for rkp purge command."""

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

runner = CliRunner()


@pytest.fixture()
def purge_repo(tmp_path: Path) -> Generator[tuple[Path, sqlite3.Connection], None, None]:
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


def _make_tombstoned_claim(
    store: SqliteClaimStore,
    builder: ClaimBuilder,
    content: str,
) -> str:
    """Create a claim, save it, then tombstone it. Returns the claim ID."""
    claim = builder.build(
        content=content,
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        scope="**",
        confidence=0.9,
        evidence=("test.py",),
    )
    store.save(claim)
    tombstoned = replace(claim, review_state=ReviewState.TOMBSTONED)
    store.update(tombstoned)
    return claim.id


class TestPurgeCommand:
    def test_purge_nothing_to_purge(self, purge_repo: tuple[Path, sqlite3.Connection]) -> None:
        """No tombstoned claims produces 'Nothing to purge' and exit 0."""
        repo, _db = purge_repo
        result = runner.invoke(app, ["--repo", str(repo), "purge", "--yes"])
        assert result.exit_code == 0
        assert "Nothing to purge" in result.output

    def test_purge_tombstoned_claims(self, purge_repo: tuple[Path, sqlite3.Connection]) -> None:
        """Tombstoned claims are deleted after purge --yes."""
        repo, db = purge_repo
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="test-repo", branch="main")

        claim_id = _make_tombstoned_claim(store, builder, "rule to purge")

        # Confirm the claim exists before purge.
        assert store.get(claim_id) is not None

        result = runner.invoke(app, ["--repo", str(repo), "purge", "--yes"])
        assert result.exit_code == 0

        # Re-open a fresh store on the same db to read committed state.
        assert store.get(claim_id) is None

    def test_purge_deletes_override_files(
        self, purge_repo: tuple[Path, sqlite3.Connection]
    ) -> None:
        """Purge removes override files for tombstoned claims."""
        repo, db = purge_repo
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="test-repo", branch="main")
        overrides_dir = repo / ".rkp" / "overrides"

        claim_id = _make_tombstoned_claim(store, builder, "rule with override")

        # Manually create an override file that would exist for this claim.
        override_file = overrides_dir / f"{claim_id}_tombstoned.yaml"
        override_file.write_text(f"claim_id: {claim_id}\naction: tombstoned\n")

        assert override_file.exists()

        result = runner.invoke(app, ["--repo", str(repo), "purge", "--yes"])
        assert result.exit_code == 0
        assert not override_file.exists()

    def test_purge_records_audit_trail(self, purge_repo: tuple[Path, sqlite3.Connection]) -> None:
        """Purge writes a 'purge' entry in the session_log table."""
        repo, db = purge_repo
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="test-repo", branch="main")

        _make_tombstoned_claim(store, builder, "rule for audit trail")

        result = runner.invoke(app, ["--repo", str(repo), "purge", "--yes"])
        assert result.exit_code == 0

        # Purge records to session_log (not claim_history, since claims are deleted).
        rows = db.execute("SELECT * FROM session_log WHERE event_type = 'purge'").fetchall()
        assert len(rows) >= 1

    def test_purge_dry_run(self, purge_repo: tuple[Path, sqlite3.Connection]) -> None:
        """Dry run shows what would be purged but does NOT delete claims."""
        repo, db = purge_repo
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="test-repo", branch="main")

        claim_id = _make_tombstoned_claim(store, builder, "rule for dry run")

        result = runner.invoke(app, ["--repo", str(repo), "purge", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.output or "dry_run" in result.output

        # Claim should still exist.
        assert store.get(claim_id) is not None

    def test_purge_confirmation_rejected(
        self, purge_repo: tuple[Path, sqlite3.Connection]
    ) -> None:
        """Rejecting the confirmation prompt leaves claims untouched."""
        repo, db = purge_repo
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="test-repo", branch="main")

        claim_id = _make_tombstoned_claim(store, builder, "rule to keep")

        # Simulate typing "n" at the prompt (no --yes flag).
        result = runner.invoke(app, ["--repo", str(repo), "purge"], input="n\n")
        assert result.exit_code == 0

        # Claim should still exist.
        assert store.get(claim_id) is not None
