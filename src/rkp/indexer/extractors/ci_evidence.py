"""CI evidence extractor: cross-reference CI commands with config-discovered commands."""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from rkp.core.types import EvidenceLevel, RiskClass, Sensitivity, SourceAuthority
from rkp.indexer.config_parsers.github_actions import CICommand, CIConfidence, ParsedWorkflow
from rkp.indexer.extractors.commands import CommandClaimInput, ParsedCommand

logger = structlog.get_logger()


@dataclass(frozen=True)
class CIEvidenceResult:
    """Result of CI evidence extraction."""

    upgraded_commands: tuple[CommandClaimInput, ...]
    new_ci_commands: tuple[CommandClaimInput, ...]


# Common CI command prefixes to normalize for matching.
_COMMAND_PREFIXES = ("npx ", "yarn ", "pnpm ", "npm run ", "make ", "python -m ", "uv run ")


def _normalize_command(cmd: str) -> str:
    """Normalize a CI command for matching against config commands."""
    cmd = cmd.strip()
    # Strip pipe suffixes (e.g., "pytest | tee output.txt")
    cmd = cmd.split("|")[0].strip()
    # Strip redirection
    cmd = re.split(r"\s*[>]", cmd)[0].strip()
    return cmd


def _command_matches(ci_cmd: str, config_cmd: ParsedCommand) -> bool:
    """Check if a CI command matches a config-discovered command."""
    normalized = _normalize_command(ci_cmd)
    # Direct match on command content
    if normalized == config_cmd.command:
        return True
    # Match on command name (e.g., "npm run test" matches script named "test")
    if normalized.endswith(config_cmd.name):
        return True
    # Match "make target" against Makefile target
    if normalized == f"make {config_cmd.name}":
        return True
    # Match "npm run script" or "yarn script" against package.json script
    for prefix in _COMMAND_PREFIXES:
        if normalized.startswith(prefix):
            suffix = normalized[len(prefix) :].strip()
            if suffix == config_cmd.name or suffix == config_cmd.command:
                return True
    # Match partial command with word boundary (e.g., "pytest tests/" matches "pytest")
    return bool(
        re.search(rf"\b{re.escape(config_cmd.command)}\b", normalized)
    ) or normalized.startswith(config_cmd.command)


def _confidence_for_ci(ci_confidence: CIConfidence) -> float:
    """Map CI confidence level to a numeric confidence value."""
    mapping: dict[CIConfidence, float] = {
        CIConfidence.HIGH: 0.95,
        CIConfidence.MEDIUM: 0.85,
        CIConfidence.LOW: 0.70,
        CIConfidence.UNKNOWN: 0.50,
    }
    return mapping.get(ci_confidence, 0.50)


def _risk_from_command(cmd: str) -> RiskClass:
    """Infer risk class from a command string."""
    cmd_lower = cmd.lower()
    if any(kw in cmd_lower for kw in ("test", "pytest", "jest", "vitest", "mocha")):
        return RiskClass.TEST_EXECUTION
    if any(kw in cmd_lower for kw in ("lint", "check", "ruff", "eslint", "pyright", "mypy")):
        return RiskClass.SAFE_READONLY
    if any(kw in cmd_lower for kw in ("format", "fmt", "prettier")):
        return RiskClass.SAFE_MUTATING
    if any(kw in cmd_lower for kw in ("build", "compile", "tsc")):
        return RiskClass.BUILD
    if any(kw in cmd_lower for kw in ("deploy", "publish", "release")):
        return RiskClass.DESTRUCTIVE
    return RiskClass.BUILD


def extract_ci_evidence(
    workflows: list[ParsedWorkflow],
    config_commands: list[ParsedCommand],
    *,
    scope: str = "**",
) -> CIEvidenceResult:
    """Cross-reference CI workflow commands against config-discovered commands.

    For each CI command:
    - If it matches a config-discovered command: upgrade evidence to ci-evidenced
    - If it's new: create a new ci-observed command claim

    Returns upgraded and new command claim inputs.
    """
    # Collect all CI commands from all workflows
    all_ci_commands: list[CICommand] = []
    for workflow in workflows:
        for job in workflow.jobs:
            all_ci_commands.extend(job.commands)

    upgraded: list[CommandClaimInput] = []
    new_commands: list[CommandClaimInput] = []
    matched_config_names: set[str] = set()
    seen_ci_commands: set[str] = set()

    for ci_cmd in all_ci_commands:
        normalized = _normalize_command(ci_cmd.command)
        if not normalized or normalized in seen_ci_commands:
            continue
        seen_ci_commands.add(normalized)

        # Try to match against config commands
        matched = False
        for config_cmd in config_commands:
            if _command_matches(ci_cmd.command, config_cmd):
                matched = True
                matched_config_names.add(config_cmd.name)
                # Upgrade to ci-evidenced
                upgraded.append(
                    CommandClaimInput(
                        content=config_cmd.command,
                        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                        evidence_level=EvidenceLevel.CI_EVIDENCED,
                        risk_class=config_cmd.risk_class,
                        scope=scope,
                        applicability=_applicability_for_risk(config_cmd.risk_class),
                        confidence=max(
                            config_cmd.confidence, _confidence_for_ci(ci_cmd.confidence)
                        ),
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=(config_cmd.source_file,),
                        command_name=config_cmd.name,
                    )
                )
                break

        if not matched:
            # New CI-only command
            risk = _risk_from_command(ci_cmd.command)
            new_commands.append(
                CommandClaimInput(
                    content=normalized,
                    source_authority=SourceAuthority.CI_OBSERVED,
                    evidence_level=EvidenceLevel.CI_EVIDENCED,
                    risk_class=risk,
                    scope=scope,
                    applicability=_applicability_for_risk(risk),
                    confidence=_confidence_for_ci(ci_cmd.confidence),
                    sensitivity=Sensitivity.PUBLIC,
                    evidence_files=(),
                    command_name=normalized.split()[0] if normalized else "unknown",
                )
            )

    logger.info(
        "CI evidence extraction complete",
        total_ci_commands=len(all_ci_commands),
        upgraded=len(upgraded),
        new_commands=len(new_commands),
    )

    return CIEvidenceResult(
        upgraded_commands=tuple(upgraded),
        new_ci_commands=tuple(new_commands),
    )


def _applicability_for_risk(risk_class: RiskClass) -> tuple[str, ...]:
    """Derive applicability tags from risk class."""
    mapping: dict[RiskClass, tuple[str, ...]] = {
        RiskClass.TEST_EXECUTION: ("test",),
        RiskClass.SAFE_READONLY: ("lint",),
        RiskClass.SAFE_MUTATING: ("format",),
        RiskClass.BUILD: ("build",),
        RiskClass.DESTRUCTIVE: ("ci", "release"),
    }
    return mapping.get(risk_class, ())
