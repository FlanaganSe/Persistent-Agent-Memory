"""Cursor rules parser: .cursor/rules directory and .cursorrules file."""

from __future__ import annotations

from pathlib import Path

import structlog

from rkp.core.types import ClaimType
from rkp.importer.models import ParsedClaimInput, ParsedInstructionFile, UnparseableSection
from rkp.importer.parsers.markdown_utils import (
    SectionType,
    collect_security_warnings,
    compute_content_hash,
    extract_bullet_items,
    extract_code_blocks,
    extract_frontmatter,
    is_command_like,
    is_directive,
    is_generic_prose,
    parse_sections,
)

logger = structlog.get_logger()

_SHELL_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh", "console", ""})


def parse_cursor_rules(
    path: Path,
    *,
    scope_prefix: str = "**",
) -> list[ParsedInstructionFile]:
    """Parse .cursor/rules directory or .cursorrules file.

    If path is a directory, parses all markdown files within it.
    If path is a file (.cursorrules), parses it as a single file.

    Returns a list of ParsedInstructionFile (one per parsed file).
    """
    results: list[ParsedInstructionFile] = []

    if path.is_dir():
        # Parse all files in .cursor/rules/
        for rule_file in sorted(path.rglob("*")):
            if rule_file.is_file() and rule_file.suffix in (".md", ".mdc", ""):
                result = _parse_single_cursor_rule(rule_file, scope_prefix=scope_prefix)
                results.append(result)
    elif path.is_file():
        result = _parse_single_cursor_rule(path, scope_prefix=scope_prefix)
        results.append(result)

    return results


def _parse_single_cursor_rule(
    file_path: Path,
    *,
    scope_prefix: str = "**",
) -> ParsedInstructionFile:
    """Parse a single cursor rule file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="cursor-rules",
            claims=(),
            unparseable_sections=(),
            warnings=(f"Failed to read {file_path}: {exc}",),
        )

    if not content.strip():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="cursor-rules",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    content_hash = compute_content_hash(content)
    warnings = collect_security_warnings(content)

    # Check for YAML frontmatter (glob patterns for scoping)
    frontmatter, body = extract_frontmatter(content)

    # Handle glob-based scoping from frontmatter
    glob_pattern = frontmatter.get("glob", "") or frontmatter.get("globs", "")
    always_apply = frontmatter.get("alwaysApply", "").lower() in ("true", "yes", "1")

    if glob_pattern:
        scope_prefix = glob_pattern
    elif always_apply:
        scope_prefix = "**"

    claims: list[ParsedClaimInput] = []
    unparseable: list[UnparseableSection] = []

    # Extract code blocks
    code_blocks = extract_code_blocks(body)
    for block in code_blocks:
        if block.language.lower() in _SHELL_LANGUAGES and block.content.strip():
            for line in block.content.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    cmd = line.lstrip("$> ").strip()
                    if cmd:
                        claims.append(
                            ParsedClaimInput(
                                content=cmd,
                                claim_type=ClaimType.VALIDATED_COMMAND,
                                scope=scope_prefix,
                                confidence=1.0,
                                evidence_file=str(file_path),
                            )
                        )

    # Parse sections
    sections = parse_sections(body)
    for section in sections:
        if not section.content.strip():
            continue

        if section.section_type == SectionType.COMMANDS:
            _extract_command_items(section.content, scope_prefix, file_path, claims)
        elif section.section_type == SectionType.CONVENTIONS:
            _extract_rule_items(section.content, scope_prefix, file_path, claims)
        elif section.section_type == SectionType.SETUP:
            _extract_setup_items(section.content, scope_prefix, file_path, claims)
        elif section.section_type == SectionType.UNKNOWN:
            # Try directive extraction
            _extract_directives(section, scope_prefix, file_path, claims, unparseable)

    # If no sections, try top-level extraction
    if not sections and body.strip():
        items = extract_bullet_items(body)
        for item in items:
            if is_generic_prose(item):
                continue
            if is_directive(item):
                claims.append(
                    ParsedClaimInput(
                        content=item,
                        claim_type=ClaimType.ALWAYS_ON_RULE,
                        scope=scope_prefix,
                        confidence=0.8,
                        evidence_file=str(file_path),
                    )
                )
            elif is_command_like(item):
                cmd = item.lstrip("$> ").strip()
                claims.append(
                    ParsedClaimInput(
                        content=cmd,
                        claim_type=ClaimType.VALIDATED_COMMAND,
                        scope=scope_prefix,
                        confidence=0.8,
                        evidence_file=str(file_path),
                    )
                )

        # Check non-bullet lines for directives
        for line in body.split("\n"):
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("#")
                and is_directive(stripped)
                and not any(c.content == stripped for c in claims)
            ):
                claims.append(
                    ParsedClaimInput(
                        content=stripped,
                        claim_type=ClaimType.ALWAYS_ON_RULE,
                        scope=scope_prefix,
                        confidence=0.8,
                        evidence_file=str(file_path),
                    )
                )

    return ParsedInstructionFile(
        source_path=str(file_path),
        source_type="cursor-rules",
        claims=tuple(claims),
        unparseable_sections=tuple(unparseable),
        warnings=tuple(warnings),
        content_hash=content_hash,
    )


def _extract_command_items(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract command claims."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        if is_command_like(item):
            cmd = item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )


def _extract_rule_items(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract rule/convention claims."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        claims.append(
            ParsedClaimInput(
                content=item,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                scope=scope,
                confidence=0.9,
                evidence_file=str(file_path),
            )
        )


def _extract_setup_items(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract setup/prerequisite claims."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        if is_command_like(item):
            cmd = item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    applicability=("setup",),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )
        else:
            claims.append(
                ParsedClaimInput(
                    content=item,
                    claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                    scope=scope,
                    applicability=("setup",),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )


def _extract_directives(
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
    unparseable: list[UnparseableSection],
) -> None:
    """Try to extract directives from an unclassified section."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return

    items = extract_bullet_items(sec.content)
    extracted = False

    for item in items:
        if is_generic_prose(item):
            continue
        if is_directive(item):
            claims.append(
                ParsedClaimInput(
                    content=item,
                    claim_type=ClaimType.ALWAYS_ON_RULE,
                    scope=scope,
                    confidence=0.8,
                    evidence_file=str(file_path),
                )
            )
            extracted = True
        elif is_command_like(item):
            cmd = item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    confidence=0.8,
                    evidence_file=str(file_path),
                )
            )
            extracted = True

    if not extracted and not is_generic_prose(sec.content):
        unparseable.append(
            UnparseableSection(
                heading=sec.heading,
                content=sec.content[:500],
                reason="Could not classify section or extract claims",
            )
        )
