"""Unit tests for migration 0002_index_metadata."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.store.database import get_user_version, open_database, run_migrations


@pytest.fixture
def fresh_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "test.db")
    return db


class TestMigration0002:
    def test_fresh_db_runs_both_migrations(self, fresh_db: sqlite3.Connection) -> None:
        run_migrations(fresh_db)
        version = get_user_version(fresh_db)
        assert version == 2

        # Verify index_metadata table exists
        row = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='index_metadata'"
        ).fetchone()
        assert row is not None

    def test_db_with_only_0001_upgrades(self, tmp_path: Path) -> None:
        db = open_database(tmp_path / "test.db")
        # Run only migration 0001
        sql = (
            Path(__file__).parent.parent.parent
            / "src"
            / "rkp"
            / "store"
            / "migrations"
            / "0001_init.sql"
        ).read_text()
        db.executescript(sql)
        db.execute("PRAGMA user_version = 1")

        assert get_user_version(db) == 1

        # Now run all migrations — should apply 0002
        run_migrations(db)
        assert get_user_version(db) == 2

        # Verify index_metadata exists
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='index_metadata'"
        ).fetchone()
        assert row is not None
        db.close()

    def test_db_with_both_is_noop(self, fresh_db: sqlite3.Connection) -> None:
        run_migrations(fresh_db)
        v1 = get_user_version(fresh_db)

        # Running again is a no-op
        run_migrations(fresh_db)
        v2 = get_user_version(fresh_db)
        assert v1 == v2 == 2
