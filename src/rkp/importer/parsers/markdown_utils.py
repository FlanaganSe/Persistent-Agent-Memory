"""Shared markdown parsing utilities for instruction file parsers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# Section heading classification keywords.
_SETUP_KEYWORDS = frozenset(
    {
        "setup",
        "installation",
        "install",
        "prerequisites",
        "prerequisite",
        "getting started",
        "requirements",
        "dependencies",
        "environment",
    }
)
_COMMAND_KEYWORDS = frozenset(
    {
        "commands",
        "scripts",
        "tasks",
        "running",
        "usage",
        "run",
        "development",
        "developing",
        "building",
        "build",
    }
)
_CONVENTION_KEYWORDS = frozenset(
    {
        "conventions",
        "style",
        "rules",
        "guidelines",
        "coding style",
        "code style",
        "standards",
        "best practices",
        "principles",
        "preferences",
    }
)
_ARCHITECTURE_KEYWORDS = frozenset(
    {
        "architecture",
        "structure",
        "modules",
        "components",
        "layout",
        "organization",
        "design",
        "system",
    }
)
_TESTING_KEYWORDS = frozenset(
    {
        "testing",
        "tests",
        "test",
        "test plan",
        "test strategy",
    }
)
_SKILLS_KEYWORDS = frozenset(
    {
        "skills",
        "procedures",
        "workflows",
        "playbooks",
        "recipes",
        "how to",
        "how-to",
    }
)

# Patterns for content that should NOT be extracted.
_GENERIC_PROSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^this (?:project|repository|repo) (?:is|provides|implements)", re.IGNORECASE),
    re.compile(r"^(?:welcome|introduction|overview|about)", re.IGNORECASE),
    re.compile(r"^(?:license|copyright|author|contributor)", re.IGNORECASE),
    re.compile(r"^we plan to", re.IGNORECASE),
    re.compile(r"^(?:how to contribute|contributing|pull request)", re.IGNORECASE),
)

# Command-like line patterns.
_COMMAND_LINE_PATTERN = re.compile(r"^\s*(?:\$|>|#\s)\s*(.+)$")
_CLI_PATTERN = re.compile(
    r"^\s*(?:npm|yarn|pnpm|make|docker|pip|uv|cargo|go|python|pytest|ruff|"
    r"pyright|eslint|prettier|jest|vitest|mocha|nox|tox|"
    r"brew|apt|dnf|curl|wget|git|gh)\s+"
)

# Directive patterns for convention extraction.
_DIRECTIVE_PATTERN = re.compile(
    r"^\s*[-*]?\s*(?:always|never|do not|don't|must|should|prefer|avoid|"
    r"use|ensure|make sure|require|keep|maintain)\s+",
    re.IGNORECASE,
)


class SectionType:
    """Classification of markdown sections."""

    SETUP = "setup"
    COMMANDS = "commands"
    CONVENTIONS = "conventions"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    SKILLS = "skills"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MarkdownSection:
    """A parsed section from a markdown file."""

    heading: str
    level: int
    content: str
    section_type: str
    line_start: int
    line_end: int


@dataclass(frozen=True)
class CodeBlock:
    """A fenced code block from a markdown file."""

    language: str
    content: str
    line_start: int
    line_end: int


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content with normalization.

    Normalizes: strip trailing whitespace per line, normalize line endings to \\n.
    """
    normalized = normalize_content(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_content(content: str) -> str:
    """Normalize content for hash comparison.

    Strips trailing whitespace per line, normalizes line endings to \\n.
    """
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines)


def classify_heading(heading: str) -> str:
    """Classify a heading into a section type based on keywords."""
    heading_lower = heading.lower().strip().strip("#").strip()

    for keyword in _SETUP_KEYWORDS:
        if keyword in heading_lower:
            return SectionType.SETUP
    for keyword in _COMMAND_KEYWORDS:
        if keyword in heading_lower:
            return SectionType.COMMANDS
    for keyword in _CONVENTION_KEYWORDS:
        if keyword in heading_lower:
            return SectionType.CONVENTIONS
    for keyword in _ARCHITECTURE_KEYWORDS:
        if keyword in heading_lower:
            return SectionType.ARCHITECTURE
    for keyword in _TESTING_KEYWORDS:
        if keyword in heading_lower:
            return SectionType.TESTING
    for keyword in _SKILLS_KEYWORDS:
        if keyword in heading_lower:
            return SectionType.SKILLS
    return SectionType.UNKNOWN


def parse_sections(content: str) -> list[MarkdownSection]:
    """Parse markdown content into sections by heading."""
    lines = content.split("\n")
    sections: list[MarkdownSection] = []
    current_heading = ""
    current_level = 0
    current_lines: list[str] = []
    current_start = 1

    for i, line in enumerate(lines, 1):
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            # Save previous section
            if current_lines or current_heading:
                section_content = "\n".join(current_lines).strip()
                if section_content or current_heading:
                    section_type = classify_heading(current_heading)
                    sections.append(
                        MarkdownSection(
                            heading=current_heading,
                            level=current_level,
                            content=section_content,
                            section_type=section_type,
                            line_start=current_start,
                            line_end=i - 1,
                        )
                    )
            current_heading = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_lines = []
            current_start = i
        else:
            current_lines.append(line)

    # Save final section
    if current_lines or current_heading:
        section_content = "\n".join(current_lines).strip()
        if section_content or current_heading:
            section_type = classify_heading(current_heading)
            sections.append(
                MarkdownSection(
                    heading=current_heading,
                    level=current_level,
                    content=section_content,
                    section_type=section_type,
                    line_start=current_start,
                    line_end=len(lines),
                )
            )

    return sections


def extract_code_blocks(content: str) -> list[CodeBlock]:
    """Extract fenced code blocks from markdown content."""
    blocks: list[CodeBlock] = []
    lines = content.split("\n")
    in_block = False
    block_lang = ""
    block_lines: list[str] = []
    block_start = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```") and not in_block:
            in_block = True
            block_lang = stripped[3:].strip().split()[0] if len(stripped) > 3 else ""
            block_lines = []
            block_start = i
        elif stripped.startswith("```") and in_block:
            in_block = False
            blocks.append(
                CodeBlock(
                    language=block_lang,
                    content="\n".join(block_lines),
                    line_start=block_start,
                    line_end=i,
                )
            )
        elif in_block:
            block_lines.append(line)

    return blocks


def extract_bullet_items(content: str) -> list[str]:
    """Extract bullet list items from content, joining continuation lines."""
    items: list[str] = []
    lines = content.split("\n")
    current_item = ""

    for line in lines:
        bullet_match = re.match(r"^\s*[-*+]\s+(.+)$", line)
        numbered_match = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        continuation = re.match(r"^\s{2,}(\S.+)$", line)

        if bullet_match:
            if current_item:
                items.append(current_item.strip())
            current_item = bullet_match.group(1)
        elif numbered_match:
            if current_item:
                items.append(current_item.strip())
            current_item = numbered_match.group(1)
        elif continuation and current_item:
            current_item += " " + continuation.group(1)
        elif not line.strip():
            if current_item:
                items.append(current_item.strip())
                current_item = ""

    if current_item:
        items.append(current_item.strip())

    return items


def is_generic_prose(text: str) -> bool:
    """Check if text is generic prose that should NOT be extracted as claims."""
    stripped = text.strip()
    if not stripped:
        return True

    return any(pattern.search(stripped) for pattern in _GENERIC_PROSE_PATTERNS)


def is_command_like(text: str) -> bool:
    """Check if text looks like a CLI command."""
    stripped = text.strip()
    if _COMMAND_LINE_PATTERN.match(stripped):
        return True
    return bool(_CLI_PATTERN.match(stripped))


def is_directive(text: str) -> bool:
    """Check if text is a directive-style rule (Always..., Never..., etc.)."""
    return bool(_DIRECTIVE_PATTERN.match(text))


def extract_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter from content.

    Returns (frontmatter_dict, remaining_content).
    """
    if not content.startswith("---"):
        return {}, content

    lines = content.split("\n")
    end_idx = -1
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        return {}, content

    frontmatter_lines = lines[1:end_idx]
    remaining = "\n".join(lines[end_idx + 1 :])

    fm: dict[str, str] = {}
    for line in frontmatter_lines:
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip("\"'")

    return fm, remaining


def collect_security_warnings(content: str) -> list[str]:
    """Run injection + secret scanning and return warning strings."""
    from rkp.core.security import scan_for_injection, scan_for_secrets

    warnings: list[str] = []
    injection_findings = scan_for_injection(content)
    warnings.extend(
        f"Injection marker detected at line {f.line_number}: {f.marker} (severity: {f.severity})"
        for f in injection_findings
    )
    secret_findings = scan_for_secrets(content)
    warnings.extend(
        f"Potential secret detected at line {f.line_number}: {f.pattern_type}"
        for f in secret_findings
    )
    return warnings
