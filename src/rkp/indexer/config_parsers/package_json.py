"""Parse package.json for commands and metadata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import structlog

from rkp.core.security import validate_path
from rkp.core.types import RiskClass
from rkp.indexer.extractors.commands import ParsedCommand

logger = structlog.get_logger()


@dataclass(frozen=True)
class PackageJsonResult:
    """Structured output from parsing package.json."""

    commands: tuple[ParsedCommand, ...]
    project_name: str | None = None
    engines: dict[str, str] | None = None
    source_file: str = "package.json"


_SCRIPT_RISK_MAP: dict[str, RiskClass] = {
    "test": RiskClass.TEST_EXECUTION,
    "spec": RiskClass.TEST_EXECUTION,
    "e2e": RiskClass.TEST_EXECUTION,
    "lint": RiskClass.SAFE_READONLY,
    "check": RiskClass.SAFE_READONLY,
    "typecheck": RiskClass.SAFE_READONLY,
    "type-check": RiskClass.SAFE_READONLY,
    "format": RiskClass.SAFE_MUTATING,
    "fmt": RiskClass.SAFE_MUTATING,
    "prettier": RiskClass.SAFE_MUTATING,
    "build": RiskClass.BUILD,
    "compile": RiskClass.BUILD,
    "start": RiskClass.BUILD,
    "dev": RiskClass.BUILD,
    "serve": RiskClass.BUILD,
    "deploy": RiskClass.DESTRUCTIVE,
    "publish": RiskClass.DESTRUCTIVE,
    "clean": RiskClass.DESTRUCTIVE,
    "reset": RiskClass.DESTRUCTIVE,
}


def _classify_risk(name: str) -> RiskClass:
    """Classify a script's risk based on its name.

    Uses word-boundary matching: splits on common separators (-, _, :, .)
    and checks if any word matches a known keyword exactly.
    Falls back to substring for compound words.
    """
    name_lower = name.lower()
    words = set(re.split(r"[-_:.\s]+", name_lower))
    # Check exact word matches first (higher precision)
    for keyword, risk in _SCRIPT_RISK_MAP.items():
        if keyword in words:
            return risk
    # Fallback: substring match for compound words like "typecheck"
    for keyword, risk in _SCRIPT_RISK_MAP.items():
        if keyword in name_lower:
            return risk
    return RiskClass.BUILD


def _as_dict(val: object) -> dict[str, Any] | None:
    """Safely cast a value to dict[str, Any] if it is a dict."""
    if isinstance(val, dict):
        return cast(dict[str, Any], val)
    return None


def parse_package_json(repo_root: Path, relative_path: str = "package.json") -> PackageJsonResult:
    """Parse a package.json and extract scripts and metadata.

    Returns an empty result if the file is missing or malformed.
    """
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        logger.warning("package.json path validation failed", path=relative_path)
        return PackageJsonResult(commands=())

    if not file_path.is_file():
        return PackageJsonResult(commands=())

    try:
        raw = file_path.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        logger.warning("Failed to parse package.json", error=str(exc))
        return PackageJsonResult(commands=())

    if not data:
        return PackageJsonResult(commands=())

    commands: list[ParsedCommand] = []
    scripts = _as_dict(data.get("scripts"))
    if scripts is not None:
        for name, cmd in scripts.items():
            if isinstance(cmd, str):
                commands.append(
                    ParsedCommand(
                        name=str(name),
                        command=cmd,
                        source_file=relative_path,
                        risk_class=_classify_risk(str(name)),
                    )
                )

    project_name: str | None = None
    raw_name = data.get("name")
    if isinstance(raw_name, str):
        project_name = raw_name

    engines: dict[str, str] | None = None
    raw_engines = _as_dict(data.get("engines"))
    if raw_engines is not None:
        engines = {str(k): str(v) for k, v in raw_engines.items() if isinstance(v, str)}

    return PackageJsonResult(
        commands=tuple(commands),
        project_name=project_name,
        engines=engines,
        source_file=relative_path,
    )
