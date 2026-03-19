"""Guardrail extractor: permission/restriction claims from commands, config, CI."""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

from rkp.core.models import Claim
from rkp.core.types import ClaimType, RiskClass, Sensitivity, SourceAuthority

logger = structlog.get_logger()

# Security-oriented tools whose presence in config implies a guardrail.
_SECURITY_TOOLS: frozenset[str] = frozenset({"bandit", "safety", "semgrep", "snyk"})

# CI command patterns that indicate security scanning.
_CI_SECURITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bnpm\s+audit\b"),
    re.compile(r"\bbandit\b"),
    re.compile(r"\bsafety\s+check\b"),
    re.compile(r"\bsnyk\s+test\b"),
    re.compile(r"\bsemgrep\b"),
    re.compile(r"\btrivy\b"),
)


@dataclass(frozen=True)
class GuardrailClaimInput:
    """Structured input for building a permission-restriction claim."""

    content: str
    source_authority: SourceAuthority
    scope: str
    applicability: tuple[str, ...]
    confidence: float
    sensitivity: Sensitivity
    evidence_files: tuple[str, ...]


def extract_guardrails(
    claims: list[Claim],
    *,
    security_tools: frozenset[str] = frozenset(),
) -> list[GuardrailClaimInput]:
    """Extract permission/restriction claims from existing claims and config signals.

    Conservative: only generates from clear, high-confidence signals.
    A false guardrail blocks legitimate work.

    Sources:
    1. Destructive commands (risk_class=destructive) → restriction
    2. Test-execution commands + service prerequisites → advisory
    3. Security tool configs (bandit, safety, semgrep) → advisory
    4. CI-observed security scan commands → advisory
    """
    results: list[GuardrailClaimInput] = []
    seen_content: set[str] = set()

    # 1. Destructive commands → restriction
    destructive_commands = [
        c
        for c in claims
        if c.claim_type == ClaimType.VALIDATED_COMMAND and c.risk_class == RiskClass.DESTRUCTIVE
    ]

    for cmd in destructive_commands:
        content = (
            f"Command `{cmd.content}` is classified as destructive "
            "— require explicit confirmation before running"
        )
        if content in seen_content:
            continue
        seen_content.add(content)
        results.append(
            GuardrailClaimInput(
                content=content,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                scope=cmd.scope,
                applicability=("destructive", "security"),
                confidence=1.0,
                sensitivity=Sensitivity.PUBLIC,
                evidence_files=cmd.evidence,
            )
        )

    # 2. Test-execution commands + service prerequisites → advisory
    test_commands = [
        c
        for c in claims
        if c.claim_type == ClaimType.VALIDATED_COMMAND and c.risk_class == RiskClass.TEST_EXECUTION
    ]
    service_claims = [
        c
        for c in claims
        if c.claim_type == ClaimType.ENVIRONMENT_PREREQUISITE
        and c.content.lower().startswith("service:")
    ]

    if test_commands and service_claims:
        service_names = [
            c.content.split(":", 1)[1].strip().split("(")[0].strip() for c in service_claims
        ]
        services_str = ", ".join(sorted(set(service_names)))
        for cmd in test_commands:
            content = f"Command `{cmd.content}` requires services: {services_str}"
            if content in seen_content:
                continue
            seen_content.add(content)
            evidence = cmd.evidence + tuple(e for sc in service_claims for e in sc.evidence)
            results.append(
                GuardrailClaimInput(
                    content=content,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    scope=cmd.scope,
                    applicability=("test", "security"),
                    confidence=0.9,
                    sensitivity=Sensitivity.PUBLIC,
                    evidence_files=evidence,
                )
            )

    # 3. Security tools in config → advisory
    detected_security = security_tools & _SECURITY_TOOLS
    if detected_security:
        tools_str = ", ".join(sorted(detected_security))
        content = f"Security tooling configured: {tools_str} — run security checks before merging"
        if content not in seen_content:
            seen_content.add(content)
            results.append(
                GuardrailClaimInput(
                    content=content,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    scope="**",
                    applicability=("security",),
                    confidence=1.0,
                    sensitivity=Sensitivity.PUBLIC,
                    evidence_files=("pyproject.toml",),
                )
            )

    # 4. CI-observed security scan commands → advisory
    ci_commands = [
        c
        for c in claims
        if c.claim_type == ClaimType.VALIDATED_COMMAND
        and c.source_authority == SourceAuthority.CI_OBSERVED
    ]

    for cmd in ci_commands:
        for pattern in _CI_SECURITY_PATTERNS:
            if pattern.search(cmd.content):
                content = (
                    f"CI runs security scan: `{cmd.content}` — ensure changes pass security checks"
                )
                if content in seen_content:
                    break
                seen_content.add(content)
                results.append(
                    GuardrailClaimInput(
                        content=content,
                        source_authority=SourceAuthority.CI_OBSERVED,
                        scope="**",
                        applicability=("security", "ci"),
                        confidence=0.9,
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=cmd.evidence,
                    )
                )
                break

    logger.info("Guardrail extraction complete", guardrails=len(results))
    return results
