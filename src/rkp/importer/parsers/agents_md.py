"""AGENTS.md parser: extract structured claims from AGENTS.md files."""

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


def parse_agents_md(
    file_path: Path,
    *,
    scope_prefix: str = "**",
) -> ParsedInstructionFile:
    """Parse an AGENTS.md file into structured claim inputs.

    Args:
        file_path: Path to the AGENTS.md file.
        scope_prefix: Scope prefix for claims (e.g., "src/" for nested AGENTS.md).

    Returns:
        ParsedInstructionFile with claims, unparseable sections, and warnings.
    """
    if not file_path.exists():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="agents-md",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="agents-md",
            claims=(),
            unparseable_sections=(),
            warnings=(f"Failed to read {file_path}: {exc}",),
        )

    if not content.strip():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="agents-md",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    content_hash = compute_content_hash(content)
    warnings = collect_security_warnings(content)

    # Strip frontmatter if present
    _, body = extract_frontmatter(content)

    claims: list[ParsedClaimInput] = []
    unparseable: list[UnparseableSection] = []

    # Extract code blocks as commands (deterministic, high confidence)
    code_blocks = extract_code_blocks(body)
    for block in code_blocks:
        if block.language.lower() in _SHELL_LANGUAGES and block.content.strip():
            for line in block.content.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    # Strip leading $ or > prompt
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

        if section_type == SectionType.SETUP:
            _extract_setup_claims(section, scope_prefix, file_path, claims)
        elif section_type == SectionType.COMMANDS:
            _extract_command_claims(section, scope_prefix, file_path, claims)
        elif section_type == SectionType.CONVENTIONS:
            _extract_convention_claims(section, scope_prefix, file_path, claims)
        elif section_type == SectionType.ARCHITECTURE:
            _extract_architecture_claims(section, scope_prefix, file_path, claims)
        elif section_type == SectionType.TESTING:
            _extract_testing_claims(section, scope_prefix, file_path, claims)
        elif section_type == SectionType.SKILLS:
            _extract_skill_claims(section, scope_prefix, file_path, claims)
        elif section_type == SectionType.UNKNOWN:
            # Try to extract directives from unknown sections
            items = extract_bullet_items(section.content)
            extracted_any = False
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
                    extracted_any = True
                elif is_command_like(item):
                    cmd = item.lstrip("$> ").strip()
                    claims.append(
                        ParsedClaimInput(
                            content=cmd,
                            claim_type=ClaimType.VALIDATED_COMMAND,
                            scope=scope_prefix,
                            applicability=_guess_applicability(cmd),
                            confidence=0.8,
                            evidence_file=str(file_path),
                        )
                    )
                    extracted_any = True

            if not extracted_any and not is_generic_prose(section.content):
                unparseable.append(
                    UnparseableSection(
                        heading=section.heading,
                        content=section.content[:500],
                        reason="Could not classify section or extract claims",
                    )
                )
        # Generic prose sections are silently skipped (not added to unparseable)

    return ParsedInstructionFile(
        source_path=str(file_path),
        source_type="agents-md",
        claims=tuple(claims),
        unparseable_sections=tuple(unparseable),
        warnings=tuple(warnings),
        content_hash=content_hash,
    )


def _extract_setup_claims(
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> None:
    """Extract environment-prerequisite claims from a setup section."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return
    items = extract_bullet_items(sec.content)
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


def _extract_command_claims(
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> None:
    """Extract validated-command claims from a commands section."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return
    items = extract_bullet_items(sec.content)
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
                    applicability=_guess_applicability(cmd),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )
        elif ":" in item:
            # "lint: ruff check ." style
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

    # Also look for inline code that might be commands
    import re

    inline_commands = re.findall(r"`([^`]+)`", sec.content)
    for cmd in inline_commands:
        if is_command_like(cmd) and not any(c.content == cmd for c in claims):
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


def _extract_convention_claims(
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> None:
    """Extract always-on-rule or scoped-rule claims from a conventions section."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return
    items = extract_bullet_items(sec.content)
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


def _extract_architecture_claims(
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> None:
    """Extract module-boundary claims from architecture sections (low confidence)."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return
    items = extract_bullet_items(sec.content)
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


def _extract_testing_claims(
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> None:
    """Extract testing-related claims."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return
    items = extract_bullet_items(sec.content)
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
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> None:
    """Extract skill-playbook claims from skills/workflows sections."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return
    items = extract_bullet_items(sec.content)
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
    if any(kw in cmd_lower for kw in ("build", "compile", "webpack", "vite build")):
        tags.append("build")
    if any(kw in cmd_lower for kw in ("typecheck", "pyright", "mypy", "tsc")):
        tags.append("lint")
    if any(kw in cmd_lower for kw in ("deploy", "release", "publish")):
        tags.append("release")
    if any(kw in cmd_lower for kw in ("install", "setup")):
        tags.append("setup")

    return tuple(tags) if tags else ("all",)
