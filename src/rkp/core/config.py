"""RKP configuration via pydantic-settings and checked-in repo config."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import structlog
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from rkp.core.security import safe_yaml_load

logger = structlog.get_logger()


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
    confidence_reduction_on_stale: float = 0.2
    trace_enabled: bool = True
    source_allowlist: SourceAllowlist = SourceAllowlist()


def load_repo_config(
    repo_root: Path,
    *,
    base: RkpConfig | None = None,
) -> RkpConfig:
    """Load repo-local configuration from ``.rkp/config.yaml`` if present.

    The checked-in file currently supports a deliberately small, low-risk surface:
    - ``thresholds.staleness_days`` → ``staleness_window_days``
    - ``discovery.exclude_dirs`` → ``excluded_dirs``

    Unknown keys are ignored so the repo can carry informational sections
    without breaking CLI startup.
    """
    repo_root = repo_root.resolve()
    config = base or RkpConfig(
        repo_root=repo_root,
        db_path=repo_root / ".rkp" / "local" / "rkp.db",
    )
    config_path = repo_root / ".rkp" / "config.yaml"

    if not config_path.is_file():
        return config

    try:
        raw = safe_yaml_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load repo config", path=str(config_path), error=str(exc))
        return config

    if not isinstance(raw, dict):
        logger.warning("Repo config must be a mapping", path=str(config_path))
        return config

    config_data = cast(dict[str, object], raw)
    updates: dict[str, object] = {}

    thresholds = config_data.get("thresholds")
    if isinstance(thresholds, dict):
        threshold_data = cast(dict[str, object], thresholds)
        staleness_days = threshold_data.get("staleness_days")
        if isinstance(staleness_days, int | float) and int(staleness_days) > 0:
            updates["staleness_window_days"] = int(staleness_days)

    discovery = config_data.get("discovery")
    if isinstance(discovery, dict):
        discovery_data = cast(dict[str, object], discovery)
        exclude_dirs = discovery_data.get("exclude_dirs")
        if isinstance(exclude_dirs, list):
            normalized_items: list[str] = []
            for item in cast(list[object], exclude_dirs):
                normalized_item = str(item).strip().strip("/").replace("\\", "/")
                if normalized_item:
                    normalized_items.append(normalized_item)
            normalized = tuple(normalized_items)
            if normalized:
                updates["excluded_dirs"] = tuple(dict.fromkeys(normalized))

    if not updates:
        return config

    return config.model_copy(update=updates)


def is_excluded_path(path: Path, excluded_dirs: tuple[str, ...]) -> bool:
    """Return True if ``path`` matches any configured exclusion.

    Supports both simple directory names (``dist``) and nested relative paths
    (``tests/fixtures``).
    """
    rel = str(path).replace("\\", "/").strip("/")
    parts = path.parts

    for raw_pattern in excluded_dirs:
        pattern = raw_pattern.strip().strip("/").replace("\\", "/")
        if not pattern:
            continue
        if "/" in pattern:
            if rel == pattern or rel.startswith(f"{pattern}/"):
                return True
            continue
        if pattern in parts:
            return True

    return False
