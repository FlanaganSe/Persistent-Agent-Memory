"""Parse version files (.python-version, .nvmrc, .node-version, .tool-versions)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from rkp.core.security import validate_path

logger = structlog.get_logger()


@dataclass(frozen=True)
class RuntimeVersionHint:
    """A runtime version hint from a version file."""

    runtime: str
    version: str
    source_file: str


@dataclass(frozen=True)
class VersionFilesResult:
    """Structured output from parsing version files."""

    hints: tuple[RuntimeVersionHint, ...]


# .tool-versions runtime name mapping.
_TOOL_VERSIONS_MAP: dict[str, str] = {
    "python": "Python",
    "nodejs": "Node.js",
    "node": "Node.js",
    "ruby": "Ruby",
    "golang": "Go",
    "java": "Java",
    "rust": "Rust",
    "erlang": "Erlang",
    "elixir": "Elixir",
}


def _parse_single_version_file(
    repo_root: Path,
    relative_path: str,
    runtime: str,
) -> RuntimeVersionHint | None:
    """Parse a single-value version file."""
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        return None

    if not file_path.is_file():
        return None

    try:
        content = file_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None

    if not content:
        return None

    # Take first non-empty, non-comment line
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            return RuntimeVersionHint(
                runtime=runtime,
                version=line,
                source_file=relative_path,
            )

    return None


def _parse_tool_versions(repo_root: Path) -> list[RuntimeVersionHint]:
    """Parse .tool-versions (asdf format: runtime version)."""
    relative_path = ".tool-versions"
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        return []

    if not file_path.is_file():
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return []

    hints: list[RuntimeVersionHint] = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            tool_name = parts[0].lower()
            version = parts[1]
            runtime = _TOOL_VERSIONS_MAP.get(tool_name, tool_name)
            hints.append(
                RuntimeVersionHint(
                    runtime=runtime,
                    version=version,
                    source_file=relative_path,
                )
            )

    return hints


def parse_version_files(repo_root: Path) -> VersionFilesResult:
    """Parse all version files in the repo root.

    Checks: .python-version, .nvmrc, .node-version, .tool-versions.
    Returns empty result if no version files are found.
    """
    hints: list[RuntimeVersionHint] = []

    # Single-value version files
    single_files = [
        (".python-version", "Python"),
        (".nvmrc", "Node.js"),
        (".node-version", "Node.js"),
    ]

    for relative_path, runtime in single_files:
        hint = _parse_single_version_file(repo_root, relative_path, runtime)
        if hint is not None:
            hints.append(hint)

    # .tool-versions (multi-value)
    hints.extend(_parse_tool_versions(repo_root))

    return VersionFilesResult(hints=tuple(hints))
