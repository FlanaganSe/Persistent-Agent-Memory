"""Checked-in-docs evidence parser: README, docs/ files with command blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog

from rkp.core.types import EvidenceLevel, RiskClass, Sensitivity, SourceAuthority
from rkp.indexer.extractors.commands import CommandClaimInput

logger = structlog.get_logger()

# Operational section headings (case-insensitive).
_OPERATIONAL_HEADINGS = frozenset(
    {
        "getting started",
        "installation",
        "install",
        "development",
        "testing",
        "building",
        "running",
        "setup",
        "prerequisites",
        "requirements",
        "usage",
        "commands",
        "quick start",
        "quickstart",
        "build",
        "deploy",
        "deployment",
        "configuration",
    }
)

# Command prefixes that indicate operational commands.
_COMMAND_PREFIXES = (
    "npm ",
    "npx ",
    "yarn ",
    "pnpm ",
    "pip ",
    "pip3 ",
    "pytest ",
    "make ",
    "docker ",
    "docker-compose ",
    "python ",
    "python3 ",
    "node ",
    "cargo ",
    "go ",
    "uv ",
    "uvx ",
    "nox ",
    "tox ",
    "ruff ",
    "black ",
    "mypy ",
    "pyright ",
    "eslint ",
    "prettier ",
    "jest ",
    "vitest ",
    "gradle ",
    "mvn ",
    "maven ",
    "mix ",
    "bundle ",
    "gem ",
    "poetry ",
    "pdm ",
    "hatch ",
    "cmake ",
    "bazel ",
    "kubectl ",
    "terraform ",
    "ansible ",
    "brew ",
    "apt-get ",
    "apt ",
    "curl ",
    "wget ",
    "git ",
)

# Fenced code block language tags that indicate shell commands.
_SHELL_LANGS = frozenset({"bash", "shell", "sh", "zsh", "console", ""})

# Runtime requirement patterns in prose.
_RUNTIME_PATTERNS = [
    re.compile(r"(?:requires?|needs?)\s+Python\s+(\d+\.\d+\+?)", re.IGNORECASE),
    re.compile(r"Python\s+(\d+\.\d+\+?)\s+(?:or\s+(?:later|higher|above|newer))", re.IGNORECASE),
    re.compile(r"(?:requires?|needs?)\s+Node(?:\.js)?\s+(>=?\s*\d+)", re.IGNORECASE),
    re.compile(
        r"Node(?:\.js)?\s+(>=?\s*\d+)\s+(?:or\s+(?:later|higher|above|newer))", re.IGNORECASE
    ),
    re.compile(r"(?:requires?|needs?)\s+(?:Go|Golang)\s+(\d+\.\d+\+?)", re.IGNORECASE),
    re.compile(r"(?:requires?|needs?)\s+(?:Ruby)\s+(\d+\.\d+\+?)", re.IGNORECASE),
    re.compile(r"(?:requires?|needs?)\s+(?:Rust|rustc)\s+(\d+\.\d+\+?)", re.IGNORECASE),
    re.compile(r"(?:requires?|needs?)\s+(?:Java|JDK)\s+(\d+\+?)", re.IGNORECASE),
]

# Risk classification for doc commands based on keywords.
_RISK_KEYWORDS: dict[str, RiskClass] = {
    "test": RiskClass.TEST_EXECUTION,
    "pytest": RiskClass.TEST_EXECUTION,
    "jest": RiskClass.TEST_EXECUTION,
    "lint": RiskClass.SAFE_READONLY,
    "check": RiskClass.SAFE_READONLY,
    "format": RiskClass.SAFE_MUTATING,
    "build": RiskClass.BUILD,
    "compile": RiskClass.BUILD,
    "install": RiskClass.SAFE_MUTATING,
    "deploy": RiskClass.DESTRUCTIVE,
    "rm ": RiskClass.DESTRUCTIVE,
    "rm -": RiskClass.DESTRUCTIVE,
    "drop": RiskClass.DESTRUCTIVE,
}


@dataclass(frozen=True)
class DocsPrerequisiteInput:
    """A runtime/tool requirement extracted from documentation prose."""

    content: str
    evidence_file: str
    line_number: int


@dataclass(frozen=True)
class DocsEvidenceResult:
    """Result of docs evidence extraction."""

    commands: tuple[CommandClaimInput, ...]
    prerequisites: tuple[DocsPrerequisiteInput, ...]
    files_scanned: int


def _classify_risk(command: str) -> RiskClass:
    """Classify the risk level of a docs command."""
    cmd_lower = command.lower()
    for keyword, risk in _RISK_KEYWORDS.items():
        if keyword in cmd_lower:
            return risk
    return RiskClass.SAFE_MUTATING


def _is_operational_command(line: str) -> bool:
    """Check if a line looks like an operational command (not a code example)."""
    stripped = line.strip()
    if not stripped:
        return False

    # Strip leading $ or # (common shell prompt markers)
    if stripped.startswith("$ ") or (
        stripped.startswith("# ") and any(stripped[2:].startswith(p) for p in _COMMAND_PREFIXES)
    ):
        stripped = stripped[2:]

    # Check if it starts with a known command prefix
    return any(stripped.startswith(prefix) for prefix in _COMMAND_PREFIXES)


def _confidence_for_heading(heading: str | None, file_path: str) -> float:
    """Determine confidence based on the section heading and file location."""
    # README commands get higher base confidence
    is_readme = Path(file_path).name.lower().startswith("readme")
    base = 0.7 if is_readme else 0.5

    if heading is None:
        return base

    heading_lower = heading.lower()
    # Commands under known operational headings get a boost
    if heading_lower in _OPERATIONAL_HEADINGS:
        return min(base + 0.2, 0.9)

    return base


def _extract_from_file(
    file_path: Path,
    rel_path: str,
) -> tuple[list[CommandClaimInput], list[DocsPrerequisiteInput]]:
    """Extract commands and prerequisites from a single markdown file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read docs file", path=str(file_path), error=str(exc))
        return [], []

    commands: list[CommandClaimInput] = []
    prerequisites: list[DocsPrerequisiteInput] = []
    seen_commands: set[str] = set()

    lines = content.splitlines()
    current_heading: str | None = None
    in_code_block = False
    code_block_lang: str = ""
    code_block_lines: list[str] = []

    for line_num, line in enumerate(lines, start=1):
        # Track headings
        heading_match = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading_match and not in_code_block:
            current_heading = heading_match.group(1).strip()
            continue

        # Track fenced code blocks
        if line.strip().startswith("```") and not in_code_block:
            in_code_block = True
            lang_part = line.strip()[3:].strip().lower()
            # Strip any additional info after language tag (e.g., ```bash title="foo")
            code_block_lang = lang_part.split()[0] if lang_part else ""
            code_block_lines = []
            continue

        if line.strip() == "```" and in_code_block:
            in_code_block = False
            # Process accumulated code block
            if code_block_lang in _SHELL_LANGS:
                for cmd_line in code_block_lines:
                    stripped = cmd_line.strip()
                    if stripped.startswith("$ "):
                        stripped = stripped[2:]
                    if _is_operational_command(stripped) and stripped not in seen_commands:
                        seen_commands.add(stripped)
                        confidence = _confidence_for_heading(current_heading, rel_path)
                        commands.append(
                            CommandClaimInput(
                                content=stripped,
                                source_authority=SourceAuthority.CHECKED_IN_DOCS,
                                evidence_level=EvidenceLevel.DISCOVERED,
                                risk_class=_classify_risk(stripped),
                                scope="**",
                                applicability=_applicability_for_command(stripped),
                                confidence=confidence,
                                sensitivity=Sensitivity.PUBLIC,
                                evidence_files=(rel_path,),
                                command_name=_extract_command_name(stripped),
                            )
                        )
            code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Check for runtime prerequisites in prose
        for pattern in _RUNTIME_PATTERNS:
            match = pattern.search(line)
            if match:
                # Reconstruct the requirement
                full_match = match.group(0)
                prerequisites.append(
                    DocsPrerequisiteInput(
                        content=full_match,
                        evidence_file=rel_path,
                        line_number=line_num,
                    )
                )

    return commands, prerequisites


def _applicability_for_command(command: str) -> tuple[str, ...]:
    """Derive applicability tags from a command string."""
    cmd_lower = command.lower()
    if any(kw in cmd_lower for kw in ("test", "pytest", "jest", "vitest")):
        return ("test",)
    if any(kw in cmd_lower for kw in ("lint", "check", "ruff", "eslint", "mypy", "pyright")):
        return ("lint",)
    if any(kw in cmd_lower for kw in ("format", "prettier", "black")):
        return ("format",)
    if any(kw in cmd_lower for kw in ("build", "compile", "tsc")):
        return ("build",)
    if any(kw in cmd_lower for kw in ("install", "setup")):
        return ("onboarding",)
    return ()


def _extract_command_name(command: str) -> str:
    """Extract a short command name from the full command string."""
    # Take the first word or two as the name
    parts = command.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return parts[0] if parts else command


def extract_docs_evidence(
    repo_root: Path,
) -> DocsEvidenceResult:
    """Extract operational evidence from checked-in documentation.

    Scans README.md, readme.md, README.rst, CONTRIBUTING.md, and docs/*.md.
    Extracts:
    - Command blocks from fenced code blocks (bash/shell/sh)
    - Runtime/tool requirements from prose
    """
    all_commands: list[CommandClaimInput] = []
    all_prerequisites: list[DocsPrerequisiteInput] = []
    files_scanned = 0

    # Discover documentation files
    doc_files: list[tuple[Path, str]] = []
    seen_inodes: set[tuple[int, int]] = set()

    # Root-level README and CONTRIBUTING
    for name in ("README.md", "readme.md", "README.rst", "CONTRIBUTING.md"):
        candidate = repo_root / name
        if candidate.is_file():
            # Deduplicate by inode to handle case-insensitive filesystems
            stat = candidate.stat()
            inode_key = (stat.st_dev, stat.st_ino)
            if inode_key not in seen_inodes:
                seen_inodes.add(inode_key)
                doc_files.append((candidate, name))

    # docs/ directory
    docs_dir = repo_root / "docs"
    if docs_dir.is_dir():
        for md_file in sorted(docs_dir.glob("*.md")):
            rel = str(md_file.relative_to(repo_root)).replace("\\", "/")
            doc_files.append((md_file, rel))

    for file_path, rel_path in doc_files:
        files_scanned += 1
        cmds, prereqs = _extract_from_file(file_path, rel_path)
        all_commands.extend(cmds)
        all_prerequisites.extend(prereqs)

    logger.info(
        "Docs evidence extraction complete",
        files_scanned=files_scanned,
        commands_found=len(all_commands),
        prerequisites_found=len(all_prerequisites),
    )

    return DocsEvidenceResult(
        commands=tuple(all_commands),
        prerequisites=tuple(all_prerequisites),
        files_scanned=files_scanned,
    )
