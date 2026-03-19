"""Snapshot tests for scoped claims — correct host-native format per adapter."""

from __future__ import annotations

import re

import yaml

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, SourceAuthority
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.adapters.copilot import CopilotAdapter
from rkp.projection.adapters.cursor import CursorAdapter
from rkp.projection.adapters.windsurf import WindsurfAdapter
from rkp.projection.capability_matrix import (
    AGENTS_MD_CAPABILITY,
    CLAUDE_CODE_CAPABILITY,
    COPILOT_CAPABILITY,
    CURSOR_CAPABILITY,
    WINDSURF_CAPABILITY,
)
from rkp.projection.engine import ProjectionPolicy, project


def _make_scoped_claims(builder: ClaimBuilder) -> list:
    """Create scoped claims targeting src/legacy."""
    return [
        builder.build(
            content="Prefer composition over inheritance in legacy module",
            claim_type=ClaimType.SCOPED_RULE,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            scope="src/legacy",
            confidence=0.95,
            applicability=("all",),
            evidence=("src/legacy/README.md",),
        ),
        builder.build(
            content="No new global mutable state in src/legacy",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            scope="src/legacy",
            confidence=0.9,
            applicability=("all",),
            evidence=("src/legacy/.cursorrules",),
        ),
    ]


class TestCursorScopedProjection:
    """Cursor: scoped claims produce globs in frontmatter."""

    def test_scoped_claims_have_globs(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = CursorAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, CURSOR_CAPABILITY, policy)

        # Should produce a scoped rule file
        scoped_files = {
            k: v for k, v in result.adapter_result.files.items() if "rkp-src-legacy" in k
        }
        assert len(scoped_files) == 1

        path, content = next(iter(scoped_files.items()))
        assert path.startswith(".cursor/rules/")

        # Parse frontmatter
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm["alwaysApply"] is False
        assert "globs" in fm
        assert any("src/legacy" in g for g in fm["globs"])

    def test_scoped_content_preserved(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = CursorAdapter()
        result = project(claims, adapter, CURSOR_CAPABILITY, ProjectionPolicy())

        all_content = "\n".join(result.adapter_result.files.values())
        assert "composition over inheritance" in all_content
        assert "global mutable state" in all_content


class TestWindsurfScopedProjection:
    """Windsurf: scoped claims produce trigger:glob in frontmatter."""

    def test_scoped_claims_have_trigger_glob(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = WindsurfAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, WINDSURF_CAPABILITY, policy)

        scoped_files = {
            k: v for k, v in result.adapter_result.files.items() if "rkp-src-legacy" in k
        }
        assert len(scoped_files) == 1

        path, content = next(iter(scoped_files.items()))
        assert path.startswith(".windsurf/rules/")

        # Parse frontmatter
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert fm["trigger"] == "glob"
        assert "src/legacy" in fm["glob"]

    def test_scoped_content_preserved(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = WindsurfAdapter()
        result = project(claims, adapter, WINDSURF_CAPABILITY, ProjectionPolicy())

        all_content = "\n".join(result.adapter_result.files.values())
        assert "composition over inheritance" in all_content
        assert "global mutable state" in all_content


class TestCopilotScopedProjection:
    """Copilot: scoped claims produce applyTo frontmatter."""

    def test_scoped_claims_have_apply_to(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = CopilotAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, COPILOT_CAPABILITY, policy)

        scoped_files = {
            k: v
            for k, v in result.adapter_result.files.items()
            if k.startswith(".github/instructions/")
        }
        assert len(scoped_files) >= 1

        _path, content = next(iter(scoped_files.items()))
        # Parse frontmatter
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert "applyTo" in fm
        assert "src/legacy" in fm["applyTo"]


class TestClaudeScopedProjection:
    """Claude: scoped claims produce paths frontmatter in .claude/rules/."""

    def test_scoped_claims_have_paths(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = ClaudeMdAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, CLAUDE_CODE_CAPABILITY, policy)

        rule_files = {
            k: v for k, v in result.adapter_result.files.items() if k.startswith(".claude/rules/")
        }
        assert len(rule_files) >= 1

        _path, content = next(iter(rule_files.items()))
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = yaml.safe_load(parts[1])
        assert "paths" in fm
        paths = fm["paths"]
        assert any("src/legacy" in p for p in paths)


class TestAgentsMdScopedProjection:
    """AGENTS.md: scoped claims appear in conventions section."""

    def test_scoped_content_in_output(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = AgentsMdAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, AGENTS_MD_CAPABILITY, policy)

        content = result.adapter_result.files.get("AGENTS.md", "")
        # Scoped claims with high authority should still appear
        assert "composition over inheritance" in content or "global mutable state" in content


class TestDeterministicScopedOutput:
    """Same scoped claims produce identical output across runs."""

    def test_cursor_deterministic(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = CursorAdapter()
        policy = ProjectionPolicy()

        r1 = project(claims, adapter, CURSOR_CAPABILITY, policy)
        r2 = project(claims, adapter, CURSOR_CAPABILITY, policy)

        ts = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        for key in r1.adapter_result.files:
            c1 = ts.sub("TS", r1.adapter_result.files[key])
            c2 = ts.sub("TS", r2.adapter_result.files[key])
            assert c1 == c2, f"Non-deterministic output in {key}"

    def test_windsurf_deterministic(self, builder: ClaimBuilder) -> None:
        claims = _make_scoped_claims(builder)
        adapter = WindsurfAdapter()
        policy = ProjectionPolicy()

        r1 = project(claims, adapter, WINDSURF_CAPABILITY, policy)
        r2 = project(claims, adapter, WINDSURF_CAPABILITY, policy)

        ts = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
        for key in r1.adapter_result.files:
            c1 = ts.sub("TS", r1.adapter_result.files[key])
            c2 = ts.sub("TS", r2.adapter_result.files[key])
            assert c1 == c2, f"Non-deterministic output in {key}"
