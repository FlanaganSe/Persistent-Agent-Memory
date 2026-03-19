"""Integration tests for M4 orchestrator: CI evidence, prerequisites, JS parsing."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.core.types import ClaimType
from rkp.indexer.orchestrator import run_extraction
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def integration_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "test.db")
    run_migrations(db)
    return db


class TestOrchestratorM4:
    def test_with_ci_fixture(self, integration_db: sqlite3.Connection) -> None:
        """End-to-end extraction on the with_ci fixture finds commands, CI evidence, prerequisites."""
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(FIXTURES / "with_ci", store, repo_id="test")
        assert summary.claims_created > 0
        # Should find commands from pyproject, package.json, Makefile
        commands = store.list_claims(claim_type=ClaimType.VALIDATED_COMMAND, repo_id="test")
        assert len(commands) >= 5
        # Should find prerequisites
        prereqs = store.list_claims(claim_type=ClaimType.ENVIRONMENT_PREREQUISITE, repo_id="test")
        assert len(prereqs) > 0

    def test_simple_js_fixture(self, integration_db: sqlite3.Connection) -> None:
        """Extraction on simple_js fixture finds package.json scripts."""
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(FIXTURES / "simple_js", store, repo_id="test")
        assert summary.claims_created > 0
        commands = store.list_claims(claim_type=ClaimType.VALIDATED_COMMAND, repo_id="test")
        # Should find scripts from package.json (test, lint, build, format)
        assert len(commands) >= 4

    def test_profiles_stored(self, integration_db: sqlite3.Connection) -> None:
        """Environment profiles are stored in the database."""
        store = SqliteClaimStore(integration_db)
        run_extraction(FIXTURES / "with_ci", store, repo_id="test")
        # Check environment profiles table
        rows = integration_db.execute(
            "SELECT * FROM environment_profiles WHERE repo_id = ?", ("test",)
        ).fetchall()
        assert len(rows) >= 1

    def test_ci_commands_found(self, integration_db: sqlite3.Connection) -> None:
        """CI evidence extraction finds CI commands from workflows."""
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(FIXTURES / "with_ci", store, repo_id="test")
        assert summary.ci_commands_found > 0

    def test_prerequisites_extracted(self, integration_db: sqlite3.Connection) -> None:
        """Prerequisites are extracted from the with_ci fixture."""
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(FIXTURES / "with_ci", store, repo_id="test")
        assert summary.prerequisites_extracted > 0

    def test_js_files_parsed(self, integration_db: sqlite3.Connection) -> None:
        """JS/TS files are parsed from the simple_js fixture."""
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(FIXTURES / "simple_js", store, repo_id="test")
        assert summary.js_files_parsed > 0
