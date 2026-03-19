"""Integration tests for rkp audit command."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rkp.cli.app import app
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations
from rkp.store.history import SqliteHistoryStore


def _parse_json(output: str) -> dict:
    """Extract JSON from CLI output."""
    start = output.find("{")
    if start == -1:
        msg = f"No JSON found in output: {output[:200]}"
        raise ValueError(msg)
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(output[start:])
    return obj


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    """Create a minimal initialized repo."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    (repo / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n')
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("def hello():\n    pass\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--repo", str(repo), "init"])
    assert result.exit_code in (0, 1), f"init failed: {result.output}"
    return repo


def _seed_history(repo: Path) -> None:
    """Seed some audit trail entries."""
    from rkp.core.models import Claim
    from rkp.core.types import ClaimType, SourceAuthority

    db_path = repo / ".rkp" / "local" / "rkp.db"
    db = open_database(db_path)
    run_migrations(db)

    claim_store = SqliteClaimStore(db)
    history_store = SqliteHistoryStore(db)

    # Find an existing claim, or create one for audit seeding
    claims = claim_store.list_claims()
    if not claims:
        claim = Claim(
            id="claim-audit-seed1",
            content="Seeded claim for audit tests",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=0.9,
            repo_id=str(repo.resolve()),
        )
        claim_store.save(claim)
        cid = claim.id
    else:
        cid = claims[0].id

    history_store.record(claim_id=cid, action="approved", actor="human", reason="Looks good")
    history_store.record(claim_id=cid, action="stale", actor="system", reason="Evidence changed")
    db.close()


class TestAuditCommand:
    def test_audit_with_no_history(self, initialized_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "audit"])
        assert result.exit_code == 0
        # Either shows entries or "No audit trail entries found"
        assert "audit" in result.output.lower() or "No audit trail" in result.output

    def test_audit_with_history(self, initialized_repo: Path) -> None:
        _seed_history(initialized_repo)
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "audit"])
        assert result.exit_code == 0
        assert "approved" in result.output or "stale" in result.output

    def test_audit_json(self, initialized_repo: Path) -> None:
        _seed_history(initialized_repo)
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(initialized_repo), "--json", "audit"])
        assert result.exit_code == 0
        data = _parse_json(result.output)
        assert "entries" in data
        assert data["count"] >= 0

    def test_audit_action_filter(self, initialized_repo: Path) -> None:
        _seed_history(initialized_repo)
        runner = CliRunner()
        result = runner.invoke(
            app, ["--repo", str(initialized_repo), "--json", "audit", "--action", "approved"]
        )
        assert result.exit_code == 0
        data = _parse_json(result.output)
        for entry in data["entries"]:
            assert entry["action"] == "approved"

    def test_audit_limit(self, initialized_repo: Path) -> None:
        _seed_history(initialized_repo)
        runner = CliRunner()
        result = runner.invoke(
            app, ["--repo", str(initialized_repo), "--json", "audit", "--limit", "1"]
        )
        assert result.exit_code == 0
        data = _parse_json(result.output)
        assert len(data["entries"]) <= 1

    def test_audit_not_initialized(self, tmp_path: Path) -> None:
        repo = tmp_path / "bare"
        repo.mkdir()
        runner = CliRunner()
        result = runner.invoke(app, ["--repo", str(repo), "audit"])
        assert result.exit_code == 3

    def test_audit_claim_id_filter(self, initialized_repo: Path) -> None:
        _seed_history(initialized_repo)
        runner = CliRunner()
        # Get a claim ID from the JSON audit
        result = runner.invoke(app, ["--repo", str(initialized_repo), "--json", "audit"])
        data = _parse_json(result.output)
        if data["entries"]:
            cid = data["entries"][0]["claim_id"]
            result2 = runner.invoke(
                app,
                ["--repo", str(initialized_repo), "--json", "audit", "--claim-id", cid],
            )
            assert result2.exit_code == 0
            data2 = json.loads(result2.output)
            for entry in data2["entries"]:
                assert entry["claim_id"] == cid
