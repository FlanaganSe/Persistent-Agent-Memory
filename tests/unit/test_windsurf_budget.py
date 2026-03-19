"""Budget edge-case tests for Windsurf adapter."""

from __future__ import annotations

from dataclasses import replace

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Provenance
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.projection.adapters.windsurf import (
    _PER_FILE_CHAR_LIMIT,
    _WORKSPACE_CHAR_LIMIT,
    WindsurfAdapter,
)
from rkp.projection.budget import BudgetTracker
from rkp.projection.capability_matrix import WINDSURF_CAPABILITY


def _make_budget() -> BudgetTracker:
    return BudgetTracker(
        hard_budget_bytes=WINDSURF_CAPABILITY.size_constraints.hard_budget_bytes,
        workspace_budget_bytes=WINDSURF_CAPABILITY.size_constraints.workspace_budget_bytes,
    )


def _provenance(head: str = "abc12345def67890") -> Provenance:
    return Provenance(repo_head=head)


class TestWindsurfBudgetEdgeCases:
    def test_many_claims_overflow(self, builder: ClaimBuilder) -> None:
        """Many claims that overflow both per-file and workspace budgets."""
        claims = [
            builder.build(
                content=f"Convention rule {i}: " + "x" * 200,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                provenance=_provenance(),
            )
            for i in range(100)
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        # Total output must respect workspace limit
        total_chars = sum(len(v) for v in result.files.values())
        assert total_chars <= _WORKSPACE_CHAR_LIMIT

        # Some claims should be excluded
        assert len(result.excluded_claims) > 0

    def test_priority_guardrails_kept(self, builder: ClaimBuilder) -> None:
        """Guardrails survive budget pressure; conventions dropped first."""
        guardrail_claims = [
            builder.build(
                content=f"Critical restriction {i}",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                provenance=_provenance(),
            )
            for i in range(3)
        ]
        # Large convention claims that would push past workspace budget
        convention_claims = [
            builder.build(
                content=f"Convention {i}: " + "c" * 400,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                provenance=_provenance(),
            )
            for i in range(30)
        ]

        all_claims = guardrail_claims + convention_claims
        adapter = WindsurfAdapter()
        result = adapter.project(all_claims, WINDSURF_CAPABILITY, _make_budget())

        # Guardrails file should be present
        assert ".windsurf/rules/rkp-guardrails.md" in result.files
        guardrails_content = result.files[".windsurf/rules/rkp-guardrails.md"]
        for gc in guardrail_claims:
            assert gc.content in guardrails_content

    def test_overflow_report_lists_excluded(self, builder: ClaimBuilder) -> None:
        """Overflow report includes claim IDs and reasons for excluded claims."""
        claims = [
            builder.build(
                content=f"Convention {i}: " + "x" * 300,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                provenance=_provenance(),
            )
            for i in range(40)
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        overflow = result.overflow_report
        assert "decisions" in overflow
        decisions = overflow["decisions"]
        assert isinstance(decisions, list)

        # At least some decisions should show exclusion reasons
        excluded_decisions = [d for d in decisions if d["destination"] == "excluded"]
        assert len(excluded_decisions) > 0
        for d in excluded_decisions:
            assert "claim_id" in d
            assert "reason" in d
            assert len(d["reason"]) > 0

    def test_budget_exactly_at_limit(self, builder: ClaimBuilder) -> None:
        """Content exactly at per-file limit is included."""
        base_claim = builder.build(
            content="x",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.95,
            provenance=_provenance(),
        )

        # Measure rendering overhead
        adapter = WindsurfAdapter()
        probe = adapter.project([base_claim], WINDSURF_CAPABILITY, _make_budget())
        probe_content = probe.files[".windsurf/rules/rkp-conventions.md"]
        overhead = len(probe_content) - 1  # 1 char for "x"

        # Exactly at limit
        exact_len = _PER_FILE_CHAR_LIMIT - overhead
        exact_claim = replace(base_claim, content="a" * exact_len)

        result = adapter.project([exact_claim], WINDSURF_CAPABILITY, _make_budget())
        assert ".windsurf/rules/rkp-conventions.md" in result.files
        assert len(result.files[".windsurf/rules/rkp-conventions.md"]) == _PER_FILE_CHAR_LIMIT

    def test_workspace_budget_across_files(self, builder: ClaimBuilder) -> None:
        """Workspace budget is enforced across multiple files, not per-file."""
        # Build three categories that individually fit in 6K but together exceed 12K.
        # Each file targets ~5K so that two fit (~10K) but the third pushes past 12K.
        # Guardrails: ~5K
        guardrail_claims = [
            builder.build(
                content=f"Restriction {i}: " + "g" * 450,
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                provenance=_provenance(),
            )
            for i in range(10)
        ]
        # Commands: ~5.5K
        command_claims = [
            replace(
                builder.build(
                    content=f"cmd-{i}: " + "c" * 500,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                    provenance=_provenance(),
                ),
                risk_class=RiskClass.BUILD,
            )
            for i in range(10)
        ]
        # Conventions: ~5.5K (should be dropped — workspace full)
        convention_claims = [
            builder.build(
                content=f"Convention {i}: " + "v" * 500,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                provenance=_provenance(),
            )
            for i in range(10)
        ]

        all_claims = guardrail_claims + command_claims + convention_claims

        adapter = WindsurfAdapter()
        result = adapter.project(all_claims, WINDSURF_CAPABILITY, _make_budget())

        total_chars = sum(len(v) for v in result.files.values())
        assert total_chars <= _WORKSPACE_CHAR_LIMIT

        # Higher-priority files (guardrails, commands) should be present
        assert ".windsurf/rules/rkp-guardrails.md" in result.files
        assert ".windsurf/rules/rkp-commands.md" in result.files

        # Conventions should have been excluded due to workspace budget
        assert ".windsurf/rules/rkp-conventions.md" not in result.files

        # Workspace budget info should be in overflow report
        overflow = result.overflow_report
        assert "windsurf_budget" in overflow
        budget_info = overflow["windsurf_budget"]
        assert budget_info["workspace_limit"] == _WORKSPACE_CHAR_LIMIT
        assert budget_info["workspace_used"] <= _WORKSPACE_CHAR_LIMIT
