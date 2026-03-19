"""MCP contract tests for get_module_info and get_conflicts tools."""

from __future__ import annotations

import pytest

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, ReviewState, SourceAuthority
from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.server.tools import get_conflicts, get_module_info
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def db(tmp_path):
    conn = open_database(tmp_path / "test.db")
    run_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture
def store(db):
    return SqliteClaimStore(db)


@pytest.fixture
def builder():
    return ClaimBuilder(repo_id="test-repo")


@pytest.fixture
def populated_db(db, store, builder):
    """Database with module boundary claims and graph edges."""
    # Add a module boundary claim
    boundary = builder.build(
        content="Module 'myapp' — Python package at src/myapp/",
        claim_type=ClaimType.MODULE_BOUNDARY,
        source_authority=SourceAuthority.INFERRED_HIGH,
        scope="src/myapp",
        confidence=0.95,
        evidence=("src/myapp/__init__.py",),
    )
    store.save(boundary)

    # Add a conflict claim
    from dataclasses import replace

    conflict = builder.build(
        content="Python version conflict: 3.11 vs 3.12",
        claim_type=ClaimType.CONFLICT,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        scope="**",
        confidence=1.0,
        evidence=("claim-abc", "claim-def"),
    )
    conflict = replace(conflict, review_state=ReviewState.NEEDS_DECLARATION)
    store.save(conflict)

    # Add graph edges
    graph = SqliteRepoGraph(db, repo_id="test-repo")
    graph.add_edge("myapp", "myapp.core", "contains", "test-repo")
    graph.add_edge("myapp", "utils", "imports", "test-repo")
    graph.add_edge("myapp", "tests/unit", "tests", "test-repo")

    return db


class TestGetModuleInfo:
    def test_response_envelope(self, populated_db):
        """Response has correct envelope structure."""
        response = get_module_info(populated_db, path_or_symbol="myapp")
        assert response.status == "ok"
        assert response.supported is True
        d = response.to_dict()
        assert "provenance" in d
        assert "data" in d
        # Envelope always includes all fields
        assert "unsupported_reason" in d
        assert "warnings" in d

    def test_module_with_dependencies(self, populated_db):
        """Returns dependencies for a known module."""
        response = get_module_info(populated_db, path_or_symbol="myapp")
        data = response.data
        assert data["module"] == "myapp"
        assert "utils" in data["dependencies"]

    def test_module_with_tests(self, populated_db):
        """Returns test locations for a module."""
        response = get_module_info(populated_db, path_or_symbol="myapp")
        data = response.data
        assert "tests/unit" in data["test_locations"]

    def test_unknown_path_graceful(self, populated_db):
        """Unknown path returns ok with note (AC-16 graceful degradation)."""
        response = get_module_info(populated_db, path_or_symbol="nonexistent/path")
        assert response.status == "ok"
        data = response.data
        assert data["module"] is None
        assert "not in a detected module boundary" in data["note"]


class TestGetConflicts:
    def test_response_envelope(self, populated_db):
        """Response has correct envelope structure."""
        response = get_conflicts(populated_db)
        assert response.status == "ok"
        d = response.to_dict()
        assert "provenance" in d
        assert "data" in d

    def test_conflicts_present(self, populated_db):
        """Returns conflict claims in paginated form."""
        response = get_conflicts(populated_db)
        data = response.data
        items = data["items"]
        assert len(items) >= 1
        conflict = items[0]
        assert "content" in conflict
        assert "evidence_claim_ids" in conflict
        assert conflict["review_state"] == "needs-declaration"

    def test_no_conflicts(self, db):
        """Returns empty paginated data when no conflicts exist."""
        response = get_conflicts(db)
        assert response.status == "ok"
        assert response.data["items"] == []
        assert response.data["has_more"] is False

    def test_scoped_filtering(self, populated_db):
        """Scope filtering returns only matching conflicts."""
        response = get_conflicts(populated_db, path_or_scope="**")
        assert len(response.data["items"]) >= 1

        # Specific scope — ** scoped conflicts still appear
        response = get_conflicts(populated_db, path_or_scope="src/other")
        assert len(response.data["items"]) >= 1
