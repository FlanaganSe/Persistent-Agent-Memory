"""Integration tests for the import engine end-to-end."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from rkp.core.types import ArtifactOwnership, SourceAuthority
from rkp.importer.engine import discover_instruction_files, run_import
from rkp.store.artifacts import SqliteArtifactStore
from rkp.store.claims import SqliteClaimStore

_AGENTS_MD_CONTENT = """\
# AGENTS.md

## Conventions

- Always use ruff for linting
- Never commit directly to main
- Prefer functional style over OOP

## Commands

```bash
pytest tests/
ruff check .
```

## Testing

- Use pytest for all tests
- Use hypothesis for property tests
"""

_CLAUDE_MD_CONTENT = """\
# CLAUDE.md

## Rules

- Use type hints on all public functions
- Keep functions under 50 lines
"""


def _create_repo(
    tmp_path: Path,
    *,
    agents_md: bool = True,
    claude_md: bool = False,
    nested_agents: bool = False,
) -> Path:
    """Create a temporary repo structure with instruction files."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Need at least a Python file so init doesn't fail on empty repo
    src = repo / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n", encoding="utf-8")

    if agents_md:
        (repo / "AGENTS.md").write_text(_AGENTS_MD_CONTENT, encoding="utf-8")

    if claude_md:
        (repo / "CLAUDE.md").write_text(_CLAUDE_MD_CONTENT, encoding="utf-8")

    if nested_agents:
        nested_dir = repo / "src" / "module"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "AGENTS.md").write_text(
            "# Nested AGENTS.md\n\n## Conventions\n\n- Use dataclasses for models\n",
            encoding="utf-8",
        )

    return repo


class TestDiscoverInstructionFiles:
    """discover_instruction_files finds AGENTS.md, CLAUDE.md, etc."""

    def test_discovers_agents_md(self, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=True)
        found = discover_instruction_files(repo)
        source_types = [st for st, _ in found]
        paths = [str(p) for _, p in found]

        assert "agents-md" in source_types
        assert any("AGENTS.md" in p for p in paths)

    def test_discovers_claude_md(self, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, claude_md=True)
        found = discover_instruction_files(repo)
        source_types = [st for st, _ in found]

        assert "claude-md" in source_types

    def test_discovers_nested_agents_md(self, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=True, nested_agents=True)
        found = discover_instruction_files(repo)
        agents_entries = [(st, p) for st, p in found if st == "agents-md"]

        # Should find root and nested
        assert len(agents_entries) >= 2

    def test_discovers_nothing_in_empty_repo(self, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=False, claude_md=False)
        found = discover_instruction_files(repo)
        assert len(found) == 0

    def test_discovers_copilot_instructions(self, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=False)
        github_dir = repo / ".github"
        github_dir.mkdir()
        (github_dir / "copilot-instructions.md").write_text(
            "# Copilot\n\n- Use TypeScript\n", encoding="utf-8"
        )

        found = discover_instruction_files(repo)
        source_types = [st for st, _ in found]
        assert "copilot-instructions" in source_types

    def test_discovers_cursor_rules(self, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=False)
        cursor_dir = repo / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True)
        (cursor_dir / "python.md").write_text("- Use type hints\n", encoding="utf-8")

        found = discover_instruction_files(repo)
        source_types = [st for st, _ in found]
        assert "cursor-rules" in source_types


class TestRunImportFullPipeline:
    """Full import on fixture directory with AGENTS.md creates correct claims."""

    def test_full_import_creates_claims(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=True)
        claim_store = SqliteClaimStore(db)
        artifact_store = SqliteArtifactStore(db)

        result = run_import(
            repo,
            claim_store,
            repo_id="test-repo",
            branch="main",
            artifact_store=artifact_store,
        )

        assert result.claims_created > 0
        assert str(repo / "AGENTS.md") in result.files_discovered
        assert len(result.files_parsed) > 0

        # Verify claims were persisted
        claims = claim_store.list_claims(repo_id="test-repo")
        assert len(claims) == result.claims_created

    def test_import_sets_correct_source_authority(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        repo = _create_repo(tmp_path, agents_md=True)
        claim_store = SqliteClaimStore(db)

        run_import(repo, claim_store, repo_id="test-repo", branch="main")

        claims = claim_store.list_claims(repo_id="test-repo")
        assert len(claims) > 0
        for claim in claims:
            assert claim.source_authority == SourceAuthority.DECLARED_IMPORTED_UNREVIEWED


class TestRunImportDryRun:
    """Import with --dry-run shows results but doesn't persist."""

    def test_dry_run_does_not_persist(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=True)
        claim_store = SqliteClaimStore(db)
        artifact_store = SqliteArtifactStore(db)

        result = run_import(
            repo,
            claim_store,
            repo_id="test-repo",
            branch="main",
            dry_run=True,
            artifact_store=artifact_store,
        )

        # Result reports claims were found
        assert result.claims_created > 0

        # But nothing persisted
        claims = claim_store.list_claims(repo_id="test-repo")
        assert len(claims) == 0

        artifacts = artifact_store.list_artifacts()
        assert len(artifacts) == 0


class TestRunImportTakeOwnership:
    """Import with --take-ownership registers managed-by-rkp."""

    def test_take_ownership_registers_managed(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        repo = _create_repo(tmp_path, agents_md=True)
        claim_store = SqliteClaimStore(db)
        artifact_store = SqliteArtifactStore(db)

        run_import(
            repo,
            claim_store,
            repo_id="test-repo",
            branch="main",
            take_ownership=True,
            artifact_store=artifact_store,
        )

        artifacts = artifact_store.list_artifacts()
        assert len(artifacts) > 0
        for artifact in artifacts:
            assert artifact.ownership_mode == ArtifactOwnership.MANAGED_BY_RKP

    def test_default_ownership_is_human_owned(
        self, db: sqlite3.Connection, tmp_path: Path
    ) -> None:
        repo = _create_repo(tmp_path, agents_md=True)
        claim_store = SqliteClaimStore(db)
        artifact_store = SqliteArtifactStore(db)

        run_import(
            repo,
            claim_store,
            repo_id="test-repo",
            branch="main",
            take_ownership=False,
            artifact_store=artifact_store,
        )

        artifacts = artifact_store.list_artifacts()
        assert len(artifacts) > 0
        for artifact in artifacts:
            assert artifact.ownership_mode == ArtifactOwnership.IMPORTED_HUMAN_OWNED


class TestRunImportNoFiles:
    """Import on repo with no instruction files produces warning."""

    def test_no_files_warning(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=False, claude_md=False)
        claim_store = SqliteClaimStore(db)

        result = run_import(repo, claim_store, repo_id="test-repo", branch="main")

        assert result.claims_created == 0
        assert any("No instruction files" in w for w in result.warnings)


class TestRunImportDeduplication:
    """Import deduplicates against existing claims."""

    def test_duplicate_claims_not_doubled(self, db: sqlite3.Connection, tmp_path: Path) -> None:
        repo = _create_repo(tmp_path, agents_md=True)
        claim_store = SqliteClaimStore(db)

        # First import
        result1 = run_import(repo, claim_store, repo_id="test-repo", branch="main")
        first_count = result1.claims_created
        assert first_count > 0

        # Second import of same content
        result2 = run_import(repo, claim_store, repo_id="test-repo", branch="main")
        assert result2.claims_created == 0
        assert result2.claims_deduplicated > 0

        # Total in store should not have doubled
        claims = claim_store.list_claims(repo_id="test-repo")
        assert len(claims) == first_count
