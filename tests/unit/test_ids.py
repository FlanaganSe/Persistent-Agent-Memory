"""Tests for content-addressable claim ID generation."""

from __future__ import annotations

from rkp.core.ids import generate_claim_id


class TestGenerateClaimId:
    def test_deterministic(self) -> None:
        """Same inputs always produce the same ID."""
        id1 = generate_claim_id("always-on-rule", "**", "Use snake_case")
        id2 = generate_claim_id("always-on-rule", "**", "Use snake_case")
        assert id1 == id2

    def test_prefix(self) -> None:
        """IDs start with 'claim-'."""
        cid = generate_claim_id("always-on-rule", "**", "test")
        assert cid.startswith("claim-")

    def test_length(self) -> None:
        """IDs are 'claim-' + 16 hex chars = 22 chars total."""
        cid = generate_claim_id("validated-command", "src/", "make test")
        assert len(cid) == 22

    def test_hex_suffix(self) -> None:
        """The suffix after 'claim-' is valid hex."""
        cid = generate_claim_id("scoped-rule", "src/auth", "require review")
        suffix = cid.removeprefix("claim-")
        int(suffix, 16)  # raises ValueError if not hex

    def test_different_content_different_id(self) -> None:
        """Different content produces different IDs."""
        id1 = generate_claim_id("always-on-rule", "**", "Use snake_case")
        id2 = generate_claim_id("always-on-rule", "**", "Use camelCase")
        assert id1 != id2

    def test_different_type_different_id(self) -> None:
        """Different claim types produce different IDs even with same content."""
        id1 = generate_claim_id("always-on-rule", "**", "test")
        id2 = generate_claim_id("scoped-rule", "**", "test")
        assert id1 != id2

    def test_different_scope_different_id(self) -> None:
        """Different scopes produce different IDs even with same content."""
        id1 = generate_claim_id("always-on-rule", "**", "test")
        id2 = generate_claim_id("always-on-rule", "src/", "test")
        assert id1 != id2

    def test_content_addressable(self) -> None:
        """Re-extraction of identical content produces the same ID."""
        id_first = generate_claim_id("validated-command", "**", "pytest tests/")
        id_reextract = generate_claim_id("validated-command", "**", "pytest tests/")
        assert id_first == id_reextract

    def test_unicode_content(self) -> None:
        """Unicode content is handled correctly."""
        cid = generate_claim_id("always-on-rule", "**", "Utiliser les accents: é, ü, ñ")
        assert cid.startswith("claim-")
        assert len(cid) == 22

    def test_empty_content(self) -> None:
        """Empty content still produces a valid ID."""
        cid = generate_claim_id("always-on-rule", "**", "")
        assert cid.startswith("claim-")
        assert len(cid) == 22
