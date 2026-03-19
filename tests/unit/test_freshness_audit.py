"""Unit tests for freshness events in audit trail."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rkp.core.models import Claim
from rkp.core.types import ClaimType, SourceAuthority
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations
from rkp.store.history import SqliteHistoryStore


@pytest.fixture
def fresh_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "test.db")
    run_migrations(db)
    return db


def _make_claim(claim_id: str = "claim-test1234") -> Claim:
    return Claim(
        id=claim_id,
        content="Test claim",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        confidence=0.95,
        repo_id="test-repo",
        last_validated=datetime.now(UTC),
    )


class TestFreshnessAuditTrail:
    def test_stale_action_recorded(self, fresh_db: sqlite3.Connection) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        history_store = SqliteHistoryStore(fresh_db)
        claim = _make_claim()
        claim_store.save(claim)

        history_store.record(
            claim_id=claim.id,
            action="stale",
            actor="system",
            reason="Evidence changed: src/utils.py",
        )

        entries = history_store.get_for_claim(claim.id)
        assert len(entries) == 1
        assert entries[0].action == "stale"
        assert entries[0].actor == "system"
        assert "src/utils.py" in (entries[0].reason or "")

    def test_revalidated_action_recorded(self, fresh_db: sqlite3.Connection) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        history_store = SqliteHistoryStore(fresh_db)
        claim = _make_claim()
        claim_store.save(claim)

        history_store.record(
            claim_id=claim.id,
            action="revalidated",
            actor="system",
            reason="Evidence unchanged after refresh",
        )

        entries = history_store.get_for_claim(claim.id)
        assert len(entries) == 1
        assert entries[0].action == "revalidated"

    def test_freshness_events_alongside_governance(self, fresh_db: sqlite3.Connection) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        history_store = SqliteHistoryStore(fresh_db)
        claim = _make_claim()
        claim_store.save(claim)

        # Governance action from M9
        history_store.record(
            claim_id=claim.id,
            action="approved",
            actor="human",
            reason="Verified by developer",
        )

        # Freshness event
        history_store.record(
            claim_id=claim.id,
            action="stale",
            actor="system",
            reason="Evidence changed",
        )

        # Re-approval after staleness
        history_store.record(
            claim_id=claim.id,
            action="approved",
            actor="human",
            reason="Re-verified after changes",
        )

        entries = history_store.get_for_claim(claim.id)
        assert len(entries) == 3
        assert [e.action for e in entries] == ["approved", "stale", "approved"]

    def test_query_by_action_filter(self, fresh_db: sqlite3.Connection) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        history_store = SqliteHistoryStore(fresh_db)
        claim = _make_claim()
        claim_store.save(claim)

        history_store.record(claim_id=claim.id, action="approved", actor="human")
        history_store.record(claim_id=claim.id, action="stale", actor="system")
        history_store.record(claim_id=claim.id, action="revalidated", actor="system")

        stale_only = history_store.query(action="stale")
        assert len(stale_only) == 1
        assert stale_only[0].action == "stale"

    def test_query_by_scope(self, fresh_db: sqlite3.Connection) -> None:
        claim_store = SqliteClaimStore(fresh_db)
        history_store = SqliteHistoryStore(fresh_db)

        claim_a = Claim(
            id="claim-scope-a123",
            content="Claim in src/",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.9,
            scope="src/",
            repo_id="test-repo",
        )
        claim_b = Claim(
            id="claim-scope-b456",
            content="Claim in tests/",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.9,
            scope="tests/",
            repo_id="test-repo",
        )
        claim_store.save(claim_a)
        claim_store.save(claim_b)

        history_store.record(claim_id=claim_a.id, action="stale", actor="system")
        history_store.record(claim_id=claim_b.id, action="stale", actor="system")

        src_entries = history_store.query_by_scope("src/")
        assert len(src_entries) >= 1
        assert all(e.claim_id == claim_a.id for e in src_entries)
