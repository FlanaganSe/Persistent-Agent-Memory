"""Integration tests for drift detection correctness."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from rkp.core.types import ArtifactOwnership
from rkp.importer.parsers.markdown_utils import compute_content_hash
from rkp.store.artifacts import SqliteArtifactStore
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def drift_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "drift.db"
    db = open_database(db_path)
    run_migrations(db)
    return db


class TestDriftDetection:
    def test_with_drift_fixture(self, drift_db: sqlite3.Connection) -> None:
        """with_drift fixture: drift detection produces correct report."""
        drift_fixture = Path("tests/fixtures/with_drift")
        if not drift_fixture.exists():
            pytest.skip("with_drift fixture not available")

        setup_path = drift_fixture / "drift_setup.json"
        with setup_path.open() as f:
            drift_data = json.load(f)

        artifact_store = SqliteArtifactStore(drift_db)
        for artifact in drift_data["artifacts"]:
            artifact_store.register_artifact(
                path=artifact["path"],
                artifact_type=artifact["artifact_type"],
                target_host=artifact["target_host"],
                expected_hash=artifact["expected_hash"],
                ownership=ArtifactOwnership(artifact["ownership"]),
            )

        report = artifact_store.detect_drift(drift_fixture)

        expected_drift_count = drift_data["expected_drift_count"]
        assert len(report.content_drifts) == expected_drift_count
        # AGENTS.md should drift, CLAUDE.md should be clean
        drifted_paths = {d.path for d in report.content_drifts}
        assert "AGENTS.md" in drifted_paths
        assert "CLAUDE.md" not in drifted_paths

    def test_no_false_drifts_on_clean_files(
        self, drift_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Files with correct hashes should not trigger drift."""
        clean_file = tmp_path / "AGENTS.md"
        clean_content = "# Clean file\n\nNo changes here.\n"
        clean_file.write_text(clean_content)

        expected_hash = compute_content_hash(clean_content)
        artifact_store = SqliteArtifactStore(drift_db)
        artifact_store.register_artifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="agents-md",
            expected_hash=expected_hash,
            ownership=ArtifactOwnership.MANAGED_BY_RKP,
        )

        report = artifact_store.detect_drift(tmp_path)
        assert len(report.content_drifts) == 0
        assert "AGENTS.md" in report.clean_files

    def test_whitespace_normalization(self, drift_db: sqlite3.Connection, tmp_path: Path) -> None:
        """Normalized hash comparison uses the same normalization."""
        content = "# Test\n\nSome content\n"
        file_path = tmp_path / "test.md"
        file_path.write_text(content)

        expected_hash = compute_content_hash(content)
        artifact_store = SqliteArtifactStore(drift_db)
        artifact_store.register_artifact(
            path="test.md",
            artifact_type="instruction-file",
            target_host="agents-md",
            expected_hash=expected_hash,
            ownership=ArtifactOwnership.MANAGED_BY_RKP,
        )

        report = artifact_store.detect_drift(tmp_path)
        assert len(report.content_drifts) == 0
