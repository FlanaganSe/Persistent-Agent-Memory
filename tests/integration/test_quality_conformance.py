"""Integration tests for export conformance per adapter."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.indexer.orchestrator import run_extraction
from rkp.quality.conformance import evaluate_conformance
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def populated_db(tmp_path: Path) -> sqlite3.Connection:
    """Database populated from the simple_python fixture."""
    fixture_path = Path("tests/fixtures/simple_python")
    if not fixture_path.exists():
        pytest.skip("simple_python fixture not available")

    db_path = tmp_path / "conformance.db"
    db = open_database(db_path)
    run_migrations(db)

    store = SqliteClaimStore(db)
    graph = SqliteRepoGraph(db, repo_id="conformance-test", branch="main")
    run_extraction(fixture_path, store, repo_id="conformance-test", branch="main", graph=graph)

    return db


class TestAgentsMdConformance:
    def test_score_reported(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "agents-md", repo_id="conformance-test")
        assert result.adapter_name == "agents-md"
        assert 0.0 <= result.score <= 1.0
        assert result.valid_format is True

    def test_within_budget(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "agents-md", repo_id="conformance-test")
        assert result.within_budget is True

    def test_deterministic(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "agents-md", repo_id="conformance-test")
        assert result.deterministic is True


class TestClaudeMdConformance:
    def test_score_reported(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "claude", repo_id="conformance-test")
        assert result.adapter_name == "claude"
        assert 0.0 <= result.score <= 1.0
        assert result.valid_format is True

    def test_within_budget(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "claude", repo_id="conformance-test")
        assert result.within_budget is True

    def test_deterministic(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "claude", repo_id="conformance-test")
        assert result.deterministic is True


class TestCopilotConformance:
    def test_score_reported(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "copilot", repo_id="conformance-test")
        assert result.adapter_name == "copilot"
        assert 0.0 <= result.score <= 1.0

    def test_valid_format(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "copilot", repo_id="conformance-test")
        assert result.valid_format is True
