"""Unit tests for SqliteArtifactStore artifact ownership and CRUD."""

from __future__ import annotations

import sqlite3

import pytest

from rkp.core.types import ArtifactOwnership
from rkp.store.artifacts import SqliteArtifactStore


class TestSqliteArtifactStoreRegister:
    """Register artifact with each ownership mode and verify persistence."""

    @pytest.mark.parametrize(
        "ownership",
        list(ArtifactOwnership),
        ids=[o.value for o in ArtifactOwnership],
    )
    def test_register_each_ownership_mode(
        self, db: sqlite3.Connection, ownership: ArtifactOwnership
    ) -> None:
        store = SqliteArtifactStore(db)
        store.register_artifact(
            path=f"test/{ownership.value}.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="abc123",
            ownership=ownership,
        )

        artifact = store.get_artifact(f"test/{ownership.value}.md")
        assert artifact is not None
        assert artifact.ownership_mode == ownership
        assert artifact.artifact_type == "instruction-file"
        assert artifact.target_host == "codex"
        assert artifact.expected_hash == "abc123"


class TestSqliteArtifactStoreGet:
    """get_artifact returns None for unknown paths."""

    def test_get_unknown_path_returns_none(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        assert store.get_artifact("nonexistent/path.md") is None


class TestSqliteArtifactStoreUpdateHash:
    """update_hash changes expected_hash."""

    def test_update_hash_changes_value(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        store.register_artifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="old_hash",
            ownership=ArtifactOwnership.IMPORTED_HUMAN_OWNED,
        )

        store.update_hash("AGENTS.md", "new_hash")

        artifact = store.get_artifact("AGENTS.md")
        assert artifact is not None
        assert artifact.expected_hash == "new_hash"

    def test_update_hash_changes_last_projected(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        store.register_artifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="old_hash",
            ownership=ArtifactOwnership.IMPORTED_HUMAN_OWNED,
        )
        before = store.get_artifact("AGENTS.md")
        assert before is not None

        store.update_hash("AGENTS.md", "new_hash")
        after = store.get_artifact("AGENTS.md")
        assert after is not None
        assert after.last_projected >= before.last_projected


class TestSqliteArtifactStoreList:
    """list_artifacts returns all artifacts or filtered by host."""

    def test_list_all_artifacts(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        store.register_artifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="h1",
            ownership=ArtifactOwnership.IMPORTED_HUMAN_OWNED,
        )
        store.register_artifact(
            path="CLAUDE.md",
            artifact_type="instruction-file",
            target_host="claude",
            expected_hash="h2",
            ownership=ArtifactOwnership.MANAGED_BY_RKP,
        )

        artifacts = store.list_artifacts()
        assert len(artifacts) == 2
        paths = {a.path for a in artifacts}
        assert paths == {"AGENTS.md", "CLAUDE.md"}

    def test_list_artifacts_with_host_filter(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        store.register_artifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="h1",
            ownership=ArtifactOwnership.IMPORTED_HUMAN_OWNED,
        )
        store.register_artifact(
            path="CLAUDE.md",
            artifact_type="instruction-file",
            target_host="claude",
            expected_hash="h2",
            ownership=ArtifactOwnership.MANAGED_BY_RKP,
        )

        codex_only = store.list_artifacts(host="codex")
        assert len(codex_only) == 1
        assert codex_only[0].path == "AGENTS.md"

        claude_only = store.list_artifacts(host="claude")
        assert len(claude_only) == 1
        assert claude_only[0].path == "CLAUDE.md"

    def test_list_artifacts_empty(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        assert store.list_artifacts() == []


class TestSqliteArtifactStoreDelete:
    """delete_artifact removes record."""

    def test_delete_removes_record(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        store.register_artifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="h1",
            ownership=ArtifactOwnership.IMPORTED_HUMAN_OWNED,
        )
        assert store.get_artifact("AGENTS.md") is not None

        store.delete_artifact("AGENTS.md")
        assert store.get_artifact("AGENTS.md") is None

    def test_delete_nonexistent_is_silent(self, db: sqlite3.Connection) -> None:
        store = SqliteArtifactStore(db)
        # Should not raise
        store.delete_artifact("nonexistent.md")


class TestOwnershipPersistence:
    """Ownership mode persists across store instantiation (same DB connection)."""

    def test_ownership_persists_across_store_instances(self, db: sqlite3.Connection) -> None:
        store1 = SqliteArtifactStore(db)
        store1.register_artifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="h1",
            ownership=ArtifactOwnership.MIXED_MIGRATION,
        )

        # Create a fresh store instance on the same connection
        store2 = SqliteArtifactStore(db)
        artifact = store2.get_artifact("AGENTS.md")
        assert artifact is not None
        assert artifact.ownership_mode == ArtifactOwnership.MIXED_MIGRATION
