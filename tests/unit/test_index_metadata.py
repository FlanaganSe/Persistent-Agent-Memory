"""Unit tests for index metadata persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rkp.store.database import open_database, run_migrations
from rkp.store.metadata import IndexMetadata, SqliteMetadataStore


@pytest.fixture
def fresh_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "test.db")
    run_migrations(db)
    return db


class TestIndexMetadata:
    def test_save_and_load(self, fresh_db: sqlite3.Connection) -> None:
        store = SqliteMetadataStore(fresh_db)
        meta = IndexMetadata(
            last_indexed="2026-03-18T19:22:00Z",
            repo_head="abc1234",
            branch="main",
            file_count=100,
            claim_count=50,
        )
        store.save(meta)
        loaded = store.load()

        assert loaded is not None
        assert loaded.last_indexed == "2026-03-18T19:22:00Z"
        assert loaded.repo_head == "abc1234"
        assert loaded.branch == "main"
        assert loaded.file_count == 100
        assert loaded.claim_count == 50

    def test_update_on_refresh(self, fresh_db: sqlite3.Connection) -> None:
        store = SqliteMetadataStore(fresh_db)
        store.save(
            IndexMetadata(
                last_indexed="2026-03-18T19:22:00Z",
                repo_head="abc1234",
                branch="main",
                file_count=100,
                claim_count=50,
            )
        )
        store.save(
            IndexMetadata(
                last_indexed="2026-03-19T10:00:00Z",
                repo_head="def5678",
                branch="main",
                file_count=110,
                claim_count=55,
            )
        )
        loaded = store.load()

        assert loaded is not None
        assert loaded.last_indexed == "2026-03-19T10:00:00Z"
        assert loaded.repo_head == "def5678"
        assert loaded.file_count == 110

    def test_missing_metadata_returns_none(self, fresh_db: sqlite3.Connection) -> None:
        store = SqliteMetadataStore(fresh_db)
        loaded = store.load()
        assert loaded is None

    def test_round_trip_fidelity(self, fresh_db: sqlite3.Connection) -> None:
        store = SqliteMetadataStore(fresh_db)
        meta = IndexMetadata(
            last_indexed="2026-03-18T19:22:00.123Z",
            repo_head="a" * 40,
            branch="feature/long-branch-name",
            file_count=99999,
            claim_count=1000,
        )
        store.save(meta)
        loaded = store.load()
        assert loaded == meta

    def test_now_iso_returns_string(self) -> None:
        result = SqliteMetadataStore.now_iso()
        assert isinstance(result, str)
        assert "T" in result
