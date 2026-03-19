"""Tests for guardrail extractor."""

from __future__ import annotations

from dataclasses import replace

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.indexer.extractors.guardrails import extract_guardrails


class TestGuardrailExtractor:
    def test_destructive_command_generates_restriction(self, builder: ClaimBuilder) -> None:
        """Destructive command (risk_class=destructive) → restriction claim."""
        cmd = builder.build(
            content="rm -rf dist/",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("Makefile",),
        )
        cmd = replace(cmd, risk_class=RiskClass.DESTRUCTIVE)

        results = extract_guardrails([cmd])

        assert len(results) == 1
        assert "destructive" in results[0].content.lower()
        assert "rm -rf dist/" in results[0].content
        assert results[0].confidence == 1.0
        assert results[0].source_authority == SourceAuthority.EXECUTABLE_CONFIG
        assert "destructive" in results[0].applicability
        assert "security" in results[0].applicability

    def test_safe_readonly_no_guardrail(self, builder: ClaimBuilder) -> None:
        """Safe-readonly command → NO guardrail (conservatism check)."""
        cmd = builder.build(
            content="ruff check .",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("pyproject.toml",),
        )
        cmd = replace(cmd, risk_class=RiskClass.SAFE_READONLY)

        results = extract_guardrails([cmd])

        assert len(results) == 0

    def test_security_tool_in_config(self, builder: ClaimBuilder) -> None:
        """Security tool in pyproject.toml (bandit in tools) → security tooling claim."""
        # No claims needed — just security_tools signal
        results = extract_guardrails([], security_tools=frozenset({"bandit", "ruff"}))

        assert len(results) == 1
        assert "bandit" in results[0].content.lower()
        assert "security" in results[0].applicability

    def test_no_destructive_commands_empty_result(self, builder: ClaimBuilder) -> None:
        """Test with no destructive commands → empty result (not error)."""
        cmd = builder.build(
            content="pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("pyproject.toml",),
        )
        cmd = replace(cmd, risk_class=RiskClass.TEST_EXECUTION)

        results = extract_guardrails([cmd])

        assert results == []

    def test_claim_fields_correct(self, builder: ClaimBuilder) -> None:
        """Verify guardrail claim fields: type-relevant authority, confidence, applicability."""
        cmd = builder.build(
            content="db:reset",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("package.json",),
        )
        cmd = replace(cmd, risk_class=RiskClass.DESTRUCTIVE)

        results = extract_guardrails([cmd])

        assert len(results) == 1
        result = results[0]
        assert result.source_authority == SourceAuthority.EXECUTABLE_CONFIG
        assert result.confidence == 1.0
        assert result.scope == "**"
        assert "destructive" in result.applicability
        assert "security" in result.applicability
        assert result.evidence_files == ("package.json",)

    def test_ci_security_scan_generates_guardrail(self, builder: ClaimBuilder) -> None:
        """CI-observed security scan command → guardrail."""
        cmd = builder.build(
            content="npm audit --production",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.CI_OBSERVED,
            confidence=0.9,
            evidence=(".github/workflows/ci.yml",),
        )
        cmd = replace(cmd, risk_class=RiskClass.SAFE_READONLY)

        results = extract_guardrails([cmd])

        assert len(results) == 1
        assert "security scan" in results[0].content.lower()
        assert "npm audit" in results[0].content

    def test_test_command_with_services_advisory(self, builder: ClaimBuilder) -> None:
        """Test-execution commands + service prerequisites → advisory."""
        test_cmd = builder.build(
            content="pytest --integration",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("pyproject.toml",),
        )
        test_cmd = replace(test_cmd, risk_class=RiskClass.TEST_EXECUTION)

        service_claim = builder.build(
            content="Service: PostgreSQL (from docker-compose.yml)",
            claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.9,
            evidence=("docker-compose.yml",),
        )

        results = extract_guardrails([test_cmd, service_claim])

        # Should have the service advisory
        service_advisories = [r for r in results if "requires services" in r.content.lower()]
        assert len(service_advisories) == 1
        assert "PostgreSQL" in service_advisories[0].content

    def test_multiple_destructive_commands(self, builder: ClaimBuilder) -> None:
        """Multiple destructive commands → multiple restrictions."""
        cmd1 = builder.build(
            content="db:drop",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("Makefile",),
        )
        cmd1 = replace(cmd1, risk_class=RiskClass.DESTRUCTIVE)

        cmd2 = builder.build(
            content="rm -rf node_modules/",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            evidence=("Makefile",),
        )
        cmd2 = replace(cmd2, risk_class=RiskClass.DESTRUCTIVE)

        results = extract_guardrails([cmd1, cmd2])

        assert len(results) == 2

    def test_non_security_tools_ignored(self, builder: ClaimBuilder) -> None:
        """Non-security tools (ruff, pytest) do not generate guardrails."""
        results = extract_guardrails([], security_tools=frozenset({"ruff", "pytest", "mypy"}))

        assert len(results) == 0
