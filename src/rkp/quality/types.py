"""Quality harness data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedClaim:
    """A single expected claim in a fixture's ground truth."""

    claim_type: str
    content_pattern: str
    source_authority: str | None = None
    risk_class: str | None = None
    min_confidence: float | None = None
    required: bool = True


@dataclass(frozen=True)
class ClaimMatch:
    """Record of a match between expected and extracted claim."""

    expected: ExpectedClaim
    extracted_claim_id: str
    extracted_content: str
    match_type: str  # "exact", "substring", "regex"


@dataclass(frozen=True)
class FixtureResult:
    """Per-fixture extraction precision/recall measurement."""

    fixture_name: str
    precision: float
    recall: float
    f1: float
    total_extracted: int
    total_required: int
    matches: tuple[ClaimMatch, ...] = ()
    missing_required: tuple[ExpectedClaim, ...] = ()
    passed: bool = True


@dataclass(frozen=True)
class ConformanceResult:
    """Per-adapter export conformance measurement."""

    adapter_name: str
    valid_format: bool
    claims_included_correctly: int
    claims_excluded_correctly: int
    claims_incorrectly_included: int
    claims_incorrectly_excluded: int
    within_budget: bool
    deterministic: bool
    score: float
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class LeakageResult:
    """Result of a single leakage boundary check."""

    boundary: str  # "mcp:get_conventions", "projection:agents-md", etc.
    sensitivity_level: str  # "local-only" or "team-only"
    leaked: bool
    details: str = ""


@dataclass(frozen=True)
class DriftResult:
    """Drift detection correctness on a fixture."""

    fixture_name: str
    expected_drifts: int
    detected_drifts: int
    false_positives: int
    false_negatives: int
    passed: bool = True


@dataclass(frozen=True)
class ImportFidelityResult:
    """Import round-trip fidelity measurement."""

    source_file: str
    adapter_name: str
    original_claim_count: int
    round_trip_claim_count: int
    surviving_claims: int
    fidelity_score: float
    passed: bool = True


@dataclass(frozen=True)
class BenchmarkResult:
    """Performance benchmark measurement."""

    name: str
    total_time_seconds: float
    gate_seconds: float
    passed: bool
    files_parsed: int = 0
    claims_created: int = 0
    memory_peak_mb: float = 0.0


@dataclass(frozen=True)
class PerformanceResults:
    """Aggregate performance benchmark results."""

    benchmarks: tuple[BenchmarkResult, ...] = ()

    @property
    def all_passed(self) -> bool:
        return all(b.passed for b in self.benchmarks)


@dataclass(frozen=True)
class PromotionAssessment:
    """Adapter maturity promotion assessment."""

    adapter_name: str
    current_maturity: str
    eligible_maturity: str
    eligible: bool
    conformance_score: float
    leakage_count: int
    drift_pass: bool
    gaps: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualityReport:
    """Full quality harness report."""

    fixture_results: tuple[FixtureResult, ...] = ()
    conformance_results: tuple[ConformanceResult, ...] = ()
    leakage_results: tuple[LeakageResult, ...] = ()
    drift_results: tuple[DriftResult, ...] = ()
    import_fidelity_results: tuple[ImportFidelityResult, ...] = ()
    performance_results: PerformanceResults = PerformanceResults()
    promotions: tuple[PromotionAssessment, ...] = ()
    overall_pass: bool = False
    summary: str = ""
