"""Tests for the prerequisite extractor."""

from __future__ import annotations

from rkp.core.types import ClaimType, EvidenceLevel, SourceAuthority
from rkp.indexer.config_parsers.docker_compose import ComposeService, ParsedComposeFile
from rkp.indexer.config_parsers.github_actions import (
    CIServiceEvidence,
    ParsedWorkflow,
    ParsedWorkflowJob,
)
from rkp.indexer.config_parsers.pyproject import PyprojectResult
from rkp.indexer.config_parsers.version_files import RuntimeVersionHint, VersionFilesResult
from rkp.indexer.extractors.prerequisites import extract_prerequisites


class TestPrerequisites:
    def test_python_runtime(self) -> None:
        """pyproject requires-python produces a runtime prerequisite."""
        pyproject = PyprojectResult(
            commands=(),
            python_requires=">=3.12",
            project_name="test",
        )
        result = extract_prerequisites(pyproject=pyproject, repo_id="test")
        runtime_claims = [c for c in result.claims if c.prerequisite_type == "runtime"]
        assert len(runtime_claims) >= 1
        py_claim = next(c for c in runtime_claims if "Python" in c.content)
        assert ">=3.12" in py_claim.content
        assert py_claim.claim_type == ClaimType.ENVIRONMENT_PREREQUISITE
        assert py_claim.source_authority == SourceAuthority.EXECUTABLE_CONFIG
        assert py_claim.confidence == 1.0

    def test_node_engines(self) -> None:
        """package.json engines produce runtime prerequisites."""
        result = extract_prerequisites(
            pkg_engines={"node": ">=18"},
            repo_id="test",
        )
        runtime_claims = [c for c in result.claims if c.prerequisite_type == "runtime"]
        assert len(runtime_claims) >= 1
        node_claim = next(c for c in runtime_claims if "node" in c.content)
        assert ">=18" in node_claim.content
        assert node_claim.evidence_level == EvidenceLevel.PREREQUISITES_EXTRACTED

    def test_services_from_compose(self) -> None:
        """docker-compose services produce service prerequisites."""
        compose = ParsedComposeFile(
            services=(
                ComposeService(
                    name="db",
                    image="postgres:15",
                    env_var_names=(),
                    ports=("5432:5432",),
                    depends_on=(),
                    volumes=(),
                ),
                ComposeService(
                    name="redis",
                    image="redis:7",
                    env_var_names=(),
                    ports=("6379:6379",),
                    depends_on=(),
                    volumes=(),
                ),
            ),
        )
        result = extract_prerequisites(compose_files=[compose], repo_id="test")
        svc_claims = [c for c in result.claims if c.prerequisite_type == "service"]
        assert len(svc_claims) == 2
        contents = {c.content for c in svc_claims}
        assert "Service: postgres:15" in contents
        assert "Service: redis:7" in contents

    def test_services_from_ci(self) -> None:
        """CI job services produce service prerequisites."""
        job = ParsedWorkflowJob(
            name="test",
            runs_on="ubuntu-latest",
            commands=(),
            runtimes=(),
            services=(
                CIServiceEvidence(
                    name="postgres",
                    image="postgres:15",
                    env_var_names=(),
                    ports=("5432:5432",),
                ),
            ),
            env_var_names=(),
            matrix_dimensions={},
        )
        workflow = ParsedWorkflow(
            name="CI",
            triggers=("push",),
            jobs=(job,),
            env_var_names=(),
            source_file=".github/workflows/ci.yml",
        )
        result = extract_prerequisites(workflows=[workflow], repo_id="test")
        svc_claims = [c for c in result.claims if c.prerequisite_type == "service"]
        assert len(svc_claims) >= 1
        assert any("postgres:15" in c.content for c in svc_claims)
        assert svc_claims[0].source_authority == SourceAuthority.CI_OBSERVED

    def test_env_vars(self) -> None:
        """Env var names from workflows and Dockerfiles produce env-var prerequisites."""
        job = ParsedWorkflowJob(
            name="test",
            runs_on="ubuntu-latest",
            commands=(),
            runtimes=(),
            services=(),
            env_var_names=("DATABASE_URL", "SECRET_KEY"),
            matrix_dimensions={},
        )
        workflow = ParsedWorkflow(
            name="CI",
            triggers=("push",),
            jobs=(job,),
            env_var_names=("CI",),
            source_file=".github/workflows/ci.yml",
        )
        result = extract_prerequisites(workflows=[workflow], repo_id="test")
        env_claims = [c for c in result.claims if c.prerequisite_type == "env-var"]
        env_contents = {c.content for c in env_claims}
        assert "Env: CI" in env_contents
        assert "Env: DATABASE_URL" in env_contents
        assert "Env: SECRET_KEY" in env_contents

    def test_os_requirements(self) -> None:
        """runs-on values from CI produce OS prerequisites."""
        job = ParsedWorkflowJob(
            name="test",
            runs_on="ubuntu-latest",
            commands=(),
            runtimes=(),
            services=(),
            env_var_names=(),
            matrix_dimensions={},
        )
        workflow = ParsedWorkflow(
            name="CI",
            triggers=("push",),
            jobs=(job,),
            env_var_names=(),
            source_file=".github/workflows/ci.yml",
        )
        result = extract_prerequisites(workflows=[workflow], repo_id="test")
        os_claims = [c for c in result.claims if c.prerequisite_type == "os"]
        assert len(os_claims) >= 1
        assert os_claims[0].content == "OS: ubuntu-latest"

    def test_version_files(self) -> None:
        """.python-version produces a runtime prerequisite."""
        vf = VersionFilesResult(
            hints=(
                RuntimeVersionHint(
                    runtime="Python",
                    version="3.12",
                    source_file=".python-version",
                ),
            ),
        )
        result = extract_prerequisites(version_files=vf, repo_id="test")
        runtime_claims = [c for c in result.claims if c.prerequisite_type == "runtime"]
        assert len(runtime_claims) >= 1
        py_claim = next(c for c in runtime_claims if "Python" in c.content)
        assert py_claim.content == "Python 3.12"
        assert py_claim.confidence == 0.95

    def test_environment_profile_created(self) -> None:
        """Prerequisites aggregate into at least one environment profile."""
        pyproject = PyprojectResult(
            commands=(),
            python_requires=">=3.12",
            project_name="test",
        )
        compose = ParsedComposeFile(
            services=(
                ComposeService(
                    name="db",
                    image="postgres:15",
                    env_var_names=(),
                    ports=(),
                    depends_on=(),
                    volumes=(),
                ),
            ),
        )
        result = extract_prerequisites(
            pyproject=pyproject,
            compose_files=[compose],
            repo_id="test",
        )
        assert len(result.profiles) >= 1
        profile = result.profiles[0]
        assert profile.repo_id == "test"
        assert profile.runtime is not None
        assert "Python" in profile.runtime
        assert len(profile.services) >= 1

    def test_empty_inputs(self) -> None:
        """No sources produce empty result."""
        result = extract_prerequisites(repo_id="test")
        assert result.claims == ()
        assert result.profiles == ()
