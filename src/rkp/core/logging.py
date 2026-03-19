"""Logging configuration for CLI and MCP entrypoints.

RKP keeps diagnostics on stderr so stdout remains safe for MCP protocol
traffic and machine-readable CLI output.
"""

from __future__ import annotations

import logging
import os
import sys

import structlog

_configured = False


def configure_logging() -> None:
    """Configure structlog and stdlib logging for stderr-only output."""
    global _configured
    if _configured:
        return

    log_level = os.environ.get("RKP_LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level, logging.INFO),
        stream=sys.stderr,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    _configured = True
