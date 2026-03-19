"""RKP configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourceAllowlist(BaseModel):
    """Configurable trust boundary for which sources influence claims.

    Controls which file types, directories, and evidence sources may
    appear in MCP query results. Default: everything allowed (backward
    compatible).
    """

    allowed_file_types: tuple[str, ...] = (
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".toml",
        ".json",
        ".yml",
        ".yaml",
        ".md",
        "Makefile",
        "Dockerfile",
    )
    allowed_directories: tuple[str, ...] = ("**",)
    excluded_directories: tuple[str, ...] = (
        "vendor/",
        "node_modules/",
        "dist/",
        "build/",
        "__pycache__/",
        ".git/",
    )
    trusted_evidence_sources: tuple[str, ...] = (
        "human-override",
        "declared-reviewed",
        "executable-config",
        "ci-observed",
        "declared-imported-unreviewed",
        "checked-in-docs",
        "inferred-high",
        "inferred-low",
    )


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
    source_allowlist: SourceAllowlist = SourceAllowlist()
