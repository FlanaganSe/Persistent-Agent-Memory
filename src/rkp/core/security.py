"""Security utilities: safe YAML, path traversal prevention, injection detection."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from rkp.core.errors import InjectionDetectedError, PathTraversalError, UnsafeYamlError

# Injection markers that indicate prompt injection attempts.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\bSystem:\s", re.IGNORECASE),
    re.compile(r"\brole:\s*(system|assistant|user)\b", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"```\s*system\b", re.IGNORECASE),
)


def safe_yaml_load(content: object) -> Any:
    """Load YAML content safely using yaml.safe_load().

    Never uses yaml.load() which can execute arbitrary Python code.
    Accepts object to enforce string type at runtime (security boundary).
    """
    if not isinstance(content, str):
        msg = "YAML content must be a string"
        raise UnsafeYamlError(msg)
    return yaml.safe_load(content)


def validate_path(path: Path, repo_root: Path) -> Path:
    """Validate that a path is contained within the repo root.

    Resolves symlinks and verifies the resolved path starts with the
    resolved repo root. Rejects paths containing null bytes.
    """
    path_str = str(path)
    if "\x00" in path_str:
        raise PathTraversalError(path_str, str(repo_root))

    resolved_root = repo_root.resolve()
    resolved_path = (repo_root / path).resolve()

    if not resolved_path.is_relative_to(resolved_root):
        raise PathTraversalError(str(path), str(repo_root))

    return resolved_path


def detect_injection_markers(content: str) -> list[str]:
    """Scan content for prompt injection markers.

    Returns a list of matched marker descriptions. Empty list means clean.
    """
    found: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(content)
        if match:
            found.append(match.group(0))
    return found


def require_no_injection(content: str) -> None:
    """Raise InjectionDetectedError if injection markers are found."""
    markers = detect_injection_markers(content)
    if markers:
        raise InjectionDetectedError(markers)
