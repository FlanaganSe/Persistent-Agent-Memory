"""Tests for Windsurf adapter."""

from __future__ import annotations

from dataclasses import replace

import yaml

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Provenance
from rkp.core.types import ClaimType, RiskClass, Sensitivity, SourceAuthority
from rkp.projection.adapters.windsurf import _PER_FILE_CHAR_LIMIT, WindsurfAdapter
from rkp.projection.budget import BudgetTracker
from rkp.projection.capability_matrix import WINDSURF_CAPABILITY


def _make_budget() -> BudgetTracker:
    return BudgetTracker(
        hard_budget_bytes=WINDSURF_CAPABILITY.size_constraints.hard_budget_bytes,
        workspace_budget_bytes=WINDSURF_CAPABILITY.size_constraints.workspace_budget_bytes,
    )


def _provenance(head: str = "abc12345def67890") -> Provenance:
    return Provenance(repo_head=head)


class TestWindsurfAdapter:
    def test_empty_claims_no_files(self, builder: ClaimBuilder) -> None:
        """No claims produces no files."""
        adapter = WindsurfAdapter()
        result = adapter.project([], WINDSURF_CAPABILITY, _make_budget())

        assert result.files == {}
        assert result.excluded_claims == []

    def test_conventions_always_on(self, builder: ClaimBuilder) -> None:
        """Broad conventions produce a trigger: always_on rule file."""
        claims = [
            builder.build(
                content="Use ruff for formatting",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        assert ".windsurf/rules/rkp-conventions.md" in result.files
        content = result.files[".windsurf/rules/rkp-conventions.md"]
        assert "trigger: always_on" in content
        assert "Use ruff for formatting" in content

    def test_commands_always_on(self, builder: ClaimBuilder) -> None:
        """Command claims produce a trigger: always_on commands file."""
        claims = [
            replace(
                builder.build(
                    content="pytest",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                    provenance=_provenance(),
                ),
                risk_class=RiskClass.TEST_EXECUTION,
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        assert ".windsurf/rules/rkp-commands.md" in result.files
        content = result.files[".windsurf/rules/rkp-commands.md"]
        assert "trigger: always_on" in content
        assert "`pytest`" in content

    def test_guardrails_always_on(self, builder: ClaimBuilder) -> None:
        """Guardrail claims produce a trigger: always_on guardrails file."""
        claims = [
            builder.build(
                content="Never run db:reset without confirmation",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        assert ".windsurf/rules/rkp-guardrails.md" in result.files
        content = result.files[".windsurf/rules/rkp-guardrails.md"]
        assert "trigger: always_on" in content
        assert "db:reset" in content

    def test_scoped_rules_with_glob(self, builder: ClaimBuilder) -> None:
        """Scoped claims produce rule files with trigger: glob."""
        claims = [
            builder.build(
                content="Use strict TypeScript",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope="src/payments",
                confidence=0.95,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        scoped_files = {k: v for k, v in result.files.items() if "glob" in v}
        assert len(scoped_files) >= 1
        content = next(iter(scoped_files.values()))
        assert "trigger: glob" in content
        assert "src/payments/**" in content

    def test_budget_enforcement_per_file(self, builder: ClaimBuilder) -> None:
        """A single file exceeding 6K characters is excluded."""
        # Build enough convention claims to exceed 6K in a single file
        claims = [
            builder.build(
                content=f"Convention rule {i}: " + "x" * 200,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                provenance=_provenance(),
            )
            for i in range(40)
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        # The conventions file should be excluded (too large)
        assert ".windsurf/rules/rkp-conventions.md" not in result.files
        # Excluded claims should mention the per-file limit
        excluded_reasons = [reason for _, reason in result.excluded_claims]
        assert any("6K" in r or "per-file" in r for r in excluded_reasons)

    def test_budget_enforcement_workspace(self, builder: ClaimBuilder) -> None:
        """Total content exceeding 12K workspace budget excludes excess files."""
        # Guardrails file: ~2K
        guardrail_claims = [
            builder.build(
                content=f"Restriction {i}: " + "r" * 150,
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                provenance=_provenance(),
            )
            for i in range(10)
        ]
        # Commands file: ~5K
        command_claims = [
            replace(
                builder.build(
                    content=f"cmd-{i}: " + "c" * 300,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                    provenance=_provenance(),
                ),
                risk_class=RiskClass.BUILD,
            )
            for i in range(15)
        ]
        # Conventions file: ~6K+ (should push past 12K workspace limit)
        convention_claims = [
            builder.build(
                content=f"Convention {i}: " + "v" * 300,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.96,
                provenance=_provenance(),
            )
            for i in range(20)
        ]

        all_claims = guardrail_claims + command_claims + convention_claims

        adapter = WindsurfAdapter()
        result = adapter.project(all_claims, WINDSURF_CAPABILITY, _make_budget())

        # At least one file should have been excluded due to workspace budget
        total_chars = sum(len(v) for v in result.files.values())
        assert total_chars <= 12288
        assert len(result.excluded_claims) > 0

    def test_budget_prioritization(self, builder: ClaimBuilder) -> None:
        """Guardrails are kept when budget is tight; low-confidence conventions dropped."""
        guardrail = builder.build(
            content="Never delete production data",
            claim_type=ClaimType.PERMISSION_RESTRICTION,
            source_authority=SourceAuthority.EXECUTABLE_CONFIG,
            confidence=1.0,
            provenance=_provenance(),
        )
        # Low-authority conventions that should be dropped
        low_conventions = [
            builder.build(
                content=f"Low authority convention {i}: " + "x" * 300,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_LOW,
                confidence=0.5,
                provenance=_provenance(),
            )
            for i in range(30)
        ]

        all_claims = [guardrail, *low_conventions]
        adapter = WindsurfAdapter()
        result = adapter.project(all_claims, WINDSURF_CAPABILITY, _make_budget())

        # Guardrails file should be present
        assert ".windsurf/rules/rkp-guardrails.md" in result.files
        content = result.files[".windsurf/rules/rkp-guardrails.md"]
        assert "Never delete production data" in content

        # Low-authority conventions should be excluded
        excluded_ids = {cid for cid, _ in result.excluded_claims}
        for claim in low_conventions:
            assert claim.id in excluded_ids

    def test_deduplication_with_agents_md(self, builder: ClaimBuilder) -> None:
        """Claims already in AGENTS.md are excluded from Windsurf rules."""
        claim = builder.build(
            content="Use ruff for formatting",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.95,
            provenance=_provenance(),
        )

        adapter = WindsurfAdapter(agents_md_claim_ids=frozenset({claim.id}))
        result = adapter.project([claim], WINDSURF_CAPABILITY, _make_budget())

        assert result.files == {}
        excluded_reasons = [reason for _, reason in result.excluded_claims]
        assert any("AGENTS.md" in r for r in excluded_reasons)

    def test_no_sensitivity_leakage(self, builder: ClaimBuilder) -> None:
        """Local-only claims are excluded via the projection engine."""
        public_claim = builder.build(
            content="Public convention",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.95,
            provenance=_provenance(),
        )
        local_claim = replace(
            builder.build(
                content="Secret local setting",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                provenance=_provenance(),
            ),
            sensitivity=Sensitivity.LOCAL_ONLY,
        )

        # Sensitivity filtering happens in the engine, but the adapter should
        # not emit local-only content if passed through directly.
        from rkp.projection.engine import ProjectionPolicy, project

        all_claims = [public_claim, local_claim]
        adapter = WindsurfAdapter()
        policy = ProjectionPolicy()
        result = project(all_claims, adapter, WINDSURF_CAPABILITY, policy)

        for content in result.adapter_result.files.values():
            assert "Secret local setting" not in content

    def test_determinism(self, builder: ClaimBuilder) -> None:
        """Same claims twice produce identical output (modulo timestamps)."""
        claims = [
            replace(
                builder.build(
                    content="pytest",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                    provenance=_provenance(),
                ),
                risk_class=RiskClass.TEST_EXECUTION,
            ),
            builder.build(
                content="Use ruff for formatting",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()

        result1 = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())
        result2 = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        assert set(result1.files.keys()) == set(result2.files.keys())

    def test_rkp_prefix(self, builder: ClaimBuilder) -> None:
        """All generated filenames have rkp- prefix."""
        claims = [
            replace(
                builder.build(
                    content="pytest",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                    provenance=_provenance(),
                ),
                risk_class=RiskClass.TEST_EXECUTION,
            ),
            builder.build(
                content="Never run rm -rf /",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                provenance=_provenance(),
            ),
            builder.build(
                content="Use ruff",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        for path in result.files:
            filename = path.rsplit("/", 1)[-1]
            assert filename.startswith("rkp-"), f"Filename {filename} missing rkp- prefix"

    def test_skill_playbooks_deferred(self, builder: ClaimBuilder) -> None:
        """Skill claims are deferred in Alpha — excluded from output."""
        claims = [
            builder.build(
                content="Run database migration playbook",
                claim_type=ClaimType.SKILL_PLAYBOOK,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        assert result.files == {}
        excluded_reasons = [reason for _, reason in result.excluded_claims]
        assert any("deferred" in r.lower() for r in excluded_reasons)

    def test_frontmatter_valid_yaml(self, builder: ClaimBuilder) -> None:
        """Trigger frontmatter is valid YAML."""
        claims = [
            builder.build(
                content="Use ruff for formatting",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                provenance=_provenance(),
            ),
            builder.build(
                content="Scoped rule for tests",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                scope="tests/",
                confidence=0.95,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        for path, content in result.files.items():
            assert content.startswith("---\n"), f"{path} missing frontmatter start"
            # Extract frontmatter between --- delimiters
            parts = content.split("---", 2)
            assert len(parts) >= 3, f"{path} missing frontmatter end"
            frontmatter = yaml.safe_load(parts[1])
            assert "trigger" in frontmatter, f"{path} missing trigger in frontmatter"
            assert frontmatter["trigger"] in ("always_on", "glob")

    def test_budget_exactly_at_limit(self, builder: ClaimBuilder) -> None:
        """Content exactly at 6K characters is included (no off-by-one)."""
        # Build a single convention claim; we control content length to hit exactly 6K
        # after rendering (frontmatter + header + bullet).
        base_claim = builder.build(
            content="x",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.95,
            provenance=_provenance(),
        )

        # Render once to measure overhead, then adjust content to hit exactly 6144
        adapter = WindsurfAdapter()
        probe_result = adapter.project([base_claim], WINDSURF_CAPABILITY, _make_budget())
        probe_content = probe_result.files[".windsurf/rules/rkp-conventions.md"]
        overhead = len(probe_content) - 1  # subtract the 1-char "x"

        target_content_len = _PER_FILE_CHAR_LIMIT - overhead
        exact_claim = replace(base_claim, content="a" * target_content_len)

        result = adapter.project([exact_claim], WINDSURF_CAPABILITY, _make_budget())
        assert ".windsurf/rules/rkp-conventions.md" in result.files
        content = result.files[".windsurf/rules/rkp-conventions.md"]
        assert len(content) == _PER_FILE_CHAR_LIMIT

    def test_budget_one_over(self, builder: ClaimBuilder) -> None:
        """Content at 6K+1 characters is excluded."""
        base_claim = builder.build(
            content="x",
            claim_type=ClaimType.ALWAYS_ON_RULE,
            source_authority=SourceAuthority.INFERRED_HIGH,
            confidence=0.95,
            provenance=_provenance(),
        )

        adapter = WindsurfAdapter()
        probe_result = adapter.project([base_claim], WINDSURF_CAPABILITY, _make_budget())
        probe_content = probe_result.files[".windsurf/rules/rkp-conventions.md"]
        overhead = len(probe_content) - 1

        target_content_len = _PER_FILE_CHAR_LIMIT - overhead + 1
        over_claim = replace(base_claim, content="a" * target_content_len)

        result = adapter.project([over_claim], WINDSURF_CAPABILITY, _make_budget())
        assert ".windsurf/rules/rkp-conventions.md" not in result.files

    def test_low_authority_excluded(self, builder: ClaimBuilder) -> None:
        """Low authority conventions are excluded from Windsurf projection."""
        claims = [
            builder.build(
                content="Low confidence convention",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_LOW,
                confidence=0.4,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        # INFERRED_LOW is not in _HIGH_AUTHORITY, so conventions are excluded
        assert ".windsurf/rules/rkp-conventions.md" not in result.files
        excluded_reasons = [reason for _, reason in result.excluded_claims]
        assert any("low-authority" in r for r in excluded_reasons)

    def test_generation_header_in_body(self, builder: ClaimBuilder) -> None:
        """Generation header is in content body, not in the YAML frontmatter."""
        claims = [
            builder.build(
                content="Use ruff for formatting",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                provenance=_provenance(),
            ),
        ]

        adapter = WindsurfAdapter()
        result = adapter.project(claims, WINDSURF_CAPABILITY, _make_budget())

        content = result.files[".windsurf/rules/rkp-conventions.md"]
        # Split on frontmatter delimiter
        parts = content.split("---", 2)
        frontmatter_text = parts[1]
        body_text = parts[2]

        # Header should be in body, not frontmatter
        assert "Generated by RKP" not in frontmatter_text
        assert "Generated by RKP" in body_text
