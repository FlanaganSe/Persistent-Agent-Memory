"""Prerequisite extractor: aggregates environment prerequisites from all sources."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from rkp.core.ids import generate_claim_id
from rkp.core.models import EnvironmentProfile
from rkp.core.types import ClaimType, EvidenceLevel, Sensitivity, SourceAuthority
from rkp.indexer.config_parsers.docker_compose import ParsedComposeFile
from rkp.indexer.config_parsers.dockerfile import ParsedDockerfile
from rkp.indexer.config_parsers.github_actions import ParsedWorkflow
from rkp.indexer.config_parsers.pyproject import PyprojectResult
from rkp.indexer.config_parsers.version_files import VersionFilesResult

logger = structlog.get_logger()


@dataclass(frozen=True)
class PrerequisiteClaimInput:
    """Structured input for building an environment-prerequisite claim."""

    content: str
    claim_type: ClaimType
    source_authority: SourceAuthority
    evidence_level: EvidenceLevel
    scope: str
    applicability: tuple[str, ...]
    confidence: float
    sensitivity: Sensitivity
    evidence_files: tuple[str, ...]
    prerequisite_type: str  # "runtime", "tool", "service", "env-var", "os"


@dataclass(frozen=True)
class PrerequisiteResult:
    """Result of prerequisite extraction."""

    claims: tuple[PrerequisiteClaimInput, ...]
    profiles: tuple[EnvironmentProfile, ...]


def _extract_runtime_prerequisites(
    pyproject: PyprojectResult | None,
    pkg_engines: dict[str, str] | None,
    version_files: VersionFilesResult | None,
    workflows: list[ParsedWorkflow],
    dockerfiles: list[ParsedDockerfile],
) -> list[PrerequisiteClaimInput]:
    """Extract runtime version requirements from all sources."""
    claims: list[PrerequisiteClaimInput] = []
    seen: set[str] = set()

    # pyproject.toml requires-python
    if pyproject is not None and pyproject.python_requires is not None:
        key = f"Python {pyproject.python_requires}"
        if key not in seen:
            seen.add(key)
            claims.append(
                PrerequisiteClaimInput(
                    content=key,
                    claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    evidence_level=EvidenceLevel.PREREQUISITES_EXTRACTED,
                    scope="**",
                    applicability=("all",),
                    confidence=1.0,
                    sensitivity=Sensitivity.PUBLIC,
                    evidence_files=("pyproject.toml",),
                    prerequisite_type="runtime",
                )
            )

    # package.json engines
    if pkg_engines is not None:
        for engine, version in pkg_engines.items():
            key = f"{engine} {version}"
            if key not in seen:
                seen.add(key)
                claims.append(
                    PrerequisiteClaimInput(
                        content=key,
                        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                        evidence_level=EvidenceLevel.PREREQUISITES_EXTRACTED,
                        scope="**",
                        applicability=("all",),
                        confidence=1.0,
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=("package.json",),
                        prerequisite_type="runtime",
                    )
                )

    # Version files (.python-version, .nvmrc, etc.)
    if version_files is not None:
        for hint in version_files.hints:
            key = f"{hint.runtime} {hint.version}"
            if key not in seen:
                seen.add(key)
                claims.append(
                    PrerequisiteClaimInput(
                        content=key,
                        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                        evidence_level=EvidenceLevel.PREREQUISITES_EXTRACTED,
                        scope="**",
                        applicability=("all",),
                        confidence=0.95,
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=(hint.source_file,),
                        prerequisite_type="runtime",
                    )
                )

    # CI setup actions
    for workflow in workflows:
        for job in workflow.jobs:
            for runtime in job.runtimes:
                for version in runtime.versions:
                    if version.startswith("<unresolvable:"):
                        continue
                    key = f"{runtime.runtime} {version}"
                    if key not in seen:
                        seen.add(key)
                        claims.append(
                            PrerequisiteClaimInput(
                                content=key,
                                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                                source_authority=SourceAuthority.CI_OBSERVED,
                                evidence_level=EvidenceLevel.CI_EVIDENCED,
                                scope="**",
                                applicability=("ci",),
                                confidence=0.9,
                                sensitivity=Sensitivity.PUBLIC,
                                evidence_files=(workflow.source_file,),
                                prerequisite_type="runtime",
                            )
                        )

    # Dockerfiles
    for dockerfile in dockerfiles:
        for hint in dockerfile.runtime_hints:
            if hint not in seen:
                seen.add(hint)
                claims.append(
                    PrerequisiteClaimInput(
                        content=hint,
                        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                        evidence_level=EvidenceLevel.PREREQUISITES_EXTRACTED,
                        scope="**",
                        applicability=("all",),
                        confidence=0.85,
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=(dockerfile.source_file,),
                        prerequisite_type="runtime",
                    )
                )

    return claims


def _extract_service_prerequisites(
    compose_files: list[ParsedComposeFile],
    workflows: list[ParsedWorkflow],
) -> list[PrerequisiteClaimInput]:
    """Extract service requirements from docker-compose and CI services."""
    claims: list[PrerequisiteClaimInput] = []
    seen: set[str] = set()

    for compose in compose_files:
        for svc in compose.services:
            svc_key = svc.image or svc.name
            if svc_key not in seen:
                seen.add(svc_key)
                claims.append(
                    PrerequisiteClaimInput(
                        content=f"Service: {svc_key}",
                        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                        evidence_level=EvidenceLevel.PREREQUISITES_EXTRACTED,
                        scope="**",
                        applicability=("all",),
                        confidence=0.9,
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=(compose.source_file,),
                        prerequisite_type="service",
                    )
                )

    for workflow in workflows:
        for job in workflow.jobs:
            for svc in job.services:
                svc_key = svc.image
                if svc_key not in seen:
                    seen.add(svc_key)
                    claims.append(
                        PrerequisiteClaimInput(
                            content=f"Service: {svc_key}",
                            claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                            source_authority=SourceAuthority.CI_OBSERVED,
                            evidence_level=EvidenceLevel.CI_EVIDENCED,
                            scope="**",
                            applicability=("ci",),
                            confidence=0.85,
                            sensitivity=Sensitivity.PUBLIC,
                            evidence_files=(workflow.source_file,),
                            prerequisite_type="service",
                        )
                    )

    return claims


def _extract_env_var_prerequisites(
    workflows: list[ParsedWorkflow],
    dockerfiles: list[ParsedDockerfile],
    compose_files: list[ParsedComposeFile],
) -> list[PrerequisiteClaimInput]:
    """Extract environment variable name requirements (never values)."""
    claims: list[PrerequisiteClaimInput] = []
    seen: set[str] = set()

    for workflow in workflows:
        all_env_vars: list[str] = list(workflow.env_var_names)
        for job in workflow.jobs:
            all_env_vars.extend(job.env_var_names)
        for var_name in all_env_vars:
            if var_name not in seen:
                seen.add(var_name)
                claims.append(
                    PrerequisiteClaimInput(
                        content=f"Env: {var_name}",
                        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                        source_authority=SourceAuthority.CI_OBSERVED,
                        evidence_level=EvidenceLevel.CI_EVIDENCED,
                        scope="**",
                        applicability=("ci",),
                        confidence=0.8,
                        sensitivity=Sensitivity.TEAM_ONLY,
                        evidence_files=(workflow.source_file,),
                        prerequisite_type="env-var",
                    )
                )

    for dockerfile in dockerfiles:
        for var_name in dockerfile.env_var_names:
            if var_name not in seen:
                seen.add(var_name)
                claims.append(
                    PrerequisiteClaimInput(
                        content=f"Env: {var_name}",
                        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                        evidence_level=EvidenceLevel.PREREQUISITES_EXTRACTED,
                        scope="**",
                        applicability=("all",),
                        confidence=0.8,
                        sensitivity=Sensitivity.TEAM_ONLY,
                        evidence_files=(dockerfile.source_file,),
                        prerequisite_type="env-var",
                    )
                )

    for compose in compose_files:
        for svc in compose.services:
            for var_name in svc.env_var_names:
                if var_name not in seen:
                    seen.add(var_name)
                    claims.append(
                        PrerequisiteClaimInput(
                            content=f"Env: {var_name}",
                            claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                            evidence_level=EvidenceLevel.PREREQUISITES_EXTRACTED,
                            scope="**",
                            applicability=("all",),
                            confidence=0.8,
                            sensitivity=Sensitivity.TEAM_ONLY,
                            evidence_files=(compose.source_file,),
                            prerequisite_type="env-var",
                        )
                    )

    return claims


def _extract_os_prerequisites(
    workflows: list[ParsedWorkflow],
) -> list[PrerequisiteClaimInput]:
    """Extract OS requirements from CI runs-on values."""
    claims: list[PrerequisiteClaimInput] = []
    seen: set[str] = set()

    for workflow in workflows:
        for job in workflow.jobs:
            if job.runs_on is not None and job.runs_on not in seen:
                seen.add(job.runs_on)
                claims.append(
                    PrerequisiteClaimInput(
                        content=f"OS: {job.runs_on}",
                        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                        source_authority=SourceAuthority.CI_OBSERVED,
                        evidence_level=EvidenceLevel.CI_EVIDENCED,
                        scope="**",
                        applicability=("ci",),
                        confidence=0.9,
                        sensitivity=Sensitivity.PUBLIC,
                        evidence_files=(workflow.source_file,),
                        prerequisite_type="os",
                    )
                )

    return claims


def _build_environment_profiles(
    claims: list[PrerequisiteClaimInput],
    workflows: list[ParsedWorkflow],
    compose_files: list[ParsedComposeFile],
    repo_id: str,
) -> list[EnvironmentProfile]:
    """Aggregate prerequisite claims into environment profiles."""
    profiles: list[EnvironmentProfile] = []

    # Build a default profile from all prerequisites
    runtimes: list[str] = []
    tools: list[str] = []
    services: list[str] = []
    env_vars: list[str] = []
    setup_commands: list[str] = []

    for claim in claims:
        if claim.prerequisite_type == "runtime":
            runtimes.append(claim.content)
        elif claim.prerequisite_type == "tool":
            tools.append(claim.content)
        elif claim.prerequisite_type == "service":
            services.append(claim.content.removeprefix("Service: "))
        elif claim.prerequisite_type == "env-var":
            env_vars.append(claim.content.removeprefix("Env: "))

    # Extract setup commands from CI
    for workflow in workflows:
        for job in workflow.jobs:
            setup_commands.extend(
                cmd.command
                for cmd in job.commands
                if any(
                    kw in cmd.command.lower()
                    for kw in ("install", "setup", "pip install", "npm install", "apt-get")
                )
            )

    if runtimes or tools or services or env_vars:
        runtime_str = runtimes[0] if runtimes else None
        profile_id = generate_claim_id("environment-profile", "**", "ci-default")
        profiles.append(
            EnvironmentProfile(
                id=profile_id,
                name="ci-default",
                repo_id=repo_id,
                runtime=runtime_str,
                tools=tuple(tools),
                services=tuple(services),
                env_vars=tuple(env_vars),
                setup_commands=tuple(setup_commands[:20]),  # Cap at 20
            )
        )

    return profiles


def extract_prerequisites(
    *,
    pyproject: PyprojectResult | None = None,
    pkg_engines: dict[str, str] | None = None,
    version_files: VersionFilesResult | None = None,
    workflows: list[ParsedWorkflow] | None = None,
    dockerfiles: list[ParsedDockerfile] | None = None,
    compose_files: list[ParsedComposeFile] | None = None,
    scope: str = "**",
    repo_id: str = "",
) -> PrerequisiteResult:
    """Aggregate prerequisite evidence from ALL sources.

    Creates environment-prerequisite claims and environment profiles.
    Extracts env var NAMES only — never values.
    """
    wf = workflows or []
    df = dockerfiles or []
    cf = compose_files or []

    all_claims: list[PrerequisiteClaimInput] = []

    all_claims.extend(
        _extract_runtime_prerequisites(pyproject, pkg_engines, version_files, wf, df)
    )
    all_claims.extend(_extract_service_prerequisites(cf, wf))
    all_claims.extend(_extract_env_var_prerequisites(wf, df, cf))
    all_claims.extend(_extract_os_prerequisites(wf))

    profiles = _build_environment_profiles(all_claims, wf, cf, repo_id)

    logger.info(
        "Prerequisite extraction complete",
        total_claims=len(all_claims),
        profiles=len(profiles),
    )

    return PrerequisiteResult(
        claims=tuple(all_claims),
        profiles=tuple(profiles),
    )
