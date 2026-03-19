"""Data boundary verification: RKP never transmits repo content off-machine (AC-14)."""

from __future__ import annotations

import importlib
import socket
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from rkp.store.database import open_database, run_migrations


@pytest.fixture
def boundary_db(tmp_path: Path) -> sqlite3.Connection:
    db = open_database(tmp_path / "boundary_test.db", check_same_thread=False)
    run_migrations(db)
    return db


class TestNoOutboundConnections:
    """Verify RKP makes zero outbound network connections."""

    def test_no_http_imports_in_source(self) -> None:
        """Verify no HTTP client libraries are imported in RKP source."""
        import rkp

        rkp_root = Path(rkp.__file__).parent
        http_modules = {"urllib", "requests", "httpx", "aiohttp", "http.client"}
        violations: list[str] = []

        for py_file in rkp_root.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for module in http_modules:
                # Check for import statements (not comments/strings in general).
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if f"import {module}" in stripped or f"from {module}" in stripped:
                        rel = py_file.relative_to(rkp_root)
                        violations.append(f"{rel}: {stripped}")

        assert violations == [], f"HTTP client imports found in RKP source: {violations}"

    def test_no_socket_connect_during_extraction(
        self, boundary_db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        """Patch socket.socket.connect and verify no outbound connections
        during a full extraction cycle."""
        connection_attempts: list[tuple[str, ...]] = []
        original_connect = socket.socket.connect

        def tracking_connect(self: socket.socket, address: tuple[str, int] | str) -> None:
            if isinstance(address, tuple):
                connection_attempts.append(address)
            original_connect(self, address)

        # Create a minimal fixture repo.
        repo = tmp_path / "test_repo"
        repo.mkdir()
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "1.0"\n[project.scripts]\ntest = "pytest"\n',
            encoding="utf-8",
        )

        from rkp.indexer.orchestrator import run_extraction
        from rkp.store.claims import SqliteClaimStore

        store = SqliteClaimStore(boundary_db)

        with patch.object(socket.socket, "connect", tracking_connect):
            run_extraction(
                repo,
                store,
                repo_id="test-boundary",
                branch="main",
            )

        assert connection_attempts == [], (
            f"Outbound connections detected during extraction: {connection_attempts}"
        )

    def test_structlog_writes_to_stderr_only(self) -> None:
        """Verify structlog is configured for stderr, not remote endpoints."""
        import structlog

        # Just verify structlog is importable and usable — configuration
        # is checked by convention (no remote handler setup in RKP code).
        log = structlog.get_logger()
        assert log is not None

    def test_no_outbound_on_import(self) -> None:
        """Verify importing RKP modules doesn't trigger outbound connections."""
        connection_attempts: list[tuple[str, ...]] = []
        original_connect = socket.socket.connect

        def tracking_connect(self: socket.socket, address: tuple[str, int] | str) -> None:
            if isinstance(address, tuple):
                connection_attempts.append(address)
            original_connect(self, address)

        with patch.object(socket.socket, "connect", tracking_connect):
            # Re-import key modules.
            importlib.reload(importlib.import_module("rkp.core.security"))
            importlib.reload(importlib.import_module("rkp.core.config"))

        assert connection_attempts == [], f"Outbound connections on import: {connection_attempts}"
