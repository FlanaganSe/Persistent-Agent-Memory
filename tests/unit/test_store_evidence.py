"""Tests for the evidence store."""

from __future__ import annotations

import sqlite3

import pytest

from rkp.core.models import Claim, Evidence
from rkp.core.types import EvidenceLevel
from rkp.store.claims import SqliteClaimStore
from rkp.store.evidence import SqliteEvidenceStore


@pytest.fixture
def evidence_store(db: sqlite3.Connection) -> SqliteEvidenceStore:
    return SqliteEvidenceStore(db)


@pytest.fixture
def claim_store(db: sqlite3.Connection) -> SqliteClaimStore:
    return SqliteClaimStore(db)


class TestSaveAndRetrieve:
    def test_save_and_get(
        self,
        evidence_store: SqliteEvidenceStore,
        claim_store: SqliteClaimStore,
        sample_claim: Claim,
    ) -> None:
        claim_store.save(sample_claim)
        ev = Evidence(
            claim_id=sample_claim.id,
            file_path="pyproject.toml",
            file_hash="abc123",
            extraction_version="0.1.0",
            line_start=10,
            line_end=15,
            evidence_level=EvidenceLevel.DISCOVERED,
        )
        row_id = evidence_store.save(ev)
        assert row_id > 0

        records = evidence_store.get_for_claim(sample_claim.id)
        assert len(records) == 1
        assert records[0].file_path == "pyproject.toml"
        assert records[0].evidence_level == EvidenceLevel.DISCOVERED
        assert records[0].line_start == 10

    def test_get_by_file(
        self,
        evidence_store: SqliteEvidenceStore,
        claim_store: SqliteClaimStore,
        sample_claim: Claim,
    ) -> None:
        claim_store.save(sample_claim)
        ev = Evidence(
            claim_id=sample_claim.id,
            file_path="src/main.py",
            file_hash="def456",
            extraction_version="0.1.0",
        )
        evidence_store.save(ev)
        records = evidence_store.get_by_file("src/main.py")
        assert len(records) == 1

    def test_delete_for_claim(
        self,
        evidence_store: SqliteEvidenceStore,
        claim_store: SqliteClaimStore,
        sample_claim: Claim,
    ) -> None:
        claim_store.save(sample_claim)
        ev = Evidence(
            claim_id=sample_claim.id,
            file_path="test.py",
            file_hash="111",
            extraction_version="0.1.0",
        )
        evidence_store.save(ev)
        count = evidence_store.delete_for_claim(sample_claim.id)
        assert count == 1
        assert evidence_store.get_for_claim(sample_claim.id) == []
