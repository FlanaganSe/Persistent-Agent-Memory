"""Unit tests for drift detection in SqliteArtifactStore."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from rkp.core.types import ArtifactOwnership
from rkp.importer.parsers.markdown_utils import compute_content_hash
from rkp.store.artifacts import SqliteArtifactStore


def _register_file(
    store: SqliteArtifactStore,
    repo_root: Path,
    rel_path: str,
    content: str,
    ownership: ArtifactOwnership = ArtifactOwnership.IMPORTED_HUMAN_OWNED,
) -> None:
    """Helper: write a file and register its hash in the store."""
    abs_path = repo_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content, encoding="utf-8")
    store.register_artifact(
        path=rel_path,
        artifact_type="instruction-file",
        target_host="codex",
        expected_hash=compute_content_hash(content),
        ownership=ownership,
    )


class TestDriftClean:
    """Managed file unchanged produces no drift."""

    def test_managed_file_unchanged_is_clean(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        content = "# AGENTS.md\n\n- Always use pytest\n"

        store = SqliteArtifactStore(db)
        _register_file(store, repo_root, "AGENTS.md", content)

        report = store.detect_drift(repo_root)
        assert len(report.content_drifts) == 0
        assert len(report.missing_files) == 0
        assert "AGENTS.md" in report.clean_files


class TestDriftContentChanged:
    """Managed file content changed triggers content drift."""

    def test_content_change_detected(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        original = "# AGENTS.md\n\n- Always use pytest\n"

        store = SqliteArtifactStore(db)
        _register_file(store, repo_root, "AGENTS.md", original)

        # Modify the file
        (repo_root / "AGENTS.md").write_text(
            "# AGENTS.md\n\n- Always use unittest\n", encoding="utf-8"
        )

        report = store.detect_drift(repo_root)
        assert len(report.content_drifts) == 1
        assert report.content_drifts[0].path == "AGENTS.md"
        assert report.content_drifts[0].expected_hash == compute_content_hash(original)
        assert report.content_drifts[0].actual_hash != report.content_drifts[0].expected_hash


class TestDriftMissingFile:
    """Managed file deleted triggers missing file detection."""

    def test_deleted_file_detected(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        content = "# AGENTS.md\n\n- Always use pytest\n"

        store = SqliteArtifactStore(db)
        _register_file(store, repo_root, "AGENTS.md", content)

        # Delete the file
        (repo_root / "AGENTS.md").unlink()

        report = store.detect_drift(repo_root)
        assert "AGENTS.md" in report.missing_files
        assert len(report.content_drifts) == 0
        assert "AGENTS.md" not in report.clean_files


class TestDriftNewUnmanaged:
    """New instruction file appeared but is not tracked."""

    def test_new_unmanaged_file_detected(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        store = SqliteArtifactStore(db)

        # Create an AGENTS.md that is NOT registered
        (repo_root / "AGENTS.md").write_text(
            "# AGENTS.md\n\n- Use ruff for linting\n", encoding="utf-8"
        )

        report = store.detect_drift(repo_root)
        assert "AGENTS.md" in report.new_unmanaged


class TestDriftHashNormalization:
    """Hash normalization: trailing whitespace and line-ending differences are not drift."""

    def test_trailing_whitespace_not_flagged(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Original content
        original = "# AGENTS.md\n\n- Always use pytest\n"
        store = SqliteArtifactStore(db)
        _register_file(store, repo_root, "AGENTS.md", original)

        # Rewrite with trailing spaces on lines (normalized away by compute_content_hash)
        with_trailing = "# AGENTS.md  \n\n- Always use pytest  \n"
        (repo_root / "AGENTS.md").write_text(with_trailing, encoding="utf-8")

        report = store.detect_drift(repo_root)
        assert len(report.content_drifts) == 0
        assert "AGENTS.md" in report.clean_files

    def test_crlf_vs_lf_not_flagged(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Original with LF
        original = "# AGENTS.md\n\n- Always use pytest\n"
        store = SqliteArtifactStore(db)
        _register_file(store, repo_root, "AGENTS.md", original)

        # Rewrite with CRLF (normalized away by compute_content_hash)
        crlf_content = "# AGENTS.md\r\n\r\n- Always use pytest\r\n"
        (repo_root / "AGENTS.md").write_bytes(crlf_content.encode("utf-8"))

        report = store.detect_drift(repo_root)
        assert len(report.content_drifts) == 0
        assert "AGENTS.md" in report.clean_files


class TestDriftEmptyStore:
    """Empty managed_artifacts produces no drift (nothing tracked)."""

    def test_empty_store_no_drift(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        store = SqliteArtifactStore(db)
        report = store.detect_drift(repo_root)

        assert len(report.content_drifts) == 0
        assert len(report.missing_files) == 0
        assert len(report.clean_files) == 0
        # new_unmanaged may or may not be empty depending on files in repo_root
