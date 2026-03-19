"""Tests for the override persistence module."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.ids import generate_claim_id
from rkp.core.models import Claim
from rkp.core.types import ClaimType, ReviewState, Sensitivity, SourceAuthority
from rkp.store.claims import SqliteClaimStore
from rkp.store.history import SqliteHistoryStore
from rkp.store.overrides import (
    FileSystemOverrideStore,
    Override,
    _deserialize_override,  # pyright: ignore[reportPrivateUsage]
    _override_filename,  # pyright: ignore[reportPrivateUsage]
    _serialize_override,  # pyright: ignore[reportPrivateUsage]
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_TS_LATER = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)


def _make_claim_store(db: sqlite3.Connection) -> SqliteClaimStore:
    return SqliteClaimStore(db)


def _make_history_store(db: sqlite3.Connection) -> SqliteHistoryStore:
    return SqliteHistoryStore(db)


def _save_claim(db: sqlite3.Connection, builder: ClaimBuilder, **kwargs: object) -> Claim:
    """Build a claim with defaults and persist it."""
    defaults: dict[str, object] = {
        "content": "Always run tests before merging",
        "claim_type": ClaimType.ALWAYS_ON_RULE,
        "source_authority": SourceAuthority.EXECUTABLE_CONFIG,
        "scope": "**",
        "applicability": ("ci",),
        "confidence": 0.9,
        "evidence": ("pyproject.toml",),
    }
    defaults.update(kwargs)
    claim = builder.build(**defaults)  # type: ignore[arg-type]
    _make_claim_store(db).save(claim)
    return claim


# ---------------------------------------------------------------------------
# Serialization round-trips
# ---------------------------------------------------------------------------


class TestSerializeDeserialize:
    def test_serialize_deserialize_approved(self) -> None:
        override = Override(
            claim_id="claim-abc123",
            action="approved",
            timestamp=_TS,
            actor="reviewer@example.com",
        )
        yaml_text = _serialize_override(override)
        result = _deserialize_override(yaml_text)
        assert result.claim_id == override.claim_id
        assert result.action == "approved"
        assert result.timestamp == _TS
        assert result.actor == "reviewer@example.com"

    def test_serialize_deserialize_edited(self) -> None:
        override = Override(
            claim_id="claim-def456",
            action="edited",
            timestamp=_TS,
            actor="editor@example.com",
            original_content="old rule",
            edited_content="new improved rule",
        )
        yaml_text = _serialize_override(override)
        result = _deserialize_override(yaml_text)
        assert result.claim_id == override.claim_id
        assert result.action == "edited"
        assert result.original_content == "old rule"
        assert result.edited_content == "new improved rule"
        assert result.timestamp == _TS

    def test_serialize_deserialize_declared(self) -> None:
        override = Override(
            claim_id="claim-ghi789",
            action="declared",
            timestamp=_TS,
            actor="human",
            content="Never push to main directly",
            claim_type=ClaimType.ALWAYS_ON_RULE.value,
            scope="src/**",
            applicability=("python", "ci"),
        )
        yaml_text = _serialize_override(override)
        result = _deserialize_override(yaml_text)
        assert result.claim_id == override.claim_id
        assert result.action == "declared"
        assert result.content == "Never push to main directly"
        assert result.claim_type == ClaimType.ALWAYS_ON_RULE.value
        assert result.scope == "src/**"
        assert result.applicability == ("python", "ci")

    def test_serialize_deserialize_tombstoned(self) -> None:
        override = Override(
            claim_id="claim-jkl012",
            action="tombstoned",
            timestamp=_TS,
            actor="admin@example.com",
            reason="Obsolete after migration to monorepo",
        )
        yaml_text = _serialize_override(override)
        result = _deserialize_override(yaml_text)
        assert result.claim_id == override.claim_id
        assert result.action == "tombstoned"
        assert result.reason == "Obsolete after migration to monorepo"
        assert result.timestamp == _TS


# ---------------------------------------------------------------------------
# Filename generation
# ---------------------------------------------------------------------------


class TestOverrideFilename:
    def test_override_filename(self) -> None:
        override = Override(
            claim_id="claim-abc123",
            action="approved",
            timestamp=_TS,
        )
        assert _override_filename(override) == "claim-abc123_approved.yaml"


# ---------------------------------------------------------------------------
# FileSystemOverrideStore: save / load / delete
# ---------------------------------------------------------------------------


class TestSaveLoadDelete:
    def test_save_override_creates_file(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        sample_claim: Claim,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim_store = _make_claim_store(db)
        claim_store.save(sample_claim)
        store = FileSystemOverrideStore(overrides_dir, claim_store=claim_store)

        override = Override(
            claim_id=sample_claim.id,
            action="approved",
            timestamp=_TS,
            actor="human",
        )
        store.save_override(override)

        expected_file = overrides_dir / f"{sample_claim.id}_approved.yaml"
        assert expected_file.exists()
        content = expected_file.read_text(encoding="utf-8")
        assert sample_claim.id in content
        assert "approved" in content

    def test_load_overrides_empty(self, tmp_path: Path) -> None:
        overrides_dir = tmp_path / "overrides"
        store = FileSystemOverrideStore(overrides_dir)
        assert store.load_overrides() == []

    def test_load_overrides_round_trip(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        sample_claim: Claim,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim_store = _make_claim_store(db)
        claim_store.save(sample_claim)
        store = FileSystemOverrideStore(overrides_dir, claim_store=claim_store)

        override_early = Override(
            claim_id=sample_claim.id,
            action="approved",
            timestamp=_TS,
            actor="human",
        )
        override_late = Override(
            claim_id=sample_claim.id,
            action="edited",
            timestamp=_TS_LATER,
            actor="editor",
            original_content=sample_claim.content,
            edited_content="Updated rule",
        )
        store.save_override(override_early)
        store.save_override(override_late)

        loaded = store.load_overrides()
        assert len(loaded) == 2
        # Sorted by timestamp: early first.
        assert loaded[0].timestamp == _TS
        assert loaded[1].timestamp == _TS_LATER
        assert loaded[0].action == "approved"
        assert loaded[1].action == "edited"

    def test_delete_override(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(db, builder)
        claim_store = _make_claim_store(db)
        store = FileSystemOverrideStore(overrides_dir, claim_store=claim_store)

        override = Override(
            claim_id=claim.id,
            action="approved",
            timestamp=_TS,
            actor="human",
        )
        store.save_override(override)
        assert (overrides_dir / f"{claim.id}_approved.yaml").exists()

        store.delete_override(claim.id)
        assert not list(overrides_dir.glob(f"{claim.id}_*.yaml"))


# ---------------------------------------------------------------------------
# apply_overrides — individual action types
# ---------------------------------------------------------------------------


class TestApplyOverrides:
    def test_apply_overrides_approved(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(db, builder)
        claim_store = _make_claim_store(db)

        override = Override(claim_id=claim.id, action="approved", timestamp=_TS)
        overrides_dir.mkdir(parents=True)
        (overrides_dir / _override_filename(override)).write_text(
            _serialize_override(override), encoding="utf-8"
        )

        store = FileSystemOverrideStore(overrides_dir)
        result = store.apply_overrides(claim_store)
        assert result.applied == 1
        assert result.skipped == 0
        updated = claim_store.get(claim.id)
        assert updated is not None
        assert updated.review_state == ReviewState.APPROVED

    def test_apply_overrides_edited(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(db, builder)
        claim_store = _make_claim_store(db)

        override = Override(
            claim_id=claim.id,
            action="edited",
            timestamp=_TS,
            original_content=claim.content,
            edited_content="Revised content for testing",
        )
        overrides_dir.mkdir(parents=True)
        (overrides_dir / _override_filename(override)).write_text(
            _serialize_override(override), encoding="utf-8"
        )

        store = FileSystemOverrideStore(overrides_dir)
        result = store.apply_overrides(claim_store)
        assert result.applied == 1
        updated = claim_store.get(claim.id)
        assert updated is not None
        assert updated.content == "Revised content for testing"
        assert updated.review_state == ReviewState.EDITED

    def test_apply_overrides_suppressed(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(db, builder)
        claim_store = _make_claim_store(db)

        override = Override(claim_id=claim.id, action="suppressed", timestamp=_TS)
        overrides_dir.mkdir(parents=True)
        (overrides_dir / _override_filename(override)).write_text(
            _serialize_override(override), encoding="utf-8"
        )

        store = FileSystemOverrideStore(overrides_dir)
        result = store.apply_overrides(claim_store)
        assert result.applied == 1
        updated = claim_store.get(claim.id)
        assert updated is not None
        assert updated.review_state == ReviewState.SUPPRESSED

    def test_apply_overrides_tombstoned(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(db, builder)
        claim_store = _make_claim_store(db)

        override = Override(
            claim_id=claim.id,
            action="tombstoned",
            timestamp=_TS,
            reason="No longer relevant",
        )
        overrides_dir.mkdir(parents=True)
        (overrides_dir / _override_filename(override)).write_text(
            _serialize_override(override), encoding="utf-8"
        )

        store = FileSystemOverrideStore(overrides_dir)
        result = store.apply_overrides(claim_store)
        assert result.applied == 1
        updated = claim_store.get(claim.id)
        assert updated is not None
        assert updated.review_state == ReviewState.TOMBSTONED

    def test_apply_overrides_declared(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim_store = _make_claim_store(db)

        declared_id = generate_claim_id(
            ClaimType.ALWAYS_ON_RULE.value, "src/**", "Human-declared rule"
        )
        override = Override(
            claim_id=declared_id,
            action="declared",
            timestamp=_TS,
            content="Human-declared rule",
            claim_type=ClaimType.ALWAYS_ON_RULE.value,
            scope="src/**",
            applicability=("python",),
        )
        overrides_dir.mkdir(parents=True)
        (overrides_dir / _override_filename(override)).write_text(
            _serialize_override(override), encoding="utf-8"
        )

        store = FileSystemOverrideStore(overrides_dir)
        result = store.apply_overrides(claim_store)
        assert result.applied == 1
        created = claim_store.get(declared_id)
        assert created is not None
        assert created.source_authority == SourceAuthority.DECLARED_REVIEWED
        assert created.review_state == ReviewState.APPROVED
        assert created.content == "Human-declared rule"
        assert created.scope == "src/**"
        assert created.applicability == ("python",)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_apply_override_claim_not_found(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim_store = _make_claim_store(db)

        override = Override(
            claim_id="claim-nonexistent99",
            action="approved",
            timestamp=_TS,
        )
        overrides_dir.mkdir(parents=True)
        (overrides_dir / _override_filename(override)).write_text(
            _serialize_override(override), encoding="utf-8"
        )

        store = FileSystemOverrideStore(overrides_dir)
        result = store.apply_overrides(claim_store)
        assert result.applied == 0
        assert result.skipped == 1
        assert len(result.warnings) == 1
        assert "claim-nonexistent99" in result.warnings[0]

    def test_apply_overrides_dedup_last_write_wins(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(db, builder)
        claim_store = _make_claim_store(db)

        # Earlier override: approve.
        override_early = Override(claim_id=claim.id, action="approved", timestamp=_TS)
        # Later override: suppress (should win).
        override_late = Override(claim_id=claim.id, action="suppressed", timestamp=_TS_LATER)

        overrides_dir.mkdir(parents=True)
        (overrides_dir / _override_filename(override_early)).write_text(
            _serialize_override(override_early), encoding="utf-8"
        )
        (overrides_dir / _override_filename(override_late)).write_text(
            _serialize_override(override_late), encoding="utf-8"
        )

        store = FileSystemOverrideStore(overrides_dir)
        result = store.apply_overrides(claim_store)
        # Dedup keeps only the last write (suppressed overwrites approved in the dict).
        assert result.applied == 1
        updated = claim_store.get(claim.id)
        assert updated is not None
        assert updated.review_state == ReviewState.SUPPRESSED


# ---------------------------------------------------------------------------
# Sensitivity enforcement
# ---------------------------------------------------------------------------


class TestSensitivity:
    def test_sensitivity_enforcement_local_only(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(
            db, builder, sensitivity=Sensitivity.LOCAL_ONLY, content="secret local rule"
        )
        claim_store = _make_claim_store(db)
        store = FileSystemOverrideStore(overrides_dir, claim_store=claim_store)

        override = Override(
            claim_id=claim.id,
            action="approved",
            timestamp=_TS,
            actor="human",
        )
        store.save_override(override)

        # File must NOT be written to the overrides dir.
        assert not overrides_dir.exists() or not list(overrides_dir.glob("*.yaml"))

        # But the claim's review_state should be updated in the DB.
        updated = claim_store.get(claim.id)
        assert updated is not None
        assert updated.review_state == ReviewState.APPROVED


# ---------------------------------------------------------------------------
# Audit trail integration
# ---------------------------------------------------------------------------


class TestAuditTrail:
    def test_audit_trail_recorded(
        self,
        tmp_path: Path,
        db: sqlite3.Connection,
        builder: ClaimBuilder,
    ) -> None:
        overrides_dir = tmp_path / "overrides"
        claim = _save_claim(db, builder)
        claim_store = _make_claim_store(db)
        history_store = _make_history_store(db)

        store = FileSystemOverrideStore(
            overrides_dir,
            claim_store=claim_store,
            history_store=history_store,
        )

        override = Override(
            claim_id=claim.id,
            action="approved",
            timestamp=_TS,
            actor="reviewer@example.com",
        )
        store.save_override(override)

        entries = history_store.get_for_claim(claim.id)
        assert len(entries) == 1
        assert entries[0].action == "approve"
        assert entries[0].actor == "reviewer@example.com"
