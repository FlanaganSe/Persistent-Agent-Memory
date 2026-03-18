"""Tests for the claim builder: construction, dedup, conflict detection."""

from __future__ import annotations

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, ReviewState, SourceAuthority


class TestClaimBuilderBuild:
    def test_generates_deterministic_id(self) -> None:
        builder = ClaimBuilder(repo_id="test-repo")
        c1 = builder.build(
            content="Use pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        )
        c2 = builder.build(
            content="Use pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        )
        assert c1.id == c2.id

    def test_sets_repo_id_and_branch(self) -> None:
        builder = ClaimBuilder(repo_id="my-repo", branch="dev")
        claim = builder.build(
            content="test",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        assert claim.repo_id == "my-repo"
        assert claim.branch == "dev"

    def test_defaults(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        claim = builder.build(
            content="x",
            claim_type=ClaimType.SCOPED_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
        )
        assert claim.review_state == ReviewState.UNREVIEWED
        assert claim.stale is False
        assert claim.created_at is not None
        assert claim.updated_at is not None
        assert claim.last_validated is not None

    def test_applicability_preserved(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        claim = builder.build(
            content="test",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            applicability=("test", "ci"),
        )
        assert claim.applicability == ("test", "ci")


class TestClaimBuilderDeduplicate:
    def test_no_duplicates(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        c1 = builder.build(
            content="a",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        c2 = builder.build(
            content="b",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        unique, dupes = builder.deduplicate([c1, c2], [])
        assert len(unique) == 2
        assert len(dupes) == 0

    def test_duplicate_against_existing(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        c1 = builder.build(
            content="same",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        c2 = builder.build(
            content="same",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        unique, dupes = builder.deduplicate([c2], [c1])
        assert len(unique) == 0
        assert len(dupes) == 1

    def test_duplicate_within_batch(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        c1 = builder.build(
            content="same",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        unique, dupes = builder.deduplicate([c1, c1], [])
        assert len(unique) == 1
        assert len(dupes) == 1


class TestClaimBuilderConflicts:
    def test_no_conflicts(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        c1 = builder.build(
            content="a",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            scope="src/",
        )
        c2 = builder.build(
            content="b",
            claim_type=ClaimType.SCOPED_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            scope="src/",
        )
        conflicts = builder.detect_conflicts([c1, c2])
        assert len(conflicts) == 0

    def test_detects_conflict(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        c1 = builder.build(
            content="use tabs",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            scope="**",
        )
        c2 = builder.build(
            content="use spaces",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
            scope="**",
        )
        conflicts = builder.detect_conflicts([c1, c2])
        assert len(conflicts) == 1
        assert conflicts[0].claim_a.content == "use tabs"
        assert conflicts[0].claim_b.content == "use spaces"

    def test_same_content_no_conflict(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        c1 = builder.build(
            content="use spaces",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            scope="**",
        )
        c2 = builder.build(
            content="use spaces",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_LOW,
            scope="**",
        )
        # Same content = same ID = deduplicate, not conflict
        conflicts = builder.detect_conflicts([c1, c2])
        assert len(conflicts) == 0


class TestClaimBuilderMerge:
    def test_merge_preserves_id(self) -> None:
        builder = ClaimBuilder(repo_id="r")
        existing = builder.build(
            content="old",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        update = builder.build(
            content="new",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        merged = builder.merge_claim(existing, update)
        assert merged.id == existing.id
        assert merged.content == "new"
        assert merged.stale is False
