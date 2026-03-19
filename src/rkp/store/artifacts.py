"""Managed artifact tracking with ownership modes and drift detection."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import structlog

from rkp.core.models import ManagedArtifact
from rkp.core.types import ArtifactOwnership
from rkp.importer.models import ContentDrift, DriftReport
from rkp.importer.parsers.markdown_utils import compute_content_hash

logger = structlog.get_logger()

# Known instruction file patterns for unmanaged file detection.
_INSTRUCTION_FILE_PATTERNS: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".cursorrules",
)

_INSTRUCTION_DIR_PATTERNS: tuple[str, ...] = (
    ".cursor/rules",
    ".github/instructions",
    ".windsurf/rules",
)


class ArtifactStore(Protocol):
    """Protocol for managed artifact storage operations."""

    def register_artifact(
        self,
        path: str,
        artifact_type: str,
        target_host: str,
        expected_hash: str,
        ownership: ArtifactOwnership,
    ) -> None: ...

    def get_artifact(self, path: str) -> ManagedArtifact | None: ...

    def update_hash(self, path: str, new_hash: str) -> None: ...

    def list_artifacts(self, *, host: str | None = None) -> list[ManagedArtifact]: ...

    def delete_artifact(self, path: str) -> None: ...

    def detect_drift(self, repo_root: Path) -> DriftReport: ...


class SqliteArtifactStore:
    """SQLite-backed managed artifact store with drift detection."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def register_artifact(
        self,
        path: str,
        artifact_type: str,
        target_host: str,
        expected_hash: str,
        ownership: ArtifactOwnership,
    ) -> None:
        """Register or update a managed artifact record."""
        now = datetime.now(UTC).isoformat()
        self._db.execute(
            """INSERT OR REPLACE INTO managed_artifacts
               (path, artifact_type, target_host, expected_hash, last_projected, ownership_mode)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (path, artifact_type, target_host, expected_hash, now, ownership.value),
        )
        self._db.commit()

    def get_artifact(self, path: str) -> ManagedArtifact | None:
        """Retrieve a managed artifact by path."""
        row = self._db.execute(
            "SELECT * FROM managed_artifacts WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_artifact(row)

    def update_hash(self, path: str, new_hash: str) -> None:
        """Update the expected hash of a managed artifact."""
        now = datetime.now(UTC).isoformat()
        self._db.execute(
            "UPDATE managed_artifacts SET expected_hash = ?, last_projected = ? WHERE path = ?",
            (new_hash, now, path),
        )
        self._db.commit()

    def list_artifacts(self, *, host: str | None = None) -> list[ManagedArtifact]:
        """List all managed artifacts, optionally filtered by host."""
        if host is not None:
            rows = self._db.execute(
                "SELECT * FROM managed_artifacts WHERE target_host = ? ORDER BY path",
                (host,),
            ).fetchall()
        else:
            rows = self._db.execute("SELECT * FROM managed_artifacts ORDER BY path").fetchall()
        return [_row_to_artifact(r) for r in rows]

    def delete_artifact(self, path: str) -> None:
        """Remove a managed artifact record (suppress tracking)."""
        self._db.execute("DELETE FROM managed_artifacts WHERE path = ?", (path,))
        self._db.commit()

    def detect_drift(self, repo_root: Path) -> DriftReport:
        """Detect drift across all managed artifacts and find unmanaged instruction files.

        Returns a DriftReport with:
        - content_drifts: files whose hash doesn't match expected
        - new_unmanaged: instruction files found but not tracked
        - missing_files: tracked files that no longer exist
        - clean_files: tracked files with matching hashes
        """
        artifacts = self.list_artifacts()
        tracked_paths = {a.path for a in artifacts}

        content_drifts: list[ContentDrift] = []
        missing_files: list[str] = []
        clean_files: list[str] = []

        for artifact in artifacts:
            abs_path = repo_root / artifact.path
            if not abs_path.exists():
                missing_files.append(artifact.path)
                continue

            try:
                file_content = abs_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                missing_files.append(artifact.path)
                continue

            actual_hash = compute_content_hash(file_content)
            if actual_hash != artifact.expected_hash:
                content_drifts.append(
                    ContentDrift(
                        path=artifact.path,
                        expected_hash=artifact.expected_hash,
                        actual_hash=actual_hash,
                        ownership_mode=artifact.ownership_mode.value,
                    )
                )
            else:
                clean_files.append(artifact.path)

        # Discover unmanaged instruction files
        new_unmanaged = _discover_unmanaged_instruction_files(repo_root, tracked_paths)

        return DriftReport(
            content_drifts=tuple(content_drifts),
            new_unmanaged=tuple(new_unmanaged),
            missing_files=tuple(missing_files),
            clean_files=tuple(clean_files),
        )


def _row_to_artifact(row: sqlite3.Row) -> ManagedArtifact:
    """Convert a database row to a ManagedArtifact domain object."""
    return ManagedArtifact(
        path=str(row["path"]),
        artifact_type=str(row["artifact_type"]),
        target_host=str(row["target_host"]),
        expected_hash=str(row["expected_hash"]),
        last_projected=str(row["last_projected"]),
        ownership_mode=ArtifactOwnership(str(row["ownership_mode"])),
    )


def _discover_unmanaged_instruction_files(
    repo_root: Path,
    tracked_paths: set[str],
) -> list[str]:
    """Find instruction files in the repo that are not tracked by RKP."""
    unmanaged: list[str] = []

    # Check known file patterns
    for pattern in _INSTRUCTION_FILE_PATTERNS:
        abs_path = repo_root / pattern
        if abs_path.is_file() and pattern not in tracked_paths:
            unmanaged.append(pattern)

    # Check for nested AGENTS.md / CLAUDE.md
    for md_name in ("AGENTS.md", "CLAUDE.md"):
        for found in repo_root.rglob(md_name):
            rel = str(found.relative_to(repo_root))
            if rel not in tracked_paths and rel != md_name:
                unmanaged.append(rel)

    # Check known directory patterns
    for dir_pattern in _INSTRUCTION_DIR_PATTERNS:
        dir_path = repo_root / dir_pattern
        if dir_path.is_dir():
            for found in dir_path.rglob("*"):
                if found.is_file():
                    rel = str(found.relative_to(repo_root))
                    if rel not in tracked_paths:
                        unmanaged.append(rel)

    # Check .github/instructions/*.instructions.md
    instructions_dir = repo_root / ".github" / "instructions"
    if instructions_dir.is_dir():
        for found in instructions_dir.rglob("*.instructions.md"):
            rel = str(found.relative_to(repo_root))
            if rel not in tracked_paths:
                unmanaged.append(rel)

    return sorted(set(unmanaged))
