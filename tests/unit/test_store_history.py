"""Tests for the append-only history store."""

from __future__ import annotations

import sqlite3

import pytest

from rkp.core.models import Claim
from rkp.store.claims import SqliteClaimStore
from rkp.store.history import SqliteHistoryStore


@pytest.fixture
def history_store(db: sqlite3.Connection) -> SqliteHistoryStore:
    return SqliteHistoryStore(db)


@pytest.fixture
def claim_store(db: sqlite3.Connection) -> SqliteClaimStore:
    return SqliteClaimStore(db)


class TestRecord:
    def test_record_action(
        self,
        history_store: SqliteHistoryStore,
        claim_store: SqliteClaimStore,
        sample_claim: Claim,
    ) -> None:
        claim_store.save(sample_claim)
        row_id = history_store.record(
            claim_id=sample_claim.id,
            action="approve",
            content_before="old content",
            content_after="new content",
            actor="user@test.com",
            reason="Verified correct",
        )
        assert row_id > 0

    def test_get_for_claim(
        self,
        history_store: SqliteHistoryStore,
        claim_store: SqliteClaimStore,
        sample_claim: Claim,
    ) -> None:
        claim_store.save(sample_claim)
        history_store.record(claim_id=sample_claim.id, action="create", actor="system")
        history_store.record(claim_id=sample_claim.id, action="approve", actor="user@test.com")
        entries = history_store.get_for_claim(sample_claim.id)
        assert len(entries) == 2
        assert entries[0].action == "create"
        assert entries[1].action == "approve"

    def test_history_is_append_only(
        self,
        history_store: SqliteHistoryStore,
        claim_store: SqliteClaimStore,
        sample_claim: Claim,
    ) -> None:
        claim_store.save(sample_claim)
        history_store.record(claim_id=sample_claim.id, action="a", actor="system")
        history_store.record(claim_id=sample_claim.id, action="b", actor="system")
        history_store.record(claim_id=sample_claim.id, action="c", actor="system")
        entries = history_store.get_for_claim(sample_claim.id)
        assert len(entries) == 3
        actions = [e.action for e in entries]
        assert actions == ["a", "b", "c"]


class TestGetAll:
    def test_get_all(
        self,
        history_store: SqliteHistoryStore,
        claim_store: SqliteClaimStore,
        sample_claim: Claim,
    ) -> None:
        claim_store.save(sample_claim)
        for i in range(3):
            history_store.record(claim_id=sample_claim.id, action=f"action-{i}", actor="system")
        all_entries = history_store.get_all(limit=10)
        assert len(all_entries) == 3
