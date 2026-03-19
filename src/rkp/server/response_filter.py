"""MCP response filter — scan outgoing data for injection markers before serving."""

from __future__ import annotations

from typing import Any

import structlog

from rkp.core.security import Severity, scan_for_injection

logger = structlog.get_logger()

# Recursive JSON-like type (approximation for pyright strict).
JsonValue = str | int | float | bool | None | dict[str, Any] | list[Any]


def filter_response(
    response_data: dict[str, Any],
    warnings: list[str],
) -> tuple[dict[str, Any], list[str]]:
    """Scan MCP response data for injection markers before sending.

    Returns (unchanged_data, updated_warnings).
    - Scans every string value in the response dict recursively.
    - If found: keeps the content but adds warnings.
    - Never modifies response structure (that would break tool contracts).
    """
    found_markers: list[tuple[str, str]] = []
    _scan_value(response_data, found_markers, path="")

    updated_warnings = list(warnings)
    for path_key, marker in found_markers:
        msg = f"Response contains potential injection marker ({marker}) at {path_key}"
        updated_warnings.append(msg)
        logger.warning(
            "Injection marker in MCP response",
            path=path_key,
            marker=marker,
        )

    return response_data, updated_warnings


def _scan_value(
    obj: JsonValue,
    found: list[tuple[str, str]],
    path: str,
) -> None:
    """Recursively scan all string values in a nested structure."""
    if isinstance(obj, str):
        findings = scan_for_injection(obj)
        found.extend(
            (path, finding.marker)
            for finding in findings
            if finding.severity in (Severity.HIGH, Severity.MEDIUM)
        )
    elif isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else key
            _scan_value(value, found, path=child_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _scan_value(item, found, path=f"{path}[{i}]")
