"""Quality harness tests for cursor/windsurf conformance and leakage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.indexer.orchestrator import run_extraction
from rkp.quality.conformance import evaluate_conformance
from rkp.quality.leakage import test_leakage
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def populated_db(tmp_path: Path) -> sqlite3.Connection:
    """Database populated from the simple_python fixture."""
    fixture_path = Path("tests/fixtures/simple_python")
    if not fixture_path.exists():
        pytest.skip("simple_python fixture not available")

    db_path = tmp_path / "quality_m15.db"
    db = open_database(db_path)
    run_migrations(db)

    store = SqliteClaimStore(db)
    graph = SqliteRepoGraph(db, repo_id="quality-m15", branch="main")
    run_extraction(fixture_path, store, repo_id="quality-m15", branch="main", graph=graph)

    return db


class TestCursorConformance:
    def test_score_reported(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "cursor", repo_id="quality-m15")
        assert result.adapter_name == "cursor"
        assert 0.0 <= result.score <= 1.0

    def test_valid_format(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "cursor", repo_id="quality-m15")
        assert result.valid_format is True

    def test_deterministic(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "cursor", repo_id="quality-m15")
        assert result.deterministic is True


class TestWindsurfConformance:
    def test_score_reported(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "windsurf", repo_id="quality-m15")
        assert result.adapter_name == "windsurf"
        assert 0.0 <= result.score <= 1.0

    def test_valid_format(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "windsurf", repo_id="quality-m15")
        assert result.valid_format is True

    def test_within_budget(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "windsurf", repo_id="quality-m15")
        assert result.within_budget is True

    def test_deterministic(self, populated_db: sqlite3.Connection) -> None:
        result = evaluate_conformance(populated_db, "windsurf", repo_id="quality-m15")
        assert result.deterministic is True


class TestCursorWindsurfLeakage:
    """Cursor and windsurf projection boundaries must have zero leakage."""

    def test_cursor_projection_boundary_checked(self, tmp_path: Path) -> None:
        db_path = tmp_path / "leakage_m15.db"
        db = open_database(db_path)
        run_migrations(db)

        results = test_leakage(db)
        boundaries = {r.boundary for r in results}
        assert "projection:cursor" in boundaries

    def test_windsurf_projection_boundary_checked(self, tmp_path: Path) -> None:
        db_path = tmp_path / "leakage_m15.db"
        db = open_database(db_path)
        run_migrations(db)

        results = test_leakage(db)
        boundaries = {r.boundary for r in results}
        assert "projection:windsurf" in boundaries

    def test_cursor_zero_leakage(self, tmp_path: Path) -> None:
        db_path = tmp_path / "leakage_m15.db"
        db = open_database(db_path)
        run_migrations(db)

        results = test_leakage(db)
        cursor_results = [r for r in results if r.boundary == "projection:cursor"]
        assert len(cursor_results) > 0
        leaked = [r for r in cursor_results if r.leaked]
        assert len(leaked) == 0, f"Cursor leakage: {[r.details for r in leaked]}"

    def test_windsurf_zero_leakage(self, tmp_path: Path) -> None:
        db_path = tmp_path / "leakage_m15.db"
        db = open_database(db_path)
        run_migrations(db)

        results = test_leakage(db)
        windsurf_results = [r for r in results if r.boundary == "projection:windsurf"]
        assert len(windsurf_results) > 0
        leaked = [r for r in windsurf_results if r.leaked]
        assert len(leaked) == 0, f"Windsurf leakage: {[r.details for r in leaked]}"
