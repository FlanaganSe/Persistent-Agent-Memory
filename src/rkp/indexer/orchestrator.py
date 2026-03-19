"""Extraction pipeline orchestrator: discover → parse → extract → store."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import structlog

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Claim, Provenance
from rkp.core.types import ClaimType
from rkp.indexer.config_parsers.package_json import parse_package_json
from rkp.indexer.config_parsers.pyproject import parse_pyproject
from rkp.indexer.extractors.commands import (
    CommandClaimInput,
    ParsedCommand,
    extract_command_claims,
)
from rkp.store.claims import ClaimStore

logger = structlog.get_logger()


@dataclass(frozen=True)
class ExtractionSummary:
    """Summary of an extraction run."""

    files_parsed: int
    claims_created: int
    claims_deduplicated: int
    warnings: tuple[str, ...] = ()


def _discover_config_files(repo_root: Path) -> list[str]:
    """Discover config files at the repo root."""
    candidates = ("pyproject.toml", "package.json")
    return [name for name in candidates if (repo_root / name).is_file()]


def run_extraction(
    repo_root: Path,
    claim_store: ClaimStore,
    *,
    repo_id: str = "",
    branch: str = "main",
) -> ExtractionSummary:
    """Run the extraction pipeline on a repo.

    Discovers config files, parses them, extracts commands,
    builds claims, deduplicates, and stores.

    Idempotent: running twice on unchanged files produces the same claims.
    """
    builder = ClaimBuilder(repo_id=repo_id, branch=branch)
    config_files = _discover_config_files(repo_root)
    all_parsed_commands: list[ParsedCommand] = []
    warnings: list[str] = []

    for config_file in config_files:
        if config_file == "pyproject.toml":
            result = parse_pyproject(repo_root)
            all_parsed_commands.extend(result.commands)
        elif config_file == "package.json":
            result_pkg = parse_package_json(repo_root)
            all_parsed_commands.extend(result_pkg.commands)

    claim_inputs = extract_command_claims(tuple(all_parsed_commands))
    new_claims = _build_claims(builder, claim_inputs)

    existing_claims = claim_store.list_claims(repo_id=repo_id)
    unique, duplicates = builder.deduplicate(new_claims, existing_claims)

    for claim in unique:
        claim_store.save(claim)

    logger.info(
        "Extraction complete",
        files_parsed=len(config_files),
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
    )

    return ExtractionSummary(
        files_parsed=len(config_files),
        claims_created=len(unique),
        claims_deduplicated=len(duplicates),
        warnings=tuple(warnings),
    )


def _build_claims(builder: ClaimBuilder, inputs: list[CommandClaimInput]) -> list[Claim]:
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
