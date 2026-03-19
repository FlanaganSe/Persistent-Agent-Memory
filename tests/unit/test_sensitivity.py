"""Tests for sensitivity filtering."""

from __future__ import annotations

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, Sensitivity, SourceAuthority
from rkp.projection.sensitivity import filter_sensitive


class TestSensitivityFilter:
    def _make_claim(self, builder: ClaimBuilder, content: str, sensitivity: Sensitivity) -> object:
        return builder.build(
            content=content,
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            sensitivity=sensitivity,
            confidence=1.0,
        )

    def test_public_claims_always_included(self, builder: ClaimBuilder) -> None:
        """Public claims pass through all targets."""
        claim = self._make_claim(builder, "public rule", Sensitivity.PUBLIC)
        included, excluded = filter_sensitive([claim], Sensitivity.PUBLIC)
        assert len(included) == 1
        assert len(excluded) == 0

    def test_local_only_excluded_from_public(self, builder: ClaimBuilder) -> None:
        """Local-only claims excluded from public projections."""
        claim = self._make_claim(builder, "local secret", Sensitivity.LOCAL_ONLY)
        included, excluded = filter_sensitive([claim], Sensitivity.PUBLIC)
        assert len(included) == 0
        assert len(excluded) == 1

    def test_local_only_excluded_from_team(self, builder: ClaimBuilder) -> None:
        """Local-only claims excluded from team projections."""
        claim = self._make_claim(builder, "local secret", Sensitivity.LOCAL_ONLY)
        included, excluded = filter_sensitive([claim], Sensitivity.TEAM_ONLY)
        assert len(included) == 0
        assert len(excluded) == 1

    def test_team_only_excluded_from_public(self, builder: ClaimBuilder) -> None:
        """Team-only claims excluded from public projections."""
        claim = self._make_claim(builder, "team internal", Sensitivity.TEAM_ONLY)
        included, excluded = filter_sensitive([claim], Sensitivity.PUBLIC)
        assert len(included) == 0
        assert len(excluded) == 1

    def test_team_only_included_in_team(self, builder: ClaimBuilder) -> None:
        """Team-only claims included in team projections."""
        claim = self._make_claim(builder, "team internal", Sensitivity.TEAM_ONLY)
        included, excluded = filter_sensitive([claim], Sensitivity.TEAM_ONLY)
        assert len(included) == 1
        assert len(excluded) == 0

    def test_mixed_sensitivity(self, builder: ClaimBuilder) -> None:
        """Filter correctly separates mixed sensitivity claims."""
        public = self._make_claim(builder, "public rule", Sensitivity.PUBLIC)
        team = self._make_claim(builder, "team rule", Sensitivity.TEAM_ONLY)
        local = self._make_claim(builder, "local rule", Sensitivity.LOCAL_ONLY)

        included, excluded = filter_sensitive([public, team, local], Sensitivity.PUBLIC)
        assert len(included) == 1
        assert len(excluded) == 2
        assert included[0].content == "public rule"
