"""Fixture evaluation — compare extracted claims against ground truth."""

from __future__ import annotations

import json
import re
from pathlib import Path

import structlog

from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.indexer.orchestrator import run_extraction
from rkp.quality.types import ClaimMatch, ExpectedClaim, FixtureResult
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations

logger = structlog.get_logger()


def load_expected_claims(expected_path: Path) -> list[ExpectedClaim]:
    """Load expected claims from a fixture's expected_claims.json."""
    with expected_path.open() as f:
        data = json.load(f)

    claims_data = data.get("claims", [])
    return [
        ExpectedClaim(
            claim_type=item["claim_type"],
            content_pattern=item["content_pattern"],
            source_authority=item.get("source_authority"),
            risk_class=item.get("risk_class"),
            min_confidence=item.get("min_confidence"),
            required=item.get("required", True),
        )
        for item in claims_data
    ]


def _match_claim(
    expected: ExpectedClaim,
    extracted_content: str,
    extracted_type: str,
) -> bool:
    """Check if an extracted claim matches an expected claim."""
    if extracted_type != expected.claim_type:
        return False
    pattern = expected.content_pattern
    # Try substring match first
    if pattern.lower() in extracted_content.lower():
        return True
    # Try regex match
    try:
        if re.search(pattern, extracted_content, re.IGNORECASE):
            return True
    except re.error:
        pass
    return False


def evaluate_fixture(
    fixture_path: Path,
    expected_claims_path: Path,
    db_path: Path | None = None,
) -> FixtureResult:
    """Extract claims from a fixture repo and compare against expected claims.

    Returns precision, recall, F1, and per-claim match details.
    """
    fixture_name = fixture_path.name
    expected = load_expected_claims(expected_claims_path)

    if not expected:
        return FixtureResult(
            fixture_name=fixture_name,
            precision=1.0,
            recall=1.0,
            f1=1.0,
            total_extracted=0,
            total_required=0,
            passed=True,
        )

    # Run extraction on the fixture repo
    effective_db_path = db_path or (fixture_path / ".rkp" / "local" / "rkp.db")
    effective_db_path.parent.mkdir(parents=True, exist_ok=True)

    db = open_database(effective_db_path)
    run_migrations(db)
    store = SqliteClaimStore(db)
    graph = SqliteRepoGraph(db, repo_id=fixture_name, branch="main")

    try:
        run_extraction(
            fixture_path,
            store,
            repo_id=fixture_name,
            branch="main",
            graph=graph,
        )

        extracted = store.list_claims(repo_id=fixture_name)
    finally:
        db.close()

    # Match expected claims against extracted
    matches: list[ClaimMatch] = []
    missing_required: list[ExpectedClaim] = []
    matched_extracted_ids: set[str] = set()

    required_claims = [e for e in expected if e.required]

    for exp in required_claims:
        found = False
        for claim in extracted:
            if claim.id in matched_extracted_ids:
                continue
            if _match_claim(exp, claim.content, claim.claim_type.value):
                # Additional checks
                if exp.min_confidence is not None and claim.confidence < exp.min_confidence:
                    continue
                matches.append(
                    ClaimMatch(
                        expected=exp,
                        extracted_claim_id=claim.id,
                        extracted_content=claim.content,
                        match_type="substring",
                    )
                )
                matched_extracted_ids.add(claim.id)
                found = True
                break
        if not found:
            missing_required.append(exp)

    # Precision/Recall per the spec:
    # - Recall: required claims found / total required
    # - Precision: correct matches / (correct matches + false positives)
    #   Per spec: "Additional extracted claims not in expected → don't penalize precision"
    #   So only false positives are claims incorrectly matched. Since matching is by
    #   type + content pattern, all matches are correct by construction.
    #   Precision = matched / matched = 1.0 when there are matches.
    total_required = len(required_claims)
    matched_count = len(matches)

    recall = matched_count / total_required if total_required > 0 else 1.0
    # Precision: all matches are correct (type+content verified), no false positives.
    # This metric is 1.0 by construction — the real quality gate is recall.
    precision = 1.0 if matched_count > 0 else (1.0 if total_required == 0 else 0.0)

    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    passed = precision >= 0.8 and recall >= 0.8

    return FixtureResult(
        fixture_name=fixture_name,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        total_extracted=len(extracted),
        total_required=total_required,
        matches=tuple(matches),
        missing_required=tuple(missing_required),
        passed=passed,
    )
