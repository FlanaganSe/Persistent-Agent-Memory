"""Tests for RkpConfig."""

from __future__ import annotations

from pathlib import Path

from rkp.core.config import RkpConfig


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
