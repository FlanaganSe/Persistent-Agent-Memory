"""CLAUDE.md parser: extract structured claims from CLAUDE.md files."""

from __future__ import annotations

import re
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

# Pattern for @file references in CLAUDE.md
_FILE_REF_PATTERN = re.compile(r"@([\w./\-]+(?:\.\w+)?)")


def parse_claude_md(
    file_path: Path,
    *,
    scope_prefix: str = "**",
) -> ParsedInstructionFile:
    """Parse a CLAUDE.md file into structured claim inputs.

    CLAUDE.md files are directive-heavy: "When doing X, always Y", "Never Z",
    "Prefer A over B". They may also contain @file import references.

    Args:
        file_path: Path to the CLAUDE.md file.
        scope_prefix: Scope prefix for claims.

    Returns:
        ParsedInstructionFile with claims, unparseable sections, and warnings.
    """
    if not file_path.exists():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="claude-md",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="claude-md",
            claims=(),
            unparseable_sections=(),
            warnings=(f"Failed to read {file_path}: {exc}",),
        )

    if not content.strip():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="claude-md",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    content_hash = compute_content_hash(content)
    warnings = collect_security_warnings(content)

    # Extract @file references (noted but not followed in M11)
    file_references = tuple(str(r) for r in _FILE_REF_PATTERN.findall(content))
    if file_references:
        warnings.append(
            f"Found {len(file_references)} @file reference(s): "
            f"{', '.join(file_references[:5])}"
            + (" ..." if len(file_references) > 5 else "")
            + " (references not followed in this version)"
        )

    # Strip frontmatter if present
    _, body = extract_frontmatter(content)

    claims: list[ParsedClaimInput] = []
    unparseable: list[UnparseableSection] = []

    # Extract code blocks as commands (deterministic)
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
                                applicability=_guess_applicability(cmd),
                                confidence=1.0,
                                evidence_file=str(file_path),
                            )
                        )

    # Parse sections
    sections = parse_sections(body)
    for section in sections:
        if not section.content.strip():
            continue

        section_type = section.section_type

        if section_type == SectionType.COMMANDS:
            _extract_command_claims(section.content, scope_prefix, file_path, claims)
        elif section_type == SectionType.CONVENTIONS:
            _extract_convention_claims(section.content, scope_prefix, file_path, claims)
        elif section_type == SectionType.SETUP:
            _extract_setup_claims(section.content, scope_prefix, file_path, claims)
        elif section_type == SectionType.TESTING:
            _extract_testing_claims(section.content, scope_prefix, file_path, claims)
        elif section_type == SectionType.SKILLS:
            _extract_skill_claims(section.content, scope_prefix, file_path, claims)
        elif section_type == SectionType.ARCHITECTURE:
            _extract_architecture_claims(section.content, scope_prefix, file_path, claims)
        elif section_type == SectionType.UNKNOWN:
            # CLAUDE.md tends to have directive-style content everywhere
            extracted = _extract_directives_from_content(
                section.content, scope_prefix, file_path, claims
            )
            if not extracted and not is_generic_prose(section.content):
                unparseable.append(
                    UnparseableSection(
                        heading=section.heading,
                        content=section.content[:500],
                        reason="Could not classify section or extract claims",
                    )
                )

    # Also scan for directives in non-section content (top-level bullets/prose)
    if not sections and body.strip():
        _extract_directives_from_content(body, scope_prefix, file_path, claims)

    return ParsedInstructionFile(
        source_path=str(file_path),
        source_type="claude-md",
        claims=tuple(claims),
        unparseable_sections=tuple(unparseable),
        warnings=tuple(warnings),
        content_hash=content_hash,
        file_references=file_references,
    )


def _extract_directives_from_content(
    content: str,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> bool:
    """Extract directive-style rules from content. Returns True if any extracted."""
    items = extract_bullet_items(content)
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
                    confidence=0.9,
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
                    applicability=_guess_applicability(cmd),
                    confidence=0.8,
                    evidence_file=str(file_path),
                )
            )
            extracted = True

    # Also check individual lines for directives
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if is_directive(stripped) and not any(c.content == stripped for c in claims):
            claims.append(
                ParsedClaimInput(
                    content=stripped,
                    claim_type=ClaimType.ALWAYS_ON_RULE,
                    scope=scope,
                    confidence=0.8,
                    evidence_file=str(file_path),
                )
            )
            extracted = True

    return extracted


def _extract_command_claims(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract validated-command claims."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        # Handle backtick-wrapped commands: `pytest tests/`
        stripped_item = item.strip("`").strip()
        if is_command_like(item) or is_command_like(stripped_item):
            cmd = stripped_item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    applicability=_guess_applicability(cmd),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )
        elif ":" in item:
            _, _, cmd_part = item.partition(":")
            cmd_part = cmd_part.strip().strip("`")
            if cmd_part and is_command_like(cmd_part):
                claims.append(
                    ParsedClaimInput(
                        content=cmd_part,
                        claim_type=ClaimType.VALIDATED_COMMAND,
                        scope=scope,
                        applicability=_guess_applicability(cmd_part),
                        confidence=0.9,
                        evidence_file=str(file_path),
                    )
                )


def _extract_convention_claims(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract convention claims."""
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


def _extract_setup_claims(
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


def _extract_testing_claims(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract testing-related claims."""
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
                    applicability=("test",),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )
        else:
            claims.append(
                ParsedClaimInput(
                    content=item,
                    claim_type=ClaimType.ALWAYS_ON_RULE,
                    scope=scope,
                    applicability=("test",),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )


def _extract_skill_claims(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract skill-playbook claims."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        claims.append(
            ParsedClaimInput(
                content=item,
                claim_type=ClaimType.SKILL_PLAYBOOK,
                scope=scope,
                confidence=0.8,
                evidence_file=str(file_path),
            )
        )


def _extract_architecture_claims(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract architecture/boundary claims (low confidence)."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        claims.append(
            ParsedClaimInput(
                content=item,
                claim_type=ClaimType.MODULE_BOUNDARY,
                scope=scope,
                confidence=0.6,
                evidence_file=str(file_path),
            )
        )


def _guess_applicability(command: str) -> tuple[str, ...]:
    """Guess applicability tags from a command string."""
    cmd_lower = command.lower()
    tags: list[str] = []

    if any(kw in cmd_lower for kw in ("test", "pytest", "jest", "vitest", "mocha")):
        tags.append("test")
    if any(kw in cmd_lower for kw in ("lint", "ruff", "eslint", "flake8")):
        tags.append("lint")
    if any(kw in cmd_lower for kw in ("format", "prettier", "black")):
        tags.append("format")
    if any(kw in cmd_lower for kw in ("build", "compile", "webpack")):
        tags.append("build")
    if any(kw in cmd_lower for kw in ("deploy", "release", "publish")):
        tags.append("release")

    return tuple(tags) if tags else ("all",)
