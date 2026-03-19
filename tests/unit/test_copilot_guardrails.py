"""Tests for Copilot guardrail projection."""

from __future__ import annotations

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, SourceAuthority
from rkp.projection.adapters.copilot import CopilotAdapter, is_copilot_enforceable
from rkp.projection.capability_matrix import COPILOT_CAPABILITY
from rkp.projection.engine import ProjectionPolicy, project


class TestCopilotGuardrails:
    def test_destructive_command_strong_warning(self, builder: ClaimBuilder) -> None:
        """Destructive command produces strong warning in copilot-instructions.md."""
        claims = [
            builder.build(
                content="Command `db:reset` is classified as destructive "
                "— require explicit confirmation before running",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("destructive", "security"),
            ),
        ]

        adapter = CopilotAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, COPILOT_CAPABILITY, policy)

        content = result.adapter_result.files[".github/copilot-instructions.md"]
        assert "WARNING" in content
        assert "db:reset" in content
        assert "## Restrictions" in content

    def test_is_copilot_enforceable_destructive(self, builder: ClaimBuilder) -> None:
        """Destructive restriction is enforceable on Copilot."""
        claim = builder.build(
            content="Command `rm -rf` is classified as destructive "
            "— require explicit confirmation before running",
            claim_type=ClaimType.PERMISSION_RESTRICTION,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
        )

        assert is_copilot_enforceable(claim) is True

    def test_is_copilot_enforceable_low_confidence(self, builder: ClaimBuilder) -> None:
        """Low-confidence restriction is not enforceable."""
        claim = builder.build(
            content="Command `rm -rf` is classified as destructive",
            claim_type=ClaimType.PERMISSION_RESTRICTION,
            source_authority=SourceAuthority.INFERRED_LOW,
            confidence=0.5,
        )

        assert is_copilot_enforceable(claim) is False

    def test_is_copilot_enforceable_non_restriction(self, builder: ClaimBuilder) -> None:
        """Non-restriction claims are not enforceable."""
        claim = builder.build(
            content="Use snake_case",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
        )

        assert is_copilot_enforceable(claim) is False

    def test_advisory_guardrail_included(self, builder: ClaimBuilder) -> None:
        """Advisory guardrails are included in copilot-instructions.md."""
        claims = [
            builder.build(
                content="CI runs security scan: `npm audit` — ensure changes pass",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.CI_OBSERVED,
                confidence=0.9,
                applicability=("security",),
            ),
        ]

        adapter = CopilotAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, COPILOT_CAPABILITY, policy)

        content = result.adapter_result.files[".github/copilot-instructions.md"]
        assert "npm audit" in content

    def test_autonomous_agent_note(self, builder: ClaimBuilder) -> None:
        """Copilot instructions include note about autonomous execution."""
        claims = [
            builder.build(
                content="Command `db:drop` is classified as destructive "
                "— require explicit confirmation before running",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("destructive",),
            ),
        ]

        adapter = CopilotAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, COPILOT_CAPABILITY, policy)

        content = result.adapter_result.files[".github/copilot-instructions.md"]
        assert "autonomous" in content.lower()
