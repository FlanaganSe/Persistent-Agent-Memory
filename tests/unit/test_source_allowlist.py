"""Source allowlist tests — filtering claims by trusted sources."""

from __future__ import annotations

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.config import SourceAllowlist
from rkp.core.types import ClaimType, SourceAuthority
from rkp.server.tools import enforce_allowlist


def _make_claim(
    content: str,
    source_authority: SourceAuthority,
    evidence: tuple[str, ...] = (),
) -> object:
    builder = ClaimBuilder(repo_id="test")
    return builder.build(
        content=content,
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=source_authority,
        confidence=0.9,
        evidence=evidence,
    )


class TestEnforceAllowlist:
    def test_default_allows_everything(self) -> None:
        """Default allowlist allows all source authorities."""
        allowlist = SourceAllowlist()
        claims = [
            _make_claim("rule1", SourceAuthority.EXECUTABLE_CONFIG),
            _make_claim("rule2", SourceAuthority.INFERRED_LOW),
            _make_claim("rule3", SourceAuthority.HUMAN_OVERRIDE),
        ]
        result = enforce_allowlist(claims, allowlist)
        assert len(result) == 3

    def test_filter_untrusted_source(self) -> None:
        """Claims from non-trusted sources are excluded."""
        allowlist = SourceAllowlist(
            trusted_evidence_sources=(
                "executable-config",
                "ci-observed",
            ),
        )
        claims = [
            _make_claim("from config", SourceAuthority.EXECUTABLE_CONFIG),
            _make_claim("inferred", SourceAuthority.INFERRED_HIGH),
            _make_claim("from ci", SourceAuthority.CI_OBSERVED),
        ]
        result = enforce_allowlist(claims, allowlist)
        assert len(result) == 2
        contents = {c.content for c in result}
        assert "from config" in contents
        assert "from ci" in contents
        assert "inferred" not in contents

    def test_none_allowlist_passes_all(self) -> None:
        """None allowlist (no config) passes everything."""
        claims = [
            _make_claim("rule1", SourceAuthority.INFERRED_LOW),
        ]
        result = enforce_allowlist(claims, None)
        assert len(result) == 1

    def test_directory_filter(self) -> None:
        """Claims with evidence in non-allowed dirs are excluded."""
        allowlist = SourceAllowlist(
            allowed_directories=("src/*",),
        )
        claims = [
            _make_claim("in src", SourceAuthority.EXECUTABLE_CONFIG, evidence=("src/main.py",)),
            _make_claim(
                "in vendor",
                SourceAuthority.EXECUTABLE_CONFIG,
                evidence=("vendor/lib.py",),
            ),
        ]
        result = enforce_allowlist(claims, allowlist)
        assert len(result) == 1
        assert result[0].content == "in src"

    def test_wildcard_directories_allow_all(self) -> None:
        """allowed_directories=('**',) allows all paths (default)."""
        allowlist = SourceAllowlist(allowed_directories=("**",))
        claims = [
            _make_claim(
                "anywhere",
                SourceAuthority.EXECUTABLE_CONFIG,
                evidence=("deep/nested/path.py",),
            ),
        ]
        result = enforce_allowlist(claims, allowlist)
        assert len(result) == 1

    def test_claims_without_evidence_pass_directory_filter(self) -> None:
        """Claims with no evidence files are not filtered by directory."""
        allowlist = SourceAllowlist(allowed_directories=("src/*",))
        claims = [
            _make_claim("no evidence", SourceAuthority.EXECUTABLE_CONFIG, evidence=()),
        ]
        result = enforce_allowlist(claims, allowlist)
        assert len(result) == 1
