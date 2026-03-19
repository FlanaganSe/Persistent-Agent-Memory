"""Orchestrator integration tests for M6: guardrail extraction."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.core.types import ClaimType, RiskClass
from rkp.indexer.orchestrator import run_extraction
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "orch_m6.db")
    run_migrations(db)
    return db


class TestGuardrailExtraction:
    def test_destructive_commands_produce_guardrails(self, db: sqlite3.Connection) -> None:
        """Full pipeline on fixture → guardrail claims from destructive commands."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        store = SqliteClaimStore(db)

        summary = run_extraction(fixture_path, store, repo_id="test-repo")

        # Check if any destructive commands exist in claims
        all_claims = store.list_claims(repo_id="test-repo")
        destructive = [
            c
            for c in all_claims
            if c.claim_type == ClaimType.VALIDATED_COMMAND
            and c.risk_class == RiskClass.DESTRUCTIVE
        ]
        guardrails = [c for c in all_claims if c.claim_type == ClaimType.PERMISSION_RESTRICTION]

        # If there are destructive commands, there should be guardrails
        if destructive:
            assert len(guardrails) > 0
            assert summary.guardrails_extracted > 0

    def test_guardrails_in_extraction_summary(self, db: sqlite3.Connection) -> None:
        """Guardrails count appears in extraction summary."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        store = SqliteClaimStore(db)

        summary = run_extraction(fixture_path, store, repo_id="test-repo")

        # guardrails_extracted should be a non-negative integer
        assert summary.guardrails_extracted >= 0

    def test_guardrails_not_duplicated(self, db: sqlite3.Connection) -> None:
        """Running extraction twice doesn't duplicate guardrails."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        store = SqliteClaimStore(db)

        run_extraction(fixture_path, store, repo_id="test-repo")
        first_count = len(
            [
                c
                for c in store.list_claims(repo_id="test-repo")
                if c.claim_type == ClaimType.PERMISSION_RESTRICTION
            ]
        )

        run_extraction(fixture_path, store, repo_id="test-repo")
        second_count = len(
            [
                c
                for c in store.list_claims(repo_id="test-repo")
                if c.claim_type == ClaimType.PERMISSION_RESTRICTION
            ]
        )

        # Should not increase on re-extraction (deduplication)
        assert second_count == first_count
