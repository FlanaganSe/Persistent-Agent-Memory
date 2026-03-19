"""Adapter maturity promotion — gated decision based on quality results."""

from __future__ import annotations

from collections.abc import Sequence

from rkp.quality.types import (
    ConformanceResult,
    DriftResult,
    LeakageResult,
    PromotionAssessment,
    QualityReport,
)

# Promotion thresholds
_GA_CONFORMANCE_THRESHOLD = 0.95
_BETA_CONFORMANCE_THRESHOLD = 0.0  # Beta just needs conformance to pass with documented gaps


def _count_leakage(results: Sequence[LeakageResult], adapter_name: str) -> int:
    """Count leakage incidents for a specific adapter's projection boundary."""
    return sum(
        1 for r in results if r.leaked and r.boundary.startswith(f"projection:{adapter_name}")
    )


def _drift_passed(results: Sequence[DriftResult]) -> bool:
    """Check if all drift tests passed."""
    return all(r.passed for r in results)


def _get_conformance(
    results: Sequence[ConformanceResult],
    adapter_name: str,
) -> ConformanceResult | None:
    """Get conformance result for a specific adapter."""
    for r in results:
        if r.adapter_name == adapter_name:
            return r
    return None


def check_promotion_eligibility(
    report: QualityReport,
) -> list[PromotionAssessment]:
    """Determine earned maturity level for each adapter based on quality results.

    Promotion criteria:
    - AGENTS.md → GA: conformance ≥ 95%, zero leakage, drift tests pass
    - CLAUDE.md → GA: conformance ≥ 95%, zero leakage, drift tests pass
    - Copilot → Beta: conformance passes with documented gaps
    """
    assessments: list[PromotionAssessment] = []
    drift_pass = _drift_passed(report.drift_results)

    # AGENTS.md
    agents_conf = _get_conformance(report.conformance_results, "agents-md")
    agents_leakage = _count_leakage(report.leakage_results, "agents-md")
    agents_score = agents_conf.score if agents_conf else 0.0
    agents_gaps: list[str] = []
    if agents_score < _GA_CONFORMANCE_THRESHOLD:
        agents_gaps.append(f"conformance {agents_score:.0%} < {_GA_CONFORMANCE_THRESHOLD:.0%}")
    if agents_leakage > 0:
        agents_gaps.append(f"{agents_leakage} leakage incident(s)")
    if not drift_pass:
        agents_gaps.append("drift tests failed")
    agents_eligible = len(agents_gaps) == 0

    assessments.append(
        PromotionAssessment(
            adapter_name="AGENTS.md",
            current_maturity="Preview",
            eligible_maturity="GA" if agents_eligible else "Preview",
            eligible=agents_eligible,
            conformance_score=agents_score,
            leakage_count=agents_leakage,
            drift_pass=drift_pass,
            gaps=tuple(agents_gaps),
        )
    )

    # CLAUDE.md
    claude_conf = _get_conformance(report.conformance_results, "claude")
    claude_leakage = _count_leakage(report.leakage_results, "claude")
    claude_score = claude_conf.score if claude_conf else 0.0
    claude_gaps: list[str] = []
    if claude_score < _GA_CONFORMANCE_THRESHOLD:
        claude_gaps.append(f"conformance {claude_score:.0%} < {_GA_CONFORMANCE_THRESHOLD:.0%}")
    if claude_leakage > 0:
        claude_gaps.append(f"{claude_leakage} leakage incident(s)")
    if not drift_pass:
        claude_gaps.append("drift tests failed")
    claude_eligible = len(claude_gaps) == 0

    assessments.append(
        PromotionAssessment(
            adapter_name="CLAUDE.md",
            current_maturity="Preview",
            eligible_maturity="GA" if claude_eligible else "Preview",
            eligible=claude_eligible,
            conformance_score=claude_score,
            leakage_count=claude_leakage,
            drift_pass=drift_pass,
            gaps=tuple(claude_gaps),
        )
    )

    # Copilot
    copilot_conf = _get_conformance(report.conformance_results, "copilot")
    copilot_leakage = _count_leakage(report.leakage_results, "copilot")
    copilot_score = copilot_conf.score if copilot_conf else 0.0
    copilot_gaps: list[str] = []
    if copilot_conf and copilot_conf.details:
        copilot_gaps.extend(copilot_conf.details)
    copilot_eligible = copilot_conf is not None and copilot_conf.valid_format

    assessments.append(
        PromotionAssessment(
            adapter_name="Copilot",
            current_maturity="Preview",
            eligible_maturity="Beta" if copilot_eligible else "Preview",
            eligible=copilot_eligible,
            conformance_score=copilot_score,
            leakage_count=copilot_leakage,
            drift_pass=drift_pass,
            gaps=tuple(copilot_gaps),
        )
    )

    return assessments
