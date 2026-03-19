"""Copilot instruction file parser: copilot-instructions.md, .instructions.md, copilot-setup-steps.yml."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import structlog
import yaml

from rkp.core.types import ClaimType
from rkp.importer.models import ParsedClaimInput, ParsedInstructionFile, UnparseableSection
from rkp.importer.parsers.markdown_utils import (
    SectionType,
    collect_security_warnings,
    compute_content_hash,
    extract_bullet_items,
    extract_code_blocks,
    extract_frontmatter,
    is_command_like,
    is_directive,
    is_generic_prose,
    parse_sections,
)

logger = structlog.get_logger()

_SHELL_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh", "console", ""})


def parse_copilot_instructions(
    file_path: Path,
    *,
    scope_prefix: str = "**",
) -> ParsedInstructionFile:
    """Parse a copilot-instructions.md file into structured claim inputs.

    This handles both .github/copilot-instructions.md and
    .github/instructions/**/*.instructions.md files.
    """
    if not file_path.exists():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-instructions",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-instructions",
            claims=(),
            unparseable_sections=(),
            warnings=(f"Failed to read {file_path}: {exc}",),
        )

    if not content.strip():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-instructions",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    content_hash = compute_content_hash(content)
    warnings = collect_security_warnings(content)

    # Check for applyTo frontmatter (path-scoped .instructions.md files)
    frontmatter, body = extract_frontmatter(content)
    apply_to = frontmatter.get("applyTo", "")
    if apply_to:
        scope_prefix = apply_to

    claims: list[ParsedClaimInput] = []
    unparseable: list[UnparseableSection] = []

    # Extract code blocks as commands
    code_blocks = extract_code_blocks(body)
    for block in code_blocks:
        if block.language.lower() in _SHELL_LANGUAGES and block.content.strip():
            for line in block.content.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    cmd = line.lstrip("$> ").strip()
                    if cmd:
                        claims.append(
                            ParsedClaimInput(
                                content=cmd,
                                claim_type=ClaimType.VALIDATED_COMMAND,
                                scope=scope_prefix,
                                applicability=_guess_applicability(cmd),
                                confidence=1.0,
                                evidence_file=str(file_path),
                            )
                        )

    # Parse sections (same markdown approach as AGENTS.md)
    sections = parse_sections(body)
    for section in sections:
        if not section.content.strip():
            continue

        if section.section_type == SectionType.COMMANDS:
            _extract_items_as_commands(section.content, scope_prefix, file_path, claims)
        elif section.section_type in (SectionType.CONVENTIONS, SectionType.UNKNOWN):
            _extract_items_as_rules(section, scope_prefix, file_path, claims, unparseable)
        elif section.section_type == SectionType.SETUP:
            _extract_setup_items(section.content, scope_prefix, file_path, claims)
        elif section.section_type == SectionType.TESTING:
            _extract_testing_items(section.content, scope_prefix, file_path, claims)

    # If no sections, try top-level bullet extraction
    if not sections and body.strip():
        items = extract_bullet_items(body)
        for item in items:
            if is_generic_prose(item):
                continue
            if is_directive(item):
                claims.append(
                    ParsedClaimInput(
                        content=item,
                        claim_type=ClaimType.ALWAYS_ON_RULE,
                        scope=scope_prefix,
                        confidence=0.8,
                        evidence_file=str(file_path),
                    )
                )
            elif is_command_like(item):
                cmd = item.lstrip("$> ").strip()
                claims.append(
                    ParsedClaimInput(
                        content=cmd,
                        claim_type=ClaimType.VALIDATED_COMMAND,
                        scope=scope_prefix,
                        applicability=_guess_applicability(cmd),
                        confidence=0.8,
                        evidence_file=str(file_path),
                    )
                )

    source_type = "copilot-instructions"
    if file_path.name.endswith(".instructions.md"):
        source_type = "copilot-scoped-instructions"

    return ParsedInstructionFile(
        source_path=str(file_path),
        source_type=source_type,
        claims=tuple(claims),
        unparseable_sections=tuple(unparseable),
        warnings=tuple(warnings),
        content_hash=content_hash,
    )


def parse_copilot_setup_steps(file_path: Path) -> ParsedInstructionFile:
    """Parse copilot-setup-steps.yml for setup commands and environment info.

    Extracts: job steps (run commands), environment variables, tool versions,
    setup actions.
    """
    if not file_path.exists():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-setup-steps",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-setup-steps",
            claims=(),
            unparseable_sections=(),
            warnings=(f"Failed to read {file_path}: {exc}",),
        )

    if not content.strip():
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-setup-steps",
            claims=(),
            unparseable_sections=(),
            warnings=(),
        )

    content_hash = compute_content_hash(content)
    warnings = collect_security_warnings(content)

    claims: list[ParsedClaimInput] = []

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-setup-steps",
            claims=(),
            unparseable_sections=(
                UnparseableSection(
                    heading="YAML",
                    content=content[:500],
                    reason=f"YAML parse error: {exc}",
                ),
            ),
            warnings=tuple(warnings),
            content_hash=content_hash,
        )

    if not isinstance(data, dict):
        return ParsedInstructionFile(
            source_path=str(file_path),
            source_type="copilot-setup-steps",
            claims=(),
            unparseable_sections=(
                UnparseableSection(
                    heading="YAML",
                    content=content[:500],
                    reason="YAML root is not a mapping",
                ),
            ),
            warnings=tuple(warnings),
            content_hash=content_hash,
        )

    data_dict = cast(dict[str, Any], data)

    # Extract from jobs.copilot-setup-steps.steps
    jobs_raw: object = data_dict.get("jobs", {})
    if isinstance(jobs_raw, dict):
        jobs_dict = cast(dict[str, Any], jobs_raw)
        for job_data_raw in jobs_dict.values():
            if not isinstance(job_data_raw, dict):
                continue
            job_data = cast(dict[str, Any], job_data_raw)

            # Extract environment variables from env
            job_env_raw: object = job_data.get("env", {})
            if isinstance(job_env_raw, dict):
                job_env = cast(dict[str, str], job_env_raw)
                for env_key, env_value in job_env.items():
                    claims.append(
                        ParsedClaimInput(
                            content=f"Environment variable: {env_key}={env_value}",
                            claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                            scope="**",
                            applicability=("setup",),
                            confidence=1.0,
                            evidence_file=str(file_path),
                        )
                    )

            steps_raw: object = job_data.get("steps", [])
            if not isinstance(steps_raw, list):
                continue
            steps = cast(list[Any], steps_raw)

            for step_raw in steps:
                if not isinstance(step_raw, dict):
                    continue
                step = cast(dict[str, object], step_raw)
                _extract_step_claims(step, file_path, claims)

    return ParsedInstructionFile(
        source_path=str(file_path),
        source_type="copilot-setup-steps",
        claims=tuple(claims),
        unparseable_sections=(),
        warnings=tuple(warnings),
        content_hash=content_hash,
    )


def _extract_step_claims(
    step: dict[str, object],
    file_path: Path,
    claims: list[ParsedClaimInput],
) -> None:
    """Extract claims from a single workflow step."""
    # Setup actions (uses: actions/setup-python@v5)
    uses = step.get("uses")
    if isinstance(uses, str):
        version_info = _extract_version_from_action(uses, step)
        if version_info:
            claims.append(
                ParsedClaimInput(
                    content=version_info,
                    claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                    scope="**",
                    applicability=("setup",),
                    confidence=1.0,
                    evidence_file=str(file_path),
                )
            )

    # Run commands
    run_cmd = step.get("run")
    if isinstance(run_cmd, str):
        for line in run_cmd.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                claims.append(
                    ParsedClaimInput(
                        content=line,
                        claim_type=ClaimType.VALIDATED_COMMAND,
                        scope="**",
                        applicability=("setup",),
                        confidence=1.0,
                        evidence_file=str(file_path),
                    )
                )


def _extract_version_from_action(uses: str, step: dict[str, object]) -> str | None:
    """Extract runtime version info from a setup action."""
    with_raw = step.get("with", {})
    if not isinstance(with_raw, dict):
        return None
    with_data = cast(dict[str, Any], with_raw)

    version_keys: tuple[tuple[str, str, str], ...] = (
        ("setup-python", "python-version", "Python"),
        ("setup-node", "node-version", "Node.js"),
        ("setup-go", "go-version", "Go"),
        ("setup-java", "java-version", "Java"),
        ("setup-ruby", "ruby-version", "Ruby"),
    )
    for action_name, key, label in version_keys:
        if action_name in uses:
            version: object = with_data.get(key)
            if isinstance(version, (str, int, float)):
                return f"{label} {version}"

    return None


def _extract_items_as_commands(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract items as command claims."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        if is_command_like(item):
            cmd = item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    applicability=_guess_applicability(cmd),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )


def _extract_items_as_rules(
    section: object,
    scope: str,
    file_path: Path,
    claims: list[ParsedClaimInput],
    unparseable: list[UnparseableSection],
) -> None:
    """Extract items as convention/rule claims."""
    from rkp.importer.parsers.markdown_utils import MarkdownSection

    sec = section if isinstance(section, MarkdownSection) else None
    if sec is None:
        return

    items = extract_bullet_items(sec.content)
    extracted = False
    for item in items:
        if is_generic_prose(item):
            continue
        if is_directive(item) or sec.section_type == SectionType.CONVENTIONS:
            claims.append(
                ParsedClaimInput(
                    content=item,
                    claim_type=ClaimType.ALWAYS_ON_RULE,
                    scope=scope,
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )
            extracted = True
        elif is_command_like(item):
            cmd = item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    applicability=_guess_applicability(cmd),
                    confidence=0.8,
                    evidence_file=str(file_path),
                )
            )
            extracted = True

    if not extracted and not is_generic_prose(sec.content):
        unparseable.append(
            UnparseableSection(
                heading=sec.heading,
                content=sec.content[:500],
                reason="Could not classify section or extract claims",
            )
        )


def _extract_setup_items(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract setup/prerequisite items."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        if is_command_like(item):
            cmd = item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    applicability=("setup",),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )
        else:
            claims.append(
                ParsedClaimInput(
                    content=item,
                    claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
                    scope=scope,
                    applicability=("setup",),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )


def _extract_testing_items(
    content: str, scope: str, file_path: Path, claims: list[ParsedClaimInput]
) -> None:
    """Extract testing items."""
    items = extract_bullet_items(content)
    for item in items:
        if is_generic_prose(item):
            continue
        if is_command_like(item):
            cmd = item.lstrip("$> ").strip()
            claims.append(
                ParsedClaimInput(
                    content=cmd,
                    claim_type=ClaimType.VALIDATED_COMMAND,
                    scope=scope,
                    applicability=("test",),
                    confidence=0.9,
                    evidence_file=str(file_path),
                )
            )


def _guess_applicability(command: str) -> tuple[str, ...]:
    """Guess applicability tags from a command string."""
    cmd_lower = command.lower()
    tags: list[str] = []

    if any(kw in cmd_lower for kw in ("test", "pytest", "jest")):
        tags.append("test")
    if any(kw in cmd_lower for kw in ("lint", "eslint", "ruff")):
        tags.append("lint")
    if any(kw in cmd_lower for kw in ("format", "prettier")):
        tags.append("format")
    if any(kw in cmd_lower for kw in ("build", "compile")):
        tags.append("build")
    if any(kw in cmd_lower for kw in ("install", "setup", "pip install", "npm install")):
        tags.append("setup")

    return tuple(tags) if tags else ("all",)
