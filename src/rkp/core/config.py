"""RKP configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class RkpConfig(BaseSettings):
    """Configuration for the Repo Knowledge Plane."""

    model_config = SettingsConfigDict(env_prefix="RKP_")

    repo_root: Path = Path()
    db_path: Path = Path(".rkp/local/rkp.db")
    log_level: str = "INFO"
    staleness_window_days: int = 90
    max_file_size_bytes: int = 1_000_000
    excluded_dirs: tuple[str, ...] = (
        "vendor",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".git",
    )
