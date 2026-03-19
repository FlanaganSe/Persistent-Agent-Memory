"""Parse pyproject.toml for commands and tool configuration."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import structlog

from rkp.core.security import validate_path
from rkp.core.types import RiskClass
from rkp.indexer.extractors.commands import ParsedCommand

logger = structlog.get_logger()


@dataclass(frozen=True)
class PyprojectResult:
    """Structured output from parsing pyproject.toml."""

    commands: tuple[ParsedCommand, ...]
    python_requires: str | None = None
    project_name: str | None = None
    tools_detected: tuple[str, ...] = ()
    source_file: str = "pyproject.toml"


_TOOL_RISK_MAP: dict[str, RiskClass] = {
    "test": RiskClass.TEST_EXECUTION,
    "pytest": RiskClass.TEST_EXECUTION,
    "check": RiskClass.SAFE_READONLY,
    "lint": RiskClass.SAFE_READONLY,
    "ruff": RiskClass.SAFE_READONLY,
    "mypy": RiskClass.SAFE_READONLY,
    "pyright": RiskClass.SAFE_READONLY,
    "typecheck": RiskClass.SAFE_READONLY,
    "format": RiskClass.SAFE_MUTATING,
    "fmt": RiskClass.SAFE_MUTATING,
    "build": RiskClass.BUILD,
    "compile": RiskClass.BUILD,
    "deploy": RiskClass.DESTRUCTIVE,
    "publish": RiskClass.DESTRUCTIVE,
    "clean": RiskClass.DESTRUCTIVE,
}


def _classify_risk(name: str) -> RiskClass:
    """Classify a command's risk based on its name.

    Uses word-boundary matching: splits on common separators (-, _, :, .)
    and checks if any word matches a known keyword exactly.
    Falls back to substring for single-word names.
    """
    name_lower = name.lower()
    words = set(re.split(r"[-_:.\s]+", name_lower))
    # Check exact word matches first (higher precision)
    for keyword, risk in _TOOL_RISK_MAP.items():
        if keyword in words:
            return risk
    # Fallback: substring match for compound words like "typecheck"
    for keyword, risk in _TOOL_RISK_MAP.items():
        if keyword in name_lower:
            return risk
    return RiskClass.BUILD


def _as_dict(val: object) -> dict[str, Any] | None:
    """Safely cast a value to dict[str, Any] if it is a dict."""
    if isinstance(val, dict):
        return cast(dict[str, Any], val)
    return None


def _extract_project_scripts(data: dict[str, Any]) -> list[ParsedCommand]:
    """Extract commands from [project.scripts]."""
    project = _as_dict(data.get("project"))
    if project is None:
        return []
    scripts = _as_dict(project.get("scripts"))
    if scripts is None:
        return []
    commands: list[ParsedCommand] = []
    for name, entry_point in scripts.items():
        if isinstance(entry_point, str):
            commands.append(
                ParsedCommand(
                    name=name,
                    command=entry_point,
                    source_file="pyproject.toml",
                    risk_class=_classify_risk(name),
                )
            )
    return commands


def _extract_tool_scripts(data: dict[str, Any]) -> list[ParsedCommand]:
    """Extract commands from [tool.hatch.envs.*.scripts] and [tool.nox]."""
    tool = _as_dict(data.get("tool"))
    if tool is None:
        return []
    commands: list[ParsedCommand] = []
    # hatch environment scripts
    hatch = _as_dict(tool.get("hatch"))
    if hatch is not None:
        envs = _as_dict(hatch.get("envs"))
        if envs is not None:
            for env_name, env_config_raw in envs.items():
                env_config = _as_dict(env_config_raw)
                if env_config is not None:
                    scripts = _as_dict(env_config.get("scripts"))
                    if scripts is not None:
                        for sname, cmd in scripts.items():
                            if isinstance(cmd, str):
                                commands.append(
                                    ParsedCommand(
                                        name=f"hatch:{env_name}:{sname}",
                                        command=cmd,
                                        source_file="pyproject.toml",
                                        risk_class=_classify_risk(sname),
                                    )
                                )
    # pytest configuration implies a test command
    pytest_cfg = _as_dict(tool.get("pytest"))
    if pytest_cfg is not None:
        commands.append(
            ParsedCommand(
                name="pytest",
                command="pytest",
                source_file="pyproject.toml",
                risk_class=RiskClass.TEST_EXECUTION,
                confidence=0.9,
            )
        )
    return commands


def _detect_tools(data: dict[str, Any]) -> list[str]:
    """Detect which tools are configured in [tool.*]."""
    tool = _as_dict(data.get("tool"))
    if tool is None:
        return []
    known_tools = (
        "ruff",
        "pytest",
        "mypy",
        "pyright",
        "black",
        "isort",
        "coverage",
        "hatch",
        "bandit",
        "safety",
        "semgrep",
    )
    return [t for t in known_tools if t in tool]


def parse_pyproject(repo_root: Path, relative_path: str = "pyproject.toml") -> PyprojectResult:
    """Parse a pyproject.toml and extract commands and metadata.

    Returns an empty result if the file is missing or malformed.
    """
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        logger.warning("pyproject.toml path validation failed", path=relative_path)
        return PyprojectResult(commands=())

    if not file_path.is_file():
        return PyprojectResult(commands=())

    try:
        raw = file_path.read_bytes()
        data: dict[str, Any] = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError, OSError) as exc:
        logger.warning("Failed to parse pyproject.toml", error=str(exc))
        return PyprojectResult(commands=())

    commands = _extract_project_scripts(data) + _extract_tool_scripts(data)
    tools = _detect_tools(data)

    project = _as_dict(data.get("project"))
    python_requires: str | None = None
    project_name: str | None = None
    if project is not None:
        pr = project.get("requires-python")
        if isinstance(pr, str):
            python_requires = pr
        pn = project.get("name")
        if isinstance(pn, str):
            project_name = pn

    return PyprojectResult(
        commands=tuple(commands),
        python_requires=python_requires,
        project_name=project_name,
        tools_detected=tuple(tools),
        source_file=relative_path,
    )
