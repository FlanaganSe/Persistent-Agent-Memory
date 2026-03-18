"""Tests for the SQLite claim store: CRUD, filtering, precedence ordering."""

from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.errors import ClaimNotFoundError, DuplicateClaimError
from rkp.core.models import Claim
from rkp.core.types import ClaimType, ReviewState, SourceAuthority
from rkp.store.claims import SqliteClaimStore


@pytest.fixture
def store(db: sqlite3.Connection) -> SqliteClaimStore:
    return SqliteClaimStore(db)


@pytest.fixture
def builder() -> ClaimBuilder:
    return ClaimBuilder(repo_id="test-repo", branch="main")


class TestSave:
    def test_save_and_retrieve(self, store: SqliteClaimStore, sample_claim: Claim) -> None:
        store.save(sample_claim)
        retrieved = store.get(sample_claim.id)
        assert retrieved is not None
        assert retrieved.id == sample_claim.id
        assert retrieved.content == sample_claim.content
        assert retrieved.claim_type == sample_claim.claim_type
        assert retrieved.source_authority == sample_claim.source_authority

    def test_save_duplicate_raises(self, store: SqliteClaimStore, sample_claim: Claim) -> None:
        store.save(sample_claim)
        with pytest.raises(DuplicateClaimError):
            store.save(sample_claim)

    def test_roundtrip_preserves_fields(
        self, store: SqliteClaimStore, sample_claim: Claim
    ) -> None:
        store.save(sample_claim)
        retrieved = store.get(sample_claim.id)
        assert retrieved is not None
        assert retrieved.scope == sample_claim.scope
        assert retrieved.applicability == sample_claim.applicability
        assert retrieved.sensitivity == sample_claim.sensitivity
        assert retrieved.review_state == sample_claim.review_state
        assert retrieved.confidence == sample_claim.confidence
        assert retrieved.evidence == sample_claim.evidence
        assert retrieved.repo_id == sample_claim.repo_id
        assert retrieved.branch == sample_claim.branch


class TestGet:
    def test_get_nonexistent(self, store: SqliteClaimStore) -> None:
        assert store.get("nonexistent") is None


class TestListClaims:
    def test_list_all(self, store: SqliteClaimStore, builder: ClaimBuilder) -> None:
        c1 = builder.build(
            content="a",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        c2 = builder.build(
            content="b",
            claim_type=ClaimType.SCOPED_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
        )
        store.save(c1)
        store.save(c2)
        claims = store.list_claims()
        assert len(claims) == 2

    def test_filter_by_type(self, store: SqliteClaimStore, builder: ClaimBuilder) -> None:
        c1 = builder.build(
            content="a",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        c2 = builder.build(
            content="b",
            claim_type=ClaimType.SCOPED_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
        )
        store.save(c1)
        store.save(c2)
        claims = store.list_claims(claim_type=ClaimType.ALWAYS_ON_RULE)
        assert len(claims) == 1
        assert claims[0].claim_type == ClaimType.ALWAYS_ON_RULE

    def test_filter_by_scope(self, store: SqliteClaimStore, builder: ClaimBuilder) -> None:
        c1 = builder.build(
            content="a",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            scope="**",
        )
        c2 = builder.build(
            content="b",
            claim_type=ClaimType.SCOPED_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
            scope="src/",
        )
        store.save(c1)
        store.save(c2)
        claims = store.list_claims(scope="src/")
        assert len(claims) == 1

    def test_filter_by_review_state(self, store: SqliteClaimStore, builder: ClaimBuilder) -> None:
        c1 = builder.build(
            content="a",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        store.save(c1)
        claims = store.list_claims(review_state=ReviewState.UNREVIEWED)
        assert len(claims) == 1
        claims = store.list_claims(review_state=ReviewState.APPROVED)
        assert len(claims) == 0


class TestDelete:
    def test_delete(self, store: SqliteClaimStore, sample_claim: Claim) -> None:
        store.save(sample_claim)
        store.delete(sample_claim.id)
        assert store.get(sample_claim.id) is None

    def test_delete_nonexistent(self, store: SqliteClaimStore) -> None:
        with pytest.raises(ClaimNotFoundError):
            store.delete("nonexistent")


class TestUpdate:
    def test_update(self, store: SqliteClaimStore, sample_claim: Claim) -> None:
        store.save(sample_claim)
        updated = replace(sample_claim, content="Updated content")
        store.update(updated)
        retrieved = store.get(sample_claim.id)
        assert retrieved is not None
        assert retrieved.content == "Updated content"

    def test_update_nonexistent(self, store: SqliteClaimStore, sample_claim: Claim) -> None:
        with pytest.raises(ClaimNotFoundError):
            store.update(sample_claim)


class TestGetByPrecedence:
    def test_ordered_by_authority(self, store: SqliteClaimStore, builder: ClaimBuilder) -> None:
        c_low = builder.build(
            content="low",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
        )
        c_high = builder.build(
            content="high",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.HUMAN_OVERRIDE,
        )
        c_mid = builder.build(
            content="mid",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        )
        store.save(c_low)
        store.save(c_high)
        store.save(c_mid)
        ordered = store.get_by_precedence()
        assert ordered[0].source_authority == SourceAuthority.HUMAN_OVERRIDE
        assert ordered[-1].source_authority == SourceAuthority.INFERRED_LOW

    def test_imported_unreviewed_below_executable_config(
        self, store: SqliteClaimStore, builder: ClaimBuilder
    ) -> None:
        c_exec = builder.build(
            content="exec",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        )
        c_imported = builder.build(
            content="imported",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.DECLARED_IMPORTED_UNREVIEWED,
        )
        store.save(c_exec)
        store.save(c_imported)
        ordered = store.get_by_precedence()
        exec_idx = next(i for i, c in enumerate(ordered) if c.content == "exec")
        imported_idx = next(i for i, c in enumerate(ordered) if c.content == "imported")
        assert exec_idx < imported_idx  # exec comes first (higher authority)
