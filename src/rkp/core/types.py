"""Core domain enumerations for the Repo Knowledge Plane."""

from __future__ import annotations

from enum import StrEnum


class ClaimType(StrEnum):
    ALWAYS_ON_RULE = "always-on-rule"
    SCOPED_RULE = "scoped-rule"
    SKILL_PLAYBOOK = "skill-playbook"
    ENVIRONMENT_PREREQUISITE = "environment-prerequisite"
    VALIDATED_COMMAND = "validated-command"
    PERMISSION_RESTRICTION = "permission-restriction"
    MODULE_BOUNDARY = "module-boundary"
    CONFLICT = "conflict"


class SourceAuthority(StrEnum):
    HUMAN_OVERRIDE = "human-override"
    DECLARED_REVIEWED = "declared-reviewed"
    EXECUTABLE_CONFIG = "executable-config"
    CI_OBSERVED = "ci-observed"
    DECLARED_IMPORTED_UNREVIEWED = "declared-imported-unreviewed"
    CHECKED_IN_DOCS = "checked-in-docs"
    INFERRED_HIGH = "inferred-high"
    INFERRED_LOW = "inferred-low"


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    NEEDS_DECLARATION = "needs-declaration"
    APPROVED = "approved"
    EDITED = "edited"
    SUPPRESSED = "suppressed"
    TOMBSTONED = "tombstoned"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    TEAM_ONLY = "team-only"
    LOCAL_ONLY = "local-only"


class RiskClass(StrEnum):
    SAFE_READONLY = "safe-readonly"
    SAFE_MUTATING = "safe-mutating"
    TEST_EXECUTION = "test-execution"
    BUILD = "build"
    DESTRUCTIVE = "destructive"


class EvidenceLevel(StrEnum):
    DISCOVERED = "discovered"
    PREREQUISITES_EXTRACTED = "prerequisites-extracted"
    CI_EVIDENCED = "ci-evidenced"
    ENVIRONMENT_PROFILED = "environment-profiled"
    SANDBOX_VERIFIED = "sandbox-verified"


class ArtifactOwnership(StrEnum):
    IMPORTED_HUMAN_OWNED = "imported-human-owned"
    MANAGED_BY_RKP = "managed-by-rkp"
    MIXED_MIGRATION = "mixed-migration"


# Precedence: lower number = higher authority.
# DECLARED_IMPORTED_UNREVIEWED is 35 (precedence 3.5), below executable-config (30)
# and above checked-in-docs (40). The build research shows 2.5 — that is wrong.
_SOURCE_AUTHORITY_PRECEDENCE: dict[SourceAuthority, int] = {
    SourceAuthority.HUMAN_OVERRIDE: 10,
    SourceAuthority.DECLARED_REVIEWED: 20,
    SourceAuthority.EXECUTABLE_CONFIG: 30,
    SourceAuthority.CI_OBSERVED: 30,
    SourceAuthority.DECLARED_IMPORTED_UNREVIEWED: 35,
    SourceAuthority.CHECKED_IN_DOCS: 40,
    SourceAuthority.INFERRED_HIGH: 50,
    SourceAuthority.INFERRED_LOW: 60,
}


def source_authority_precedence(authority: SourceAuthority) -> int:
    """Return the numeric precedence for a source authority (lower = higher authority)."""
    return _SOURCE_AUTHORITY_PRECEDENCE[authority]
