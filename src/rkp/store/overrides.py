""".rkp/overrides/ persistence: serialize human governance decisions as strictyaml files."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import strictyaml  # type: ignore[import-untyped]
import structlog

from rkp.core.models import Claim, Provenance
from rkp.core.types import (
    ClaimType,
    ReviewState,
    Sensitivity,
    SourceAuthority,
)
from rkp.store.claims import ClaimStore
from rkp.store.history import SqliteHistoryStore

logger = structlog.get_logger()

_VALID_ACTIONS = frozenset({"approved", "edited", "suppressed", "tombstoned", "declared"})


@dataclass(frozen=True)
class Override:
    """A single human governance decision."""

    claim_id: str
    action: str  # approved | edited | suppressed | tombstoned | declared
    timestamp: datetime
    actor: str = "human"
    original_content: str | None = None
    edited_content: str | None = None
    content: str | None = None
    claim_type: str | None = None
    scope: str | None = None
    applicability: tuple[str, ...] = ()
    sensitivity: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ApplyResult:
    """Summary of applying overrides to the claim store."""

    applied: int = 0
    skipped: int = 0
    warnings: tuple[str, ...] = ()
    by_action: tuple[tuple[str, int], ...] = ()


class OverrideStore(Protocol):
    """Protocol for override persistence."""

    def save_override(self, override: Override) -> None: ...
    def load_overrides(self) -> list[Override]: ...
    def delete_override(self, claim_id: str) -> None: ...
    def apply_overrides(self, claim_store: ClaimStore, *, repo_id: str = "") -> ApplyResult: ...


# Safe claim ID: alphanumeric + hyphens only, no path separators.
_SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def _validate_claim_id(claim_id: str) -> None:
    """Validate claim_id to prevent path traversal via override filenames."""
    if not _SAFE_ID_PATTERN.match(claim_id) or ".." in claim_id:
        msg = f"Invalid claim_id format: {claim_id!r}"
        raise ValueError(msg)


def _override_filename(override: Override) -> str:
    """Generate a filename for an override: {claim_id}_{action}.yaml."""
    _validate_claim_id(override.claim_id)
    return f"{override.claim_id}_{override.action}.yaml"


def _serialize_override(override: Override) -> str:
    """Serialize an Override to strictyaml string."""
    data: dict[str, str | list[str]] = {
        "claim_id": override.claim_id,
        "action": override.action,
        "timestamp": override.timestamp.isoformat(),
        "actor": override.actor,
    }

    if override.action == "edited":
        if override.original_content is not None:
            data["original_content"] = override.original_content
        if override.edited_content is not None:
            data["edited_content"] = override.edited_content

    if override.action == "declared":
        if override.content is not None:
            data["content"] = override.content
        if override.claim_type is not None:
            data["claim_type"] = override.claim_type
        if override.scope is not None:
            data["scope"] = override.scope
        if override.applicability:
            data["applicability"] = list(override.applicability)
        if override.sensitivity is not None:
            data["sensitivity"] = override.sensitivity

    if override.action == "tombstoned" and override.reason is not None:
        data["reason"] = override.reason

    doc = strictyaml.as_document(data)  # pyright: ignore[reportUnknownMemberType]
    yaml_str = cast(str, doc.as_yaml())  # pyright: ignore[reportUnknownMemberType]
    return yaml_str


def _deserialize_override(yaml_text: str) -> Override:
    """Deserialize a strictyaml string to an Override."""
    schema = strictyaml.Map(
        {
            "claim_id": strictyaml.Str(),
            "action": strictyaml.Enum(list(_VALID_ACTIONS)),
            "timestamp": strictyaml.Str(),
            "actor": strictyaml.Str(),
            strictyaml.Optional("original_content"): strictyaml.Str(),
            strictyaml.Optional("edited_content"): strictyaml.Str(),
            strictyaml.Optional("content"): strictyaml.Str(),
            strictyaml.Optional("claim_type"): strictyaml.Str(),
            strictyaml.Optional("scope"): strictyaml.Str(),
            strictyaml.Optional("applicability"): strictyaml.Seq(strictyaml.Str()),
            strictyaml.Optional("sensitivity"): strictyaml.Str(),
            strictyaml.Optional("reason"): strictyaml.Str(),
        }
    )
    parsed = strictyaml.load(yaml_text, schema)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    data = cast(dict[str, Any], parsed.data)  # pyright: ignore[reportUnknownMemberType]

    applicability: tuple[str, ...] = ()
    raw_app = data.get("applicability")
    if raw_app:
        applicability = tuple(cast(list[str], raw_app))

    return Override(
        claim_id=str(data["claim_id"]),
        action=str(data["action"]),
        timestamp=datetime.fromisoformat(str(data["timestamp"])),
        actor=str(data.get("actor", "human")),
        original_content=str(data["original_content"]) if data.get("original_content") else None,
        edited_content=str(data["edited_content"]) if data.get("edited_content") else None,
        content=str(data["content"]) if data.get("content") else None,
        claim_type=str(data["claim_type"]) if data.get("claim_type") else None,
        scope=str(data["scope"]) if data.get("scope") else None,
        applicability=applicability,
        sensitivity=str(data["sensitivity"]) if data.get("sensitivity") else None,
        reason=str(data["reason"]) if data.get("reason") else None,
    )


class FileSystemOverrideStore:
    """Reads/writes override files in .rkp/overrides/ using strictyaml."""

    def __init__(
        self,
        overrides_dir: Path,
        *,
        history_store: SqliteHistoryStore | None = None,
        claim_store: ClaimStore | None = None,
        repo_id: str = "",
    ) -> None:
        self._dir = overrides_dir
        self._history = history_store
        self._claim_store = claim_store
        self._repo_id = repo_id

    def save_override(self, override: Override) -> None:
        """Write an override file and record in audit trail.

        For non-declared overrides, validates the claim exists in the store.
        Enforces sensitivity: local-only claims are never written to overrides dir.
        """
        # Sensitivity check: local-only claims stay in local DB only.
        if self._claim_store is not None and override.action != "declared":
            existing = self._claim_store.get(override.claim_id)
            if existing is not None and existing.sensitivity == Sensitivity.LOCAL_ONLY:
                _apply_single(self._claim_store, override, repo_id=self._repo_id)
                if self._history is not None:
                    self._record_history(override, existing)
                logger.info(
                    "Override applied to local DB only (local-only sensitivity)",
                    claim_id=override.claim_id,
                    action=override.action,
                )
                return

        self._dir.mkdir(parents=True, exist_ok=True)
        filename = _override_filename(override)
        filepath = self._dir / filename
        yaml_content = _serialize_override(override)
        filepath.write_text(yaml_content, encoding="utf-8")

        # Apply to claim store if available.
        if self._claim_store is not None:
            existing = (
                self._claim_store.get(override.claim_id) if override.action != "declared" else None
            )
            _apply_single(self._claim_store, override, repo_id=self._repo_id)
            if self._history is not None:
                self._record_history(override, existing)

    def load_overrides(self) -> list[Override]:
        """Load all overrides from .rkp/overrides/, sorted by timestamp."""
        if not self._dir.exists():
            return []

        overrides: list[Override] = []
        for filepath in sorted(self._dir.glob("*.yaml")):
            try:
                yaml_text = filepath.read_text(encoding="utf-8")
                override = _deserialize_override(yaml_text)
                overrides.append(override)
            except Exception as exc:
                logger.warning(
                    "Failed to load override file",
                    path=str(filepath),
                    error=str(exc),
                )

        return sorted(overrides, key=lambda o: o.timestamp)

    def delete_override(self, claim_id: str) -> None:
        """Delete all override files for a given claim ID (used by purge)."""
        if not self._dir.exists():
            return
        for filepath in self._dir.glob(f"{claim_id}_*.yaml"):
            filepath.unlink()

    def apply_overrides(self, claim_store: ClaimStore, *, repo_id: str = "") -> ApplyResult:
        """Load overrides and apply them to the claim store.

        Called during rkp init on a clone that has .rkp/overrides/ but fresh DB.
        Deduplicates: if two overrides target the same claim, last-write-wins.
        """
        overrides = self.load_overrides()
        if not overrides:
            return ApplyResult()

        # Deduplicate: last-write-wins per claim_id (for non-declared).
        seen: dict[str, Override] = {}
        declared: list[Override] = []
        for override in overrides:
            if override.action == "declared":
                declared.append(override)
            else:
                seen[override.claim_id] = override

        deduped = list(seen.values()) + declared
        applied = 0
        skipped = 0
        warnings: list[str] = []
        action_counts: dict[str, int] = {}

        for override in deduped:
            try:
                _apply_single(claim_store, override, repo_id=repo_id)
                applied += 1
                action_counts[override.action] = action_counts.get(override.action, 0) + 1
            except Exception as exc:
                skipped += 1
                msg = f"Override skipped for {override.claim_id}: {exc}"
                warnings.append(msg)
                logger.warning("Override skipped", claim_id=override.claim_id, error=str(exc))

        return ApplyResult(
            applied=applied,
            skipped=skipped,
            warnings=tuple(warnings),
            by_action=tuple(sorted(action_counts.items())),
        )

    def _record_history(self, override: Override, existing: Claim | None) -> None:
        """Record a governance action in the audit trail."""
        if self._history is None:
            return

        if override.action == "approved":
            self._history.record(
                claim_id=override.claim_id,
                action="approve",
                actor=override.actor,
            )
        elif override.action == "edited":
            self._history.record(
                claim_id=override.claim_id,
                action="edit",
                content_before=override.original_content
                or (existing.content if existing else None),
                content_after=override.edited_content,
                actor=override.actor,
            )
        elif override.action == "suppressed":
            self._history.record(
                claim_id=override.claim_id,
                action="suppress",
                actor=override.actor,
            )
        elif override.action == "tombstoned":
            self._history.record(
                claim_id=override.claim_id,
                action="tombstone",
                actor=override.actor,
                reason=override.reason,
            )
        elif override.action == "declared":
            self._history.record(
                claim_id=override.claim_id,
                action="declare",
                content_after=override.content,
                actor=override.actor,
            )


def _apply_single(claim_store: ClaimStore, override: Override, *, repo_id: str = "") -> None:
    """Apply a single override to the claim store."""
    if override.action == "declared":
        _apply_declared(claim_store, override, repo_id=repo_id)
        return

    existing = claim_store.get(override.claim_id)
    if existing is None:
        msg = "Claim not found (may have changed between extractions)"
        raise ValueError(msg)

    if override.action == "approved":
        updated = replace(existing, review_state=ReviewState.APPROVED)
        claim_store.update(updated)

    elif override.action == "edited":
        new_content = override.edited_content or existing.content
        updated = replace(existing, content=new_content, review_state=ReviewState.EDITED)
        claim_store.update(updated)

    elif override.action == "suppressed":
        updated = replace(existing, review_state=ReviewState.SUPPRESSED)
        claim_store.update(updated)

    elif override.action == "tombstoned":
        updated = replace(existing, review_state=ReviewState.TOMBSTONED)
        claim_store.update(updated)

    else:
        msg = f"Unknown override action: {override.action}"
        raise ValueError(msg)


def _apply_declared(claim_store: ClaimStore, override: Override, *, repo_id: str = "") -> None:
    """Create a new declared claim from an override."""
    content = override.content or ""
    claim_type_str = override.claim_type or ClaimType.ALWAYS_ON_RULE.value
    scope = override.scope or "**"

    try:
        claim_type = ClaimType(claim_type_str)
    except ValueError:
        claim_type = ClaimType.ALWAYS_ON_RULE

    sensitivity = Sensitivity.PUBLIC
    if override.sensitivity:
        with contextlib.suppress(ValueError):
            sensitivity = Sensitivity(override.sensitivity)

    claim_id = override.claim_id
    now = datetime.now(UTC)

    claim = Claim(
        id=claim_id,
        content=content,
        claim_type=claim_type,
        source_authority=SourceAuthority.DECLARED_REVIEWED,
        scope=scope,
        applicability=override.applicability or ("all",),
        sensitivity=sensitivity,
        review_state=ReviewState.APPROVED,
        confidence=1.0,
        evidence=(),
        provenance=Provenance(extraction_version="human-declared"),
        repo_id=repo_id,
        branch="main",
        created_at=override.timestamp,
        updated_at=now,
        last_validated=now,
    )

    existing = claim_store.get(claim_id)
    if existing is not None:
        claim_store.update(claim)
    else:
        claim_store.save(claim)
