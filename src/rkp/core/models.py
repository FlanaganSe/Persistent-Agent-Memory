"""Frozen dataclass domain models for the Repo Knowledge Plane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rkp.core.types import (
    ArtifactOwnership,
    ClaimType,
    EvidenceLevel,
    ReviewState,
    RiskClass,
    Sensitivity,
    SourceAuthority,
)


@dataclass(frozen=True)
class Provenance:
    """Extraction provenance metadata."""

    index_version: str = ""
    repo_head: str = ""
    branch: str = ""
    timestamp: str = ""
    extraction_version: str = ""


@dataclass(frozen=True)
class Claim:
    """A single piece of repo knowledge with provenance and review metadata."""

    id: str
    content: str
    claim_type: ClaimType
    source_authority: SourceAuthority
    scope: str = "**"
    applicability: tuple[str, ...] = ()
    sensitivity: Sensitivity = Sensitivity.PUBLIC
    review_state: ReviewState = ReviewState.UNREVIEWED
    confidence: float = 0.0
    evidence: tuple[str, ...] = ()
    provenance: Provenance = Provenance()
    risk_class: RiskClass | None = None
    projection_targets: tuple[str, ...] = ()
    repo_id: str = ""
    branch: str = "main"
    worktree_id: str | None = None
    session_id: str | None = None
    last_validated: datetime | None = None
    revalidation_trigger: str | None = None
    stale: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class Evidence:
    """Detailed evidence record linking a claim to a source file."""

    claim_id: str
    file_path: str
    file_hash: str
    extraction_version: str
    line_start: int | None = None
    line_end: int | None = None
    evidence_level: EvidenceLevel = EvidenceLevel.DISCOVERED
    id: int | None = None


@dataclass(frozen=True)
class ClaimHistory:
    """Audit trail entry for a claim action."""

    claim_id: str
    action: str
    content_before: str | None = None
    content_after: str | None = None
    actor: str = "system"
    timestamp: datetime | None = None
    reason: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class EnvironmentProfile:
    """Top-level environment profile aggregating prerequisites for commands."""

    id: str
    name: str
    repo_id: str
    claim_id: str | None = None
    runtime: str | None = None
    tools: tuple[str, ...] = ()
    services: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()
    setup_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class ManagedArtifact:
    """A projected artifact tracked for drift detection."""

    path: str
    artifact_type: str
    target_host: str
    expected_hash: str
    last_projected: str
    ownership_mode: ArtifactOwnership = ArtifactOwnership.MANAGED_BY_RKP


@dataclass(frozen=True)
class ModuleEdge:
    """A dependency edge between two modules."""

    source_path: str
    target_path: str
    edge_type: str
    repo_id: str
    branch: str = "main"


@dataclass(frozen=True)
class Identity:
    """Repo/branch/worktree/session identity context."""

    repo_id: str
    branch: str = "main"
    worktree_id: str | None = None
    session_id: str | None = None
