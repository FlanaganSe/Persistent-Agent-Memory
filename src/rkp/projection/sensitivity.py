"""Sensitivity filter — single enforcement point for claim visibility."""

from __future__ import annotations

from rkp.core.models import Claim
from rkp.core.types import Sensitivity


def filter_sensitive(
    claims: list[Claim],
    target_sensitivity: Sensitivity,
) -> tuple[list[Claim], list[Claim]]:
    """Filter claims by sensitivity level.

    Returns (included, excluded).

    Rules:
    - local-only claims excluded from any checked-in projection (team-only or public)
    - team-only claims excluded from public projections
    - public claims always included
    """
    included: list[Claim] = []
    excluded: list[Claim] = []

    for claim in claims:
        if _is_allowed(claim.sensitivity, target_sensitivity):
            included.append(claim)
        else:
            excluded.append(claim)

    return included, excluded


def _is_allowed(claim_sensitivity: Sensitivity, target: Sensitivity) -> bool:
    """Check if a claim's sensitivity allows it into the target projection."""
    if claim_sensitivity == Sensitivity.LOCAL_ONLY:
        # local-only never goes to checked-in projections
        return target == Sensitivity.LOCAL_ONLY
    if claim_sensitivity == Sensitivity.TEAM_ONLY:
        # team-only excluded from public
        return target in (Sensitivity.TEAM_ONLY, Sensitivity.LOCAL_ONLY)
    # public claims always allowed
    return True
