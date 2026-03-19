"""Integration tests for the extraction orchestrator."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.core.types import ClaimType
from rkp.indexer.orchestrator import run_extraction
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def integration_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "test.db")
    run_migrations(db)
    return db


class TestOrchestrator:
    def test_extract_from_fixture(self, integration_db: sqlite3.Connection) -> None:
        """End-to-end extraction on the simple_python fixture."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(fixture_path, store, repo_id="test-repo")
        assert summary.files_parsed >= 1
        assert summary.claims_created >= 1

        claims = store.list_claims(repo_id="test-repo")
        assert len(claims) >= 1

    def test_idempotent_extraction(self, integration_db: sqlite3.Connection) -> None:
        """Running extraction twice produces the same claims (idempotent)."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        store = SqliteClaimStore(integration_db)

        summary1 = run_extraction(fixture_path, store, repo_id="test-repo")
        claims1 = store.list_claims(repo_id="test-repo")

        summary2 = run_extraction(fixture_path, store, repo_id="test-repo")
        claims2 = store.list_claims(repo_id="test-repo")

        # Second run should deduplicate all claims
        assert summary2.claims_created == 0
        assert summary2.claims_deduplicated == summary1.claims_created
        assert len(claims1) == len(claims2)

    def test_extract_from_empty_repo(
        self, integration_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Extraction on a repo with no config files returns empty summary."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(empty_dir, store, repo_id="empty")
        assert summary.files_parsed == 0
        assert summary.claims_created == 0

    def test_extract_pyproject_scripts(
        self, integration_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Extract commands from pyproject.toml scripts."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "test"\n\n[project.scripts]\n'
            'mytest = "pytest"\nmylint = "ruff check ."\n'
        )
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(repo, store, repo_id="test")
        assert summary.claims_created == 2

        claims = store.list_claims(repo_id="test")
        contents = {c.content for c in claims}
        assert "pytest" in contents
        assert "ruff check ." in contents

    def test_extract_package_json_scripts(
        self, integration_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Extract commands from package.json scripts."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "package.json").write_text(
            '{"name": "test", "scripts": {"test": "jest", "build": "webpack"}}'
        )
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(repo, store, repo_id="test")
        assert summary.claims_created == 2

    def test_extract_conventions_from_fixture(self, integration_db: sqlite3.Connection) -> None:
        """Convention extraction on the simple_python fixture."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        store = SqliteClaimStore(integration_db)
        summary = run_extraction(fixture_path, store, repo_id="test-repo")

        # Should have found Python files and extracted conventions
        assert summary.python_files_parsed > 0
        assert summary.conventions_extracted > 0

        # Check that convention claims exist
        claims = store.list_claims(repo_id="test-repo")
        convention_claims = [
            c for c in claims if c.claim_type in (ClaimType.ALWAYS_ON_RULE, ClaimType.SCOPED_RULE)
        ]
        assert len(convention_claims) > 0

    def test_fixture_has_convention_claims(self, integration_db: sqlite3.Connection) -> None:
        """The fixture produces convention claims (e.g. type annotations, docstrings)."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        store = SqliteClaimStore(integration_db)
        run_extraction(fixture_path, store, repo_id="test-repo")

        claims = store.list_claims(repo_id="test-repo")
        convention_claims = [
            c for c in claims if c.claim_type in (ClaimType.ALWAYS_ON_RULE, ClaimType.SCOPED_RULE)
        ]
        assert len(convention_claims) >= 1
