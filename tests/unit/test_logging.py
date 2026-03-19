"""Logging configuration tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_structlog_writes_to_stderr() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import structlog; "
                "from rkp.core.logging import configure_logging; "
                "configure_logging(); "
                "structlog.get_logger().info('stderr-only-check')"
            ),
        ],
        capture_output=True,
        check=True,
        text=True,
        env=env,
    )

    assert result.stdout == ""
    assert "stderr-only-check" in result.stderr
