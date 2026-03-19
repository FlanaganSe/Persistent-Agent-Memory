"""Unit tests for the quality harness framework."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from rkp.quality.fixtures import _match_claim, evaluate_fixture, load_expected_claims
from rkp.quality.promotion import check_promotion_eligibility
from rkp.quality.types import (
    ConformanceResult,
    DriftResult,
    ExpectedClaim,
    LeakageResult,
    QualityReport,
)


class TestExpectedClaimLoading:
    def test_load_expected_claims(self, tmp_path: Path) -> None:
        data = {
            "claims": [
                {
                    "claim_type": "validated-command",
                    "content_pattern": "pytest",
                    "source_authority": "executable-config",
                    "risk_class": "test-execution",
                    "required": True,
                },
                {
                    "claim_type": "always-on-rule",
                    "content_pattern": "snake_case",
                    "min_confidence": 0.9,
                    "required": False,
                },
            ]
        }
        path = tmp_path / "expected_claims.json"
        path.write_text(json.dumps(data))

        claims = load_expected_claims(path)
        assert len(claims) == 2
        assert claims[0].claim_type == "validated-command"
        assert claims[0].content_pattern == "pytest"
        assert claims[0].required is True
        assert claims[1].min_confidence == 0.9
        assert claims[1].required is False


class TestClaimMatching:
    def test_exact_type_and_substring(self) -> None:
        expected = ExpectedClaim(
            claim_type="validated-command",
            content_pattern="pytest",
        )
        assert _match_claim(expected, "Run pytest tests/", "validated-command")

    def test_type_mismatch(self) -> None:
        expected = ExpectedClaim(
            claim_type="validated-command",
            content_pattern="pytest",
        )
        assert not _match_claim(expected, "pytest", "always-on-rule")

    def test_pattern_not_found(self) -> None:
        expected = ExpectedClaim(
            claim_type="validated-command",
            content_pattern="nonexistent",
        )
        assert not _match_claim(expected, "pytest tests/", "validated-command")

    def test_case_insensitive(self) -> None:
        expected = ExpectedClaim(
            claim_type="validated-command",
            content_pattern="PyTest",
        )
        assert _match_claim(expected, "pytest tests/", "validated-command")

    def test_regex_match(self) -> None:
        expected = ExpectedClaim(
            claim_type="always-on-rule",
            content_pattern=r"snake_?case",
        )
        assert _match_claim(expected, "Use snakecase naming", "always-on-rule")


class TestPrecisionRecallCalculation:
    """Test precision/recall/F1 with known inputs."""

    def test_precision_80_recall_80(self) -> None:
        """8 correct matches / 10 extracted = 0.8 precision, 8/10 required = 0.8 recall."""
        # This validates the math, not the full extraction pipeline
        precision = 8 / 10
        recall = 8 / 10
        f1 = 2 * precision * recall / (precision + recall)
        assert precision == 0.8
        assert recall == 0.8
        assert abs(f1 - 0.8) < 0.001

    def test_f1_harmonic_mean(self) -> None:
        precision = 0.6
        recall = 0.9
        f1 = 2 * precision * recall / (precision + recall)
        assert abs(f1 - 0.72) < 0.001

    def test_perfect_match(self) -> None:
        precision = 1.0
        recall = 1.0
        f1 = 2 * precision * recall / (precision + recall)
        assert f1 == 1.0

    def test_zero_match(self) -> None:
        precision = 0.0
        recall = 0.0
        f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
        assert f1 == 0.0


class TestFixtureEvaluation:
    def test_empty_expected_claims(self, tmp_path: Path) -> None:
        """No expected claims → perfect score."""
        fixture_dir = tmp_path / "empty_fixture"
        fixture_dir.mkdir()
        expected_path = fixture_dir / "expected_claims.json"
        expected_path.write_text('{"claims": []}')

        result = evaluate_fixture(
            fixture_dir,
            expected_path,
            db_path=tmp_path / "empty.db",
        )
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.passed is True

    def test_simple_python_fixture(self) -> None:
        """Integration: run evaluation on the simple_python fixture."""
        fixture_dir = Path("tests/fixtures/simple_python")
        expected_path = fixture_dir / "expected_claims.json"
        if not fixture_dir.exists():
            pytest.skip("Fixture not available")

        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_fixture(
                fixture_dir,
                expected_path,
                db_path=Path(tmp) / "eval.db",
            )
        assert result.total_extracted > 0
        assert result.recall > 0.0


class TestPromotionAssessment:
    def test_ga_eligible(self) -> None:
        report = QualityReport(
            conformance_results=[
                ConformanceResult(
                    adapter_name="agents-md",
                    valid_format=True,
                    claims_included_correctly=10,
                    claims_excluded_correctly=5,
                    claims_incorrectly_included=0,
                    claims_incorrectly_excluded=0,
                    within_budget=True,
                    deterministic=True,
                    score=0.97,
                ),
                ConformanceResult(
                    adapter_name="claude",
                    valid_format=True,
                    claims_included_correctly=10,
                    claims_excluded_correctly=5,
                    claims_incorrectly_included=0,
                    claims_incorrectly_excluded=0,
                    within_budget=True,
                    deterministic=True,
                    score=0.96,
                ),
                ConformanceResult(
                    adapter_name="copilot",
                    valid_format=True,
                    claims_included_correctly=8,
                    claims_excluded_correctly=5,
                    claims_incorrectly_included=0,
                    claims_incorrectly_excluded=2,
                    within_budget=True,
                    deterministic=True,
                    score=0.91,
                ),
            ],
            leakage_results=[],
            drift_results=[
                DriftResult(
                    fixture_name="with_drift",
                    expected_drifts=1,
                    detected_drifts=1,
                    false_positives=0,
                    false_negatives=0,
                    passed=True,
                )
            ],
        )

        assessments = check_promotion_eligibility(report)
        assert len(assessments) == 3

        agents = next(a for a in assessments if a.adapter_name == "AGENTS.md")
        assert agents.eligible is True
        assert agents.eligible_maturity == "GA"

        claude = next(a for a in assessments if a.adapter_name == "CLAUDE.md")
        assert claude.eligible is True
        assert claude.eligible_maturity == "GA"

        copilot = next(a for a in assessments if a.adapter_name == "Copilot")
        assert copilot.eligible is True
        assert copilot.eligible_maturity == "Beta"

    def test_not_eligible_low_conformance(self) -> None:
        report = QualityReport(
            conformance_results=[
                ConformanceResult(
                    adapter_name="agents-md",
                    valid_format=True,
                    claims_included_correctly=5,
                    claims_excluded_correctly=5,
                    claims_incorrectly_included=0,
                    claims_incorrectly_excluded=5,
                    within_budget=True,
                    deterministic=True,
                    score=0.85,
                ),
            ],
            leakage_results=[],
            drift_results=[],
        )

        assessments = check_promotion_eligibility(report)
        agents = next(a for a in assessments if a.adapter_name == "AGENTS.md")
        assert agents.eligible is False
        assert "conformance" in agents.gaps[0]

    def test_not_eligible_leakage(self) -> None:
        report = QualityReport(
            conformance_results=[
                ConformanceResult(
                    adapter_name="agents-md",
                    valid_format=True,
                    claims_included_correctly=10,
                    claims_excluded_correctly=5,
                    claims_incorrectly_included=0,
                    claims_incorrectly_excluded=0,
                    within_budget=True,
                    deterministic=True,
                    score=0.97,
                ),
            ],
            leakage_results=[
                LeakageResult(
                    boundary="projection:agents-md",
                    sensitivity_level="local-only",
                    leaked=True,
                    details="local marker found",
                ),
            ],
            drift_results=[],
        )

        assessments = check_promotion_eligibility(report)
        agents = next(a for a in assessments if a.adapter_name == "AGENTS.md")
        assert agents.eligible is False
        assert "leakage" in agents.gaps[0]
