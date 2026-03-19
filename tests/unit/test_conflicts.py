"""Unit tests for the conflict detector."""

from __future__ import annotations

import pytest

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, SourceAuthority
from rkp.indexer.extractors.conflicts import detect_conflicts


@pytest.fixture
def builder():
    return ClaimBuilder(repo_id="test-repo")


def _make_prereq(builder, content, authority, evidence):
    return builder.build(
        content=content,
        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
        source_authority=authority,
        confidence=1.0,
        evidence=evidence,
    )


def _make_command(builder, content, authority, evidence):
    return builder.build(
        content=content,
        claim_type=ClaimType.VALIDATED_COMMAND,
        source_authority=authority,
        confidence=1.0,
        evidence=evidence,
    )


class TestVersionConflicts:
    def test_detects_version_conflict(self, builder):
        """Detect when two sources specify different Python versions."""
        claim_a = _make_prereq(
            builder, "Python 3.11", SourceAuthority.EXECUTABLE_CONFIG, (".python-version",)
        )
        claim_b = _make_prereq(
            builder, "Python 3.12", SourceAuthority.EXECUTABLE_CONFIG, ("pyproject.toml",)
        )

        result = detect_conflicts([claim_a, claim_b])
        assert len(result.conflicts) == 1
        assert result.conflicts[0].conflict_type == "version"
        assert "3.11" in result.conflicts[0].content
        assert "3.12" in result.conflicts[0].content

    def test_no_conflict_with_range(self, builder):
        """No conflict between '>=3.12' and '3.12'."""
        claim_a = _make_prereq(
            builder, "Python >=3.12", SourceAuthority.EXECUTABLE_CONFIG, ("pyproject.toml",)
        )
        claim_b = _make_prereq(
            builder, "Python 3.12", SourceAuthority.EXECUTABLE_CONFIG, (".python-version",)
        )

        result = detect_conflicts([claim_a, claim_b])
        assert len(result.conflicts) == 0

    def test_no_conflict_same_version(self, builder):
        """No conflict when versions match."""
        claim_a = _make_prereq(
            builder, "Python 3.12", SourceAuthority.EXECUTABLE_CONFIG, ("pyproject.toml",)
        )
        claim_b = _make_prereq(
            builder, "Python 3.12", SourceAuthority.CI_OBSERVED, (".github/workflows/ci.yml",)
        )

        result = detect_conflicts([claim_a, claim_b])
        assert len(result.conflicts) == 0

    def test_different_runtimes_no_conflict(self, builder):
        """Different runtimes (Python vs Node) are not conflicts."""
        claim_a = _make_prereq(
            builder, "Python 3.12", SourceAuthority.EXECUTABLE_CONFIG, ("pyproject.toml",)
        )
        claim_b = _make_prereq(
            builder, "node >=18", SourceAuthority.EXECUTABLE_CONFIG, ("package.json",)
        )

        result = detect_conflicts([claim_a, claim_b])
        assert len(result.conflicts) == 0


class TestCommandConflicts:
    def test_detects_missing_test_script(self, builder):
        """Detect when README references 'npm test' but no test script exists."""
        docs_cmd = _make_command(
            builder, "npm test", SourceAuthority.CHECKED_IN_DOCS, ("README.md",)
        )
        config_cmd = _make_command(
            builder, "npm run build", SourceAuthority.EXECUTABLE_CONFIG, ("package.json",)
        )

        result = detect_conflicts([docs_cmd, config_cmd])
        assert any(c.conflict_type == "command" for c in result.conflicts)


class TestNoConflicts:
    def test_empty_claims(self, builder):
        """No conflicts when there are no claims."""
        result = detect_conflicts([])
        assert len(result.conflicts) == 0

    def test_single_claim(self, builder):
        """No conflicts with a single claim."""
        claim = _make_prereq(
            builder, "Python 3.12", SourceAuthority.EXECUTABLE_CONFIG, ("pyproject.toml",)
        )
        result = detect_conflicts([claim])
        assert len(result.conflicts) == 0

    def test_minor_wording_not_conflict(self, builder):
        """Minor wording differences in conventions are not conflicts."""
        # Both claim snake_case — same assertion, not a conflict
        conv_a = builder.build(
            content="Use snake_case for function names (95% consistency across 50 identifiers)",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.95,
        )
        conv_b = builder.build(
            content="Use snake_case for function names (97% consistency across 60 identifiers)",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.97,
        )

        result = detect_conflicts([conv_a, conv_b])
        # These are similar but technically different content — still shouldn't be a convention conflict
        # because they both assert snake_case (same style)
        convention_conflicts = [c for c in result.conflicts if c.conflict_type == "convention"]
        assert len(convention_conflicts) == 0
