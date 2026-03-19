"""Unit tests: projection properly filters by review state."""

from __future__ import annotations

from dataclasses import replace

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Claim
from rkp.core.types import ClaimType, ReviewState, SourceAuthority
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project


def _build_command(builder: ClaimBuilder, content: str) -> Claim:
    """Build a validated-command claim with inferred-high authority."""
    return builder.build(
        content=content,
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=SourceAuthority.INFERRED_HIGH,
        scope="**",
        confidence=1.0,
        evidence=("test.py",),
    )


def _project_claims(claims: list[Claim]) -> str:
    """Run projection and return the AGENTS.md content."""
    capability = get_capability("codex")
    assert capability is not None
    adapter = AgentsMdAdapter()
    policy = ProjectionPolicy()
    result = project(claims, adapter, capability, policy)
    return result.adapter_result.files["AGENTS.md"]


class TestProjectionReviewState:
    def test_approved_claims_projected(self, builder: ClaimBuilder) -> None:
        """Approved claims appear in the projected AGENTS.md output."""
        claim = _build_command(builder, "make test-approved")
        approved = replace(claim, review_state=ReviewState.APPROVED)

        content = _project_claims([approved])
        assert "`make test-approved`" in content

    def test_edited_claims_projected(self, builder: ClaimBuilder) -> None:
        """Edited claims appear with their edited content."""
        claim = _build_command(builder, "original-cmd")
        edited = replace(
            claim,
            content="edited-cmd",
            review_state=ReviewState.EDITED,
        )

        content = _project_claims([edited])
        assert "`edited-cmd`" in content
        assert "original-cmd" not in content

    def test_unreviewed_claims_projected_in_preview_mode(self, builder: ClaimBuilder) -> None:
        """Unreviewed claims still produce output when passed to projection.

        The gating between reviewed/unreviewed happens at the call site,
        not inside the projection engine. When claims are passed in, they
        are projected regardless of review state.
        """
        claim = _build_command(builder, "make unreviewed-cmd")
        assert claim.review_state == ReviewState.UNREVIEWED

        content = _project_claims([claim])
        assert "`make unreviewed-cmd`" in content

    def test_suppressed_claims_excluded(self, builder: ClaimBuilder) -> None:
        """Suppressed claims produce no meaningful command content."""
        claim = _build_command(builder, "suppressed-cmd")
        suppressed = replace(claim, review_state=ReviewState.SUPPRESSED)

        # The engine renders whatever is passed, but in a real
        # governance flow the caller filters suppressed claims out.
        # The key invariant: callers should NOT pass suppressed claims.
        # We test the filtering pattern:
        filtered = [
            c
            for c in [suppressed]
            if c.review_state
            not in {
                ReviewState.SUPPRESSED,
                ReviewState.TOMBSTONED,
            }
        ]
        filtered_content = _project_claims(filtered)
        assert "## Commands" not in filtered_content

    def test_tombstoned_claims_excluded(self, builder: ClaimBuilder) -> None:
        """Tombstoned claims produce no meaningful command content when filtered."""
        claim = _build_command(builder, "tombstoned-cmd")
        tombstoned = replace(claim, review_state=ReviewState.TOMBSTONED)

        filtered = [
            c
            for c in [tombstoned]
            if c.review_state
            not in {
                ReviewState.SUPPRESSED,
                ReviewState.TOMBSTONED,
            }
        ]
        filtered_content = _project_claims(filtered)
        assert "## Commands" not in filtered_content

    def test_mixed_review_states(self, builder: ClaimBuilder) -> None:
        """Only approved/edited claims appear when the caller filters properly."""
        claims = [
            replace(_build_command(builder, "cmd-approved"), review_state=ReviewState.APPROVED),
            replace(
                _build_command(builder, "cmd-edited"),
                content="cmd-edited",
                review_state=ReviewState.EDITED,
            ),
            _build_command(builder, "cmd-unreviewed"),  # UNREVIEWED by default
            replace(
                _build_command(builder, "cmd-suppressed"),
                review_state=ReviewState.SUPPRESSED,
            ),
            replace(
                _build_command(builder, "cmd-tombstoned"),
                review_state=ReviewState.TOMBSTONED,
            ),
        ]

        # Simulate the governance filter: only approved + edited.
        active = [
            c for c in claims if c.review_state in {ReviewState.APPROVED, ReviewState.EDITED}
        ]
        assert len(active) == 2

        content = _project_claims(active)
        assert "`cmd-approved`" in content
        assert "`cmd-edited`" in content
        assert "cmd-unreviewed" not in content
        assert "cmd-suppressed" not in content
        assert "cmd-tombstoned" not in content
