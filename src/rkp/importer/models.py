"""Shared data models for the import subsystem."""

from __future__ import annotations

from dataclasses import dataclass

from rkp.core.types import ClaimType


@dataclass(frozen=True)
class ParsedClaimInput:
    """A single claim extracted by an import parser."""

    content: str
    claim_type: ClaimType
    scope: str = "**"
    applicability: tuple[str, ...] = ()
    confidence: float = 0.9
    evidence_file: str = ""


@dataclass(frozen=True)
class UnparseableSection:
    """A section of an instruction file that could not be parsed into claims."""

    heading: str
    content: str
    reason: str


@dataclass(frozen=True)
class ParsedInstructionFile:
    """Result of parsing a single instruction file."""

    source_path: str
    source_type: str  # "agents-md", "claude-md", "copilot-instructions", etc.
    claims: tuple[ParsedClaimInput, ...]
    unparseable_sections: tuple[UnparseableSection, ...]
    warnings: tuple[str, ...]
    content_hash: str = ""
    file_references: tuple[str, ...] = ()  # @file refs in CLAUDE.md


@dataclass(frozen=True)
class ContentDrift:
    """A managed file whose on-disk content differs from expected."""

    path: str
    expected_hash: str
    actual_hash: str
    ownership_mode: str


@dataclass(frozen=True)
class DriftReport:
    """Result of drift detection across all managed artifacts."""

    content_drifts: tuple[ContentDrift, ...]
    new_unmanaged: tuple[str, ...]
    missing_files: tuple[str, ...]
    clean_files: tuple[str, ...]


@dataclass(frozen=True)
class ImportResult:
    """Summary of a full import run."""

    files_discovered: tuple[str, ...]
    files_parsed: tuple[str, ...]
    claims_created: int
    claims_deduplicated: int
    conflicts_found: int
    unparseable_sections: tuple[UnparseableSection, ...]
    security_warnings: tuple[str, ...]
    warnings: tuple[str, ...]
