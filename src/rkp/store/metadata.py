"""Index metadata persistence for freshness tracking."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class IndexMetadata:
    """Snapshot of index state at last extraction."""

    last_indexed: str
    repo_head: str
    branch: str
    file_count: int
    claim_count: int


class SqliteMetadataStore:
    """SQLite-backed index metadata store (single-row table)."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def save(self, metadata: IndexMetadata) -> None:
        """Upsert the index metadata (single row, id=1)."""
        self._db.execute(
            """INSERT INTO index_metadata (id, last_indexed, repo_head, branch, file_count, claim_count)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_indexed = excluded.last_indexed,
                repo_head = excluded.repo_head,
                branch = excluded.branch,
                file_count = excluded.file_count,
                claim_count = excluded.claim_count""",
            (
                metadata.last_indexed,
                metadata.repo_head,
                metadata.branch,
                metadata.file_count,
                metadata.claim_count,
            ),
        )
        self._db.commit()

    def load(self) -> IndexMetadata | None:
        """Load the index metadata, or None if never indexed."""
        row = self._db.execute("SELECT * FROM index_metadata WHERE id = 1").fetchone()
        if row is None:
            return None
        return IndexMetadata(
            last_indexed=str(row["last_indexed"]),
            repo_head=str(row["repo_head"]),
            branch=str(row["branch"]),
            file_count=int(row["file_count"]),
            claim_count=int(row["claim_count"]),
        )

    @staticmethod
    def now_iso() -> str:
        """Current UTC timestamp in ISO 8601 format."""
        return datetime.now(UTC).isoformat()
