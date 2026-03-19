"""Projection engine: claims + adapter + policy → artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from rkp.core.models import Claim
from rkp.core.types import Sensitivity
from rkp.projection.adapters.base import AdapterResult, BaseAdapter
from rkp.projection.budget import BudgetTracker, prioritize_claims
from rkp.projection.capability_matrix import HostCapability
from rkp.projection.sensitivity import filter_sensitive


@dataclass(frozen=True)
class ProjectionPolicy:
    """Policy settings for a projection run."""

    target_sensitivity: Sensitivity = Sensitivity.PUBLIC
    min_confidence: float = 0.0


@dataclass(frozen=True)
class ProjectionResult:
    """Full result of a projection including artifacts and decision log."""

    adapter_result: AdapterResult
    excluded_sensitive: list[tuple[str, str]]
    excluded_low_confidence: list[tuple[str, str]]
    warnings: list[str]


def project(
    claims: list[Claim],
    adapter: BaseAdapter,
    capability: HostCapability,
    policy: ProjectionPolicy | None = None,
) -> ProjectionResult:
    """Pure function: project claims through an adapter into artifacts.

    Steps:
    1. Filter by sensitivity
    2. Filter by minimum confidence
    3. Prioritize by authority
    4. Run adapter projection with budget tracking
    """
    if policy is None:
        policy = ProjectionPolicy()

    warnings: list[str] = []

    # 1. Sensitivity filter
    included, sensitive_excluded = filter_sensitive(claims, policy.target_sensitivity)
    excluded_sensitive = [(c.id, f"sensitivity:{c.sensitivity.value}") for c in sensitive_excluded]

    # 2. Confidence filter
    confident: list[Claim] = []
    low_confidence_excluded: list[tuple[str, str]] = []
    for claim in included:
        if claim.confidence >= policy.min_confidence:
            confident.append(claim)
        else:
            low_confidence_excluded.append(
                (claim.id, f"confidence:{claim.confidence}<{policy.min_confidence}")
            )

    # 3. Prioritize
    prioritized = prioritize_claims(confident)

    # 4. Budget + adapter
    budget = BudgetTracker(
        hard_budget_bytes=capability.size_constraints.hard_budget_bytes,
        soft_budget_lines=capability.size_constraints.soft_budget_lines,
    )
    adapter_result = adapter.project(prioritized, capability, budget)

    return ProjectionResult(
        adapter_result=adapter_result,
        excluded_sensitive=excluded_sensitive,
        excluded_low_confidence=low_confidence_excluded,
        warnings=warnings,
    )
