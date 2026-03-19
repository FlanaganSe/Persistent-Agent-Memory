"""Command extractor: transforms parsed config output into claim builder inputs."""

from __future__ import annotations

from dataclasses import dataclass

from rkp.core.types import EvidenceLevel, RiskClass, Sensitivity, SourceAuthority


@dataclass(frozen=True)
class CommandClaimInput:
    """Structured input for building a validated-command claim."""

    content: str
    source_authority: SourceAuthority
    evidence_level: EvidenceLevel
    risk_class: RiskClass
    scope: str
    applicability: tuple[str, ...]
    confidence: float
    sensitivity: Sensitivity
    evidence_files: tuple[str, ...]
    command_name: str


_RISK_TO_APPLICABILITY: dict[RiskClass, tuple[str, ...]] = {
    RiskClass.TEST_EXECUTION: ("test",),
    RiskClass.SAFE_READONLY: ("lint",),
    RiskClass.SAFE_MUTATING: ("format",),
    RiskClass.BUILD: ("build",),
    RiskClass.DESTRUCTIVE: ("ci", "release"),
}


def _applicability_for_risk(risk_class: RiskClass) -> tuple[str, ...]:
    """Derive applicability tags from risk class."""
    return _RISK_TO_APPLICABILITY.get(risk_class, ())


@dataclass(frozen=True)
class ParsedCommand:
    """Generic parsed command from any config parser."""

    name: str
    command: str
    source_file: str
    risk_class: RiskClass
    confidence: float = 1.0


def extract_command_claims(
    parsed_commands: tuple[ParsedCommand, ...],
    scope: str = "**",
) -> list[CommandClaimInput]:
    """Transform parsed commands into claim builder inputs.

    Each command becomes a validated-command claim with appropriate
    source authority, evidence level, risk class, and applicability.
    """
    return [
        CommandClaimInput(
            content=cmd.command,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            evidence_level=EvidenceLevel.DISCOVERED,
            risk_class=cmd.risk_class,
            scope=scope,
            applicability=_applicability_for_risk(cmd.risk_class),
            confidence=cmd.confidence,
            sensitivity=Sensitivity.PUBLIC,
            evidence_files=(cmd.source_file,),
            command_name=cmd.name,
        )
        for cmd in parsed_commands
    ]
