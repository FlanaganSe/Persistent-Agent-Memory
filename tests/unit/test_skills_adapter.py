"""Tests for skills adapter."""

from __future__ import annotations

import re
from dataclasses import replace

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, RiskClass, SourceAuthority
from rkp.projection.adapters.skills import (
    MAX_BODY_CHARS,
    project_skills,
)


class TestSkillsAdapter:
    def test_narrow_applicability_grouped_into_skill(self, builder: ClaimBuilder) -> None:
        """Claims with narrow applicability ['testing'] → grouped into one skill."""
        claims = [
            builder.build(
                content="pytest",
                claim_type=ClaimType.VALIDATED_COMMAND,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("testing",),
            ),
            builder.build(
                content="Tests are placed in tests/ directory",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                applicability=("testing",),
            ),
        ]
        claims[0] = replace(claims[0], risk_class=RiskClass.TEST_EXECUTION)

        files, descriptors = project_skills(claims)

        assert len(files) == 1
        assert len(descriptors) == 1
        assert descriptors[0].name == "validate-and-test"
        path = descriptors[0].path
        assert path in files
        content = files[path]
        assert "name: validate-and-test" in content
        assert "pytest" in content

    def test_broad_applicability_not_routed_to_skills(self, builder: ClaimBuilder) -> None:
        """Claims with ['all'] applicability passed to skills adapter still get grouped."""
        # Note: the Claude adapter decides what goes to skills; the skills adapter
        # just processes whatever it receives. But if given broad claims, they go to "general".
        claims = [
            builder.build(
                content="Use snake_case",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=1.0,
                applicability=("all",),
            ),
            builder.build(
                content="Use docstrings",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=1.0,
                applicability=("all",),
            ),
        ]

        files, descriptors = project_skills(claims)

        # These have "all" applicability → grouped under "general"
        assert len(files) == 1
        assert descriptors[0].name == "general"

    def test_multiple_applicability_groups(self, builder: ClaimBuilder) -> None:
        """Multiple applicability groups → multiple skills."""
        claims = [
            builder.build(
                content="Run pytest for unit tests",
                claim_type=ClaimType.VALIDATED_COMMAND,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("testing",),
            ),
            builder.build(
                content="Tests in tests/ directory",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.INFERRED_HIGH,
                confidence=0.95,
                applicability=("testing",),
            ),
            builder.build(
                content="Run npm audit for security",
                claim_type=ClaimType.VALIDATED_COMMAND,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("security",),
            ),
            builder.build(
                content="Security scan required before merge",
                claim_type=ClaimType.PERMISSION_RESTRICTION,
                source_authority=SourceAuthority.CI_OBSERVED,
                confidence=0.9,
                applicability=("security",),
            ),
        ]
        claims[0] = replace(claims[0], risk_class=RiskClass.TEST_EXECUTION)
        claims[2] = replace(claims[2], risk_class=RiskClass.SAFE_READONLY)

        files, descriptors = project_skills(claims)

        assert len(files) == 2
        skill_names = {d.name for d in descriptors}
        assert "validate-and-test" in skill_names
        assert "security-checks" in skill_names

    def test_single_low_value_claim_no_skill(self, builder: ClaimBuilder) -> None:
        """Single low-value claim in a group → no skill generated."""
        claims = [
            builder.build(
                content="Minor convention",
                claim_type=ClaimType.SCOPED_RULE,
                source_authority=SourceAuthority.INFERRED_LOW,
                confidence=0.7,
                applicability=("testing",),
            ),
        ]

        files, descriptors = project_skills(claims)

        assert len(files) == 0
        assert len(descriptors) == 0

    def test_skill_name_validation(self, builder: ClaimBuilder) -> None:
        """Skill name: max 64 chars, lowercase-hyphens only."""
        claims = [
            builder.build(
                content="Claim A",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("testing",),
            ),
            builder.build(
                content="Claim B",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("testing",),
            ),
        ]

        _, descriptors = project_skills(claims)

        for desc in descriptors:
            assert len(desc.name) <= 64
            assert re.match(r"^[a-z][a-z0-9-]*$", desc.name)

    def test_skill_body_size_limit(self, builder: ClaimBuilder) -> None:
        """Skill body size: verify < 5000 tokens (approximate by char count)."""
        # Create many claims to test body truncation
        claims = [
            builder.build(
                content=f"Very long claim content for testing body size limits #{i} " * 50,
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("testing",),
            )
            for i in range(50)
        ]

        files, _ = project_skills(claims)

        for content in files.values():
            # Body is everything after the frontmatter
            parts = content.split("---", 2)
            body = parts[2] if len(parts) > 2 else content
            assert len(body) <= MAX_BODY_CHARS + 100  # Allow some header overhead

    def test_skill_format_valid_frontmatter(self, builder: ClaimBuilder) -> None:
        """Skill format: valid frontmatter with name and description."""
        claims = [
            builder.build(
                content="Run linter",
                claim_type=ClaimType.VALIDATED_COMMAND,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("lint",),
            ),
            builder.build(
                content="Format code",
                claim_type=ClaimType.VALIDATED_COMMAND,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("format",),
            ),
        ]

        files, _descriptors = project_skills(claims)

        assert len(files) >= 1
        for content in files.values():
            assert content.startswith("---\n")
            assert "name: " in content
            assert "description: " in content

    def test_empty_claims_no_skills(self, builder: ClaimBuilder) -> None:
        """Empty claims → no skills generated."""
        files, descriptors = project_skills([])

        assert files == {}
        assert descriptors == []

    def test_path_prefix_customization(self, builder: ClaimBuilder) -> None:
        """Path prefix is customizable for different hosts."""
        claims = [
            builder.build(
                content="Test A",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("testing",),
            ),
            builder.build(
                content="Test B",
                claim_type=ClaimType.ALWAYS_ON_RULE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("testing",),
            ),
        ]

        files, _ = project_skills(claims, path_prefix=".agents/skills")

        for path in files:
            assert path.startswith(".agents/skills/")
