"""Tests for context budget tracking."""

from __future__ import annotations

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, SourceAuthority
from rkp.projection.budget import BudgetTracker, prioritize_claims


class TestBudgetTracker:
    def test_include_within_budget(self, builder: ClaimBuilder) -> None:
        """Claims within budget are included."""
        tracker = BudgetTracker(hard_budget_bytes=1000)
        claim = builder.build(
            content="pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
        )
        assert tracker.try_include(claim, "- `pytest`\n")
        assert len(tracker.included) == 1
        assert len(tracker.omitted) == 0

    def test_exclude_over_budget(self, builder: ClaimBuilder) -> None:
        """Claims that exceed budget are omitted."""
        tracker = BudgetTracker(hard_budget_bytes=10)
        claim = builder.build(
            content="a very long command that exceeds the budget",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
        )
        assert not tracker.try_include(claim, "- `a very long command that exceeds the budget`\n")
        assert len(tracker.included) == 0
        assert len(tracker.omitted) == 1

    def test_overflow_report(self, builder: ClaimBuilder) -> None:
        """Overflow report contains correct information."""
        tracker = BudgetTracker(hard_budget_bytes=100)
        claim = builder.build(
            content="test",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
        )
        tracker.try_include(claim, "- `test`\n")
        report = tracker.overflow_report
        assert report["hard_budget_bytes"] == 100
        assert report["included_count"] == 1
        assert report["omitted_count"] == 0


class TestPrioritizeClaims:
    def test_higher_authority_first(self, builder: ClaimBuilder) -> None:
        """Higher authority claims come first."""
        low = builder.build(
            content="low",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
            confidence=1.0,
        )
        high = builder.build(
            content="high",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.HUMAN_OVERRIDE,
            confidence=1.0,
        )
        result = prioritize_claims([low, high])
        assert result[0].source_authority == SourceAuthority.HUMAN_OVERRIDE
        assert result[1].source_authority == SourceAuthority.INFERRED_LOW

    def test_same_authority_higher_confidence_first(self, builder: ClaimBuilder) -> None:
        """Same authority, higher confidence first."""
        low_conf = builder.build(
            content="low conf",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.5,
        )
        high_conf = builder.build(
            content="high conf",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.95,
        )
        result = prioritize_claims([low_conf, high_conf])
        assert result[0].confidence == 0.95
