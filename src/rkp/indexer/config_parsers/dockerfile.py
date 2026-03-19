"""Parse Dockerfile for environment prerequisites."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog

from rkp.core.security import validate_path

logger = structlog.get_logger()


@dataclass(frozen=True)
class ParsedDockerfile:
    """Structured output from parsing a Dockerfile."""

    base_images: tuple[str, ...]
    runtime_hints: tuple[str, ...]
    tool_installs: tuple[str, ...]
    env_var_names: tuple[str, ...]
    exposed_ports: tuple[str, ...]
    workdir: str | None = None
    source_file: str = "Dockerfile"


# Regex patterns for Dockerfile instructions.
_FROM_RE = re.compile(r"^FROM\s+(\S+)", re.IGNORECASE | re.MULTILINE)
_RUN_RE = re.compile(r"^RUN\s+(.+?)(?:\s*\\?\s*$)", re.IGNORECASE | re.MULTILINE)
_ENV_RE = re.compile(r"^ENV\s+(\S+)", re.IGNORECASE | re.MULTILINE)
_EXPOSE_RE = re.compile(r"^EXPOSE\s+(.+)$", re.IGNORECASE | re.MULTILINE)
_WORKDIR_RE = re.compile(r"^WORKDIR\s+(.+)$", re.IGNORECASE | re.MULTILINE)

# Runtime hints from base images.
_RUNTIME_PATTERNS: dict[str, str] = {
    "python": "Python",
    "node": "Node.js",
    "golang": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "openjdk": "Java",
    "eclipse-temurin": "Java",
    "amazoncorretto": "Java",
}


def _extract_runtime_hints(base_images: list[str]) -> list[str]:
    """Derive runtime hints from base image names."""
    hints: list[str] = []
    for image in base_images:
        # Strip registry prefix and get the image name
        image_name = image.split("/")[-1].split(":")[0].lower()
        for pattern, runtime in _RUNTIME_PATTERNS.items():
            if pattern in image_name:
                # Include version tag if present
                tag = image.split(":")[-1] if ":" in image else "latest"
                hints.append(f"{runtime}:{tag}" if tag != "latest" else runtime)
                break
    return hints


def _extract_tool_installs(content: str) -> list[str]:
    """Extract tool install commands from RUN instructions."""
    tools: list[str] = []
    # Join continuation lines
    normalized = re.sub(r"\\\n\s*", " ", content)
    for match in _RUN_RE.finditer(normalized):
        run_cmd = match.group(1).strip()
        # Detect apt-get/apk/yum install commands
        pkg_match = re.search(
            r"(?:apt-get|apk|yum|dnf)\s+(?:install|add)\s+(.+?)(?:\s*&&|$)",
            run_cmd,
        )
        if pkg_match:
            packages = pkg_match.group(1)
            tools.extend(
                pkg
                for pkg in packages.split()
                if not pkg.startswith("-") and pkg not in ("--no-cache", "-y", "-q")
            )
        # Detect pip install
        pip_match = re.search(r"pip\s+install\s+(.+?)(?:\s*&&|$)", run_cmd)
        if pip_match:
            tools.extend(
                f"pip:{pkg}" for pkg in pip_match.group(1).split() if not pkg.startswith("-")
            )
        # Detect npm install -g
        npm_match = re.search(r"npm\s+install\s+-g\s+(.+?)(?:\s*&&|$)", run_cmd)
        if npm_match:
            tools.extend(
                f"npm:{pkg}" for pkg in npm_match.group(1).split() if not pkg.startswith("-")
            )
    return tools


def parse_dockerfile(
    repo_root: Path,
    relative_path: str = "Dockerfile",
) -> ParsedDockerfile:
    """Parse a Dockerfile and extract environment prerequisites.

    Returns empty result if the file is missing or malformed.
    Does NOT generate instruction claims — only provides evidence for prerequisites.
    """
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        logger.warning("Dockerfile path validation failed", path=relative_path)
        return ParsedDockerfile(
            base_images=(),
            runtime_hints=(),
            tool_installs=(),
            env_var_names=(),
            exposed_ports=(),
        )

    if not file_path.is_file():
        return ParsedDockerfile(
            base_images=(),
            runtime_hints=(),
            tool_installs=(),
            env_var_names=(),
            exposed_ports=(),
        )

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Failed to read Dockerfile", error=str(exc))
        return ParsedDockerfile(
            base_images=(),
            runtime_hints=(),
            tool_installs=(),
            env_var_names=(),
            exposed_ports=(),
        )

    # Join continuation lines for multi-line instructions
    normalized = re.sub(r"\\\n\s*", " ", content)

    # Extract base images
    base_images = [m.group(1) for m in _FROM_RE.finditer(normalized)]
    # Strip "AS stage_name" from images
    base_images = [img.split(" ")[0] for img in base_images]

    runtime_hints = _extract_runtime_hints(base_images)
    tool_installs = _extract_tool_installs(content)

    # Extract ENV variable names (never values)
    env_var_names = [m.group(1) for m in _ENV_RE.finditer(normalized)]

    # Extract EXPOSE ports
    exposed_ports: list[str] = []
    for m in _EXPOSE_RE.finditer(normalized):
        for port in m.group(1).split():
            port_num = port.split("/")[0]  # Strip protocol (e.g., 8080/tcp)
            exposed_ports.append(port_num)

    # Extract WORKDIR
    workdir: str | None = None
    workdir_matches = list(_WORKDIR_RE.finditer(normalized))
    if workdir_matches:
        workdir = workdir_matches[-1].group(1).strip()

    return ParsedDockerfile(
        base_images=tuple(base_images),
        runtime_hints=tuple(runtime_hints),
        tool_installs=tuple(tool_installs),
        env_var_names=tuple(env_var_names),
        exposed_ports=tuple(exposed_ports),
        workdir=workdir,
        source_file=relative_path,
    )
