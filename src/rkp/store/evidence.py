"""Evidence chain storage and retrieval."""

from __future__ import annotations

import sqlite3

from rkp.core.models import Evidence
from rkp.core.types import EvidenceLevel


class SqliteEvidenceStore:
    """SQLite-backed evidence store."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def save(self, evidence: Evidence) -> int:
        """Insert an evidence record. Returns the new row ID."""
        cursor = self._db.execute(
            """INSERT INTO claim_evidence
                (claim_id, file_path, file_hash, line_start, line_end,
                 evidence_level, extraction_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                evidence.claim_id,
                evidence.file_path,
                evidence.file_hash,
                evidence.line_start,
                evidence.line_end,
                evidence.evidence_level.value,
                evidence.extraction_version,
            ),
        )
        self._db.commit()
        return cursor.lastrowid or 0

    def get_for_claim(self, claim_id: str) -> list[Evidence]:
        """Retrieve all evidence records for a claim."""
        rows = self._db.execute(
            "SELECT * FROM claim_evidence WHERE claim_id = ? ORDER BY id",
            (claim_id,),
        ).fetchall()
        return [_row_to_evidence(r) for r in rows]

    def get_by_file(self, file_path: str) -> list[Evidence]:
        """Retrieve all evidence records referencing a file."""
        rows = self._db.execute(
            "SELECT * FROM claim_evidence WHERE file_path = ? ORDER BY id",
            (file_path,),
        ).fetchall()
        return [_row_to_evidence(r) for r in rows]

    def delete_for_claim(self, claim_id: str) -> int:
        """Delete all evidence for a claim. Returns count deleted."""
        cursor = self._db.execute("DELETE FROM claim_evidence WHERE claim_id = ?", (claim_id,))
        self._db.commit()
        return cursor.rowcount


def _row_to_evidence(row: sqlite3.Row) -> Evidence:
    """Convert a database row to an Evidence domain object."""
    return Evidence(
        claim_id=str(row["claim_id"]),
        file_path=str(row["file_path"]),
        file_hash=str(row["file_hash"]),
        extraction_version=str(row["extraction_version"]),
        line_start=int(row["line_start"]) if row["line_start"] is not None else None,
        line_end=int(row["line_end"]) if row["line_end"] is not None else None,
        evidence_level=EvidenceLevel(str(row["evidence_level"])),
        id=int(row["id"]),  # type: ignore[arg-type]
    )
