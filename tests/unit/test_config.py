"""Tests for RkpConfig."""

from __future__ import annotations

from pathlib import Path

from rkp.core.config import RkpConfig, is_excluded_path, load_repo_config


class TestRkpConfig:
    def test_defaults(self) -> None:
        config = RkpConfig()
        assert config.repo_root == Path()
        assert config.db_path == Path(".rkp/local/rkp.db")
        assert config.log_level == "INFO"
        assert config.staleness_window_days == 90
        assert config.max_file_size_bytes == 1_000_000

    def test_excluded_dirs_defaults(self) -> None:
        config = RkpConfig()
        assert "node_modules" in config.excluded_dirs
        assert "__pycache__" in config.excluded_dirs
        assert ".git" in config.excluded_dirs

    def test_override_via_constructor(self) -> None:
        config = RkpConfig(log_level="DEBUG", staleness_window_days=30)
        assert config.log_level == "DEBUG"
        assert config.staleness_window_days == 30

    def test_env_prefix(self, monkeypatch: object) -> None:
        """Config reads from RKP_-prefixed environment variables."""
        import os

        os.environ["RKP_LOG_LEVEL"] = "WARNING"
        try:
            config = RkpConfig()
            assert config.log_level == "WARNING"
        finally:
            del os.environ["RKP_LOG_LEVEL"]

    def test_load_repo_config_reads_checked_in_fields(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        config_dir = repo / ".rkp"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text(
            "thresholds:\n"
            "  staleness_days: 45\n"
            "discovery:\n"
            "  exclude_dirs:\n"
            "    - tests/fixtures\n"
            "    - dist\n",
            encoding="utf-8",
        )

        loaded = load_repo_config(repo)

        assert loaded.staleness_window_days == 45
        assert loaded.excluded_dirs == ("tests/fixtures", "dist")

    def test_load_repo_config_ignores_unknown_sections(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        config_dir = repo / ".rkp"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text(
            "support_envelope:\n  languages: [Python]\ncustom:\n  foo: bar\n",
            encoding="utf-8",
        )

        loaded = load_repo_config(repo)

        assert loaded.staleness_window_days == 90
        assert "node_modules" in loaded.excluded_dirs


class TestExcludedPaths:
    def test_simple_dir_name_matches_any_segment(self) -> None:
        assert is_excluded_path(Path("src/dist/app.py"), ("dist",))

    def test_nested_relative_path_matches_prefix(self) -> None:
        assert is_excluded_path(Path("tests/fixtures/simple_python/app.py"), ("tests/fixtures",))

    def test_non_matching_path_is_allowed(self) -> None:
        assert not is_excluded_path(Path("src/app.py"), ("tests/fixtures", "dist"))
