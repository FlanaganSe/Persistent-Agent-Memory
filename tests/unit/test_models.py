"""Tests for frozen dataclass domain models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rkp.core.models import (
    Claim,
    ClaimHistory,
    EnvironmentProfile,
    Evidence,
    Identity,
    ManagedArtifact,
    ModuleEdge,
    Provenance,
)
from rkp.core.types import (
    ArtifactOwnership,
    ClaimType,
    EvidenceLevel,
    ReviewState,
    RiskClass,
    Sensitivity,
    SourceAuthority,
)


class TestProvenance:
    def test_defaults(self) -> None:
        p = Provenance()
        assert p.index_version == ""
        assert p.repo_head == ""
        assert p.branch == ""
        assert p.timestamp == ""
        assert p.extraction_version == ""

    def test_with_values(self) -> None:
        p = Provenance(
            index_version="2026-03-18T00:00:00Z",
            repo_head="abc1234",
            branch="main",
            timestamp="2026-03-18T00:00:00Z",
            extraction_version="0.1.0",
        )
        assert p.repo_head == "abc1234"

    def test_frozen(self) -> None:
        p = Provenance()
        with pytest.raises(AttributeError):
            p.branch = "dev"  # type: ignore[misc]


class TestClaim:
    def test_minimal_claim(self) -> None:
        claim = Claim(
            id="claim-abc123",
            content="Use snake_case",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
        )
        assert claim.id == "claim-abc123"
        assert claim.scope == "**"
        assert claim.sensitivity == Sensitivity.PUBLIC
        assert claim.review_state == ReviewState.UNREVIEWED
        assert claim.confidence == 0.0
        assert claim.stale is False

    def test_full_claim(self) -> None:
        now = datetime.now(UTC)
        claim = Claim(
            id="claim-full",
            content="Run pytest",
            claim_type=ClaimType.VALIDATED_COMMAND,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            scope="src/",
            applicability=("test", "ci"),
            sensitivity=Sensitivity.TEAM_ONLY,
            review_state=ReviewState.APPROVED,
            confidence=0.95,
            evidence=("pyproject.toml",),
            provenance=Provenance(repo_head="abc"),
            risk_class=RiskClass.TEST_EXECUTION,
            projection_targets=("agents-md", "claude-md"),
            repo_id="my-repo",
            branch="dev",
            worktree_id="wt-1",
            session_id="sess-1",
            last_validated=now,
            revalidation_trigger="file-changed",
            stale=False,
            created_at=now,
            updated_at=now,
        )
        assert claim.applicability == ("test", "ci")
        assert claim.risk_class == RiskClass.TEST_EXECUTION
        assert claim.worktree_id == "wt-1"
        assert claim.session_id == "sess-1"
        assert claim.projection_targets == ("agents-md", "claude-md")

    def test_frozen(self) -> None:
        claim = Claim(
            id="claim-frz",
            content="x",
            claim_type=ClaimType.CONFLICT,
            source_authority=SourceAuthority.INFERRED_LOW,
        )
        with pytest.raises(AttributeError):
            claim.content = "y"  # type: ignore[misc]


class TestEvidence:
    def test_creation(self) -> None:
        e = Evidence(
            claim_id="claim-001",
            file_path="src/main.py",
            file_hash="abc123",
            extraction_version="0.1.0",
            line_start=10,
            line_end=20,
            evidence_level=EvidenceLevel.CI_EVIDENCED,
        )
        assert e.file_path == "src/main.py"
        assert e.evidence_level == EvidenceLevel.CI_EVIDENCED
        assert e.id is None


class TestClaimHistory:
    def test_creation(self) -> None:
        h = ClaimHistory(
            claim_id="claim-001",
            action="approve",
            content_before="old",
            content_after="new",
            actor="user@example.com",
            reason="Verified correct",
        )
        assert h.action == "approve"
        assert h.actor == "user@example.com"


class TestEnvironmentProfile:
    def test_creation(self) -> None:
        ep = EnvironmentProfile(
            id="ep-001",
            name="python-dev",
            repo_id="my-repo",
            runtime="python:3.12",
            tools=("ruff", "pyright"),
            services=("postgres",),
            env_vars=("DATABASE_URL",),
            setup_commands=("pip install -e .",),
        )
        assert ep.runtime == "python:3.12"
        assert ep.tools == ("ruff", "pyright")


class TestManagedArtifact:
    def test_defaults(self) -> None:
        ma = ManagedArtifact(
            path="AGENTS.md",
            artifact_type="instruction-file",
            target_host="codex",
            expected_hash="abc",
            last_projected="2026-03-18T00:00:00Z",
        )
        assert ma.ownership_mode == ArtifactOwnership.MANAGED_BY_RKP


class TestModuleEdge:
    def test_creation(self) -> None:
        edge = ModuleEdge(
            source_path="src/auth",
            target_path="src/core",
            edge_type="imports",
            repo_id="my-repo",
        )
        assert edge.branch == "main"


class TestIdentity:
    def test_defaults(self) -> None:
        ident = Identity(repo_id="my-repo")
        assert ident.branch == "main"
        assert ident.worktree_id is None
        assert ident.session_id is None
