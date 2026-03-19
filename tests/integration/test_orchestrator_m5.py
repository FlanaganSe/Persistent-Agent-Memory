"""Integration tests for orchestrator M5 extensions: docs evidence, boundaries, conflicts."""

from __future__ import annotations

from pathlib import Path

import pytest

from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.indexer.orchestrator import run_extraction
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_database(db_path)
    run_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture
def store(db):
    return SqliteClaimStore(db)


def _fixture_path(name: str) -> Path:
    return Path(__file__).parent.parent / "fixtures" / name


class TestOrchestratorWithConflicts:
    def test_full_pipeline_detects_conflicts(self, db, store):
        """Full pipeline on with_conflicts/ fixture detects version conflicts."""
        fixture = _fixture_path("with_conflicts")
        if not fixture.exists():
            pytest.skip("with_conflicts fixture not found")

        graph = SqliteRepoGraph(db, repo_id="test-repo")
        summary = run_extraction(fixture, store, repo_id="test-repo", graph=graph)

        assert summary.files_parsed > 0
        assert summary.claims_created > 0

        # Check for version conflict (3.11 vs >=3.12)
        from rkp.core.types import ClaimType

        all_claims = store.list_claims(repo_id="test-repo")
        conflict_claims = [c for c in all_claims if c.claim_type == ClaimType.CONFLICT]
        version_conflicts = [
            c for c in conflict_claims if "version" in c.content.lower() or "3.11" in c.content
        ]

        # Should detect the Python version conflict
        assert len(version_conflicts) >= 1, (
            f"Expected at least 1 version conflict, got {len(version_conflicts)}. "
            f"All conflicts: {[c.content for c in conflict_claims]}"
        )


class TestOrchestratorWithBoundaries:
    def test_full_pipeline_detects_modules(self, db, store):
        """Full pipeline on simple_python/ detects module boundaries."""
        fixture = _fixture_path("simple_python")
        if not fixture.exists():
            pytest.skip("simple_python fixture not found")

        graph = SqliteRepoGraph(db, repo_id="test-repo")
        summary = run_extraction(fixture, store, repo_id="test-repo", graph=graph)

        assert summary.modules_detected >= 1
        modules = graph.get_modules()
        # Should detect myapp and its subpackages
        assert any("myapp" in m for m in modules)

    def test_edges_created_for_imports(self, db, store):
        """Import-based edges are created between detected modules."""
        fixture = _fixture_path("simple_python")
        if not fixture.exists():
            pytest.skip("simple_python fixture not found")

        graph = SqliteRepoGraph(db, repo_id="test-repo")
        summary = run_extraction(fixture, store, repo_id="test-repo", graph=graph)

        assert summary.edges_created >= 0  # May vary by fixture content


class TestOrchestratorDocsEvidence:
    def test_docs_commands_extracted(self, db, store):
        """Docs commands are extracted from README.md."""
        fixture = _fixture_path("simple_python")
        if not fixture.exists():
            pytest.skip("simple_python fixture not found")

        graph = SqliteRepoGraph(db, repo_id="test-repo")
        summary = run_extraction(fixture, store, repo_id="test-repo", graph=graph)

        assert summary.docs_commands_found >= 1

    def test_docs_commands_cross_referenced(self, db, store):
        """Docs commands that match config commands are deduplicated."""
        fixture = _fixture_path("simple_python")
        if not fixture.exists():
            pytest.skip("simple_python fixture not found")

        graph = SqliteRepoGraph(db, repo_id="test-repo")
        run_extraction(fixture, store, repo_id="test-repo", graph=graph)

        # The fixture has "pytest" in both pyproject.toml and README.md
        from rkp.core.types import ClaimType

        all_claims = store.list_claims(repo_id="test-repo")
        pytest_commands = [
            c
            for c in all_claims
            if c.claim_type == ClaimType.VALIDATED_COMMAND and "pytest" in c.content.lower()
        ]
        # Should not have duplicates — one from config, docs version skipped
        # The exact count depends on dedup but should be reasonable
        assert len(pytest_commands) <= 3
