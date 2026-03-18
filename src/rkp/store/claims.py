"""ClaimStore: CRUD, scope filtering, and precedence ordering for claims."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Protocol

from rkp.core.errors import ClaimNotFoundError, DuplicateClaimError
from rkp.core.models import Claim, Provenance
from rkp.core.types import (
    ClaimType,
    ReviewState,
    RiskClass,
    Sensitivity,
    SourceAuthority,
    source_authority_precedence,
)


class ClaimStore(Protocol):
    """Protocol for claim storage operations."""

    def save(self, claim: Claim) -> None: ...
    def get(self, claim_id: str) -> Claim | None: ...
    def list_claims(
        self,
        *,
        scope: str | None = None,
        claim_type: ClaimType | None = None,
        review_state: ReviewState | None = None,
        repo_id: str | None = None,
    ) -> list[Claim]: ...
    def delete(self, claim_id: str) -> None: ...
    def get_by_precedence(
        self, *, scope: str | None = None, repo_id: str | None = None
    ) -> list[Claim]: ...
    def update(self, claim: Claim) -> None: ...


class SqliteClaimStore:
    """SQLite-backed claim store."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def save(self, claim: Claim) -> None:
        """Insert a new claim. Raises DuplicateClaimError if ID exists."""
        existing = self.get(claim.id)
        if existing is not None:
            raise DuplicateClaimError(claim.id)
        self._insert(claim)

    def get(self, claim_id: str) -> Claim | None:
        """Retrieve a claim by ID, or None if not found."""
        row = self._db.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if row is None:
            return None
        return _row_to_claim(row)

    def list_claims(
        self,
        *,
        scope: str | None = None,
        claim_type: ClaimType | None = None,
        review_state: ReviewState | None = None,
        repo_id: str | None = None,
    ) -> list[Claim]:
        """List claims with optional filtering."""
        conditions: list[str] = []
        params: list[str] = []

        if scope is not None:
            conditions.append("scope = ?")
            params.append(scope)
        if claim_type is not None:
            conditions.append("claim_type = ?")
            params.append(claim_type.value)
        if review_state is not None:
            conditions.append("review_state = ?")
            params.append(review_state.value)
        if repo_id is not None:
            conditions.append("repo_id = ?")
            params.append(repo_id)

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM claims WHERE {where}"
        rows = self._db.execute(query, params).fetchall()
        return [_row_to_claim(r) for r in rows]

    def delete(self, claim_id: str) -> None:
        """Delete a claim by ID. Raises ClaimNotFoundError if not found."""
        existing = self.get(claim_id)
        if existing is None:
            raise ClaimNotFoundError(claim_id)
        self._db.execute("DELETE FROM claim_applicability WHERE claim_id = ?", (claim_id,))
        self._db.execute("DELETE FROM claims WHERE id = ?", (claim_id,))
        self._db.commit()

    def get_by_precedence(
        self, *, scope: str | None = None, repo_id: str | None = None
    ) -> list[Claim]:
        """Get claims ordered by source authority precedence (highest first)."""
        conditions: list[str] = []
        params: list[str] = []

        if scope is not None:
            conditions.append("scope = ?")
            params.append(scope)
        if repo_id is not None:
            conditions.append("repo_id = ?")
            params.append(repo_id)

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM claims WHERE {where} ORDER BY authority_level ASC, confidence DESC"
        rows = self._db.execute(query, params).fetchall()
        return [_row_to_claim(r) for r in rows]

    def update(self, claim: Claim) -> None:
        """Update an existing claim. Raises ClaimNotFoundError if not found."""
        existing = self.get(claim.id)
        if existing is None:
            raise ClaimNotFoundError(claim.id)
        self._db.execute(
            """UPDATE claims SET
                content = ?, claim_type = ?, source_authority = ?,
                authority_level = ?, scope = ?, applicability = ?,
                sensitivity = ?, review_state = ?, confidence = ?,
                evidence = ?, provenance = ?, risk_class = ?,
                projection_targets = ?, repo_id = ?, branch = ?,
                worktree_id = ?, session_id = ?, last_validated = ?,
                revalidation_trigger = ?, stale = ?, updated_at = ?
            WHERE id = ?""",
            (
                claim.content,
                claim.claim_type.value,
                claim.source_authority.value,
                source_authority_precedence(claim.source_authority),
                claim.scope,
                json.dumps(list(claim.applicability)),
                claim.sensitivity.value,
                claim.review_state.value,
                claim.confidence,
                json.dumps(list(claim.evidence)),
                json.dumps(asdict(claim.provenance)),
                claim.risk_class.value if claim.risk_class else None,
                json.dumps(list(claim.projection_targets)),
                claim.repo_id,
                claim.branch,
                claim.worktree_id,
                claim.session_id,
                claim.last_validated.isoformat() if claim.last_validated else None,
                claim.revalidation_trigger,
                int(claim.stale),
                datetime.now(UTC).isoformat(),
                claim.id,
            ),
        )
        self._db.execute("DELETE FROM claim_applicability WHERE claim_id = ?", (claim.id,))
        _insert_applicability(self._db, claim)
        self._db.commit()

    def _insert(self, claim: Claim) -> None:
        """Insert a claim into the database."""
        self._db.execute(
            """INSERT INTO claims (
                id, content, claim_type, source_authority, authority_level,
                scope, applicability, sensitivity, review_state, confidence,
                evidence, provenance, risk_class, projection_targets,
                repo_id, branch, worktree_id, session_id,
                last_validated, revalidation_trigger, stale,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                claim.id,
                claim.content,
                claim.claim_type.value,
                claim.source_authority.value,
                source_authority_precedence(claim.source_authority),
                claim.scope,
                json.dumps(list(claim.applicability)),
                claim.sensitivity.value,
                claim.review_state.value,
                claim.confidence,
                json.dumps(list(claim.evidence)),
                json.dumps(asdict(claim.provenance)),
                claim.risk_class.value if claim.risk_class else None,
                json.dumps(list(claim.projection_targets)),
                claim.repo_id,
                claim.branch,
                claim.worktree_id,
                claim.session_id,
                claim.last_validated.isoformat() if claim.last_validated else None,
                claim.revalidation_trigger,
                int(claim.stale),
                claim.created_at.isoformat()
                if claim.created_at
                else datetime.now(UTC).isoformat(),
                claim.updated_at.isoformat()
                if claim.updated_at
                else datetime.now(UTC).isoformat(),
            ),
        )
        _insert_applicability(self._db, claim)
        self._db.commit()


def _insert_applicability(db: sqlite3.Connection, claim: Claim) -> None:
    """Insert applicability tags for a claim."""
    for tag in claim.applicability:
        db.execute(
            "INSERT OR IGNORE INTO claim_applicability (claim_id, tag) VALUES (?, ?)",
            (claim.id, tag),
        )


def _row_to_claim(row: sqlite3.Row) -> Claim:
    """Convert a database row to a Claim domain object."""
    applicability_raw: str = row["applicability"]  # type: ignore[assignment]
    evidence_raw: str = row["evidence"]  # type: ignore[assignment]
    provenance_raw: str = row["provenance"]  # type: ignore[assignment]
    projection_raw: str = row["projection_targets"]  # type: ignore[assignment]

    provenance_dict: dict[str, str] = json.loads(provenance_raw)
    last_validated_str: str | None = row["last_validated"]  # type: ignore[assignment]

    return Claim(
        id=str(row["id"]),
        content=str(row["content"]),
        claim_type=ClaimType(str(row["claim_type"])),
        source_authority=SourceAuthority(str(row["source_authority"])),
        scope=str(row["scope"]),
        applicability=tuple(json.loads(applicability_raw)),
        sensitivity=Sensitivity(str(row["sensitivity"])),
        review_state=ReviewState(str(row["review_state"])),
        confidence=float(row["confidence"]),  # type: ignore[arg-type]
        evidence=tuple(json.loads(evidence_raw)),
        provenance=Provenance(**{k: str(v) for k, v in provenance_dict.items()}),
        risk_class=RiskClass(str(row["risk_class"])) if row["risk_class"] else None,
        projection_targets=tuple(json.loads(projection_raw)),
        repo_id=str(row["repo_id"]),
        branch=str(row["branch"]),
        worktree_id=str(row["worktree_id"]) if row["worktree_id"] else None,
        session_id=str(row["session_id"]) if row["session_id"] else None,
        last_validated=datetime.fromisoformat(last_validated_str) if last_validated_str else None,
        revalidation_trigger=str(row["revalidation_trigger"])
        if row["revalidation_trigger"]
        else None,
        stale=bool(row["stale"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )
