"""Tests for the command extractor."""

from __future__ import annotations

from rkp.core.types import EvidenceLevel, RiskClass, Sensitivity, SourceAuthority
from rkp.indexer.extractors.commands import ParsedCommand, extract_command_claims


class TestCommandExtractor:
    def test_extract_basic_commands(self) -> None:
        """Extract claims from parsed commands."""
        commands = (
            ParsedCommand(
                name="test",
                command="pytest",
                source_file="pyproject.toml",
                risk_class=RiskClass.TEST_EXECUTION,
            ),
            ParsedCommand(
                name="lint",
                command="ruff check .",
                source_file="pyproject.toml",
                risk_class=RiskClass.SAFE_READONLY,
            ),
        )
        results = extract_command_claims(commands)
        assert len(results) == 2

    def test_claim_fields(self) -> None:
        """Verify claim input fields are correctly populated."""
        commands = (
            ParsedCommand(
                name="test",
                command="pytest",
                source_file="pyproject.toml",
                risk_class=RiskClass.TEST_EXECUTION,
                confidence=0.95,
            ),
        )
        results = extract_command_claims(commands)
        claim = results[0]
        assert claim.content == "pytest"
        assert claim.source_authority == SourceAuthority.EXECUTABLE_CONFIG
        assert claim.evidence_level == EvidenceLevel.DISCOVERED
        assert claim.risk_class == RiskClass.TEST_EXECUTION
        assert claim.confidence == 0.95
        assert claim.sensitivity == Sensitivity.PUBLIC
        assert "pyproject.toml" in claim.evidence_files

    def test_applicability_for_test(self) -> None:
        """Test commands get test applicability."""
        commands = (
            ParsedCommand(
                name="test",
                command="pytest",
                source_file="pyproject.toml",
                risk_class=RiskClass.TEST_EXECUTION,
            ),
        )
        results = extract_command_claims(commands)
        assert "test" in results[0].applicability

    def test_applicability_for_lint(self) -> None:
        """Lint commands get lint applicability."""
        commands = (
            ParsedCommand(
                name="lint",
                command="ruff check",
                source_file="pyproject.toml",
                risk_class=RiskClass.SAFE_READONLY,
            ),
        )
        results = extract_command_claims(commands)
        assert "lint" in results[0].applicability

    def test_custom_scope(self) -> None:
        """Custom scope is passed through."""
        commands = (
            ParsedCommand(
                name="test",
                command="pytest",
                source_file="pyproject.toml",
                risk_class=RiskClass.TEST_EXECUTION,
            ),
        )
        results = extract_command_claims(commands, scope="src/")
        assert results[0].scope == "src/"

    def test_empty_input(self) -> None:
        """Empty command list returns empty results."""
        results = extract_command_claims(())
        assert results == []
