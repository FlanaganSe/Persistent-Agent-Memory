"""Tests for copilot-setup-steps.yml generation."""

from __future__ import annotations

from dataclasses import replace

import yaml

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.types import ClaimType, SourceAuthority
from rkp.projection.adapters.copilot import generate_setup_steps


class TestSetupStepsGeneration:
    def test_python_only_repo(self, builder: ClaimBuilder) -> None:
        """Python-only repo generates setup-python step with correct version."""
        claims = [
            builder.build(
                content="Python 3.12",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                evidence=(".python-version",),
            ),
        ]

        content, errors = generate_setup_steps(claims, repo="test", head="abc", branch="main")

        assert len(errors) == 0
        parsed = yaml.safe_load(content)
        assert parsed is not None

        steps = parsed["jobs"]["copilot-setup-steps"]["steps"]
        # Should have checkout + setup-python
        uses_list = [s.get("uses", "") for s in steps]
        assert any("setup-python" in u for u in uses_list)

        # Check version is set
        for step in steps:
            if "setup-python" in step.get("uses", ""):
                assert step.get("with", {}).get("python-version") == "3.12"

    def test_node_only_repo(self, builder: ClaimBuilder) -> None:
        """Node-only repo generates setup-node step."""
        claims = [
            builder.build(
                content="Node.js 20",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                evidence=(".nvmrc",),
            ),
        ]

        content, errors = generate_setup_steps(claims)

        assert len(errors) == 0
        parsed = yaml.safe_load(content)
        steps = parsed["jobs"]["copilot-setup-steps"]["steps"]
        uses_list = [s.get("uses", "") for s in steps]
        assert any("setup-node" in u for u in uses_list)

    def test_python_and_node_repo(self, builder: ClaimBuilder) -> None:
        """Repo with both Python and Node generates both setup steps."""
        claims = [
            builder.build(
                content="Python 3.12",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
            builder.build(
                content="Node.js 20",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
        ]

        content, errors = generate_setup_steps(claims)

        assert len(errors) == 0
        parsed = yaml.safe_load(content)
        steps = parsed["jobs"]["copilot-setup-steps"]["steps"]
        uses_list = [s.get("uses", "") for s in steps]
        assert any("setup-python" in u for u in uses_list)
        assert any("setup-node" in u for u in uses_list)

    def test_no_environment_profiles(self, builder: ClaimBuilder) -> None:
        """No environment profiles → minimal setup (checkout only)."""
        claims = [
            replace(
                builder.build(
                    content="pytest",
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                    confidence=1.0,
                ),
            ),
        ]

        content, errors = generate_setup_steps(claims)

        assert len(errors) == 0
        parsed = yaml.safe_load(content)
        steps = parsed["jobs"]["copilot-setup-steps"]["steps"]
        # Should have at least checkout
        assert any("checkout" in s.get("uses", "") for s in steps)

    def test_generated_yaml_is_valid(self, builder: ClaimBuilder) -> None:
        """Generated YAML can be parsed with yaml.safe_load."""
        claims = [
            builder.build(
                content="Python 3.12",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
        ]

        content, errors = generate_setup_steps(claims)

        assert len(errors) == 0
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)
        assert "jobs" in parsed

    def test_constraint_compliance(self, builder: ClaimBuilder) -> None:
        """Generated setup-steps comply with constraints."""
        claims = [
            builder.build(
                content="Python 3.12",
                claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
            ),
        ]

        content, errors = generate_setup_steps(claims)

        assert len(errors) == 0
        parsed = yaml.safe_load(content)

        # Single job named copilot-setup-steps
        assert len(parsed["jobs"]) == 1
        assert "copilot-setup-steps" in parsed["jobs"]

        # Timeout <= 59
        job = parsed["jobs"]["copilot-setup-steps"]
        assert job["timeout-minutes"] <= 59

    def test_setup_commands_included(self, builder: ClaimBuilder) -> None:
        """Setup commands from claims are included in steps."""
        claims = [
            builder.build(
                content='pip install -e ".[dev]"',
                claim_type=ClaimType.VALIDATED_COMMAND,
                source_authority=SourceAuthority.EXECUTABLE_CONFIG,
                confidence=1.0,
                applicability=("setup",),
            ),
        ]

        content, errors = generate_setup_steps(claims)

        assert len(errors) == 0
        parsed = yaml.safe_load(content)
        steps = parsed["jobs"]["copilot-setup-steps"]["steps"]
        run_cmds = [s.get("run", "") for s in steps]
        assert any("pip install" in cmd for cmd in run_cmds)

    def test_generation_header(self, builder: ClaimBuilder) -> None:
        """Generated YAML includes provenance header."""
        content, _ = generate_setup_steps([], repo="my-project", head="abc1234", branch="main")

        assert "Generated by RKP" in content
        assert "my-project" in content
        assert "abc1234" in content
