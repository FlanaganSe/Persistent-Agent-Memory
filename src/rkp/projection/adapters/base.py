"""Base adapter Protocol for projection targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rkp.core.models import Claim
from rkp.projection.budget import BudgetTracker
from rkp.projection.capability_matrix import HostCapability


@dataclass(frozen=True)
class AdapterResult:
    """Result of adapter projection."""

    files: dict[str, str]
    excluded_claims: list[tuple[str, str]]
    overflow_report: dict[str, object]


class BaseAdapter(Protocol):
    """Protocol for host-specific projection adapters."""

    def project(
        self,
        claims: list[Claim],
        capability: HostCapability,
        budget: BudgetTracker,
    ) -> AdapterResult: ...
