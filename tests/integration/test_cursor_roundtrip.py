"""Import .cursor/rules -> project .cursor/rules round-trip tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import SourceAuthority
from rkp.importer.parsers.cursor import parse_cursor_rules
from rkp.projection.adapters.cursor import CursorAdapter
from rkp.projection.capability_matrix import CURSOR_CAPABILITY
from rkp.projection.engine import ProjectionPolicy, project
from rkp.store.claims import SqliteClaimStore
from rkp.store.database import open_database, run_migrations


def _write_cursor_rule(
    rules_dir: Path,
    filename: str,
    *,
    description: str = "",
    always_apply: bool = True,
    glob: str | None = None,
    body: str = "",
) -> Path:
    """Write a .cursor/rules/ file with frontmatter."""
    lines: list[str] = ["---"]
    if description:
        lines.append(f'description: "{description}"')
    if glob:
        lines.append(f'glob: "{glob}"')
        lines.append("alwaysApply: false")
    else:
        lines.append(f"alwaysApply: {str(always_apply).lower()}")
    lines.append("---")
    lines.append("")
    lines.append(body)

    file_path = rules_dir / filename
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


@pytest.fixture
def cursor_repo(tmp_path: Path) -> Path:
    """Create a repo with .cursor/rules/ files to import."""
    repo = tmp_path / "cursor_repo"
    rules_dir = repo / ".cursor" / "rules"
    rules_dir.mkdir(parents=True)

    _write_cursor_rule(
        rules_dir,
        "conventions.md",
        description="Project conventions",
        always_apply=True,
        body="## Conventions\n\n- Always use type hints\n- Prefer immutable data structures\n",
    )

    _write_cursor_rule(
        rules_dir,
        "legacy-rules.md",
        description="Legacy module rules",
        glob="src/legacy/**",
        body="## Legacy\n\n- No new global state\n- Prefer composition over inheritance\n",
    )

    return repo


class TestCursorRoundTrip:
    """Import .cursor/rules -> claims -> project .cursor/rules -> verify content."""

    def test_key_content_preserved(self, cursor_repo: Path, tmp_path: Path) -> None:
        """Core directive content survives the import-project round-trip."""
        # Step 1: Import (parse)
        rules_dir = cursor_repo / ".cursor" / "rules"
        parsed_files = parse_cursor_rules(rules_dir)
        assert len(parsed_files) >= 2

        # Collect all parsed claims
        all_parsed_claims = []
        for pf in parsed_files:
            all_parsed_claims.extend(pf.claims)
        assert len(all_parsed_claims) > 0

        # Step 2: Convert parsed claims into real claims via ClaimBuilder + store
        db_path = tmp_path / "roundtrip.db"
        db = open_database(db_path)
        run_migrations(db)
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="roundtrip-test", branch="main")

        for pc in all_parsed_claims:
            claim = builder.build(
                content=pc.content,
                claim_type=pc.claim_type,
                source_authority=SourceAuthority.DECLARED_REVIEWED,
                scope=pc.scope,
                confidence=pc.confidence,
                evidence=(pc.evidence_file,) if pc.evidence_file else (),
            )
            store.save(claim)

        # Step 3: Load claims and project through CursorAdapter
        claims = store.list_claims(repo_id="roundtrip-test")
        adapter = CursorAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, CURSOR_CAPABILITY, policy)

        all_output = "\n".join(result.adapter_result.files.values()).lower()

        # Step 4: Verify key content survived
        assert "type hints" in all_output
        assert "immutable" in all_output

    def test_scoped_globs_survive_roundtrip(self, cursor_repo: Path, tmp_path: Path) -> None:
        """Scoped globs from import appear in projected frontmatter."""
        rules_dir = cursor_repo / ".cursor" / "rules"
        parsed_files = parse_cursor_rules(rules_dir)

        # Find the scoped file's claims
        scoped_claims_parsed = [pc for pf in parsed_files for pc in pf.claims if pc.scope != "**"]

        assert len(scoped_claims_parsed) > 0, "No scoped claims found from import"

        # Build real claims
        db_path = tmp_path / "roundtrip_scoped.db"
        db = open_database(db_path)
        run_migrations(db)
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="roundtrip-scoped", branch="main")

        for pc in scoped_claims_parsed:
            claim = builder.build(
                content=pc.content,
                claim_type=pc.claim_type,
                source_authority=SourceAuthority.DECLARED_REVIEWED,
                scope=pc.scope,
                confidence=pc.confidence,
                evidence=(pc.evidence_file,) if pc.evidence_file else (),
            )
            store.save(claim)

        claims = store.list_claims(repo_id="roundtrip-scoped")
        adapter = CursorAdapter()
        result = project(claims, adapter, CURSOR_CAPABILITY, ProjectionPolicy())

        # Find scoped rule files (non-alwaysApply)
        scoped_files = {}
        for path, content in result.adapter_result.files.items():
            if "---" in content:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict) and fm.get("alwaysApply") is False:
                        scoped_files[path] = fm

        assert len(scoped_files) > 0, "No scoped rule files in projected output"

        # Verify at least one file has globs containing the original scope
        all_globs = []
        for fm in scoped_files.values():
            all_globs.extend(fm.get("globs", []))
        assert any("src/legacy" in g for g in all_globs), (
            f"Original scope not in projected globs: {all_globs}"
        )

    def test_always_apply_preserved(self, cursor_repo: Path, tmp_path: Path) -> None:
        """alwaysApply:true claims remain alwaysApply:true after round-trip."""
        rules_dir = cursor_repo / ".cursor" / "rules"
        parsed_files = parse_cursor_rules(rules_dir)

        # Collect global-scope claims (alwaysApply: true)
        global_claims_parsed = [pc for pf in parsed_files for pc in pf.claims if pc.scope == "**"]

        assert len(global_claims_parsed) > 0

        db_path = tmp_path / "roundtrip_always.db"
        db = open_database(db_path)
        run_migrations(db)
        store = SqliteClaimStore(db)
        builder = ClaimBuilder(repo_id="roundtrip-always", branch="main")

        for pc in global_claims_parsed:
            claim = builder.build(
                content=pc.content,
                claim_type=pc.claim_type,
                source_authority=SourceAuthority.DECLARED_REVIEWED,
                scope=pc.scope,
                confidence=pc.confidence,
                evidence=(pc.evidence_file,) if pc.evidence_file else (),
            )
            store.save(claim)

        claims = store.list_claims(repo_id="roundtrip-always")
        adapter = CursorAdapter()
        result = project(claims, adapter, CURSOR_CAPABILITY, ProjectionPolicy())

        # Check that at least one file has alwaysApply: true
        always_apply_found = False
        for content in result.adapter_result.files.values():
            if "---" in content:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict) and fm.get("alwaysApply") is True:
                        always_apply_found = True
                        break

        assert always_apply_found, "No alwaysApply: true files in projected output"
