"""Integration tests for sensitivity leakage — must pass with zero leakage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.quality.leakage import check_leakage
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def leakage_db(tmp_path: Path) -> sqlite3.Connection:
    """Fresh database for leakage testing."""
    db_path = tmp_path / "leakage.db"
    db = open_database(db_path)
    run_migrations(db)
    return db


class TestLeakage:
    def test_zero_leakage(self, leakage_db: sqlite3.Connection) -> None:
        """All output boundaries must have zero leakage — hard gate."""
        results = check_leakage(leakage_db)
        assert len(results) > 0, "No leakage checks were run"

        leaked = [r for r in results if r.leaked]
        if leaked:
            details = "\n".join(
                f"  {r.boundary} ({r.sensitivity_level}): {r.details}" for r in leaked
            )
            pytest.fail(f"Leakage detected at {len(leaked)} boundary(ies):\n{details}")

    def test_projection_boundaries_checked(self, leakage_db: sqlite3.Connection) -> None:
        """All three projection adapters must be checked."""
        results = check_leakage(leakage_db)
        boundaries = {r.boundary for r in results}
        assert "projection:agents-md" in boundaries
        assert "projection:claude" in boundaries
        assert "projection:copilot" in boundaries

    def test_mcp_tool_boundaries_checked(self, leakage_db: sqlite3.Connection) -> None:
        """MCP tools must be checked for leakage."""
        results = check_leakage(leakage_db)
        boundaries = {r.boundary for r in results}
        assert any(b.startswith("mcp:") for b in boundaries)

    def test_get_claim_blocks_local_only(self, leakage_db: sqlite3.Connection) -> None:
        """get_claim must block local-only claims entirely."""
        results = check_leakage(leakage_db)
        get_claim_results = [r for r in results if r.boundary == "mcp:get_claim"]
        assert len(get_claim_results) > 0
        for r in get_claim_results:
            assert r.leaked is False, f"get_claim leaked: {r.details}"

    def test_both_sensitivity_levels_checked(self, leakage_db: sqlite3.Connection) -> None:
        """Both local-only and team-only sensitivity levels must be checked."""
        results = check_leakage(leakage_db)
        levels = {r.sensitivity_level for r in results}
        assert "local-only" in levels
        assert "team-only" in levels
