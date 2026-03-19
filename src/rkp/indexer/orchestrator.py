"""Extraction pipeline orchestrator: discover → parse → extract → store."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path

import structlog

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.config import RkpConfig, is_excluded_path
from rkp.core.errors import DuplicateClaimError
from rkp.core.models import Claim, EnvironmentProfile, Provenance
from rkp.core.security import (
    Severity,
    max_injection_severity,
    redact_secrets,
    scan_for_injection,
    scan_for_secrets,
)
from rkp.core.types import ClaimType, ReviewState, Sensitivity, SourceAuthority
from rkp.git.backend import GitBackend
from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.indexer.config_parsers.docker_compose import ParsedComposeFile, parse_docker_compose
from rkp.indexer.config_parsers.dockerfile import ParsedDockerfile, parse_dockerfile
from rkp.indexer.config_parsers.github_actions import (
    ParsedWorkflow,
    discover_workflow_files,
    parse_github_actions_workflow,
)
from rkp.indexer.config_parsers.makefile import parse_makefile
from rkp.indexer.config_parsers.package_json import PackageJsonResult, parse_package_json
from rkp.indexer.config_parsers.pyproject import PyprojectResult, parse_pyproject
from rkp.indexer.config_parsers.version_files import parse_version_files
from rkp.indexer.extractors.boundaries import BoundaryClaimInput, extract_boundaries
from rkp.indexer.extractors.ci_evidence import extract_ci_evidence
from rkp.indexer.extractors.commands import (
    CommandClaimInput,
    ParsedCommand,
    extract_command_claims,
)
from rkp.indexer.extractors.conflicts import ConflictClaimInput, detect_conflicts
from rkp.indexer.extractors.conventions import (
    ConventionClaimInput,
    extract_conventions,
    extract_js_conventions,
)
from rkp.indexer.extractors.docs_evidence import extract_docs_evidence
from rkp.indexer.extractors.guardrails import GuardrailClaimInput, extract_guardrails
from rkp.indexer.extractors.prerequisites import PrerequisiteClaimInput, extract_prerequisites
from rkp.indexer.parsers.javascript import ParsedJavaScriptFile, parse_javascript_file
from rkp.indexer.parsers.python import ParsedPythonFile, parse_python_file
from rkp.store.claims import ClaimStore

logger = structlog.get_logger()

# Directories excluded from file discovery by default.
_DEFAULT_EXCLUDES = frozenset(
    {
        "vendor",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".rkp",
        ".next",
        "out",
        "coverage",
    }
)

# Maximum file size to parse (bytes). Files larger than this are skipped.
_MAX_FILE_SIZE = 1_000_000

# JS/TS file extensions to discover.
_JS_EXTENSIONS = frozenset({".js", ".jsx", ".ts", ".tsx"})


@dataclass(frozen=True)
class ExtractionSummary:
    """Summary of an extraction run."""

    files_parsed: int
    claims_created: int
    claims_deduplicated: int
    python_files_parsed: int = 0
    js_files_parsed: int = 0
    conventions_extracted: int = 0
    ci_commands_found: int = 0
    prerequisites_extracted: int = 0
    profiles_created: int = 0
    modules_detected: int = 0
    edges_created: int = 0
    docs_commands_found: int = 0
    guardrails_extracted: int = 0
    conflicts_detected: int = 0
    warnings: tuple[str, ...] = ()


def _discover_config_files(repo_root: Path) -> list[str]:
    """Discover config files at the repo root."""
    candidates = ("pyproject.toml", "package.json", "Makefile")
    return [name for name in candidates if (repo_root / name).is_file()]


def _discover_docker_files(repo_root: Path) -> tuple[list[str], list[str]]:
    """Discover Dockerfile and docker-compose files."""
    dockerfiles: list[str] = []
    if (repo_root / "Dockerfile").is_file():
        dockerfiles.append("Dockerfile")

    compose_candidates = (
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    )
    compose_files = [name for name in compose_candidates if (repo_root / name).is_file()]

    return dockerfiles, compose_files


def _should_exclude(
    path: Path,
    *,
    excluded_dirs: tuple[str, ...] = tuple(_DEFAULT_EXCLUDES),
) -> bool:
    """Check if a path should be excluded from parsing."""
    return is_excluded_path(path, excluded_dirs)


def _discover_python_files(
    repo_root: Path,
    git_backend: GitBackend | None = None,
    *,
    excluded_dirs: tuple[str, ...] = tuple(_DEFAULT_EXCLUDES),
    max_file_size_bytes: int = _MAX_FILE_SIZE,
) -> list[Path]:
    """Discover Python files to parse."""
    python_files: list[Path] = []

    if git_backend is not None:
        all_files = git_backend.list_tracked_files() + git_backend.list_untracked_files()
        for rel_path in all_files:
            if rel_path.suffix != ".py":
                continue
            if _should_exclude(rel_path, excluded_dirs=excluded_dirs):
                continue
            full_path = repo_root / rel_path
            if full_path.is_file() and full_path.stat().st_size <= max_file_size_bytes:
                python_files.append(rel_path)
    else:
        for full_path in repo_root.rglob("*.py"):
            rel_path = full_path.relative_to(repo_root)
            if _should_exclude(rel_path, excluded_dirs=excluded_dirs):
                continue
            if full_path.stat().st_size <= max_file_size_bytes:
                python_files.append(rel_path)

    return sorted(python_files)


def _discover_js_files(
    repo_root: Path,
    git_backend: GitBackend | None = None,
    *,
    excluded_dirs: tuple[str, ...] = tuple(_DEFAULT_EXCLUDES),
    max_file_size_bytes: int = _MAX_FILE_SIZE,
) -> list[Path]:
    """Discover JS/TS files to parse (excludes node_modules, dist, .next, out)."""
    js_files: list[Path] = []

    if git_backend is not None:
        all_files = git_backend.list_tracked_files() + git_backend.list_untracked_files()
        for rel_path in all_files:
            if rel_path.suffix not in _JS_EXTENSIONS:
                continue
            if _should_exclude(rel_path, excluded_dirs=excluded_dirs):
                continue
            full_path = repo_root / rel_path
            if full_path.is_file() and full_path.stat().st_size <= max_file_size_bytes:
                js_files.append(rel_path)
    else:
        for ext in _JS_EXTENSIONS:
            for full_path in repo_root.rglob(f"*{ext}"):
                rel_path = full_path.relative_to(repo_root)
                if _should_exclude(rel_path, excluded_dirs=excluded_dirs):
                    continue
                if full_path.stat().st_size <= max_file_size_bytes:
                    js_files.append(rel_path)

    return sorted(js_files)


def run_extraction(
    repo_root: Path,
    claim_store: ClaimStore,
    *,
    repo_id: str = "",
    branch: str = "main",
    git_backend: GitBackend | None = None,
    graph: SqliteRepoGraph | None = None,
    config: RkpConfig | None = None,
) -> ExtractionSummary:
    """Run the extraction pipeline on a repo.

    Pipeline order:
    1.  Config parsers (pyproject.toml, package.json, Makefile)
    2.  Docker parsers (Dockerfile, docker-compose)
    3.  CI parsers (GitHub Actions workflows)
    4.  Version files
    5.  Docs evidence extraction (README, docs/)
    6.  CI evidence cross-referencing
    7.  Prerequisite extraction + environment profiles
    8.  Python code parsing
    9.  JS/TS code parsing
    10. Convention extraction
    11. Guardrail extraction
    12. Boundary extraction + graph construction
    13. Conflict detection
    """
    builder = ClaimBuilder(repo_id=repo_id, branch=branch)
    effective_config = config or RkpConfig()
    config_files = _discover_config_files(repo_root)
    all_parsed_commands: list[ParsedCommand] = []
    warnings: list[str] = []
    tools_detected: set[str] = set()
    pyproject_result: PyprojectResult | None = None
    pkg_result: PackageJsonResult | None = None

    # Phase 1: Parse config files for commands
    for config_file in config_files:
        if config_file == "pyproject.toml":
            pyproject_result = parse_pyproject(repo_root)
            all_parsed_commands.extend(pyproject_result.commands)
            tools_detected.update(pyproject_result.tools_detected)
        elif config_file == "package.json":
            pkg_result = parse_package_json(repo_root)
            all_parsed_commands.extend(pkg_result.commands)
        elif config_file == "Makefile":
            makefile_result = parse_makefile(repo_root)
            all_parsed_commands.extend(makefile_result.commands)

    # Phase 2: Docker parsers
    dockerfile_paths, compose_paths = _discover_docker_files(repo_root)
    dockerfiles: list[ParsedDockerfile] = [
        parse_dockerfile(repo_root, p) for p in dockerfile_paths
    ]
    compose_files: list[ParsedComposeFile] = [
        parse_docker_compose(repo_root, p) for p in compose_paths
    ]

    # Phase 3: CI parsers
    workflow_paths = discover_workflow_files(repo_root)
    workflows: list[ParsedWorkflow] = [
        parse_github_actions_workflow(repo_root, p) for p in workflow_paths
    ]

    # Phase 4: Version files
    version_files = parse_version_files(repo_root)

    # Phase 5: Docs evidence extraction
    docs_result = extract_docs_evidence(
        repo_root,
        excluded_dirs=effective_config.excluded_dirs,
    )
    docs_command_claims = _build_command_claims(builder, list(docs_result.commands))

    # Phase 6: CI evidence cross-referencing
    ci_result = extract_ci_evidence(workflows, all_parsed_commands)

    # Build initial command claims (discovered level)
    claim_inputs = extract_command_claims(tuple(all_parsed_commands))
    new_claims = _build_command_claims(builder, claim_inputs)

    # Add docs commands (cross-reference: skip if already discovered from config)
    config_command_contents = {c.content.strip().lower() for c in new_claims}
    for docs_claim in docs_command_claims:
        if docs_claim.content.strip().lower() not in config_command_contents:
            new_claims.append(docs_claim)

    # Upgrade commands that appear in CI
    for upgraded in ci_result.upgraded_commands:
        upgraded_claims = _build_command_claims(builder, [upgraded])
        new_claims.extend(upgraded_claims)

    # Add new CI-only commands
    for ci_cmd in ci_result.new_ci_commands:
        ci_claims = _build_command_claims(builder, [ci_cmd])
        new_claims.extend(ci_claims)

    # Phase 7: Prerequisites + environment profiles
    prereq_result = extract_prerequisites(
        pyproject=pyproject_result,
        pkg_engines=pkg_result.engines if pkg_result is not None else None,
        version_files=version_files,
        workflows=workflows,
        dockerfiles=dockerfiles,
        compose_files=compose_files,
        repo_id=repo_id,
    )
    prereq_claims = _build_prerequisite_claims(builder, list(prereq_result.claims))
    new_claims.extend(prereq_claims)

    # Build prerequisite claims from docs evidence
    for docs_prereq in docs_result.prerequisites:
        prereq_claim = builder.build(
            content=docs_prereq.content,
            claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
            source_authority=SourceAuthority.CHECKED_IN_DOCS,
            scope="**",
            applicability=("all",),
            confidence=0.7,
            evidence=(docs_prereq.evidence_file,),
            provenance=Provenance(extraction_version="0.1.0", timestamp=""),
        )
        new_claims.append(prereq_claim)

    # Store environment profiles
    from rkp.store.claims import SqliteClaimStore

    db_conn: sqlite3.Connection | None = None
    if isinstance(claim_store, SqliteClaimStore):
        db_conn = claim_store.connection
    profiles_created = _store_profiles(db_conn, prereq_result.profiles, repo_id)

    # Phase 8: Parse Python files
    python_files = _discover_python_files(
        repo_root,
        git_backend,
        excluded_dirs=effective_config.excluded_dirs,
        max_file_size_bytes=effective_config.max_file_size_bytes,
    )
    parsed_python: list[ParsedPythonFile] = []
    for rel_path in python_files:
        full_path = repo_root / rel_path
        parsed = parse_python_file(full_path)
        parsed_python.append(parsed)

    convention_inputs = extract_conventions(
        parsed_python, tools_detected=frozenset(tools_detected)
    )
    convention_claims = _build_convention_claims(builder, convention_inputs)
    new_claims.extend(convention_claims)

    # Phase 9: Parse JS/TS files
    js_files = _discover_js_files(
        repo_root,
        git_backend,
        excluded_dirs=effective_config.excluded_dirs,
        max_file_size_bytes=effective_config.max_file_size_bytes,
    )
    parsed_js: list[ParsedJavaScriptFile] = []
    for rel_path in js_files:
        full_path = repo_root / rel_path
        parsed_js_file = parse_javascript_file(full_path)
        parsed_js.append(parsed_js_file)

    js_convention_inputs = extract_js_conventions(
        parsed_js, tools_detected=frozenset(tools_detected)
    )
    js_convention_claims = _build_convention_claims(builder, js_convention_inputs)
    new_claims.extend(js_convention_claims)

    # Phase 10: Guardrail extraction (from claims + config signals)
    guardrail_inputs = extract_guardrails(
        new_claims,
        security_tools=frozenset(tools_detected),
    )
    guardrail_claims = _build_guardrail_claims(builder, guardrail_inputs)
    new_claims.extend(guardrail_claims)

    # Phase 12: Boundary extraction + graph construction
    modules_detected = 0
    edges_created = 0
    if graph is not None:
        graph.clear(repo_id)
        boundary_result = extract_boundaries(
            repo_root=repo_root,
            parsed_python=parsed_python,
            parsed_js=parsed_js,
            graph=graph,
            repo_id=repo_id,
        )
        modules_detected = boundary_result.modules_detected
        edges_created = boundary_result.edges_created
        boundary_claims = _build_boundary_claims(builder, list(boundary_result.claims))
        new_claims.extend(boundary_claims)

    # Deduplicate and store
    existing_claims = claim_store.list_claims(repo_id=repo_id)
    unique, duplicates = builder.deduplicate(new_claims, existing_claims)

    # Security scanning: injection + secret detection on claims before storing.
    scanned = [_security_scan_claim(claim, warnings) for claim in unique]

    for claim in scanned:
        claim_store.save(claim)

    # Phase 13: Conflict detection (needs all claims stored)
    conflicts_detected = 0
    all_claims_for_conflicts = claim_store.list_claims(repo_id=repo_id)
    conflict_result = detect_conflicts(all_claims_for_conflicts)
    if conflict_result.conflicts:
        conflict_claims = _build_conflict_claims(builder, list(conflict_result.conflicts))
        for cc in conflict_claims:
            try:
                claim_store.save(cc)
                conflicts_detected += 1
            except DuplicateClaimError:
                pass

    total_files = (
        len(config_files)
        + len(dockerfile_paths)
        + len(compose_paths)
        + len(workflow_paths)
        + len(python_files)
        + len(js_files)
        + docs_result.files_scanned
    )

    logger.info(
        "Extraction complete",
        files_parsed=total_files,
        python_files=len(python_files),
        js_files=len(js_files),
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
        conventions=len(convention_claims) + len(js_convention_claims),
        ci_commands=len(ci_result.upgraded_commands) + len(ci_result.new_ci_commands),
        prerequisites=len(prereq_claims),
        profiles=profiles_created,
        guardrails=len(guardrail_claims),
        modules=modules_detected,
        edges=edges_created,
        docs_commands=len(docs_result.commands),
        conflicts=conflicts_detected,
    )

    return ExtractionSummary(
        files_parsed=total_files,
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
        python_files_parsed=len(python_files),
        js_files_parsed=len(js_files),
        conventions_extracted=len(convention_claims) + len(js_convention_claims),
        ci_commands_found=len(ci_result.upgraded_commands) + len(ci_result.new_ci_commands),
        prerequisites_extracted=len(prereq_claims),
        profiles_created=profiles_created,
        modules_detected=modules_detected,
        edges_created=edges_created,
        docs_commands_found=len(docs_result.commands),
        guardrails_extracted=len(guardrail_claims),
        conflicts_detected=conflicts_detected,
        warnings=tuple(warnings),
    )


def _build_command_claims(builder: ClaimBuilder, inputs: list[CommandClaimInput]) -> list[Claim]:
    """Build claims from command extractor inputs."""
    claims: list[Claim] = []
    for inp in inputs:
        claim = builder.build(
            content=inp.content,
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=inp.source_authority,
            scope=inp.scope,
            applicability=inp.applicability,
            sensitivity=inp.sensitivity,
            confidence=inp.confidence,
            evidence=inp.evidence_files,
            provenance=Provenance(
                extraction_version="0.1.0",
                timestamp="",
            ),
        )
        claim = replace(claim, risk_class=inp.risk_class)
        claims.append(claim)
    return claims


def _build_convention_claims(
    builder: ClaimBuilder, inputs: list[ConventionClaimInput]
) -> list[Claim]:
    """Build claims from convention extractor inputs."""
    claims: list[Claim] = []
    for inp in inputs:
        claim = builder.build(
            content=inp.content,
            claim_type=inp.claim_type,
            source_authority=inp.source_authority,
            scope=inp.scope,
            applicability=inp.applicability,
            sensitivity=inp.sensitivity,
            confidence=inp.confidence,
            evidence=inp.evidence_files,
            provenance=Provenance(
                extraction_version="0.1.0",
                timestamp="",
            ),
        )
        if inp.review_state_hint == "needs-declaration":
            claim = replace(claim, review_state=ReviewState.NEEDS_DECLARATION)
        claims.append(claim)
    return claims


def _build_prerequisite_claims(
    builder: ClaimBuilder, inputs: list[PrerequisiteClaimInput]
) -> list[Claim]:
    """Build claims from prerequisite extractor inputs."""
    claims: list[Claim] = []
    for inp in inputs:
        claim = builder.build(
            content=inp.content,
            claim_type=inp.claim_type,
            source_authority=inp.source_authority,
            scope=inp.scope,
            applicability=inp.applicability,
            sensitivity=inp.sensitivity,
            confidence=inp.confidence,
            evidence=inp.evidence_files,
            provenance=Provenance(
                extraction_version="0.1.0",
                timestamp="",
            ),
        )
        claims.append(claim)
    return claims


def _build_boundary_claims(builder: ClaimBuilder, inputs: list[BoundaryClaimInput]) -> list[Claim]:
    """Build claims from boundary extractor inputs."""
    claims: list[Claim] = []
    for inp in inputs:
        claim = builder.build(
            content=inp.content,
            claim_type=ClaimType.MODULE_BOUNDARY,
            source_authority=inp.source_authority,
            scope=inp.scope,
            applicability=(),
            confidence=inp.confidence,
            evidence=inp.evidence_files,
            provenance=Provenance(
                extraction_version="0.1.0",
                timestamp="",
            ),
        )
        claims.append(claim)
    return claims


def _build_conflict_claims(builder: ClaimBuilder, inputs: list[ConflictClaimInput]) -> list[Claim]:
    """Build claims from conflict detector inputs."""
    claims: list[Claim] = []
    for inp in inputs:
        claim = builder.build(
            content=inp.content,
            claim_type=ClaimType.CONFLICT,
            source_authority=inp.source_authority,
            scope=inp.scope,
            applicability=(),
            confidence=inp.confidence,
            evidence=inp.evidence_claim_ids,
            provenance=Provenance(
                extraction_version="0.1.0",
                timestamp="",
            ),
        )
        claim = replace(claim, review_state=ReviewState.NEEDS_DECLARATION)
        claims.append(claim)
    return claims


def _build_guardrail_claims(
    builder: ClaimBuilder, inputs: list[GuardrailClaimInput]
) -> list[Claim]:
    """Build claims from guardrail extractor inputs."""
    claims: list[Claim] = []
    for inp in inputs:
        claim = builder.build(
            content=inp.content,
            claim_type=ClaimType.PERMISSION_RESTRICTION,
            source_authority=inp.source_authority,
            scope=inp.scope,
            applicability=inp.applicability,
            sensitivity=inp.sensitivity,
            confidence=inp.confidence,
            evidence=inp.evidence_files,
            provenance=Provenance(
                extraction_version="0.1.0",
                timestamp="",
            ),
        )
        claims.append(claim)
    return claims


def _security_scan_claim(claim: Claim, warnings: list[str]) -> Claim:
    """Scan a single claim's content for injection markers and secrets.

    Returns a (possibly modified) claim with:
    - Injection warnings appended (HIGH severity → needs-declaration)
    - Secret values redacted, sensitivity forced to local-only
    """
    # Injection scanning.
    injection_findings = scan_for_injection(claim.content)
    if injection_findings:
        sev = max_injection_severity(injection_findings)
        markers = [f.marker for f in injection_findings]
        warn_msg = f"Potential injection marker detected in claim {claim.id}: {markers}"
        warnings.append(warn_msg)
        logger.warning("Injection markers in extracted claim", claim_id=claim.id, markers=markers)

        if sev == Severity.HIGH:
            claim = replace(claim, review_state=ReviewState.NEEDS_DECLARATION)

    # Secret scanning.
    secret_findings = scan_for_secrets(claim.content)
    if secret_findings:
        types = [f.pattern_type for f in secret_findings]
        warn_msg = (
            f"Potential secret detected in claim {claim.id} ({types}). Claim marked as local-only."
        )
        warnings.append(warn_msg)
        logger.warning("Secret detected in extracted claim", claim_id=claim.id, types=types)

        # Redact secrets in content and force local-only.
        redacted_content = redact_secrets(claim.content, secret_findings)
        claim = replace(
            claim,
            content=redacted_content,
            sensitivity=Sensitivity.LOCAL_ONLY,
        )

    return claim


def _store_profiles(
    db: sqlite3.Connection | None,
    profiles: tuple[EnvironmentProfile, ...],
    repo_id: str,
) -> int:
    """Store environment profiles in the database."""
    if db is None:
        logger.warning("No database connection available for storing profiles")
        return 0

    count = 0
    for profile in profiles:
        try:
            db.execute(
                """INSERT OR REPLACE INTO environment_profiles
                   (id, name, claim_id, runtime, tools, services, env_vars, setup_commands, repo_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile.id,
                    profile.name,
                    profile.claim_id,
                    profile.runtime,
                    json.dumps(list(profile.tools)),
                    json.dumps(list(profile.services)),
                    json.dumps(list(profile.env_vars)),
                    json.dumps(list(profile.setup_commands)),
                    repo_id or profile.repo_id,
                ),
            )
            db.commit()
            count += 1
        except Exception as exc:
            logger.warning("Failed to store profile", name=profile.name, error=str(exc))

    return count
