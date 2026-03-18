"""Append-only audit trail for claim actions."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from rkp.core.models import ClaimHistory


class SqliteHistoryStore:
    """SQLite-backed append-only history store."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def record(
        self,
        *,
        claim_id: str,
        action: str,
        content_before: str | None = None,
        content_after: str | None = None,
        actor: str = "system",
        reason: str | None = None,
    ) -> int:
        """Append a history entry. Returns the new row ID."""
        cursor = self._db.execute(
            """INSERT INTO claim_history
                (claim_id, action, content_before, content_after, actor, reason)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (claim_id, action, content_before, content_after, actor, reason),
        )
        self._db.commit()
        return cursor.lastrowid or 0

    def get_for_claim(self, claim_id: str) -> list[ClaimHistory]:
        """Retrieve the full audit trail for a claim, oldest first."""
        rows = self._db.execute(
            "SELECT * FROM claim_history WHERE claim_id = ? ORDER BY id ASC",
            (claim_id,),
        ).fetchall()
        return [_row_to_history(r) for r in rows]

    def get_all(self, *, limit: int = 100) -> list[ClaimHistory]:
        """Retrieve recent history entries across all claims."""
        rows = self._db.execute(
            "SELECT * FROM claim_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_history(r) for r in rows]


def _row_to_history(row: sqlite3.Row) -> ClaimHistory:
    """Convert a database row to a ClaimHistory domain object."""
    ts_str: str | None = row["timestamp"]  # type: ignore[assignment]
    return ClaimHistory(
        claim_id=str(row["claim_id"]),
        action=str(row["action"]),
        content_before=str(row["content_before"]) if row["content_before"] is not None else None,
        content_after=str(row["content_after"]) if row["content_after"] is not None else None,
        actor=str(row["actor"]),
        timestamp=datetime.fromisoformat(ts_str) if ts_str else None,
        reason=str(row["reason"]) if row["reason"] is not None else None,
        id=int(row["id"]),  # type: ignore[arg-type]
    )
