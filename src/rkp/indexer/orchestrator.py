"""Extraction pipeline orchestrator: discover → parse → extract → store."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import structlog

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Claim, Provenance
from rkp.core.types import ClaimType, ReviewState
from rkp.git.backend import GitBackend
from rkp.indexer.config_parsers.package_json import parse_package_json
from rkp.indexer.config_parsers.pyproject import PyprojectResult, parse_pyproject
from rkp.indexer.extractors.commands import (
    CommandClaimInput,
    ParsedCommand,
    extract_command_claims,
)
from rkp.indexer.extractors.conventions import ConventionClaimInput, extract_conventions
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
    }
)

# Maximum file size to parse (bytes). Files larger than this are skipped.
_MAX_FILE_SIZE = 1_000_000


@dataclass(frozen=True)
class ExtractionSummary:
    """Summary of an extraction run."""

    files_parsed: int
    claims_created: int
    claims_deduplicated: int
    python_files_parsed: int = 0
    conventions_extracted: int = 0
    warnings: tuple[str, ...] = ()


def _discover_config_files(repo_root: Path) -> list[str]:
    """Discover config files at the repo root."""
    candidates = ("pyproject.toml", "package.json")
    return [name for name in candidates if (repo_root / name).is_file()]


def _should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from parsing."""
    return any(part in _DEFAULT_EXCLUDES for part in path.parts)


def _discover_python_files(
    repo_root: Path,
    git_backend: GitBackend | None = None,
) -> list[Path]:
    """Discover Python files to parse.

    Uses git backend when available for tracked+untracked files.
    Falls back to filesystem walk when git is not available.
    """
    python_files: list[Path] = []

    if git_backend is not None:
        all_files = git_backend.list_tracked_files() + git_backend.list_untracked_files()
        for rel_path in all_files:
            if rel_path.suffix != ".py":
                continue
            if _should_exclude(rel_path):
                continue
            full_path = repo_root / rel_path
            if full_path.is_file() and full_path.stat().st_size <= _MAX_FILE_SIZE:
                python_files.append(rel_path)
    else:
        for full_path in repo_root.rglob("*.py"):
            rel_path = full_path.relative_to(repo_root)
            if _should_exclude(rel_path):
                continue
            if full_path.stat().st_size <= _MAX_FILE_SIZE:
                python_files.append(rel_path)

    return sorted(python_files)


def run_extraction(
    repo_root: Path,
    claim_store: ClaimStore,
    *,
    repo_id: str = "",
    branch: str = "main",
    git_backend: GitBackend | None = None,
) -> ExtractionSummary:
    """Run the extraction pipeline on a repo.

    Discovers config files and Python source files, parses them,
    extracts commands and conventions, builds claims, deduplicates, and stores.

    Idempotent: running twice on unchanged files produces the same claims.
    """
    builder = ClaimBuilder(repo_id=repo_id, branch=branch)
    config_files = _discover_config_files(repo_root)
    all_parsed_commands: list[ParsedCommand] = []
    warnings: list[str] = []
    tools_detected: set[str] = set()
    pyproject_result: PyprojectResult | None = None

    # Phase 1: Parse config files for commands
    for config_file in config_files:
        if config_file == "pyproject.toml":
            pyproject_result = parse_pyproject(repo_root)
            all_parsed_commands.extend(pyproject_result.commands)
            tools_detected.update(pyproject_result.tools_detected)
        elif config_file == "package.json":
            result_pkg = parse_package_json(repo_root)
            all_parsed_commands.extend(result_pkg.commands)

    # Build command claims
    claim_inputs = extract_command_claims(tuple(all_parsed_commands))
    new_claims = _build_command_claims(builder, claim_inputs)

    # Phase 2: Parse Python files for conventions
    python_files = _discover_python_files(repo_root, git_backend)
    parsed_python: list[ParsedPythonFile] = []

    for rel_path in python_files:
        full_path = repo_root / rel_path
        parsed = parse_python_file(full_path)
        parsed_python.append(parsed)

    # Extract conventions from parsed Python files
    convention_inputs = extract_conventions(
        parsed_python,
        tools_detected=frozenset(tools_detected),
    )
    convention_claims = _build_convention_claims(builder, convention_inputs)
    new_claims.extend(convention_claims)

    # Deduplicate and store
    existing_claims = claim_store.list_claims(repo_id=repo_id)
    unique, duplicates = builder.deduplicate(new_claims, existing_claims)

    for claim in unique:
        claim_store.save(claim)

    total_files = len(config_files) + len(python_files)

    logger.info(
        "Extraction complete",
        files_parsed=total_files,
        python_files=len(python_files),
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
        conventions=len(convention_claims),
    )

    return ExtractionSummary(
        files_parsed=total_files,
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
        python_files_parsed=len(python_files),
        conventions_extracted=len(convention_claims),
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
        # Set review state hint (needs-declaration for weak conventions)
        if inp.review_state_hint == "needs-declaration":
            claim = replace(claim, review_state=ReviewState.NEEDS_DECLARATION)
        claims.append(claim)
    return claims
