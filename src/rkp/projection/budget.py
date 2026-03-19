"""Context budget tracking and overflow routing."""

from __future__ import annotations

from dataclasses import dataclass, field

from rkp.core.models import Claim
from rkp.core.types import source_authority_precedence


@dataclass
class BudgetTracker:
    """Tracks context budget usage during projection.

    When content exceeds the hard budget, claims are prioritized by
    authority level (highest first), then by confidence.
    """

    hard_budget_bytes: int
    soft_budget_lines: int | None = None
    current_bytes: int = 0
    current_lines: int = 0
    included: list[tuple[Claim, str]] = field(default_factory=lambda: [])
    omitted: list[tuple[Claim, str]] = field(default_factory=lambda: [])

    def try_include(self, claim: Claim, rendered: str) -> bool:
        """Try to include a claim's rendered content within budget.

        Returns True if included, False if omitted for budget reasons.
        """
        content_bytes = len(rendered.encode("utf-8"))
        content_lines = rendered.count("\n") + 1

        if self.current_bytes + content_bytes > self.hard_budget_bytes:
            self.omitted.append((claim, "exceeded hard budget"))
            return False

        self.current_bytes += content_bytes
        self.current_lines += content_lines
        self.included.append((claim, "within budget"))
        return True

    @property
    def overflow_report(self) -> dict[str, object]:
        """Generate a report of budget usage and overflow."""
        return {
            "hard_budget_bytes": self.hard_budget_bytes,
            "used_bytes": self.current_bytes,
            "included_count": len(self.included),
            "omitted_count": len(self.omitted),
            "omitted_claims": [{"claim_id": c.id, "reason": r} for c, r in self.omitted],
        }


def prioritize_claims(claims: list[Claim]) -> list[Claim]:
    """Sort claims by authority (highest first), then confidence (highest first).

    Used when content exceeds budget to decide what to keep.
    """
    return sorted(
        claims,
        key=lambda c: (source_authority_precedence(c.source_authority), -c.confidence),
    )
