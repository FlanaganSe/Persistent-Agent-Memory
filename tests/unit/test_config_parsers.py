"""Tests for config parsers: pyproject.toml and package.json."""

from __future__ import annotations

from pathlib import Path

from rkp.core.types import RiskClass
from rkp.indexer.config_parsers.package_json import parse_package_json
from rkp.indexer.config_parsers.pyproject import parse_pyproject


class TestPyprojectParser:
    def test_parse_minimal(self, tmp_path: Path) -> None:
        """Minimal pyproject.toml with just project metadata."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nrequires-python = ">=3.12"\n'
        )
        result = parse_pyproject(tmp_path)
        assert result.project_name == "test"
        assert result.python_requires == ">=3.12"
        assert len(result.commands) == 0

    def test_parse_with_scripts(self, tmp_path: Path) -> None:
        """Extract commands from [project.scripts]."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\n\n[project.scripts]\nmyapp = "myapp.main:run"\n'
        )
        result = parse_pyproject(tmp_path)
        assert len(result.commands) == 1
        assert result.commands[0].name == "myapp"
        assert result.commands[0].command == "myapp.main:run"

    def test_parse_with_tool_configs(self, tmp_path: Path) -> None:
        """Detect tools from [tool.*] sections."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\n\n[tool.ruff]\nline-length = 88\n\n'
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        )
        result = parse_pyproject(tmp_path)
        assert "ruff" in result.tools_detected
        assert "pytest" in result.tools_detected
        # pytest config implies a test command
        pytest_cmds = [c for c in result.commands if c.name == "pytest"]
        assert len(pytest_cmds) == 1
        assert pytest_cmds[0].risk_class == RiskClass.TEST_EXECUTION

    def test_parse_hatch_scripts(self, tmp_path: Path) -> None:
        """Extract commands from [tool.hatch.envs.*.scripts]."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\n\n'
            '[tool.hatch.envs.default.scripts]\ntest = "pytest"\n'
            'lint = "ruff check ."\n'
        )
        result = parse_pyproject(tmp_path)
        names = [c.name for c in result.commands]
        assert "hatch:default:test" in names
        assert "hatch:default:lint" in names

    def test_parse_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns empty result, not error."""
        result = parse_pyproject(tmp_path)
        assert len(result.commands) == 0
        assert result.project_name is None

    def test_parse_malformed_file(self, tmp_path: Path) -> None:
        """Malformed TOML returns empty result, not error."""
        (tmp_path / "pyproject.toml").write_text("this is not valid toml [[[")
        result = parse_pyproject(tmp_path)
        assert len(result.commands) == 0

    def test_risk_classification(self, tmp_path: Path) -> None:
        """Commands get correct risk classification."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\n\n[project.scripts]\n'
            'test-runner = "pytest"\n'
            'lint-check = "ruff check"\n'
            'build-app = "python -m build"\n'
            'deploy-prod = "deploy.sh"\n'
        )
        result = parse_pyproject(tmp_path)
        by_name = {c.name: c for c in result.commands}
        assert by_name["test-runner"].risk_class == RiskClass.TEST_EXECUTION
        assert by_name["lint-check"].risk_class == RiskClass.SAFE_READONLY
        assert by_name["build-app"].risk_class == RiskClass.BUILD
        assert by_name["deploy-prod"].risk_class == RiskClass.DESTRUCTIVE

    def test_fixture_repo(self) -> None:
        """Parse the simple_python fixture repo."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "simple_python"
        result = parse_pyproject(fixture_path)
        assert result.project_name == "simple-python-project"
        assert result.python_requires == ">=3.12"
        assert len(result.commands) >= 1


class TestPackageJsonParser:
    def test_parse_with_scripts(self, tmp_path: Path) -> None:
        """Extract commands from scripts."""
        (tmp_path / "package.json").write_text(
            '{"name": "test-app", "scripts": {"test": "jest", "build": "webpack"}}'
        )
        result = parse_package_json(tmp_path)
        assert result.project_name == "test-app"
        assert len(result.commands) == 2
        by_name = {c.name: c for c in result.commands}
        assert by_name["test"].risk_class == RiskClass.TEST_EXECUTION
        assert by_name["build"].risk_class == RiskClass.BUILD

    def test_parse_with_engines(self, tmp_path: Path) -> None:
        """Extract engines metadata."""
        (tmp_path / "package.json").write_text('{"name": "test", "engines": {"node": ">=18"}}')
        result = parse_package_json(tmp_path)
        assert result.engines is not None
        assert result.engines["node"] == ">=18"

    def test_parse_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns empty result."""
        result = parse_package_json(tmp_path)
        assert len(result.commands) == 0

    def test_parse_malformed_file(self, tmp_path: Path) -> None:
        """Malformed JSON returns empty result."""
        (tmp_path / "package.json").write_text("{not valid json")
        result = parse_package_json(tmp_path)
        assert len(result.commands) == 0

    def test_risk_classification(self, tmp_path: Path) -> None:
        """Scripts get correct risk classification."""
        (tmp_path / "package.json").write_text(
            '{"scripts": {"test": "jest", "lint": "eslint .",'
            ' "format": "prettier --write .", "deploy": "deploy.sh",'
            ' "dev": "next dev"}}'
        )
        result = parse_package_json(tmp_path)
        by_name = {c.name: c for c in result.commands}
        assert by_name["test"].risk_class == RiskClass.TEST_EXECUTION
        assert by_name["lint"].risk_class == RiskClass.SAFE_READONLY
        assert by_name["format"].risk_class == RiskClass.SAFE_MUTATING
        assert by_name["deploy"].risk_class == RiskClass.DESTRUCTIVE
        assert by_name["dev"].risk_class == RiskClass.BUILD
