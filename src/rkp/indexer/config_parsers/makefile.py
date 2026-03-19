"""Parse Makefile for targets and commands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog

from rkp.core.security import validate_path
from rkp.core.types import RiskClass
from rkp.indexer.extractors.commands import ParsedCommand

logger = structlog.get_logger()


@dataclass(frozen=True)
class MakefileResult:
    """Structured output from parsing a Makefile."""

    commands: tuple[ParsedCommand, ...]
    source_file: str = "Makefile"


# Regex: target name at column 0 followed by colon.
# Excludes lines starting with tab/space (recipe lines) and variable assignments.
_TARGET_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*", re.MULTILINE)

# Risk classification for well-known Makefile targets.
_TARGET_RISK_MAP: dict[str, RiskClass] = {
    "test": RiskClass.TEST_EXECUTION,
    "tests": RiskClass.TEST_EXECUTION,
    "check": RiskClass.SAFE_READONLY,
    "lint": RiskClass.SAFE_READONLY,
    "format": RiskClass.SAFE_MUTATING,
    "fmt": RiskClass.SAFE_MUTATING,
    "build": RiskClass.BUILD,
    "compile": RiskClass.BUILD,
    "all": RiskClass.BUILD,
    "install": RiskClass.SAFE_MUTATING,
    "clean": RiskClass.DESTRUCTIVE,
    "deploy": RiskClass.DESTRUCTIVE,
    "release": RiskClass.DESTRUCTIVE,
    "publish": RiskClass.DESTRUCTIVE,
}


def _classify_target_risk(name: str) -> RiskClass:
    """Classify a Makefile target's risk based on its name."""
    name_lower = name.lower()
    if name_lower in _TARGET_RISK_MAP:
        return _TARGET_RISK_MAP[name_lower]
    # Substring matching for compound names
    for keyword, risk in _TARGET_RISK_MAP.items():
        if keyword in name_lower:
            return risk
    return RiskClass.BUILD


def parse_makefile(repo_root: Path, relative_path: str = "Makefile") -> MakefileResult:
    """Parse a Makefile and extract targets with their first command lines.

    Uses regex-based extraction — does NOT resolve make variables, includes,
    or conditionals. Marks all commands at confidence 0.9.
    """
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        logger.warning("Makefile path validation failed", path=relative_path)
        return MakefileResult(commands=())

    if not file_path.is_file():
        return MakefileResult(commands=())

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read Makefile", error=str(exc))
        return MakefileResult(commands=())

    lines = content.split("\n")
    commands: list[ParsedCommand] = []
    seen_targets: set[str] = set()

    i = 0
    while i < len(lines):
        match = _TARGET_RE.match(lines[i])
        if match:
            target_name = match.group(1)
            # Skip .PHONY and duplicate targets
            if target_name.startswith(".") or target_name in seen_targets:
                i += 1
                continue
            seen_targets.add(target_name)

            # Collect recipe lines (lines starting with tab)
            recipe_lines: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("\t"):
                recipe_line = lines[j][1:].strip()  # Remove leading tab
                if recipe_line and not recipe_line.startswith("#"):
                    recipe_lines.append(recipe_line)
                j += 1

            command_text = f"make {target_name}"
            commands.append(
                ParsedCommand(
                    name=target_name,
                    command=command_text,
                    source_file=relative_path,
                    risk_class=_classify_target_risk(target_name),
                    confidence=0.9,
                )
            )
            i = j
        else:
            i += 1

    return MakefileResult(commands=tuple(commands), source_file=relative_path)
