"""Tests for Cursor adapter."""

from __future__ import annotations

from dataclasses import replace

import yaml

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, Sensitivity, SourceAuthority
from rkp.projection.adapters.cursor import CursorAdapter
from rkp.projection.budget import BudgetTracker
from rkp.projection.capability_matrix import CURSOR_CAPABILITY
from rkp.projection.engine import ProjectionPolicy, project


def _budget() -> BudgetTracker:
    return BudgetTracker(soft_budget_lines=CURSOR_CAPABILITY.size_constraints.soft_budget_lines)


class TestCursorAdapter:
    def test_empty_claims_no_files(self) -> None:
        """No claims produces no files."""
        adapter = CursorAdapter()
        result = adapter.project([], CURSOR_CAPABILITY, _budget())
        assert result.files == {}

    def test_conventions_always_apply(self, builder: ClaimBuilder) -> None:
        """Broad conventions produce an alwaysApply: true file."""
        claims = [
            builder.build(
                content="Use ruff for formatting",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=0.95,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        assert ".cursor/rules/rkp-conventions.md" in result.files
        content = result.files[".cursor/rules/rkp-conventions.md"]
        assert "alwaysApply: true" in content
        assert "Use ruff for formatting" in content

    def test_commands_always_apply(self, builder: ClaimBuilder) -> None:
        """Commands produce an alwaysApply: true file with risk labels."""
        claims = [
            replace(
                builder.build(
                    content="pytest",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                ),
                risk_class=RiskClass.TEST_EXECUTION,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        assert ".cursor/rules/rkp-commands.md" in result.files
        content = result.files[".cursor/rules/rkp-commands.md"]
        assert "alwaysApply: true" in content
        assert "`pytest`" in content
        assert "test-execution" in content

    def test_guardrails_always_apply(self, builder: ClaimBuilder) -> None:
        """Guardrails produce an alwaysApply: true file with restrictions."""
        claims = [
            builder.build(
                content="Never run db:reset without confirmation",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        assert ".cursor/rules/rkp-guardrails.md" in result.files
        content = result.files[".cursor/rules/rkp-guardrails.md"]
        assert "alwaysApply: true" in content
        assert "## Restrictions" in content
        assert "db:reset" in content

    def test_scoped_rules_with_globs(self, builder: ClaimBuilder) -> None:
        """Scoped claims produce alwaysApply: false files with globs."""
        claims = [
            builder.build(
                content="Use strict TypeScript",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope="src/payments",
                confidence=0.95,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        scoped_files = {k: v for k, v in result.files.items() if "alwaysApply: false" in v}
        assert len(scoped_files) == 1

        content = next(iter(scoped_files.values()))
        assert "alwaysApply: false" in content
        assert "globs:" in content
        assert "src/payments/**" in content
        assert "Use strict TypeScript" in content

    def test_setup_always_apply(self, builder: ClaimBuilder) -> None:
        """Environment prerequisites produce a setup rule file."""
        claims = [
            builder.build(
                content="Python 3.12 required",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        assert ".cursor/rules/rkp-setup.md" in result.files
        content = result.files[".cursor/rules/rkp-setup.md"]
        assert "alwaysApply: true" in content
        assert "## Environment Setup" in content
        assert "Python 3.12 required" in content

    def test_skills_inlined(self, builder: ClaimBuilder) -> None:
        """Skill claims are inlined into conventions (Cursor has no separate skills)."""
        claims = [
            builder.build(
                content="Always run tests before committing",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
            ),
            builder.build(
                content="1. Open the PR\n2. Run lint\n3. Merge",
                claim_type=ClaimType.SKILL_PLAYBOOK,
                source_authority=SourceAuthority.DECLARED_REVIEWED,
                scope="release-workflow",
                confidence=1.0,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        assert ".cursor/rules/rkp-conventions.md" in result.files
        content = result.files[".cursor/rules/rkp-conventions.md"]
        assert "## Conventions" in content
        assert "## Procedures" in content
        assert "1. Open the PR" in content
        # No separate skill file should exist
        skill_files = [k for k in result.files if "skill" in k.lower()]
        assert skill_files == []

    def test_no_sensitivity_leakage(self, builder: ClaimBuilder) -> None:
        """Local-only claims are excluded via the projection engine."""
        claims = [
            builder.build(
                content="Public convention",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
            ),
            replace(
                builder.build(
                    content="Secret local credential path",
                    claim_type=ClaimType.ALWAYS_ON_RULE,
                    source_authority=SourceAuthority.INFERRED_HIGH,
                    confidence=0.95,
                ),
                sensitivity=Sensitivity.LOCAL_ONLY,
            ),
        ]
        adapter = CursorAdapter()
        policy = ProjectionPolicy()
        result = project(claims, adapter, CURSOR_CAPABILITY, policy)

        assert len(result.excluded_sensitive) == 1
        for content in result.adapter_result.files.values():
            assert "Secret local credential path" not in content

    def test_determinism(self, builder: ClaimBuilder) -> None:
        """Same claims twice produce identical file keys."""
        claims = [
            replace(
                builder.build(
                    content="pytest",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                ),
                risk_class=RiskClass.TEST_EXECUTION,
            ),
            builder.build(
                content="Use ruff",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
            ),
        ]
        adapter = CursorAdapter()

        r1 = adapter.project(claims, CURSOR_CAPABILITY, _budget())
        r2 = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        assert set(r1.files.keys()) == set(r2.files.keys())

    def test_rkp_prefix(self, builder: ClaimBuilder) -> None:
        """All generated filenames start with rkp-."""
        claims = [
            builder.build(
                content="Convention A",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=0.95,
            ),
            replace(
                builder.build(
                    content="make build",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                ),
                risk_class=RiskClass.BUILD,
            ),
            builder.build(
                content="No force push",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.DECLARED_REVIEWED,
                confidence=1.0,
            ),
            builder.build(
                content="Node 20 required",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
            builder.build(
                content="Use ESLint in frontend",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope="src/frontend",
                confidence=0.90,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        for path in result.files:
            filename = path.rsplit("/", 1)[-1]
            assert filename.startswith("rkp-"), f"{path} does not have rkp- prefix"

    def test_multiple_scoped_rules(self, builder: ClaimBuilder) -> None:
        """Multiple scoped paths produce multiple files with correct globs."""
        claims = [
            builder.build(
                content="Strict types in payments",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope="src/payments",
                confidence=0.95,
            ),
            builder.build(
                content="Use React Testing Library in UI",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope="src/ui",
                confidence=0.95,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        scoped_files = {k: v for k, v in result.files.items() if "alwaysApply: false" in v}
        assert len(scoped_files) == 2

        all_content = "\n".join(scoped_files.values())
        assert "src/payments/**" in all_content
        assert "src/ui/**" in all_content

    def test_low_authority_excluded(self, builder: ClaimBuilder) -> None:
        """Low-authority conventions are excluded from Cursor projection."""
        claims = [
            builder.build(
                content="High-authority convention",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=0.95,
            ),
            builder.build(
                content="Low-authority convention",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_LOW,
                confidence=0.50,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        assert ".cursor/rules/rkp-conventions.md" in result.files
        content = result.files[".cursor/rules/rkp-conventions.md"]
        assert "High-authority convention" in content
        assert "Low-authority convention" not in content

        # Check excluded in overflow report
        excluded_ids = {e[0] for e in result.excluded_claims}
        low_claim = claims[1]
        assert low_claim.id in excluded_ids

    def test_frontmatter_valid_yaml(self, builder: ClaimBuilder) -> None:
        """All generated files have valid YAML frontmatter."""
        claims = [
            builder.build(
                content="Convention X",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=0.95,
            ),
            replace(
                builder.build(
                    content="make test",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                ),
                risk_class=RiskClass.TEST_EXECUTION,
            ),
            builder.build(
                content="No sudo",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.DECLARED_REVIEWED,
                confidence=1.0,
            ),
            builder.build(
                content="Scoped rule for api",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope="src/api",
                confidence=0.90,
            ),
        ]
        adapter = CursorAdapter()
        result = adapter.project(claims, CURSOR_CAPABILITY, _budget())

        for path, content in result.files.items():
            assert content.startswith("---\n"), f"{path} missing frontmatter delimiter"
            # Extract YAML between --- delimiters
            parts = content.split("---\n", 2)
            assert len(parts) >= 3, f"{path} missing closing frontmatter delimiter"
            frontmatter = yaml.safe_load(parts[1])
            assert isinstance(frontmatter, dict), f"{path} frontmatter is not a dict"
            assert "description" in frontmatter, f"{path} missing description"
            assert "alwaysApply" in frontmatter, f"{path} missing alwaysApply"
