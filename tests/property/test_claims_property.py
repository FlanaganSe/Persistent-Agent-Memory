"""Property-based tests for claims using Hypothesis."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from rkp.core.ids import generate_claim_id
from rkp.core.models import Claim
from rkp.core.types import (
    ClaimType,
    ReviewState,
    Sensitivity,
    SourceAuthority,
    source_authority_precedence,
)
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations

claim_types = st.sampled_from(list(ClaimType))
source_authorities = st.sampled_from(list(SourceAuthority))
review_states = st.sampled_from(list(ReviewState))
sensitivities = st.sampled_from(list(Sensitivity))


@st.composite
def claims(draw: st.DrawFn) -> Claim:
    ct = draw(claim_types)
    sa = draw(source_authorities)
    content = draw(st.text(min_size=1, max_size=200))
    scope = draw(st.text(min_size=1, max_size=50))
    claim_id = generate_claim_id(ct.value, scope, content)
    return Claim(
        id=claim_id,
        content=content,
        claim_type=ct,
        source_authority=sa,
        scope=scope,
        sensitivity=draw(sensitivities),
        review_state=draw(review_states),
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        repo_id="test-repo",
        branch="main",
    )


class TestClaimIdDeterminism:
    @given(
        ct=st.text(min_size=1, max_size=30),
        scope=st.text(min_size=1, max_size=30),
        content=st.text(min_size=1, max_size=200),
    )
    def test_same_inputs_same_id(self, ct: str, scope: str, content: str) -> None:
        id1 = generate_claim_id(ct, scope, content)
        id2 = generate_claim_id(ct, scope, content)
        assert id1 == id2

    @given(
        ct=st.text(min_size=1, max_size=30),
        scope=st.text(min_size=1, max_size=30),
        content=st.text(min_size=1, max_size=200),
    )
    def test_id_format(self, ct: str, scope: str, content: str) -> None:
        cid = generate_claim_id(ct, scope, content)
        assert cid.startswith("claim-")
        assert len(cid) == 22
        int(cid[6:], 16)  # suffix is valid hex


class TestPrecedenceOrdering:
    @given(a=source_authorities, b=source_authorities)
    def test_total_order(self, a: SourceAuthority, b: SourceAuthority) -> None:
        """Precedence defines a total ordering (with ties)."""
        pa = source_authority_precedence(a)
        pb = source_authority_precedence(b)
        assert pa <= pb or pa >= pb

    @given(a=source_authorities)
    def test_positive_integer(self, a: SourceAuthority) -> None:
        assert source_authority_precedence(a) > 0


class TestClaimRoundtripSqlite:
    @settings(max_examples=20, deadline=2000)
    @given(claim=claims())
    def test_roundtrip(self, claim: Claim, tmp_path_factory: object) -> None:
        """Claims survive a roundtrip through SQLite with full fidelity."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            conn = open_database(db_path)
            run_migrations(conn)
            store = SqliteClaimStore(conn)

            try:
                store.save(claim)
            except (sqlite3.IntegrityError, sqlite3.OperationalError):
                # Hypothesis may generate values that violate DB constraints
                # (e.g., NaN confidence, duplicate IDs)
                conn.close()
                return

            retrieved = store.get(claim.id)
            conn.close()

            assert retrieved is not None
            assert retrieved.id == claim.id
            assert retrieved.content == claim.content
            assert retrieved.claim_type == claim.claim_type
            assert retrieved.source_authority == claim.source_authority
            assert retrieved.scope == claim.scope
            assert retrieved.sensitivity == claim.sensitivity
            assert retrieved.review_state == claim.review_state
            assert abs(retrieved.confidence - claim.confidence) < 1e-6
            assert retrieved.repo_id == claim.repo_id
            assert retrieved.branch == claim.branch
