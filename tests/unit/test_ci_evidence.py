"""Tests for the CI evidence extractor."""

from __future__ import annotations

from rkp.core.types import EvidenceLevel, RiskClass, SourceAuthority
from rkp.indexer.config_parsers.github_actions import (
    CICommand,
    CIConfidence,
    ParsedWorkflow,
    ParsedWorkflowJob,
)
from rkp.indexer.extractors.ci_evidence import extract_ci_evidence
from rkp.indexer.extractors.commands import ParsedCommand


def _make_workflow(
    commands: list[CICommand],
    *,
    name: str = "CI",
    source_file: str = ".github/workflows/ci.yml",
) -> ParsedWorkflow:
    """Helper to build a minimal ParsedWorkflow with given commands."""
    job = ParsedWorkflowJob(
        name="test",
        runs_on="ubuntu-latest",
        commands=tuple(commands),
        runtimes=(),
        services=(),
        env_var_names=(),
        matrix_dimensions={},
    )
    return ParsedWorkflow(
        name=name,
        triggers=("push",),
        jobs=(job,),
        env_var_names=(),
        source_file=source_file,
    )


class TestCIEvidence:
    def test_upgrade_config_command(self) -> None:
        """CI command matching a config command is upgraded to ci-evidenced."""
        config_commands = [
            ParsedCommand(
                name="test",
                command="pytest",
                source_file="pyproject.toml",
                risk_class=RiskClass.TEST_EXECUTION,
                confidence=0.9,
            ),
        ]
        ci_commands = [
            CICommand(
                command="pytest tests/ --cov",
                confidence=CIConfidence.HIGH,
                job_name="test",
                step_name="Run tests",
            ),
        ]
        workflow = _make_workflow(ci_commands)
        result = extract_ci_evidence([workflow], config_commands)
        assert len(result.upgraded_commands) == 1
        upgraded = result.upgraded_commands[0]
        assert upgraded.evidence_level == EvidenceLevel.CI_EVIDENCED
        assert upgraded.source_authority == SourceAuthority.EXECUTABLE_CONFIG
        assert upgraded.content == "pytest"

    def test_new_ci_command(self) -> None:
        """CI command not matching any config command creates a new ci-observed command."""
        config_commands: list[ParsedCommand] = []
        ci_commands = [
            CICommand(
                command="pyright",
                confidence=CIConfidence.HIGH,
                job_name="lint",
                step_name="Typecheck",
            ),
        ]
        workflow = _make_workflow(ci_commands)
        result = extract_ci_evidence([workflow], config_commands)
        assert len(result.new_ci_commands) == 1
        new_cmd = result.new_ci_commands[0]
        assert new_cmd.source_authority == SourceAuthority.CI_OBSERVED
        assert new_cmd.evidence_level == EvidenceLevel.CI_EVIDENCED
        assert new_cmd.content == "pyright"

    def test_no_duplicates(self) -> None:
        """Same command in multiple CI jobs produces only one result."""
        ci_commands = [
            CICommand(
                command="pytest",
                confidence=CIConfidence.HIGH,
                job_name="test-3.12",
                step_name="Run tests",
            ),
        ]
        ci_commands_dupe = [
            CICommand(
                command="pytest",
                confidence=CIConfidence.HIGH,
                job_name="test-3.13",
                step_name="Run tests",
            ),
        ]
        job1 = ParsedWorkflowJob(
            name="test-3.12",
            runs_on="ubuntu-latest",
            commands=tuple(ci_commands),
            runtimes=(),
            services=(),
            env_var_names=(),
            matrix_dimensions={},
        )
        job2 = ParsedWorkflowJob(
            name="test-3.13",
            runs_on="ubuntu-latest",
            commands=tuple(ci_commands_dupe),
            runtimes=(),
            services=(),
            env_var_names=(),
            matrix_dimensions={},
        )
        workflow = ParsedWorkflow(
            name="CI",
            triggers=("push",),
            jobs=(job1, job2),
            env_var_names=(),
            source_file=".github/workflows/ci.yml",
        )
        result = extract_ci_evidence([workflow], [])
        # Only one new command despite appearing in two jobs
        assert len(result.new_ci_commands) == 1

    def test_empty_inputs(self) -> None:
        """Empty workflows and commands produce empty result."""
        result = extract_ci_evidence([], [])
        assert result.upgraded_commands == ()
        assert result.new_ci_commands == ()

    def test_confidence_mapping(self) -> None:
        """HIGH/MEDIUM/LOW CI confidence maps to appropriate numeric values."""
        config_commands = [
            ParsedCommand(
                name="test",
                command="pytest",
                source_file="pyproject.toml",
                risk_class=RiskClass.TEST_EXECUTION,
                confidence=0.5,
            ),
        ]
        for ci_confidence, min_expected in [
            (CIConfidence.HIGH, 0.9),
            (CIConfidence.MEDIUM, 0.8),
            (CIConfidence.LOW, 0.7),
        ]:
            ci_commands = [
                CICommand(
                    command="pytest",
                    confidence=ci_confidence,
                    job_name="test",
                    step_name="Run tests",
                ),
            ]
            workflow = _make_workflow(ci_commands)
            result = extract_ci_evidence([workflow], config_commands)
            assert len(result.upgraded_commands) == 1
            assert result.upgraded_commands[0].confidence >= min_expected
