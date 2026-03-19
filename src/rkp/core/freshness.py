"""Freshness tracking: evidence-triggered, branch-aware, time-based stale detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rkp.core.config import RkpConfig
from rkp.core.models import Claim
from rkp.git.backend import GitBackend
from rkp.store.claims import ClaimStore
from rkp.store.evidence import SqliteEvidenceStore
from rkp.store.metadata import IndexMetadata


@dataclass(frozen=True)
class FreshnessState:
    """Freshness evaluation result for a single claim."""

    last_validated: str
    revalidation_trigger: str | None
    stale: bool
    staleness_reason: str | None
    evidence_current: bool
    days_since_validation: int


@dataclass(frozen=True)
class FreshnessReport:
    """Summary of freshness evaluation across all claims."""

    total_claims: int
    fresh_claims: int
    stale_claims: int
    stale_by_trigger: dict[str, int]
    stale_claim_ids: list[str]
    stale_details: dict[str, FreshnessState]
    branch_current: str
    branch_at_index: str
    branch_changed: bool
    head_current: str
    head_at_index: str
    head_changed: bool


def effective_confidence(claim: Claim, config: RkpConfig) -> float:
    """Compute effective confidence, reduced if claim is stale.

    Multiplicative reduction: confidence * (1 - reduction_factor).
    """
    if not claim.stale:
        return claim.confidence
    return claim.confidence * (1.0 - config.confidence_reduction_on_stale)


def _check_evidence_via_git_diff(
    claim: Claim,
    git: GitBackend,
    index_metadata: IndexMetadata,
    last_validated_str: str,
    days_since: int,
    file_hash_cache: dict[str, str | None],
) -> FreshnessState:
    """Fallback freshness check using git diff between indexed HEAD and current HEAD.

    Used when claim_evidence table has no records for this claim but the claim
    has evidence file paths stored in its evidence tuple.
    """
    current_head = git.head()
    if current_head == index_metadata.repo_head:
        # Same HEAD — no files could have changed
        return FreshnessState(
            last_validated=last_validated_str,
            revalidation_trigger=None,
            stale=False,
            staleness_reason=None,
            evidence_current=True,
            days_since_validation=days_since,
        )

    # Get the set of files changed between indexed HEAD and current HEAD
    cache_key = f"__diff__{index_metadata.repo_head}__{current_head}"
    if cache_key in file_hash_cache:
        # We cached the diff result set as a comma-separated string
        changed_set = set(str(file_hash_cache[cache_key] or "").split(","))
    else:
        changed_set = git.changed_files_between(index_metadata.repo_head, current_head)
        # Store in cache as comma-separated (cache values are str | None)
        file_hash_cache[cache_key] = ",".join(changed_set) if changed_set else ""

    # Normalize evidence paths (some may be absolute, some relative)
    repo_root_str = str(git.repo_root())
    changed_evidence: list[str] = []
    for ev_path in claim.evidence:
        # Normalize to relative path
        rel = ev_path
        if ev_path.startswith(repo_root_str):
            rel = ev_path[len(repo_root_str) :].lstrip("/")
        if rel in changed_set:
            changed_evidence.append(rel)

    if changed_evidence:
        return FreshnessState(
            last_validated=last_validated_str,
            revalidation_trigger="evidence-changed",
            stale=True,
            staleness_reason=f"Evidence file(s) changed: {', '.join(changed_evidence)}",
            evidence_current=False,
            days_since_validation=days_since,
        )

    return FreshnessState(
        last_validated=last_validated_str,
        revalidation_trigger=None,
        stale=False,
        staleness_reason=None,
        evidence_current=True,
        days_since_validation=days_since,
    )


def check_claim_freshness(
    claim: Claim,
    evidence_store: SqliteEvidenceStore,
    git: GitBackend,
    config: RkpConfig,
    current_time: datetime,
    *,
    index_metadata: IndexMetadata | None = None,
    file_hash_cache: dict[str, str | None] | None = None,
) -> FreshnessState:
    """Evaluate freshness of a single claim against current repo state."""
    last_validated_str = claim.last_validated.isoformat() if claim.last_validated else ""

    # Time-based expiry check
    if claim.last_validated is not None:
        delta = current_time - claim.last_validated
        days_since = delta.days
    elif claim.created_at is not None:
        # Never validated — use creation time as baseline
        delta = current_time - claim.created_at
        days_since = delta.days
    else:
        days_since = 0

    if days_since > config.staleness_window_days:
        return FreshnessState(
            last_validated=last_validated_str,
            revalidation_trigger="time-expired",
            stale=True,
            staleness_reason=f"Last validated {days_since} days ago (threshold: {config.staleness_window_days})",
            evidence_current=True,
            days_since_validation=days_since,
        )

    # Branch change check
    if index_metadata is not None:
        current_branch = git.current_branch()
        if index_metadata.branch and current_branch != index_metadata.branch:
            return FreshnessState(
                last_validated=last_validated_str,
                revalidation_trigger="branch-changed",
                stale=True,
                staleness_reason=f"Branch changed: {index_metadata.branch} -> {current_branch}",
                evidence_current=False,
                days_since_validation=days_since,
            )

    # Evidence hash comparison
    evidence_records = evidence_store.get_for_claim(claim.id)
    if not evidence_records:
        # Fallback: use claim's evidence file paths + git diff when claim_evidence
        # table is not populated (common for extracted claims).
        if claim.evidence and index_metadata and index_metadata.repo_head:
            return _check_evidence_via_git_diff(
                claim,
                git,
                index_metadata,
                last_validated_str,
                days_since,
                file_hash_cache if file_hash_cache is not None else {},
            )
        return FreshnessState(
            last_validated=last_validated_str,
            revalidation_trigger=None,
            stale=False,
            staleness_reason=None,
            evidence_current=True,
            days_since_validation=days_since,
        )

    cache = file_hash_cache if file_hash_cache is not None else {}
    changed_files: list[str] = []
    deleted_files: list[str] = []

    for ev in evidence_records:
        file_path = ev.file_path
        if file_path in cache:
            current_hash = cache[file_path]
        else:
            # Use git hash-object to get current hash; empty string means file missing
            current_hash = git.file_hash(Path(file_path)) or None
            cache[file_path] = current_hash

        if current_hash is None:
            deleted_files.append(file_path)
        elif current_hash != ev.file_hash and ev.file_hash:
            changed_files.append(file_path)

    if deleted_files:
        return FreshnessState(
            last_validated=last_validated_str,
            revalidation_trigger="evidence-deleted",
            stale=True,
            staleness_reason=f"Evidence file(s) deleted: {', '.join(deleted_files)}",
            evidence_current=False,
            days_since_validation=days_since,
        )

    if changed_files:
        return FreshnessState(
            last_validated=last_validated_str,
            revalidation_trigger="evidence-changed",
            stale=True,
            staleness_reason=f"Evidence file(s) changed: {', '.join(changed_files)}",
            evidence_current=False,
            days_since_validation=days_since,
        )

    return FreshnessState(
        last_validated=last_validated_str,
        revalidation_trigger=None,
        stale=False,
        staleness_reason=None,
        evidence_current=True,
        days_since_validation=days_since,
    )


def check_all_freshness(
    claim_store: ClaimStore,
    evidence_store: SqliteEvidenceStore,
    git: GitBackend,
    config: RkpConfig,
    *,
    index_metadata: IndexMetadata | None = None,
    repo_id: str = "",
    current_time: datetime | None = None,
) -> FreshnessReport:
    """Evaluate freshness of all claims. Returns summary + stale claim list."""
    if current_time is None:
        current_time = datetime.now(UTC)

    claims = claim_store.list_claims(repo_id=repo_id if repo_id else None)
    current_head = git.head()
    current_branch = git.current_branch()
    index_head = index_metadata.repo_head if index_metadata else ""
    index_branch = index_metadata.branch if index_metadata else ""

    file_hash_cache: dict[str, str | None] = {}
    stale_by_trigger: dict[str, int] = {}
    stale_claim_ids: list[str] = []
    stale_details: dict[str, FreshnessState] = {}
    fresh_count = 0

    for claim in claims:
        state = check_claim_freshness(
            claim,
            evidence_store,
            git,
            config,
            current_time,
            index_metadata=index_metadata,
            file_hash_cache=file_hash_cache,
        )
        if state.stale:
            trigger = state.revalidation_trigger or "unknown"
            stale_by_trigger[trigger] = stale_by_trigger.get(trigger, 0) + 1
            stale_claim_ids.append(claim.id)
            stale_details[claim.id] = state
        else:
            fresh_count += 1

    return FreshnessReport(
        total_claims=len(claims),
        fresh_claims=fresh_count,
        stale_claims=len(stale_claim_ids),
        stale_by_trigger=stale_by_trigger,
        stale_claim_ids=stale_claim_ids,
        stale_details=stale_details,
        branch_current=current_branch,
        branch_at_index=index_branch,
        branch_changed=bool(index_branch and current_branch != index_branch),
        head_current=current_head,
        head_at_index=index_head,
        head_changed=bool(index_head and current_head != index_head),
    )
