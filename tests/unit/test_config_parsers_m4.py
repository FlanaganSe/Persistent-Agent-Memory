"""Tests for M4 config parsers: makefile, dockerfile, docker_compose, github_actions, version_files."""

from __future__ import annotations

from pathlib import Path

from rkp.core.types import RiskClass
from rkp.indexer.config_parsers.docker_compose import parse_docker_compose
from rkp.indexer.config_parsers.dockerfile import parse_dockerfile
from rkp.indexer.config_parsers.github_actions import (
    CIConfidence,
    discover_workflow_files,
    parse_github_actions_workflow,
)
from rkp.indexer.config_parsers.makefile import parse_makefile
from rkp.indexer.config_parsers.version_files import parse_version_files


class TestMakefileParser:
    def test_extract_targets(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("test:\n\tpytest tests/\n\nlint:\n\truff check src/\n")
        result = parse_makefile(tmp_path)
        assert len(result.commands) == 2
        names = {c.name for c in result.commands}
        assert "test" in names
        assert "lint" in names
        # Command text should be "make <target>"
        test_cmd = next(c for c in result.commands if c.name == "test")
        assert test_cmd.command == "make test"

    def test_risk_classification(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text(
            "test:\n\tpytest\n\nlint:\n\truff check\n\n"
            "build:\n\tpython -m build\n\nclean:\n\trm -rf dist/\n"
        )
        result = parse_makefile(tmp_path)
        by_name = {c.name: c for c in result.commands}
        assert by_name["test"].risk_class == RiskClass.TEST_EXECUTION
        assert by_name["lint"].risk_class == RiskClass.SAFE_READONLY
        assert by_name["build"].risk_class == RiskClass.BUILD
        assert by_name["clean"].risk_class == RiskClass.DESTRUCTIVE

    def test_phony_targets(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text(
            ".PHONY: test lint\n\ntest:\n\tpytest\n\nlint:\n\truff check\n"
        )
        result = parse_makefile(tmp_path)
        # .PHONY line itself should be skipped (starts with .)
        names = {c.name for c in result.commands}
        assert ".PHONY" not in names
        # Real targets should still be found
        assert "test" in names
        assert "lint" in names

    def test_missing_file(self, tmp_path: Path) -> None:
        result = parse_makefile(tmp_path)
        assert result.commands == ()


class TestDockerfileParser:
    def test_extract_base_image(self, tmp_path: Path) -> None:
        (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim\nRUN pip install poetry\n")
        result = parse_dockerfile(tmp_path)
        assert "python:3.12-slim" in result.base_images
        assert len(result.runtime_hints) >= 1
        assert any("Python" in h for h in result.runtime_hints)

    def test_extract_env_names(self, tmp_path: Path) -> None:
        # Use space-separated form (ENV KEY VALUE) so the regex captures just the name
        (tmp_path / "Dockerfile").write_text(
            "FROM python:3.12\nENV FOO bar\nENV DATABASE_URL postgres://...\n"
        )
        result = parse_dockerfile(tmp_path)
        assert "FOO" in result.env_var_names
        assert "DATABASE_URL" in result.env_var_names

    def test_extract_exposed_ports(self, tmp_path: Path) -> None:
        (tmp_path / "Dockerfile").write_text("FROM python:3.12\nEXPOSE 8080\nEXPOSE 443/tcp\n")
        result = parse_dockerfile(tmp_path)
        assert "8080" in result.exposed_ports
        assert "443" in result.exposed_ports

    def test_extract_tool_installs(self, tmp_path: Path) -> None:
        (tmp_path / "Dockerfile").write_text(
            "FROM ubuntu:22.04\nRUN apt-get install -y git curl wget\n"
        )
        result = parse_dockerfile(tmp_path)
        assert "git" in result.tool_installs
        assert "curl" in result.tool_installs
        assert "wget" in result.tool_installs

    def test_missing_file(self, tmp_path: Path) -> None:
        result = parse_dockerfile(tmp_path)
        assert result.base_images == ()
        assert result.runtime_hints == ()
        assert result.tool_installs == ()
        assert result.env_var_names == ()
        assert result.exposed_ports == ()


class TestDockerComposeParser:
    def test_extract_services(self, tmp_path: Path) -> None:
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n"
            "  web:\n"
            "    image: myapp:latest\n"
            "    ports:\n"
            "      - '8080:8080'\n"
            "    depends_on:\n"
            "      - db\n"
            "  db:\n"
            "    image: postgres:15\n"
            "    ports:\n"
            "      - '5432:5432'\n"
        )
        result = parse_docker_compose(tmp_path)
        assert len(result.services) == 2
        svc_names = {s.name for s in result.services}
        assert "web" in svc_names
        assert "db" in svc_names

        web = next(s for s in result.services if s.name == "web")
        assert web.image == "myapp:latest"
        assert "8080:8080" in web.ports
        assert "db" in web.depends_on

        db = next(s for s in result.services if s.name == "db")
        assert db.image == "postgres:15"

    def test_extract_env_var_names(self, tmp_path: Path) -> None:
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n"
            "  app:\n"
            "    image: myapp\n"
            "    environment:\n"
            "      DATABASE_URL: postgres://...\n"
            "      SECRET_KEY: supersecret\n"
        )
        result = parse_docker_compose(tmp_path)
        assert len(result.services) == 1
        app = result.services[0]
        assert "DATABASE_URL" in app.env_var_names
        assert "SECRET_KEY" in app.env_var_names

    def test_missing_file(self, tmp_path: Path) -> None:
        result = parse_docker_compose(tmp_path)
        assert result.services == ()


class TestGitHubActionsParser:
    def test_extract_commands(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - name: Run tests\n"
            "        run: pytest tests/\n"
            "      - name: Run lint\n"
            "        run: ruff check src/\n"
        )
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        assert len(result.jobs) == 1
        job = result.jobs[0]
        assert len(job.commands) >= 2
        cmd_texts = {c.command for c in job.commands}
        assert "pytest tests/" in cmd_texts
        assert "ruff check src/" in cmd_texts

    def test_extract_setup_runtimes(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/setup-python@v5\n"
            "        with:\n"
            "          python-version: '3.12'\n"
        )
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        job = result.jobs[0]
        assert len(job.runtimes) >= 1
        rt = job.runtimes[0]
        assert rt.runtime == "python"
        assert "3.12" in rt.versions

    def test_extract_services(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    services:\n"
            "      redis:\n"
            "        image: redis:7\n"
            "        ports:\n"
            "          - 6379:6379\n"
            "    steps:\n"
            "      - run: echo hi\n"
        )
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        job = result.jobs[0]
        assert len(job.services) == 1
        svc = job.services[0]
        assert svc.name == "redis"
        assert svc.image == "redis:7"
        assert "6379:6379" in svc.ports

    def test_confidence_levels(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Unconditional\n"
            "        run: pytest\n"
            "      - name: Conditional\n"
            "        if: github.ref == 'refs/heads/main'\n"
            "        run: deploy.sh\n"
            "      - name: Fragile\n"
            "        run: optional-check\n"
            "        continue-on-error: true\n"
        )
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        job = result.jobs[0]
        by_name = {c.step_name: c for c in job.commands}
        assert by_name["Unconditional"].confidence == CIConfidence.HIGH
        assert by_name["Conditional"].confidence == CIConfidence.MEDIUM
        assert by_name["Fragile"].confidence == CIConfidence.LOW

    def test_matrix_resolution(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        # Use a matrix key without hyphens so _MATRIX_EXPR_RE (\w+) can match
        (wf_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    strategy:\n"
            "      matrix:\n"
            "        pyver: ['3.12', '3.13']\n"
            "    steps:\n"
            "      - uses: actions/setup-python@v5\n"
            "        with:\n"
            "          python-version: ${{ matrix.pyver }}\n"
            "      - run: pytest\n"
        )
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        job = result.jobs[0]
        assert "pyver" in job.matrix_dimensions
        assert "3.12" in job.matrix_dimensions["pyver"]
        assert "3.13" in job.matrix_dimensions["pyver"]
        # Runtimes should resolve the matrix expression
        assert len(job.runtimes) >= 1
        rt = job.runtimes[0]
        assert "3.12" in rt.versions
        assert "3.13" in rt.versions

    def test_matrix_hyphenated_key_resolved(self, tmp_path: Path) -> None:
        """Hyphenated matrix keys like python-version are resolved correctly."""
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    strategy:\n"
            "      matrix:\n"
            "        python-version: ['3.12', '3.13']\n"
            "    steps:\n"
            "      - uses: actions/setup-python@v5\n"
            "        with:\n"
            "          python-version: ${{ matrix.python-version }}\n"
            "      - run: pytest\n"
        )
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        job = result.jobs[0]
        assert "python-version" in job.matrix_dimensions
        assert len(job.runtimes) >= 1
        rt = job.runtimes[0]
        assert "3.12" in rt.versions
        assert "3.13" in rt.versions

    def test_env_var_extraction(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: push\n"
            "env:\n"
            "  CI: 'true'\n"
            "  NODE_ENV: production\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Test\n"
            "        run: pytest\n"
            "        env:\n"
            "          DATABASE_URL: postgres://...\n"
        )
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        # Workflow-level env vars
        assert "CI" in result.env_var_names
        assert "NODE_ENV" in result.env_var_names
        # Step-level env vars should be on the job
        job = result.jobs[0]
        assert "DATABASE_URL" in job.env_var_names

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("this is not: valid: yaml: [[[\n  broken\n")
        result = parse_github_actions_workflow(tmp_path, ".github/workflows/ci.yml")
        assert result.jobs == ()

    def test_discover_workflow_files(self, tmp_path: Path) -> None:
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("name: CI\non: push\njobs: {}\n")
        (wf_dir / "release.yaml").write_text("name: Release\non: push\njobs: {}\n")
        (wf_dir / "not-a-workflow.txt").write_text("ignore me")

        files = discover_workflow_files(tmp_path)
        assert len(files) == 2
        assert any("ci.yml" in f for f in files)
        assert any("release.yaml" in f for f in files)
        assert not any("not-a-workflow" in f for f in files)


class TestVersionFiles:
    def test_python_version(self, tmp_path: Path) -> None:
        (tmp_path / ".python-version").write_text("3.12\n")
        result = parse_version_files(tmp_path)
        assert len(result.hints) == 1
        hint = result.hints[0]
        assert hint.runtime == "Python"
        assert hint.version == "3.12"
        assert hint.source_file == ".python-version"

    def test_nvmrc(self, tmp_path: Path) -> None:
        (tmp_path / ".nvmrc").write_text("18\n")
        result = parse_version_files(tmp_path)
        assert len(result.hints) == 1
        hint = result.hints[0]
        assert hint.runtime == "Node.js"
        assert hint.version == "18"
        assert hint.source_file == ".nvmrc"

    def test_tool_versions(self, tmp_path: Path) -> None:
        (tmp_path / ".tool-versions").write_text("python 3.12.0\nnodejs 20.10.0\nruby 3.2.0\n")
        result = parse_version_files(tmp_path)
        assert len(result.hints) == 3
        runtimes = {h.runtime for h in result.hints}
        assert "Python" in runtimes
        assert "Node.js" in runtimes
        assert "Ruby" in runtimes

    def test_no_files(self, tmp_path: Path) -> None:
        result = parse_version_files(tmp_path)
        assert result.hints == ()
