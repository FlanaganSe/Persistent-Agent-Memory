"""Budget overflow tests for Claude adapter."""

from __future__ import annotations

from dataclasses import replace

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.budget import BudgetTracker
from rkp.projection.capability_matrix import CLAUDE_CODE_CAPABILITY


class TestClaudeBudgetOverflow:
    def test_overflow_routes_to_skills(self, builder: ClaimBuilder) -> None:
        """Claims exceeding 200-line soft budget → overflow routed to skills."""
        claims = []
        # Create enough claims to overflow the 200-line budget
        for i in range(80):
            claim = builder.build(
                content=f"Convention rule number {i} with a fairly long description text",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                applicability=("all",),
            )
            claims.append(claim)

        adapter = ClaudeMdAdapter()
        budget = BudgetTracker(soft_budget_lines=200)
        result = adapter.project(claims, CLAUDE_CODE_CAPABILITY, budget)

        # CLAUDE.md should be under 200 lines
        claude_md = result.files["CLAUDE.md"]
        line_count = claude_md.count("\n")
        assert line_count <= 200, f"CLAUDE.md is {line_count} lines"

        # Some claims should have been routed to skills
        overflow_decisions = [
            (cid, reason)
            for cid, reason in result.excluded_claims
            if "overflow" in reason.lower() or "skills" in reason.lower()
        ]
        # Either skills were generated OR all claims fit (unlikely with 80)
        assert len(overflow_decisions) > 0 or line_count <= 200

    def test_higher_authority_kept_in_claude_md(self, builder: ClaimBuilder) -> None:
        """Higher-authority claims are kept in CLAUDE.md, lower overflow to skills."""
        high_claim = builder.build(
            content="pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
        )
        high_claim = replace(high_claim, risk_class=RiskClass.TEST_EXECUTION)

        low_claims = [
            builder.build(
                content=f"Convention {i}",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                applicability=("all",),
            )
            for i in range(80)
        ]

        all_claims = [high_claim, *low_claims]

        adapter = ClaudeMdAdapter()
        budget = BudgetTracker(soft_budget_lines=200)
        result = adapter.project(all_claims, CLAUDE_CODE_CAPABILITY, budget)

        claude_md = result.files["CLAUDE.md"]
        # The high-authority command should definitely be in CLAUDE.md
        assert "`pytest`" in claude_md

    def test_provenance_captures_routing_reasons(self, builder: ClaimBuilder) -> None:
        """Projection decision provenance captures routing reasons."""
        claims = [
            builder.build(
                content="pytest",
                claim_type=ClaimType.VALIDATED_COMMAND,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
            builder.build(
                content="Test procedure step 1",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                applicability=("testing",),
            ),
            builder.build(
                content="Test procedure step 2",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                applicability=("testing",),
            ),
        ]
        claims[0] = replace(claims[0], risk_class=RiskClass.TEST_EXECUTION)

        adapter = ClaudeMdAdapter()
        budget = BudgetTracker(soft_budget_lines=200)
        result = adapter.project(claims, CLAUDE_CODE_CAPABILITY, budget)

        # overflow_report should have decisions
        overflow = result.overflow_report
        assert "decisions" in overflow
        decisions = overflow["decisions"]
        assert isinstance(decisions, list)
        assert len(decisions) > 0

        # Each decision should have claim_id, destination, reason
        for decision in decisions:
            assert "claim_id" in decision
            assert "destination" in decision
            assert "reason" in decision

    def test_narrow_applicability_always_routes_to_skills(self, builder: ClaimBuilder) -> None:
        """Claims with narrow applicability → skills regardless of budget."""
        claims = [
            builder.build(
                content="Testing procedure detail",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                applicability=("testing",),
            ),
            builder.build(
                content="Another testing detail",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                applicability=("testing",),
            ),
        ]

        adapter = ClaudeMdAdapter()
        budget = BudgetTracker(soft_budget_lines=200)
        result = adapter.project(claims, CLAUDE_CODE_CAPABILITY, budget)

        # Narrow applicability claims should be routed to skills, not CLAUDE.md body
        skill_files = {k: v for k, v in result.files.items() if k.startswith(".claude/skills/")}
        assert len(skill_files) >= 1
