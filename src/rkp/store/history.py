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

    def query(
        self,
        *,
        claim_id: str | None = None,
        action: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[ClaimHistory]:
        """Query history with optional filters.

        Args:
            claim_id: Filter to a specific claim.
            action: Filter to a specific action type.
            since: ISO timestamp lower bound.
            limit: Max entries to return.
        """
        conditions: list[str] = []
        params: list[str | int] = []

        if claim_id is not None:
            conditions.append("claim_id = ?")
            params.append(claim_id)
        if action is not None:
            conditions.append("action = ?")
            params.append(action)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        query_sql = f"SELECT * FROM claim_history WHERE {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._db.execute(query_sql, params).fetchall()
        return [_row_to_history(r) for r in rows]

    def query_by_scope(
        self,
        scope: str,
        *,
        limit: int = 100,
    ) -> list[ClaimHistory]:
        """Query history for claims matching a scope prefix.

        Joins with claims table to filter by scope.
        """
        # Escape LIKE metacharacters in user-supplied scope
        escaped = scope.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = self._db.execute(
            """SELECT h.* FROM claim_history h
            JOIN claims c ON h.claim_id = c.id
            WHERE c.scope LIKE ? ESCAPE '\\' OR c.scope = '**'
            ORDER BY h.id DESC LIMIT ?""",
            (escaped + "%", limit),
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
