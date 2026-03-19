"""Unit tests for freshness tracking model."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rkp.core.config import RkpConfig
from rkp.core.freshness import (
    check_all_freshness,
    check_claim_freshness,
    effective_confidence,
)
from rkp.core.models import Claim, Evidence
from rkp.core.types import ClaimType, SourceAuthority
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations
from rkp.store.evidence import SqliteEvidenceStore
from rkp.store.metadata import IndexMetadata


@pytest.fixture
def fresh_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "test.db")
    run_migrations(db)
    return db


@pytest.fixture
def mock_git() -> MagicMock:
    git = MagicMock()
    git.repo_root.return_value = Path("/repo")
    git.head.return_value = "abc123"
    git.current_branch.return_value = "main"
    git.file_hash.return_value = "hash123"
    return git


def _make_claim(
    claim_id: str = "claim-test1234",
    content: str = "Test claim",
    last_validated: datetime | None = None,
    stale: bool = False,
    confidence: float = 0.95,
    branch: str = "main",
) -> Claim:
    return Claim(
        id=claim_id,
        content=content,
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=confidence,
        repo_id="test-repo",
        branch=branch,
        last_validated=last_validated,
        stale=stale,
    )


class TestCheckClaimFreshness:
    def test_unchanged_evidence_is_fresh(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        ev_store.save(
            Evidence(
                claim_id=claim.id,
                file_path="src/main.py",
                file_hash="hash123",
                extraction_version="0.1.0",
            )
        )

        mock_git.file_hash.return_value = "hash123"
        mock_git.repo_root.return_value = Path("/repo")
        # Make the file appear to exist
        config = RkpConfig()

        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert not state.stale
        assert state.revalidation_trigger is None
        assert state.evidence_current

    def test_changed_evidence_hash_is_stale(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        ev_store.save(
            Evidence(
                claim_id=claim.id,
                file_path="src/main.py",
                file_hash="old_hash",
                extraction_version="0.1.0",
            )
        )

        mock_git.file_hash.return_value = "new_hash"

        config = RkpConfig()
        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert state.stale
        assert state.revalidation_trigger == "evidence-changed"
        assert not state.evidence_current

    def test_deleted_evidence_file_is_stale(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        ev_store.save(
            Evidence(
                claim_id=claim.id,
                file_path="src/deleted.py",
                file_hash="hash123",
                extraction_version="0.1.0",
            )
        )

        # File doesn't exist — git hash-object returns empty string
        mock_git.file_hash.return_value = ""

        config = RkpConfig()
        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert state.stale
        assert state.revalidation_trigger == "evidence-deleted"

    def test_branch_change_is_stale(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)

        mock_git.current_branch.return_value = "feature-branch"
        metadata = IndexMetadata(
            last_indexed="2026-03-18T00:00:00Z",
            repo_head="abc123",
            branch="main",
            file_count=10,
            claim_count=5,
        )

        config = RkpConfig()
        state = check_claim_freshness(
            claim,
            ev_store,
            mock_git,
            config,
            datetime.now(UTC),
            index_metadata=metadata,
        )
        assert state.stale
        assert state.revalidation_trigger == "branch-changed"

    def test_time_expired_is_stale(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        old_time = datetime.now(UTC) - timedelta(days=100)
        claim = _make_claim(last_validated=old_time)
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        config = RkpConfig(staleness_window_days=90)

        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert state.stale
        assert state.revalidation_trigger == "time-expired"
        assert state.days_since_validation > 90

    def test_time_not_expired_is_fresh(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        recent_time = datetime.now(UTC) - timedelta(days=30)
        claim = _make_claim(last_validated=recent_time)
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        config = RkpConfig(staleness_window_days=90)

        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert not state.stale
        assert state.days_since_validation < 90

    def test_configurable_staleness_window(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        old_time = datetime.now(UTC) - timedelta(days=45)
        claim = _make_claim(last_validated=old_time)
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        config = RkpConfig(staleness_window_days=30)

        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert state.stale
        assert state.revalidation_trigger == "time-expired"

    def test_multiple_evidence_one_changed(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        # First evidence unchanged
        ev_store.save(
            Evidence(
                claim_id=claim.id,
                file_path="src/a.py",
                file_hash="hash_a",
                extraction_version="0.1.0",
            )
        )
        # Second evidence changed
        ev_store.save(
            Evidence(
                claim_id=claim.id,
                file_path="src/b.py",
                file_hash="old_hash_b",
                extraction_version="0.1.0",
            )
        )

        def file_hash_side_effect(path: Path) -> str:
            if str(path) == "src/a.py":
                return "hash_a"
            return "new_hash_b"

        mock_git.file_hash.side_effect = file_hash_side_effect

        config = RkpConfig()
        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert state.stale
        assert state.revalidation_trigger == "evidence-changed"

    def test_no_evidence_is_fresh(self, fresh_db: sqlite3.Connection, mock_git: MagicMock) -> None:
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store = SqliteClaimStore(fresh_db)
        claim_store.save(claim)

        ev_store = SqliteEvidenceStore(fresh_db)
        config = RkpConfig()

        state = check_claim_freshness(claim, ev_store, mock_git, config, datetime.now(UTC))
        assert not state.stale


class TestEffectiveConfidence:
    def test_fresh_claim_full_confidence(self) -> None:
        claim = _make_claim(confidence=0.97, stale=False)
        config = RkpConfig()
        assert effective_confidence(claim, config) == 0.97

    def test_stale_claim_reduced_confidence(self) -> None:
        claim = _make_claim(confidence=0.97, stale=True)
        config = RkpConfig(confidence_reduction_on_stale=0.2)
        result = effective_confidence(claim, config)
        assert abs(result - 0.97 * 0.8) < 1e-9

    def test_multiplicative_not_absolute(self) -> None:
        claim = _make_claim(confidence=0.5, stale=True)
        config = RkpConfig(confidence_reduction_on_stale=0.2)
        result = effective_confidence(claim, config)
        # 0.5 * 0.8 = 0.4, not 0.5 - 0.2 = 0.3
        assert abs(result - 0.4) < 1e-9


class TestCheckAllFreshness:
    def test_all_fresh(self, fresh_db: sqlite3.Connection, mock_git: MagicMock) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        ev_store = SqliteEvidenceStore(fresh_db)
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store.save(claim)

        config = RkpConfig()
        report = check_all_freshness(
            claim_store,
            ev_store,
            mock_git,
            config,
            repo_id="test-repo",
        )
        assert report.total_claims == 1
        assert report.fresh_claims == 1
        assert report.stale_claims == 0
        assert report.stale_claim_ids == []

    def test_mixed_freshness(self, fresh_db: sqlite3.Connection, mock_git: MagicMock) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        ev_store = SqliteEvidenceStore(fresh_db)

        fresh_claim = _make_claim(
            claim_id="claim-fresh12345",
            last_validated=datetime.now(UTC),
        )
        claim_store.save(fresh_claim)

        old_claim = _make_claim(
            claim_id="claim-old123456",
            content="Old claim",
            last_validated=datetime.now(UTC) - timedelta(days=100),
        )
        claim_store.save(old_claim)

        config = RkpConfig(staleness_window_days=90)
        report = check_all_freshness(
            claim_store,
            ev_store,
            mock_git,
            config,
            repo_id="test-repo",
        )
        assert report.total_claims == 2
        assert report.fresh_claims == 1
        assert report.stale_claims == 1
        assert "time-expired" in report.stale_by_trigger

    def test_branch_change_detection(
        self, fresh_db: sqlite3.Connection, mock_git: MagicMock
    ) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        ev_store = SqliteEvidenceStore(fresh_db)
        claim = _make_claim(last_validated=datetime.now(UTC))
        claim_store.save(claim)

        mock_git.current_branch.return_value = "feature"
        metadata = IndexMetadata(
            last_indexed="2026-03-18T00:00:00Z",
            repo_head="abc123",
            branch="main",
            file_count=10,
            claim_count=1,
        )

        config = RkpConfig()
        report = check_all_freshness(
            claim_store,
            ev_store,
            mock_git,
            config,
            index_metadata=metadata,
            repo_id="test-repo",
        )
        assert report.branch_changed
        assert report.branch_current == "feature"
        assert report.branch_at_index == "main"
