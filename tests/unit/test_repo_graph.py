"""Unit tests for RepoGraph (SqliteRepoGraph)."""

from __future__ import annotations

import pytest

from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def graph_db(tmp_path):
    db = open_database(tmp_path / "test.db")
    run_migrations(db)
    yield db
    db.close()


@pytest.fixture
def graph(graph_db):
    return SqliteRepoGraph(graph_db, repo_id="test-repo")


class TestAddEdgeAndQueries:
    def test_add_edge_and_get_dependencies(self, graph):
        graph.add_edge("mod_a", "mod_b", "imports", "test-repo")
        assert graph.get_dependencies("mod_a") == ["mod_b"]
        assert graph.get_dependencies("mod_b") == []

    def test_add_edge_and_get_dependents(self, graph):
        graph.add_edge("mod_a", "mod_b", "imports", "test-repo")
        assert graph.get_dependents("mod_b") == ["mod_a"]
        assert graph.get_dependents("mod_a") == []

    def test_multiple_dependencies(self, graph):
        graph.add_edge("core", "utils", "imports", "test-repo")
        graph.add_edge("core", "models", "imports", "test-repo")
        deps = graph.get_dependencies("core")
        assert sorted(deps) == ["models", "utils"]

    def test_multiple_dependents(self, graph):
        graph.add_edge("api", "core", "imports", "test-repo")
        graph.add_edge("cli", "core", "imports", "test-repo")
        dependents = graph.get_dependents("core")
        assert sorted(dependents) == ["api", "cli"]


class TestTestLocations:
    def test_get_test_locations(self, graph):
        graph.add_edge("myapp.core", "tests/unit", "tests", "test-repo")
        assert graph.get_test_locations("myapp.core") == ["tests/unit"]

    def test_no_test_locations(self, graph):
        graph.add_edge("mod_a", "mod_b", "imports", "test-repo")
        assert graph.get_test_locations("mod_a") == []


class TestPathToModule:
    def test_path_to_module_exact(self, graph):
        graph.register_module("src/myapp")
        assert graph.path_to_module("src/myapp/core.py") == "src/myapp"

    def test_path_to_module_longest_prefix(self, graph):
        graph.register_module("src/myapp")
        graph.register_module("src/myapp/models")
        assert graph.path_to_module("src/myapp/models/user.py") == "src/myapp/models"

    def test_path_to_module_no_match(self, graph):
        graph.register_module("src/myapp")
        assert graph.path_to_module("other/path.py") is None


class TestGetModules:
    def test_get_modules_empty(self, graph):
        assert graph.get_modules() == []

    def test_get_modules_from_edges(self, graph):
        graph.add_edge("mod_a", "mod_b", "imports", "test-repo")
        assert sorted(graph.get_modules()) == ["mod_a", "mod_b"]

    def test_get_modules_with_registered(self, graph):
        graph.register_module("isolated")
        assert graph.get_modules() == ["isolated"]


class TestClear:
    def test_clear_removes_edges(self, graph):
        graph.add_edge("mod_a", "mod_b", "imports", "test-repo")
        assert graph.get_dependencies("mod_a") == ["mod_b"]
        graph.clear("test-repo")
        assert graph.get_dependencies("mod_a") == []
        assert graph.get_modules() == []


class TestCycles:
    def test_cycle_does_not_crash(self, graph):
        """Cycles in imports should not crash graph operations."""
        graph.add_edge("mod_a", "mod_b", "imports", "test-repo")
        graph.add_edge("mod_b", "mod_a", "imports", "test-repo")
        assert graph.get_dependencies("mod_a") == ["mod_b"]
        assert graph.get_dependencies("mod_b") == ["mod_a"]
        assert graph.get_dependents("mod_a") == ["mod_b"]
        assert graph.get_dependents("mod_b") == ["mod_a"]


class TestIsolatedModules:
    def test_isolated_module_no_edges(self, graph):
        """A registered module with no edges should appear in get_modules."""
        graph.register_module("isolated_mod")
        assert "isolated_mod" in graph.get_modules()
        assert graph.get_dependencies("isolated_mod") == []
        assert graph.get_dependents("isolated_mod") == []


class TestPersistence:
    def test_edges_persist_across_instances(self, graph_db):
        """Edges written to SQLite are loaded by a new graph instance."""
        g1 = SqliteRepoGraph(graph_db, repo_id="test-repo")
        g1.add_edge("mod_a", "mod_b", "imports", "test-repo")

        g2 = SqliteRepoGraph(graph_db, repo_id="test-repo")
        assert g2.get_dependencies("mod_a") == ["mod_b"]
