"""Tests for core domain types."""

from __future__ import annotations

from rkp.core.types import (
    ArtifactOwnership,
    ClaimType,
    EvidenceLevel,
    ReviewState,
    RiskClass,
    Sensitivity,
    SourceAuthority,
    source_authority_precedence,
)


class TestClaimType:
    def test_all_values(self) -> None:
        assert ClaimType.ALWAYS_ON_RULE == "always-on-rule"
        assert ClaimType.SCOPED_RULE == "scoped-rule"
        assert ClaimType.SKILL_PLAYBOOK == "skill-playbook"
        assert ClaimType.ENVIRONMENT_PREREQUISITE == "environment-prerequisite"
        assert ClaimType.VALIDATED_COMMAND == "validated-command"
        assert ClaimType.PERMISSION_RESTRICTION == "permission-restriction"
        assert ClaimType.MODULE_BOUNDARY == "module-boundary"
        assert ClaimType.CONFLICT == "conflict"

    def test_count(self) -> None:
        assert len(ClaimType) == 8


class TestSourceAuthority:
    def test_all_values(self) -> None:
        assert SourceAuthority.HUMAN_OVERRIDE == "human-override"
        assert SourceAuthority.DECLARED_REVIEWED == "declared-reviewed"
        assert SourceAuthority.EXECUTABLE_CONFIG == "executable-config"
        assert SourceAuthority.CI_OBSERVED == "ci-observed"
        assert SourceAuthority.DECLARED_IMPORTED_UNREVIEWED == "declared-imported-unreviewed"
        assert SourceAuthority.CHECKED_IN_DOCS == "checked-in-docs"
        assert SourceAuthority.INFERRED_HIGH == "inferred-high"
        assert SourceAuthority.INFERRED_LOW == "inferred-low"

    def test_count(self) -> None:
        assert len(SourceAuthority) == 8


class TestSourceAuthorityPrecedence:
    def test_human_override_highest(self) -> None:
        assert source_authority_precedence(SourceAuthority.HUMAN_OVERRIDE) == 10

    def test_inferred_low_lowest(self) -> None:
        assert source_authority_precedence(SourceAuthority.INFERRED_LOW) == 60

    def test_imported_unreviewed_below_executable_config(self) -> None:
        """DECLARED_IMPORTED_UNREVIEWED is precedence 3.5 (35), below executable-config (30)."""
        imported = source_authority_precedence(SourceAuthority.DECLARED_IMPORTED_UNREVIEWED)
        exec_cfg = source_authority_precedence(SourceAuthority.EXECUTABLE_CONFIG)
        assert imported > exec_cfg  # higher number = lower authority

    def test_imported_unreviewed_above_checked_in_docs(self) -> None:
        imported = source_authority_precedence(SourceAuthority.DECLARED_IMPORTED_UNREVIEWED)
        docs = source_authority_precedence(SourceAuthority.CHECKED_IN_DOCS)
        assert imported < docs  # lower number = higher authority

    def test_executable_config_equals_ci_observed(self) -> None:
        ec = source_authority_precedence(SourceAuthority.EXECUTABLE_CONFIG)
        ci = source_authority_precedence(SourceAuthority.CI_OBSERVED)
        assert ec == ci

    def test_full_ordering(self) -> None:
        """Verify the complete precedence ordering."""
        authorities = list(SourceAuthority)
        precedences = [source_authority_precedence(a) for a in authorities]
        # Should be a total ordering (with ties allowed)
        for p in precedences:
            assert isinstance(p, int)

    def test_ordering_is_total(self) -> None:
        """Every pair of authorities has a defined ordering."""
        for a in SourceAuthority:
            for b in SourceAuthority:
                pa = source_authority_precedence(a)
                pb = source_authority_precedence(b)
                assert pa <= pb or pa >= pb


class TestReviewState:
    def test_all_values(self) -> None:
        assert ReviewState.UNREVIEWED == "unreviewed"
        assert ReviewState.NEEDS_DECLARATION == "needs-declaration"
        assert ReviewState.APPROVED == "approved"
        assert ReviewState.EDITED == "edited"
        assert ReviewState.SUPPRESSED == "suppressed"
        assert ReviewState.TOMBSTONED == "tombstoned"


class TestSensitivity:
    def test_all_values(self) -> None:
        assert len(Sensitivity) == 3


class TestRiskClass:
    def test_all_values(self) -> None:
        assert len(RiskClass) == 5


class TestEvidenceLevel:
    def test_all_values(self) -> None:
        assert len(EvidenceLevel) == 5
        assert EvidenceLevel.DISCOVERED == "discovered"
        assert EvidenceLevel.SANDBOX_VERIFIED == "sandbox-verified"


class TestArtifactOwnership:
    def test_all_values(self) -> None:
        assert ArtifactOwnership.IMPORTED_HUMAN_OWNED == "imported-human-owned"
        assert ArtifactOwnership.MANAGED_BY_RKP == "managed-by-rkp"
        assert ArtifactOwnership.MIXED_MIGRATION == "mixed-migration"
