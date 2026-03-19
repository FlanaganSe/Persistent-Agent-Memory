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

    workspace_budget_bytes tracks a cumulative budget across multiple files
    (used by Windsurf: 12K total across all workspace rules).
    """

    hard_budget_bytes: int | None = None
    soft_budget_lines: int | None = None
    workspace_budget_bytes: int | None = None
    current_bytes: int = 0
    current_lines: int = 0
    workspace_bytes: int = 0
    included: list[tuple[Claim, str]] = field(default_factory=lambda: [])
    omitted: list[tuple[Claim, str]] = field(default_factory=lambda: [])

    def try_include(self, claim: Claim, rendered: str) -> bool:
        """Try to include a claim's rendered content within budget.

        Returns True if included, False if omitted for budget reasons.
        """
        content_bytes = len(rendered.encode("utf-8"))
        content_lines = rendered.count("\n") + 1

        if (
            self.hard_budget_bytes is not None
            and self.current_bytes + content_bytes > self.hard_budget_bytes
        ):
            self.omitted.append((claim, "exceeded hard budget"))
            return False

        if (
            self.workspace_budget_bytes is not None
            and self.workspace_bytes + content_bytes > self.workspace_budget_bytes
        ):
            self.omitted.append((claim, "exceeded workspace budget"))
            return False

        self.current_bytes += content_bytes
        self.current_lines += content_lines
        self.workspace_bytes += content_bytes
        self.included.append((claim, "within budget"))
        return True

    def add_workspace_bytes(self, byte_count: int) -> None:
        """Add bytes to workspace total without affecting per-file tracking."""
        self.workspace_bytes += byte_count

    def reset_per_file(self) -> None:
        """Reset per-file counters while preserving workspace totals."""
        self.current_bytes = 0
        self.current_lines = 0

    @property
    def overflow_report(self) -> dict[str, object]:
        """Generate a report of budget usage and overflow."""
        report: dict[str, object] = {
            "hard_budget_bytes": self.hard_budget_bytes,
            "soft_budget_lines": self.soft_budget_lines,
            "used_bytes": self.current_bytes,
            "used_lines": self.current_lines,
            "included_count": len(self.included),
            "omitted_count": len(self.omitted),
            "omitted_claims": [{"claim_id": c.id, "reason": r} for c, r in self.omitted],
        }
        if self.workspace_budget_bytes is not None:
            report["workspace_budget_bytes"] = self.workspace_budget_bytes
            report["workspace_used_bytes"] = self.workspace_bytes
        return report


def prioritize_claims(claims: list[Claim]) -> list[Claim]:
    """Sort claims by authority (highest first), then confidence (highest first).

    Used when content exceeds budget to decide what to keep.
    """
    return sorted(
        claims,
        key=lambda c: (source_authority_precedence(c.source_authority), -c.confidence),
    )
