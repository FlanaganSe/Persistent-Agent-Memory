"""Tests for database connection factory and migration runner."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from rkp.store.database import (
    checkpoint_wal,
    get_user_version,
    open_database,
    run_migrations,
)


class TestOpenDatabase:
    def test_creates_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn = open_database(db_path)
        assert db_path.exists()
        conn.close()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        db_path = tmp_path / "deep" / "nested" / "test.db"
        conn = open_database(db_path)
        assert db_path.exists()
        conn.close()

    def test_wal_mode(self, tmp_path: Path) -> None:
        conn = open_database(tmp_path / "test.db")
        mode = conn.execute("PRAGMA journal_mode").fetchone()
        assert mode[0] == "wal"
        conn.close()

    def test_foreign_keys_on(self, tmp_path: Path) -> None:
        conn = open_database(tmp_path / "test.db")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()
        assert fk[0] == 1
        conn.close()

    def test_row_factory(self, tmp_path: Path) -> None:
        conn = open_database(tmp_path / "test.db")
        assert conn.row_factory is sqlite3.Row
        conn.close()


class TestRunMigrations:
    def test_fresh_db(self, tmp_path: Path) -> None:
        conn = open_database(tmp_path / "test.db")
        run_migrations(conn)
        version = get_user_version(conn)
        assert version == 1
        conn.close()

    def test_already_migrated(self, tmp_path: Path) -> None:
        conn = open_database(tmp_path / "test.db")
        run_migrations(conn)
        run_migrations(conn)  # should be idempotent
        version = get_user_version(conn)
        assert version == 1
        conn.close()

    def test_tables_created(self, tmp_path: Path) -> None:
        conn = open_database(tmp_path / "test.db")
        run_migrations(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {str(t[0]) for t in tables}
        # Check core tables (FTS5 subtable names vary by SQLite version)
        expected = {
            "claims",
            "claim_evidence",
            "claim_history",
            "claim_applicability",
            "managed_artifacts",
            "environment_profiles",
            "module_edges",
            "session_log",
        }
        assert expected.issubset(table_names)
        conn.close()


class TestCheckpointWal:
    def test_checkpoint(self, tmp_path: Path) -> None:
        conn = open_database(tmp_path / "test.db")
        run_migrations(conn)
        checkpoint_wal(conn)
        conn.close()


class TestConcurrentAccess:
    def test_concurrent_reader_writer(self, tmp_path: Path) -> None:
        """WAL mode allows concurrent reader and writer."""
        db_path = tmp_path / "test.db"
        setup_conn = open_database(db_path)
        run_migrations(setup_conn)
        setup_conn.close()

        errors: list[str] = []

        def write_claims() -> None:
            writer = open_database(db_path)
            try:
                for i in range(5):
                    writer.execute(
                        """INSERT INTO claims
                            (id, content, claim_type, source_authority,
                             authority_level, repo_id)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            f"claim-w{i}",
                            f"content-{i}",
                            "always-on-rule",
                            "inferred-high",
                            50,
                            "test",
                        ),
                    )
                    writer.commit()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"writer: {e}")
            finally:
                writer.close()

        def read_claims() -> None:
            reader = open_database(db_path)
            try:
                for _ in range(5):
                    reader.execute("SELECT COUNT(*) FROM claims").fetchone()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"reader: {e}")
            finally:
                reader.close()

        t_write = threading.Thread(target=write_claims)
        t_read = threading.Thread(target=read_claims)
        t_write.start()
        t_read.start()
        t_write.join()
        t_read.join()

        assert len(errors) == 0, f"Concurrent access errors: {errors}"
