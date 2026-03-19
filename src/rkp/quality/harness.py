"""Quality harness runner — full evaluation framework."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import structlog

from rkp.quality.conformance import evaluate_conformance
from rkp.quality.fixtures import evaluate_fixture
from rkp.quality.leakage import test_leakage
from rkp.quality.promotion import check_promotion_eligibility
from rkp.quality.types import (
    DriftResult,
    ImportFidelityResult,
    PerformanceResults,
    QualityReport,
)
from rkp.store.artifacts import SqliteArtifactStore
from rkp.store.database import open_database, run_migrations

logger = structlog.get_logger()

_ADAPTERS = ("agents-md", "claude", "copilot")


def _evaluate_fixtures(fixtures_dir: Path) -> list[object]:
    """Run extraction precision/recall on each fixture with expected_claims.json."""
    from rkp.quality.types import FixtureResult

    results: list[FixtureResult] = []
    for fixture_path in sorted(fixtures_dir.iterdir()):
        if not fixture_path.is_dir():
            continue
        expected_path = fixture_path / "expected_claims.json"
        if not expected_path.exists():
            continue

        # Check that expected_claims.json has the standardized format
        with expected_path.open() as f:
            data = json.load(f)
        if "claims" not in data:
            logger.info("Skipping fixture (legacy format)", fixture=fixture_path.name)
            continue

        # Use a temp DB to avoid polluting fixtures
        with tempfile.TemporaryDirectory() as tmp:
            tmp_db = Path(tmp) / "eval.db"
            result = evaluate_fixture(fixture_path, expected_path, db_path=tmp_db)
            results.append(result)

    return results  # type: ignore[return-value]


def _evaluate_conformance(fixtures_dir: Path) -> list[object]:
    """Run export conformance for each adapter on the simple_python fixture."""
    from rkp.quality.types import ConformanceResult

    results: list[ConformanceResult] = []
    fixture_path = fixtures_dir / "simple_python"
    if not fixture_path.is_dir():
        return results  # type: ignore[return-value]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db_path = Path(tmp) / "conformance.db"
        db = open_database(tmp_db_path)
        run_migrations(db)

        # Run extraction first to populate claims
        from rkp.graph.repo_graph import SqliteRepoGraph
        from rkp.indexer.orchestrator import run_extraction
        from rkp.store.claims import SqliteClaimStore

        store = SqliteClaimStore(db)
        graph = SqliteRepoGraph(db, repo_id="conformance-test", branch="main")
        run_extraction(
            fixture_path,
            store,
            repo_id="conformance-test",
            branch="main",
            graph=graph,
        )

        for adapter_name in _ADAPTERS:
            result = evaluate_conformance(db, adapter_name, repo_id="conformance-test")
            results.append(result)

        db.close()

    return results  # type: ignore[return-value]


def _evaluate_leakage() -> list[object]:
    """Run leakage tests across all output boundaries."""
    from rkp.quality.types import LeakageResult

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db_path = Path(tmp) / "leakage.db"
        db = open_database(tmp_db_path)
        run_migrations(db)

        try:
            results: list[LeakageResult] = test_leakage(db)
        finally:
            db.close()

    return results  # type: ignore[return-value]


def _evaluate_drift(fixtures_dir: Path) -> list[object]:
    """Run drift detection on the with_drift fixture."""
    from rkp.quality.types import DriftResult

    results: list[DriftResult] = []
    drift_fixture = fixtures_dir / "with_drift"
    if not drift_fixture.is_dir():
        return results  # type: ignore[return-value]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db_path = Path(tmp) / "drift.db"
        db = open_database(tmp_db_path)
        run_migrations(db)

        artifact_store = SqliteArtifactStore(db)

        # Load pre-populated drift data
        drift_data_path = drift_fixture / "drift_setup.json"
        if drift_data_path.exists():
            with drift_data_path.open() as f:
                drift_data = json.load(f)

            from rkp.core.types import ArtifactOwnership

            for artifact in drift_data.get("artifacts", []):
                artifact_store.register_artifact(
                    path=artifact["path"],
                    artifact_type=artifact["artifact_type"],
                    target_host=artifact["target_host"],
                    expected_hash=artifact["expected_hash"],
                    ownership=ArtifactOwnership(artifact["ownership"]),
                )

            # Run drift detection
            report = artifact_store.detect_drift(drift_fixture)

            expected_drifts = drift_data.get("expected_drift_count", 0)
            detected_drifts = len(report.content_drifts)

            results.append(
                DriftResult(
                    fixture_name="with_drift",
                    expected_drifts=expected_drifts,
                    detected_drifts=detected_drifts,
                    false_positives=max(0, detected_drifts - expected_drifts),
                    false_negatives=max(0, expected_drifts - detected_drifts),
                    passed=detected_drifts == expected_drifts,
                )
            )

        db.close()

    return results  # type: ignore[return-value]


def _evaluate_import_fidelity(fixtures_dir: Path) -> list[object]:
    """Run import → project round-trip tests."""
    from rkp.quality.types import ImportFidelityResult

    results: list[ImportFidelityResult] = []
    agents_fixture = fixtures_dir / "with_agents_md"
    if not agents_fixture.is_dir():
        return results  # type: ignore[return-value]

    agents_md_path = agents_fixture / "AGENTS.md"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db_path = Path(tmp) / "fidelity.db"
        db = open_database(tmp_db_path)
        run_migrations(db)

        try:
            from rkp.importer.engine import run_import
            from rkp.store.claims import SqliteClaimStore

            store = SqliteClaimStore(db)

            # Import AGENTS.md
            if agents_md_path.exists():
                run_import(
                    agents_fixture,
                    store,
                    repo_id="fidelity-test",
                    branch="main",
                )
                # Project back through agents-md adapter
                from rkp.projection.adapters.agents_md import AgentsMdAdapter
                from rkp.projection.capability_matrix import AGENTS_MD_CAPABILITY
                from rkp.projection.engine import ProjectionPolicy, project

                claims = store.list_claims(repo_id="fidelity-test")
                result = project(
                    claims, AgentsMdAdapter(), AGENTS_MD_CAPABILITY, ProjectionPolicy()
                )

                # Count operational claims that survived (commands + always-on rules)
                from rkp.core.types import ClaimType

                projected_content = result.adapter_result.files.get("AGENTS.md", "")
                operational_claims = [
                    c
                    for c in claims
                    if c.claim_type
                    in (
                        ClaimType.VALIDATED_COMMAND,
                        ClaimType.ALWAYS_ON_RULE,
                        ClaimType.PERMISSION_RESTRICTION,
                    )
                ]
                surviving = 0
                for claim in operational_claims:
                    if claim.content.lower() in projected_content.lower():
                        surviving += 1
                operational_count = len(operational_claims)

                fidelity = surviving / max(operational_count, 1)
                results.append(
                    ImportFidelityResult(
                        source_file="AGENTS.md",
                        adapter_name="agents-md",
                        original_claim_count=operational_count,
                        round_trip_claim_count=len(claims),
                        surviving_claims=surviving,
                        fidelity_score=round(fidelity, 4),
                        passed=fidelity
                        >= 0.2,  # Conservative: import from multiple files, adapter projects subset
                    )
                )
        finally:
            db.close()

    return results  # type: ignore[return-value]


def _format_report(report: QualityReport) -> str:
    """Format a human-readable summary of the quality report."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("RKP Quality Harness Report")
    lines.append("=" * 60)

    # Fixture results
    lines.append("\n--- Extraction Precision/Recall ---")
    for fr in report.fixture_results:
        status = "PASS" if fr.passed else "FAIL"
        lines.append(
            f"  {fr.fixture_name}: precision={fr.precision:.0%} recall={fr.recall:.0%} "
            f"F1={fr.f1:.0%} [{status}]"
        )
        if fr.missing_required:
            lines.extend(
                f"    missing: {m.claim_type} ~ {m.content_pattern}" for m in fr.missing_required
            )

    # Conformance results
    lines.append("\n--- Export Conformance ---")
    for cr in report.conformance_results:
        lines.append(
            f"  {cr.adapter_name}: score={cr.score:.0%} format={'OK' if cr.valid_format else 'FAIL'} "
            f"budget={'OK' if cr.within_budget else 'OVER'} deterministic={'YES' if cr.deterministic else 'NO'}"
        )
        if cr.details:
            lines.extend(f"    {d}" for d in cr.details)

    # Leakage results
    lines.append("\n--- Sensitivity Leakage ---")
    leaked_count = sum(1 for lr in report.leakage_results if lr.leaked)
    total_checks = len(report.leakage_results)
    lines.append(f"  {total_checks} boundaries checked, {leaked_count} leaked")
    lines.extend(
        f"  LEAKED: {lr.boundary} ({lr.sensitivity_level}): {lr.details}"
        for lr in report.leakage_results
        if lr.leaked
    )

    # Drift results
    lines.append("\n--- Drift Detection ---")
    for dr in report.drift_results:
        status = "PASS" if dr.passed else "FAIL"
        lines.append(
            f"  {dr.fixture_name}: expected={dr.expected_drifts} detected={dr.detected_drifts} [{status}]"
        )

    # Import fidelity
    lines.append("\n--- Import Fidelity ---")
    for ifr in report.import_fidelity_results:
        status = "PASS" if ifr.passed else "FAIL"
        lines.append(
            f"  {ifr.source_file} → {ifr.adapter_name}: fidelity={ifr.fidelity_score:.0%} "
            f"({ifr.surviving_claims}/{ifr.original_claim_count} survived) [{status}]"
        )

    # Performance
    lines.append("\n--- Performance Benchmarks ---")
    for br in report.performance_results.benchmarks:
        status = "PASS" if br.passed else "FAIL"
        lines.append(
            f"  {br.name}: {br.total_time_seconds:.2f}s (gate: {br.gate_seconds:.0f}s) [{status}]"
        )

    # Adapter maturity
    lines.append("\n--- Adapter Maturity Assessment ---")
    for pa in report.promotions:
        if pa.eligible:
            lines.append(
                f"  {pa.adapter_name}: {pa.eligible_maturity} eligible \u2713 "
                f"(conformance: {pa.conformance_score:.0%}, leakage: {pa.leakage_count}, "
                f"drift: {'pass' if pa.drift_pass else 'fail'})"
            )
        else:
            lines.append(
                f"  {pa.adapter_name}: NOT eligible for promotion "
                f"(conformance: {pa.conformance_score:.0%}, gaps: {', '.join(pa.gaps)})"
            )

    # Overall
    lines.append("\n" + "=" * 60)
    lines.append(f"Overall: {'PASS' if report.overall_pass else 'FAIL'}")
    lines.append("=" * 60)

    return "\n".join(lines)


def run_quality_harness(
    fixtures_dir: Path,
    report_path: Path | None = None,
    *,
    skip_performance: bool = False,
) -> QualityReport:
    """Run the full quality harness.

    1. Extraction precision/recall on each fixture
    2. Export conformance for each adapter
    3. Sensitivity leakage across all output boundaries
    4. Drift detection correctness
    5. Import fidelity (import → export round-trip)
    6. Performance benchmarks (optional)
    """
    logger.info("Starting quality harness", fixtures_dir=str(fixtures_dir))

    # 1. Fixture evaluation
    fixture_results = _evaluate_fixtures(fixtures_dir)

    # 2. Conformance
    conformance_results = _evaluate_conformance(fixtures_dir)

    # 3. Leakage
    leakage_results = _evaluate_leakage()

    # 4. Drift
    drift_results = _evaluate_drift(fixtures_dir)

    # 5. Import fidelity
    import_fidelity_results = _evaluate_import_fidelity(fixtures_dir)

    # 6. Performance (optional, slow)
    performance_results = PerformanceResults()
    if not skip_performance:
        from rkp.quality.benchmark import benchmark_extraction, generate_benchmark_repo

        with tempfile.TemporaryDirectory() as tmp:
            bench_dir = Path(tmp) / "bench_repo"
            bench_dir.mkdir()
            generate_benchmark_repo(bench_dir, target_loc=250_000)
            bench_result = benchmark_extraction(bench_dir)
            performance_results = PerformanceResults(benchmarks=(bench_result,))

    # Build report with tuples (frozen dataclass convention)
    from dataclasses import replace as dc_replace

    report = QualityReport(
        fixture_results=tuple(fixture_results),
        conformance_results=tuple(conformance_results),
        leakage_results=tuple(leakage_results),
        drift_results=tuple(drift_results),
        import_fidelity_results=tuple(import_fidelity_results),
        performance_results=performance_results,
    )

    # Promotion assessment
    report = dc_replace(report, promotions=tuple(check_promotion_eligibility(report)))

    # Gate checks
    fixtures_pass = all(fr.passed for fr in report.fixture_results)
    conformance_pass = all(
        cr.score >= 0.95
        for cr in report.conformance_results
        if cr.adapter_name in ("agents-md", "claude")
    )
    leakage_pass = not any(lr.leaked for lr in report.leakage_results)
    drift_pass = all(dr.passed for dr in report.drift_results)
    perf_pass = report.performance_results.all_passed
    fidelity_pass = all(ifr.passed for ifr in report.import_fidelity_results)

    overall_pass = (
        fixtures_pass
        and conformance_pass
        and leakage_pass
        and drift_pass
        and perf_pass
        and fidelity_pass
    )

    report = dc_replace(report, overall_pass=overall_pass)
    summary = _format_report(report)
    report = dc_replace(report, summary=summary)

    # Output
    print(summary, file=sys.stderr)

    if report_path is not None:
        _write_json_report(report, report_path)
        logger.info("Report written", path=str(report_path))

    return report


def _write_json_report(report: QualityReport, path: Path) -> None:
    """Write the quality report as JSON."""
    data = {
        "overall_pass": report.overall_pass,
        "fixture_results": [
            {
                "fixture_name": fr.fixture_name,
                "precision": fr.precision,
                "recall": fr.recall,
                "f1": fr.f1,
                "total_extracted": fr.total_extracted,
                "total_required": fr.total_required,
                "passed": fr.passed,
            }
            for fr in report.fixture_results
        ],
        "conformance_results": [
            {
                "adapter_name": cr.adapter_name,
                "score": cr.score,
                "valid_format": cr.valid_format,
                "within_budget": cr.within_budget,
                "deterministic": cr.deterministic,
                "claims_included_correctly": cr.claims_included_correctly,
                "claims_excluded_correctly": cr.claims_excluded_correctly,
                "claims_incorrectly_included": cr.claims_incorrectly_included,
                "claims_incorrectly_excluded": cr.claims_incorrectly_excluded,
                "details": list(cr.details),
            }
            for cr in report.conformance_results
        ],
        "leakage_results": [
            {
                "boundary": lr.boundary,
                "sensitivity_level": lr.sensitivity_level,
                "leaked": lr.leaked,
                "details": lr.details,
            }
            for lr in report.leakage_results
        ],
        "drift_results": [
            {
                "fixture_name": dr.fixture_name,
                "expected_drifts": dr.expected_drifts,
                "detected_drifts": dr.detected_drifts,
                "passed": dr.passed,
            }
            for dr in report.drift_results
        ],
        "import_fidelity_results": [
            {
                "source_file": ifr.source_file,
                "adapter_name": ifr.adapter_name,
                "fidelity_score": ifr.fidelity_score,
                "surviving_claims": ifr.surviving_claims,
                "original_claim_count": ifr.original_claim_count,
                "passed": ifr.passed,
            }
            for ifr in report.import_fidelity_results
        ],
        "performance_results": [
            {
                "name": br.name,
                "total_time_seconds": br.total_time_seconds,
                "gate_seconds": br.gate_seconds,
                "passed": br.passed,
            }
            for br in report.performance_results.benchmarks
        ],
        "promotions": [
            {
                "adapter_name": pa.adapter_name,
                "current_maturity": pa.current_maturity,
                "eligible_maturity": pa.eligible_maturity,
                "eligible": pa.eligible,
                "conformance_score": pa.conformance_score,
                "leakage_count": pa.leakage_count,
                "drift_pass": pa.drift_pass,
                "gaps": list(pa.gaps),
            }
            for pa in report.promotions
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
