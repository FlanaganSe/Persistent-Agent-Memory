"""Rich table renderers for CLI output."""

from __future__ import annotations

from collections import Counter
from typing import Any

from rich.table import Table

from rkp.core.models import Claim
from rkp.core.types import ClaimType, ReviewState

# Human-friendly names for claim types.
CLAIM_TYPE_LABELS: dict[str, str] = {
    ClaimType.VALIDATED_COMMAND: "Validated Commands",
    ClaimType.ALWAYS_ON_RULE: "Conventions",
    ClaimType.SCOPED_RULE: "Scoped Rules",
    ClaimType.SKILL_PLAYBOOK: "Skills",
    ClaimType.ENVIRONMENT_PREREQUISITE: "Prerequisites",
    ClaimType.PERMISSION_RESTRICTION: "Guardrails",
    ClaimType.MODULE_BOUNDARY: "Module Boundaries",
    ClaimType.CONFLICT: "Conflicts",
}


def render_init_summary(claims: list[Claim]) -> Table:
    """Build a summary table of claim counts by type with average confidence."""
    type_counts: Counter[str] = Counter()
    type_confidence: dict[str, list[float]] = {}

    for claim in claims:
        ct = claim.claim_type.value
        type_counts[ct] += 1
        if ct not in type_confidence:
            type_confidence[ct] = []
        type_confidence[ct].append(claim.confidence)

    table = Table(title="Extraction Summary", show_lines=True)
    table.add_column("Claim Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Confidence", justify="right")

    # Show types in a stable order.
    for ct_value in [ct.value for ct in ClaimType]:
        count = type_counts.get(ct_value, 0)
        if count == 0:
            continue
        label = CLAIM_TYPE_LABELS.get(ct_value, ct_value)
        confidences = type_confidence[ct_value]
        if ct_value == ClaimType.CONFLICT:
            conf_str = "\u2014"
        else:
            avg = sum(confidences) / len(confidences)
            conf_str = f"{avg:.0%} avg"
        table.add_row(label, str(count), conf_str)

    return table


def render_status_table(summary: dict[str, Any]) -> Table:
    """Build a status dashboard table."""
    table = Table(title="Claim Summary", show_lines=True)
    table.add_column("Claim Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Confidence", justify="right")

    for entry in summary.get("by_type", []):
        table.add_row(
            entry["label"],
            str(entry["count"]),
            entry.get("confidence", "\u2014"),
        )

    return table


def render_review_state_table(claims: list[Claim]) -> Table:
    """Build a table of claims by review state."""
    state_counts: Counter[str] = Counter()
    for claim in claims:
        state_counts[claim.review_state.value] += 1

    table = Table(title="Review States")
    table.add_column("State", style="cyan")
    table.add_column("Count", justify="right")

    for state in ReviewState:
        count = state_counts.get(state.value, 0)
        if count == 0:
            continue
        table.add_row(state.value, str(count))

    return table
