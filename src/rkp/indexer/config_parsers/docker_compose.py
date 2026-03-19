"""Parse docker-compose.yml for services and environment evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import structlog
import yaml

from rkp.core.security import validate_path

logger = structlog.get_logger()


@dataclass(frozen=True)
class ComposeService:
    """A service extracted from docker-compose."""

    name: str
    image: str | None
    env_var_names: tuple[str, ...]
    ports: tuple[str, ...]
    depends_on: tuple[str, ...]
    volumes: tuple[str, ...]


@dataclass(frozen=True)
class ParsedComposeFile:
    """Structured output from parsing docker-compose.yml."""

    services: tuple[ComposeService, ...]
    source_file: str = "docker-compose.yml"


def _as_dict(val: object) -> dict[str, Any] | None:
    """Safely cast a value to dict[str, Any] if it is a dict."""
    if isinstance(val, dict):
        return cast(dict[str, Any], val)
    return None


def _as_list(val: object) -> list[Any] | None:
    """Safely cast a value to list[Any] if it is a list."""
    if isinstance(val, list):
        return cast(list[Any], val)
    return None


def _extract_env_names(env: object) -> list[str]:
    """Extract environment variable names (never values) from various formats."""
    names: list[str] = []
    d = _as_dict(env)
    if d is not None:
        names.extend(str(k) for k in d)
        return names
    lst = _as_list(env)
    if lst is not None:
        names.extend(str(item).split("=")[0] for item in lst if isinstance(item, str))
    return names


def _extract_service(name: str, config: dict[str, Any]) -> ComposeService:
    """Extract structured data from a single service definition."""
    image = config.get("image")
    image_str = str(image) if isinstance(image, str) else None

    env_var_names = _extract_env_names(config.get("environment"))

    ports: list[str] = []
    raw_ports = _as_list(config.get("ports"))
    if raw_ports is not None:
        ports = [str(p) for p in raw_ports]

    depends_on: list[str] = []
    raw_depends = config.get("depends_on")
    depends_list = _as_list(raw_depends)
    depends_dict = _as_dict(raw_depends)
    if depends_list is not None:
        depends_on = [str(d) for d in depends_list]
    elif depends_dict is not None:
        depends_on = list(depends_dict.keys())

    volumes: list[str] = []
    raw_volumes = _as_list(config.get("volumes"))
    if raw_volumes is not None:
        volumes = [str(v) for v in raw_volumes]

    return ComposeService(
        name=name,
        image=image_str,
        env_var_names=tuple(env_var_names),
        ports=tuple(ports),
        depends_on=tuple(depends_on),
        volumes=tuple(volumes),
    )


def parse_docker_compose(
    repo_root: Path,
    relative_path: str = "docker-compose.yml",
) -> ParsedComposeFile:
    """Parse a docker-compose file and extract service definitions.

    Uses yaml.safe_load() — NEVER yaml.load().
    Returns empty result if file is missing or malformed.
    """
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        logger.warning("docker-compose path validation failed", path=relative_path)
        return ParsedComposeFile(services=())

    if not file_path.is_file():
        return ParsedComposeFile(services=())

    try:
        content = file_path.read_text(encoding="utf-8")
        raw_data: object = yaml.safe_load(content)
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Failed to parse docker-compose", error=str(exc))
        return ParsedComposeFile(services=())

    data = _as_dict(raw_data)
    if data is None:
        return ParsedComposeFile(services=())

    raw_services = _as_dict(data.get("services"))
    if raw_services is None:
        return ParsedComposeFile(services=())

    services: list[ComposeService] = []
    for svc_name, svc_config_raw in raw_services.items():
        svc_config = _as_dict(svc_config_raw)
        if svc_config is not None:
            services.append(_extract_service(str(svc_name), svc_config))

    return ParsedComposeFile(
        services=tuple(services),
        source_file=relative_path,
    )
