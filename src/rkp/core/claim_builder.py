"""Deterministic claim construction, deduplication, and conflict detection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from rkp.core.ids import generate_claim_id
from rkp.core.models import Claim, Provenance
from rkp.core.types import ClaimType, ReviewState, Sensitivity, SourceAuthority


@dataclass(frozen=True)
class ConflictPair:
    """Two claims that conflict on the same type and scope."""

    claim_a: Claim
    claim_b: Claim
    reason: str


class ClaimBuilder:
    """Builds claims deterministically from extractor output."""

    def __init__(self, repo_id: str, branch: str = "main") -> None:
        self._repo_id = repo_id
        self._branch = branch

    def build(
        self,
        *,
        content: str,
        claim_type: ClaimType,
        source_authority: SourceAuthority,
        scope: str = "**",
        applicability: tuple[str, ...] = (),
        sensitivity: Sensitivity = Sensitivity.PUBLIC,
        confidence: float = 0.0,
        evidence: tuple[str, ...] = (),
        provenance: Provenance | None = None,
        projection_targets: tuple[str, ...] = (),
        worktree_id: str | None = None,
        session_id: str | None = None,
    ) -> Claim:
        """Build a claim with a deterministic content-addressable ID."""
        claim_id = generate_claim_id(claim_type.value, scope, content)
        now = datetime.now(UTC)
        return Claim(
            id=claim_id,
            content=content,
            claim_type=claim_type,
            source_authority=source_authority,
            scope=scope,
            applicability=applicability,
            sensitivity=sensitivity,
            review_state=ReviewState.UNREVIEWED,
            confidence=confidence,
            evidence=evidence,
            provenance=provenance or Provenance(),
            projection_targets=projection_targets,
            repo_id=self._repo_id,
            branch=self._branch,
            worktree_id=worktree_id,
            session_id=session_id,
            last_validated=now,
            stale=False,
            created_at=now,
            updated_at=now,
        )

    def deduplicate(
        self,
        new_claims: Sequence[Claim],
        existing_claims: Sequence[Claim],
    ) -> tuple[list[Claim], list[Claim]]:
        """Separate new claims into unique and duplicate lists.

        A claim is a duplicate if an existing claim has the same ID
        (same claim_type + scope + content).

        Returns (unique, duplicates).
        """
        existing_ids = {c.id for c in existing_claims}
        unique: list[Claim] = []
        duplicates: list[Claim] = []
        seen: set[str] = set()

        for claim in new_claims:
            if claim.id in existing_ids or claim.id in seen:
                duplicates.append(claim)
            else:
                unique.append(claim)
                seen.add(claim.id)

        return unique, duplicates

    def detect_conflicts(self, claims: Sequence[Claim]) -> list[ConflictPair]:
        """Detect claims that conflict on the same type and scope.

        Two claims conflict when they share the same claim_type and scope
        but have different content.
        """
        by_type_scope: defaultdict[tuple[ClaimType, str], list[Claim]] = defaultdict(list)
        for claim in claims:
            by_type_scope[(claim.claim_type, claim.scope)].append(claim)

        conflicts: list[ConflictPair] = []
        for group in by_type_scope.values():
            if len(group) < 2:
                continue
            for i, a in enumerate(group):
                conflicts.extend(
                    ConflictPair(
                        claim_a=a,
                        claim_b=b,
                        reason=f"Same type '{a.claim_type}' and scope '{a.scope}' "
                        "but different content",
                    )
                    for b in group[i + 1 :]
                    if a.content != b.content
                )

        return conflicts

    def merge_claim(self, existing: Claim, update: Claim) -> Claim:
        """Merge an updated claim into an existing one, preserving the original ID."""
        now = datetime.now(UTC)
        return replace(
            existing,
            content=update.content,
            source_authority=update.source_authority,
            confidence=update.confidence,
            evidence=update.evidence,
            provenance=update.provenance,
            last_validated=now,
            updated_at=now,
            stale=False,
        )
