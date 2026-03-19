"""Parse GitHub Actions workflow files for CI evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import structlog
import yaml

from rkp.core.security import validate_path

logger = structlog.get_logger()


class CIConfidence(StrEnum):
    """Confidence level for CI-extracted evidence."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CICommand:
    """A command extracted from a CI workflow step."""

    command: str
    confidence: CIConfidence
    job_name: str
    step_name: str | None
    os: str | None = None
    condition: str | None = None


@dataclass(frozen=True)
class CIRuntimeEvidence:
    """Runtime version evidence from CI setup actions."""

    runtime: str  # e.g., "python", "node"
    versions: tuple[str, ...]
    source_action: str


@dataclass(frozen=True)
class CIServiceEvidence:
    """Service evidence from CI job services."""

    name: str
    image: str
    env_var_names: tuple[str, ...]
    ports: tuple[str, ...]


@dataclass(frozen=True)
class ParsedWorkflowJob:
    """A parsed job from a workflow file."""

    name: str
    runs_on: str | None
    commands: tuple[CICommand, ...]
    runtimes: tuple[CIRuntimeEvidence, ...]
    services: tuple[CIServiceEvidence, ...]
    env_var_names: tuple[str, ...]
    matrix_dimensions: dict[str, list[str]]


@dataclass(frozen=True)
class ParsedWorkflow:
    """Structured output from parsing a GitHub Actions workflow."""

    name: str | None
    triggers: tuple[str, ...]
    jobs: tuple[ParsedWorkflowJob, ...]
    env_var_names: tuple[str, ...]
    source_file: str


# Matrix expression pattern: ${{ matrix.KEY }}
_MATRIX_EXPR_RE = re.compile(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}")

# General expression pattern
_EXPR_RE = re.compile(r"\$\{\{.*?\}\}")

# Setup action patterns for runtime detection.
_SETUP_ACTIONS: dict[str, str] = {
    "actions/setup-python": "python",
    "actions/setup-node": "node",
    "actions/setup-go": "go",
    "actions/setup-java": "java",
    "actions/setup-dotnet": "dotnet",
}

# Version input keys per setup action.
_VERSION_KEYS: dict[str, str] = {
    "actions/setup-python": "python-version",
    "actions/setup-node": "node-version",
    "actions/setup-go": "go-version",
    "actions/setup-java": "java-version",
    "actions/setup-dotnet": "dotnet-version",
}


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


def _is_schedule_or_dispatch_only(triggers: list[str]) -> bool:
    """Check if workflow only has schedule/dispatch triggers."""
    non_schedule = {"push", "pull_request", "pull_request_target"}
    return not any(t in non_schedule for t in triggers)


def _extract_triggers(data: dict[str, Any]) -> list[str]:
    """Extract workflow trigger event names."""
    on_field: object = data.get("on")
    if on_field is None:
        # YAML "on" can parse as boolean True
        on_field = cast(object, cast(dict[object, Any], data).get(True))
    if isinstance(on_field, str):
        return [on_field]
    on_list = _as_list(on_field)
    if on_list is not None:
        return [str(t) for t in on_list]
    on_dict = _as_dict(on_field)
    if on_dict is not None:
        return list(on_dict.keys())
    return []


def _extract_env_names(env: object) -> list[str]:
    """Extract env var names from an env block (names only, never values).

    Notes which reference secrets.* but never stores the values.
    """
    d = _as_dict(env)
    if d is None:
        return []
    names: list[str] = []
    for key, val in d.items():
        name = str(key)
        if isinstance(val, str) and "secrets." in val:
            name = f"{name} (secret-ref)"
        names.append(name)
    return names


def _resolve_matrix_value(
    val: str,
    matrix: dict[str, list[str]],
) -> list[str]:
    """Resolve simple ${{ matrix.KEY }} references.

    Returns resolved values for simple cases, or the original expression
    marked as unresolvable for complex cases.
    """
    match = _MATRIX_EXPR_RE.fullmatch(val.strip())
    if match:
        key = match.group(1)
        if key in matrix:
            return matrix[key]
    if _EXPR_RE.search(val):
        return [f"<unresolvable:{val}>"]
    return [val]


def _extract_matrix(strategy: dict[str, Any]) -> dict[str, list[str]]:
    """Extract matrix dimensions from strategy.matrix."""
    raw_matrix = _as_dict(strategy.get("matrix"))
    if raw_matrix is None:
        return {}

    dimensions: dict[str, list[str]] = {}
    for key, val in raw_matrix.items():
        if key in ("include", "exclude"):
            continue
        val_list: list[Any] | None = _as_list(val)
        if val_list is not None:
            dimensions[key] = [str(v) for v in val_list]
        elif isinstance(val, str) and _EXPR_RE.search(val):
            dimensions[key] = [f"<unresolvable:{val}>"]
    return dimensions


def _determine_step_confidence(
    step: dict[str, Any],
    *,
    has_matrix: bool,
    schedule_only: bool,
) -> CIConfidence:
    """Determine confidence level for a CI step."""
    if step.get("continue-on-error"):
        return CIConfidence.LOW
    if schedule_only:
        return CIConfidence.LOW
    if step.get("if"):
        return CIConfidence.MEDIUM
    if has_matrix:
        return CIConfidence.MEDIUM
    return CIConfidence.HIGH


def _extract_step_commands(
    step: dict[str, Any],
    *,
    job_name: str,
    confidence: CIConfidence,
    runs_on: str | None,
) -> list[CICommand]:
    """Extract commands from a step's 'run' field."""
    run_field = step.get("run")
    if not isinstance(run_field, str):
        return []

    commands: list[CICommand] = []
    step_name = step.get("name")
    step_name_str = str(step_name) if step_name is not None else None
    condition = step.get("if")
    condition_str = str(condition) if condition is not None else None

    for line in run_field.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        commands.append(
            CICommand(
                command=line,
                confidence=confidence,
                job_name=job_name,
                step_name=step_name_str,
                os=runs_on,
                condition=condition_str,
            )
        )

    return commands


def _extract_setup_runtimes(
    step: dict[str, Any],
    matrix: dict[str, list[str]],
) -> CIRuntimeEvidence | None:
    """Extract runtime version from setup-* actions."""
    uses = step.get("uses")
    if not isinstance(uses, str):
        return None

    action_name = uses.split("@")[0]
    runtime = _SETUP_ACTIONS.get(action_name)
    if runtime is None:
        return None

    version_key = _VERSION_KEYS.get(action_name)
    if version_key is None:
        return None

    with_block = _as_dict(step.get("with"))
    if with_block is None:
        return None

    raw_version = with_block.get(version_key)
    if raw_version is None:
        return None

    versions: list[str] = []
    raw_version_list = _as_list(raw_version)
    if raw_version_list is not None:
        versions = [str(v) for v in raw_version_list]
    elif isinstance(raw_version, str):
        versions = _resolve_matrix_value(raw_version, matrix)
    elif isinstance(raw_version, (int, float)):
        versions = [str(raw_version)]

    if not versions:
        return None

    return CIRuntimeEvidence(
        runtime=runtime,
        versions=tuple(versions),
        source_action=uses,
    )


def _extract_job_services(
    services: dict[str, Any],
) -> list[CIServiceEvidence]:
    """Extract service definitions from a job."""
    result: list[CIServiceEvidence] = []
    for svc_name, svc_config_raw in services.items():
        svc_config = _as_dict(svc_config_raw)
        if svc_config is None:
            continue
        image = svc_config.get("image")
        image_str = str(image) if isinstance(image, str) else str(svc_name)

        env_names = _extract_env_names(svc_config.get("env"))
        ports: list[str] = []
        raw_ports = _as_list(svc_config.get("ports"))
        if raw_ports is not None:
            ports = [str(p) for p in raw_ports]

        result.append(
            CIServiceEvidence(
                name=str(svc_name),
                image=image_str,
                env_var_names=tuple(env_names),
                ports=tuple(ports),
            )
        )
    return result


def _parse_job(
    job_name: str,
    job_config: dict[str, Any],
    *,
    schedule_only: bool,
) -> ParsedWorkflowJob:
    """Parse a single workflow job."""
    runs_on = job_config.get("runs-on")
    runs_on_str: str | None = None
    if isinstance(runs_on, str):
        runs_on_str = runs_on
    else:
        runs_on_list = _as_list(runs_on)
        if runs_on_list is not None:
            runs_on_str = ", ".join(str(r) for r in runs_on_list)

    strategy = _as_dict(job_config.get("strategy"))
    matrix: dict[str, list[str]] = {}
    if strategy is not None:
        matrix = _extract_matrix(strategy)
    has_matrix = bool(matrix)

    job_env = _extract_env_names(job_config.get("env"))

    services_raw = _as_dict(job_config.get("services"))
    services: list[CIServiceEvidence] = []
    if services_raw is not None:
        services = _extract_job_services(services_raw)

    steps = _as_list(job_config.get("steps"))
    if steps is None:
        return ParsedWorkflowJob(
            name=job_name,
            runs_on=runs_on_str,
            commands=(),
            runtimes=(),
            services=tuple(services),
            env_var_names=tuple(job_env),
            matrix_dimensions=matrix,
        )

    all_commands: list[CICommand] = []
    all_runtimes: list[CIRuntimeEvidence] = []

    for step_raw in steps:
        step = _as_dict(step_raw)
        if step is None:
            continue

        confidence = _determine_step_confidence(
            step,
            has_matrix=has_matrix,
            schedule_only=schedule_only,
        )

        step_commands = _extract_step_commands(
            step,
            job_name=job_name,
            confidence=confidence,
            runs_on=runs_on_str,
        )
        all_commands.extend(step_commands)

        runtime_evidence = _extract_setup_runtimes(step, matrix)
        if runtime_evidence is not None:
            all_runtimes.append(runtime_evidence)

        step_env = _extract_env_names(step.get("env"))
        job_env.extend(step_env)

    return ParsedWorkflowJob(
        name=job_name,
        runs_on=runs_on_str,
        commands=tuple(all_commands),
        runtimes=tuple(all_runtimes),
        services=tuple(services),
        env_var_names=tuple(job_env),
        matrix_dimensions=matrix,
    )


def parse_github_actions_workflow(
    repo_root: Path,
    relative_path: str,
) -> ParsedWorkflow:
    """Parse a GitHub Actions workflow YAML file.

    Uses yaml.safe_load() — NEVER yaml.load().
    Returns empty result if file is missing or malformed.
    """
    try:
        file_path = validate_path(Path(relative_path), repo_root)
    except Exception:
        logger.warning("Workflow path validation failed", path=relative_path)
        return ParsedWorkflow(
            name=None, triggers=(), jobs=(), env_var_names=(), source_file=relative_path
        )

    if not file_path.is_file():
        return ParsedWorkflow(
            name=None, triggers=(), jobs=(), env_var_names=(), source_file=relative_path
        )

    try:
        content = file_path.read_text(encoding="utf-8")
        raw_data: object = yaml.safe_load(content)
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Failed to parse workflow", path=relative_path, error=str(exc))
        return ParsedWorkflow(
            name=None, triggers=(), jobs=(), env_var_names=(), source_file=relative_path
        )

    data = _as_dict(raw_data)
    if data is None:
        return ParsedWorkflow(
            name=None, triggers=(), jobs=(), env_var_names=(), source_file=relative_path
        )

    workflow_name = data.get("name")
    name_str = str(workflow_name) if isinstance(workflow_name, str) else None

    triggers = _extract_triggers(data)
    schedule_only = _is_schedule_or_dispatch_only(triggers)

    workflow_env = _extract_env_names(data.get("env"))

    raw_jobs = _as_dict(data.get("jobs"))
    if raw_jobs is None:
        return ParsedWorkflow(
            name=name_str,
            triggers=tuple(triggers),
            jobs=(),
            env_var_names=tuple(workflow_env),
            source_file=relative_path,
        )

    jobs: list[ParsedWorkflowJob] = []
    for job_name_raw, job_config_raw in raw_jobs.items():
        job_config = _as_dict(job_config_raw)
        if job_config is None:
            continue
        jobs.append(_parse_job(str(job_name_raw), job_config, schedule_only=schedule_only))

    return ParsedWorkflow(
        name=name_str,
        triggers=tuple(triggers),
        jobs=tuple(jobs),
        env_var_names=tuple(workflow_env),
        source_file=relative_path,
    )


def discover_workflow_files(repo_root: Path) -> list[str]:
    """Discover GitHub Actions workflow files."""
    workflows_dir = repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []

    result: list[str] = []
    for suffix in ("*.yml", "*.yaml"):
        result.extend(
            str(path.relative_to(repo_root)) for path in sorted(workflows_dir.glob(suffix))
        )
    return result
