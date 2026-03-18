"""Shared test fixtures."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Claim
from rkp.core.types import ClaimType, SourceAuthority
from rkp.store.database import open_database, run_migrations


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def db(tmp_db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = open_database(tmp_db_path)
    run_migrations(conn)
    yield conn
    conn.close()


@pytest.fixture
def builder() -> ClaimBuilder:
    return ClaimBuilder(repo_id="test-repo", branch="main")


@pytest.fixture
def sample_claim(builder: ClaimBuilder) -> Claim:
    return builder.build(
        content="Use pytest for all tests",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        scope="**",
        applicability=("test",),
        confidence=0.95,
        evidence=("pyproject.toml",),
    )
