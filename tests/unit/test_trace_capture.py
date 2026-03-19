"""Unit tests for trace capture."""

from __future__ import annotations

import json
import time
from pathlib import Path

from rkp.server.trace import TraceLogger, _sanitize_arguments, create_trace_logger


class TestTraceLogger:
    def test_log_call_writes_jsonl(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "traces.jsonl"
        logger = TraceLogger(
            trace_path, enabled=True, session_id="test-session", repo_id="test-repo"
        )

        entry = logger.log_call(
            tool_name="get_conventions",
            arguments={"path_or_symbol": "**"},
            response_status="ok",
            response_claim_count=5,
            response_size_bytes=1024,
            duration_ms=12.5,
        )

        assert entry is not None
        assert entry.tool_name == "get_conventions"
        assert entry.response_claim_count == 5
        assert entry.session_id == "test-session"

        # Verify file contents
        content = trace_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        assert parsed["tool_name"] == "get_conventions"
        assert parsed["response_status"] == "ok"
        assert parsed["duration_ms"] == 12.5

    def test_required_fields(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "traces.jsonl"
        logger = TraceLogger(trace_path, enabled=True)

        entry = logger.log_call(
            tool_name="get_repo_overview",
            arguments={},
            response_status="ok",
            response_claim_count=0,
            response_size_bytes=256,
            duration_ms=5.0,
        )

        assert entry is not None
        parsed = json.loads(trace_path.read_text().strip())
        required_fields = {
            "timestamp",
            "tool_name",
            "arguments",
            "response_status",
            "response_claim_count",
            "response_size_bytes",
            "duration_ms",
            "session_id",
            "repo_id",
        }
        assert required_fields.issubset(parsed.keys())

    def test_disabled_no_file(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "traces.jsonl"
        logger = TraceLogger(trace_path, enabled=False)

        entry = logger.log_call(
            tool_name="get_conventions",
            arguments={},
            response_status="ok",
            response_claim_count=0,
            response_size_bytes=0,
            duration_ms=1.0,
        )

        assert entry is None
        assert not trace_path.exists()

    def test_append_only(self, tmp_path: Path) -> None:
        trace_path = tmp_path / "traces.jsonl"
        logger = TraceLogger(trace_path, enabled=True)

        logger.log_call("tool_a", {}, "ok", 1, 100, 5.0)
        logger.log_call("tool_b", {}, "ok", 2, 200, 10.0)
        logger.log_call("tool_c", {}, "error", 0, 50, 3.0)

        lines = trace_path.read_text().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["tool_name"] == "tool_a"
        assert json.loads(lines[1])["tool_name"] == "tool_b"
        assert json.loads(lines[2])["tool_name"] == "tool_c"

    def test_duration_accuracy(self, tmp_path: Path) -> None:
        """Duration measurement should be within reasonable tolerance."""
        trace_path = tmp_path / "traces.jsonl"
        logger = TraceLogger(trace_path, enabled=True)

        start = time.perf_counter()
        # Simulate a fast operation
        duration_ms = (time.perf_counter() - start) * 1000

        entry = logger.log_call(
            tool_name="fast_tool",
            arguments={},
            response_status="ok",
            response_claim_count=0,
            response_size_bytes=0,
            duration_ms=duration_ms,
        )

        assert entry is not None
        # Duration should be very small (near 0) for a no-op
        assert entry.duration_ms < 100


class TestSanitization:
    def test_secret_redaction(self) -> None:
        args = {"query": "AKIAIOSFODNN7EXAMPLE"}
        sanitized = _sanitize_arguments(args)
        assert "AKIAIOSFODNN7EXAMPLE" not in str(sanitized)

    def test_long_value_truncation(self) -> None:
        args = {"content": "x" * 500}
        sanitized = _sanitize_arguments(args)
        value = str(sanitized["content"])
        assert len(value) < 500
        assert "500 chars" in value

    def test_list_shape(self) -> None:
        args = {"items": [1, 2, 3, 4, 5]}
        sanitized = _sanitize_arguments(args)
        assert sanitized["items"] == "[list of 5 items]"

    def test_dict_shape(self) -> None:
        args = {"data": {"a": 1, "b": 2}}
        sanitized = _sanitize_arguments(args)
        assert sanitized["data"] == "{dict with 2 keys}"


class TestCreateTraceLogger:
    def test_default_path(self, tmp_path: Path) -> None:
        logger = create_trace_logger(tmp_path)
        assert logger.enabled is True
        assert logger.session_id  # auto-generated

    def test_disabled(self, tmp_path: Path) -> None:
        logger = create_trace_logger(tmp_path, enabled=False)
        assert logger.enabled is False
