"""MCP trace capture — log queries, responses, timestamps for evaluation."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from rkp.core.security import redact_secrets, scan_for_secrets

logger = structlog.get_logger()


@dataclass(frozen=True)
class TraceEntry:
    """A single MCP tool call trace record."""

    timestamp: str
    tool_name: str
    arguments: dict[str, object]
    response_status: str
    response_claim_count: int
    response_size_bytes: int
    duration_ms: float
    session_id: str
    repo_id: str


class TraceLogger:
    """Append-only trace logger for MCP tool calls.

    Writes JSONL to .rkp/local/traces.jsonl. File-append is O(1).
    """

    def __init__(
        self,
        trace_path: Path,
        *,
        enabled: bool = True,
        session_id: str = "",
        repo_id: str = "",
    ) -> None:
        self._trace_path = trace_path
        self._enabled = enabled
        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._repo_id = repo_id

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def session_id(self) -> str:
        return self._session_id

    def log_call(
        self,
        tool_name: str,
        arguments: dict[str, object],
        response_status: str,
        response_claim_count: int,
        response_size_bytes: int,
        duration_ms: float,
    ) -> TraceEntry | None:
        """Log a tool call to the trace file.

        Returns the TraceEntry if written, None if tracing is disabled.
        """
        if not self._enabled:
            return None

        # Sanitize arguments: redact secrets and remove local-only content
        sanitized_args = _sanitize_arguments(arguments)

        entry = TraceEntry(
            timestamp=datetime.now(UTC).isoformat(),
            tool_name=tool_name,
            arguments=sanitized_args,
            response_status=response_status,
            response_claim_count=response_claim_count,
            response_size_bytes=response_size_bytes,
            duration_ms=round(duration_ms, 3),
            session_id=self._session_id,
            repo_id=self._repo_id,
        )

        self._append(entry)
        return entry

    def _append(self, entry: TraceEntry) -> None:
        """Append a trace entry to the JSONL file."""
        self._trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self._trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")


def _sanitize_arguments(args: dict[str, object]) -> dict[str, object]:
    """Sanitize tool call arguments for tracing.

    - Redact values that look like secrets
    - Strip local-only content markers
    - Log argument shapes, not full bodies
    """
    sanitized: dict[str, object] = {}
    for key, value in args.items():
        sanitized_val: object = value
        if isinstance(value, str):
            # Redact secrets
            secret_findings = scan_for_secrets(value)
            clean_value = redact_secrets(value, secret_findings) if secret_findings else value
            # Truncate long values to shapes
            if len(clean_value) > 200:
                sanitized_val = f"{clean_value[:100]}... ({len(clean_value)} chars)"
            else:
                sanitized_val = clean_value
        elif isinstance(value, list):
            typed_list: list[Any] = value  # type: ignore[assignment]
            sanitized_val = f"[list of {len(typed_list)} items]"
        elif isinstance(value, tuple):
            typed_tuple: tuple[Any, ...] = value  # type: ignore[assignment]
            sanitized_val = f"[list of {len(typed_tuple)} items]"
        elif isinstance(value, dict):
            typed_dict: dict[str, Any] = dict(value)  # type: ignore[arg-type]
            sanitized_val = f"{{dict with {len(typed_dict)} keys}}"
        sanitized[key] = sanitized_val
    return sanitized


def create_trace_logger(
    repo_root: Path,
    *,
    enabled: bool = True,
    repo_id: str = "",
) -> TraceLogger:
    """Create a TraceLogger for the given repo."""
    trace_path = repo_root / ".rkp" / "local" / "traces.jsonl"
    return TraceLogger(
        trace_path,
        enabled=enabled,
        repo_id=repo_id,
    )
