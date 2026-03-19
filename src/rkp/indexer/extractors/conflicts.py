"""Conflict detector: declared-vs-inferred mismatch detection."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

import structlog

from rkp.core.models import Claim
from rkp.core.types import ClaimType, SourceAuthority, source_authority_precedence

logger = structlog.get_logger()


@dataclass(frozen=True)
class ConflictClaimInput:
    """Structured input for building a conflict claim."""

    content: str
    source_authority: SourceAuthority
    scope: str
    confidence: float
    evidence_claim_ids: tuple[str, ...]
    conflict_type: str  # "version", "command", "convention"


@dataclass(frozen=True)
class ConflictResult:
    """Result of conflict detection."""

    conflicts: tuple[ConflictClaimInput, ...]


def _normalize_version(version_str: str) -> str | None:
    """Extract a normalized version number from a version string.

    Returns just the major.minor (e.g., "3.12") or None if unparseable.
    """
    match = re.search(r"(\d+)\.(\d+)", version_str)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    # Try just major version
    match = re.search(r"(\d+)", version_str)
    if match:
        return match.group(1)
    return None


def _extract_runtime_name(content: str) -> str | None:
    """Extract a normalized runtime name from a prerequisite claim content."""
    content_lower = content.lower()
    if "python" in content_lower:
        return "python"
    if "node" in content_lower:
        return "node"
    if "go" in content_lower or "golang" in content_lower:
        return "go"
    if "ruby" in content_lower:
        return "ruby"
    if "java" in content_lower or "jdk" in content_lower:
        return "java"
    if "rust" in content_lower or "rustc" in content_lower:
        return "rust"
    return None


def _parse_version_tuple(version_str: str) -> tuple[int, ...] | None:
    """Parse a version string to a comparable tuple."""
    match = re.search(r"(\d+(?:\.\d+)*)", version_str)
    if match:
        return tuple(int(p) for p in match.group(1).split("."))
    return None


def _versions_conflict(v1: str, v2: str) -> bool:
    """Check if two version specifications conflict.

    Conservative: only flag clear contradictions, not minor variations.
    For example:
    - "3.11" vs "3.12" is a conflict (different exact versions)
    - ">=3.12" vs "3.12" is NOT a conflict (3.12 satisfies >=3.12)
    - "3.12" vs "3.12+" is NOT a conflict
    - ">=3.12" vs "3.11" IS a conflict (3.11 < 3.12)
    """
    vt1 = _parse_version_tuple(v1)
    vt2 = _parse_version_tuple(v2)

    if vt1 is None or vt2 is None:
        return False

    has_min_1 = ">=" in v1 or ">" in v1
    has_min_2 = ">=" in v2 or ">" in v2
    has_plus_1 = "+" in v1
    has_plus_2 = "+" in v2

    # Both are exact (no range markers) — conflict if different
    if not (has_min_1 or has_min_2 or has_plus_1 or has_plus_2):
        return vt1 != vt2

    # One is a minimum range, the other is exact — conflict if exact < minimum
    if has_min_1 and not (has_min_2 or has_plus_2):
        # v1 is ">=X", v2 is exact — conflict if v2 < X
        return vt2 < vt1
    if has_min_2 and not (has_min_1 or has_plus_1):
        # v2 is ">=X", v1 is exact — conflict if v1 < X
        return vt1 < vt2

    # Both have range markers — don't flag
    return False


def _extract_command_key(content: str) -> str | None:
    """Extract a normalized command key for comparison.

    Returns the base command (e.g., "npm test", "pytest", "make lint").
    """
    stripped = content.strip()
    if stripped.startswith("$ "):
        stripped = stripped[2:]

    parts = stripped.split()
    if not parts:
        return None

    # For commands like "npm test", "npm run test", "make lint" — use first two words
    if len(parts) >= 2 and parts[0] in ("npm", "yarn", "pnpm", "make", "docker"):
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def _highest_authority(claims: list[Claim]) -> SourceAuthority:
    """Return the highest source authority among a list of claims."""
    if not claims:
        return SourceAuthority.INFERRED_LOW
    return min(
        (c.source_authority for c in claims),
        key=source_authority_precedence,
    )


def detect_conflicts(claims: list[Claim]) -> ConflictResult:
    """Detect conflicts among a set of claims.

    Conflict types detected:
    1. Version conflicts: Two prerequisite claims specify different versions
       for the same runtime (e.g., .python-version says 3.11, pyproject.toml says >=3.12)
    2. Command conflicts: A docs command references a command that doesn't
       exist in config (e.g., README says "run npm test" but no test script)
    3. Convention conflicts: Two convention claims disagree on the same topic

    Conservative: only flag clear contradictions, not minor variations.
    """
    conflicts: list[ConflictClaimInput] = []

    # 1. Version conflicts — group prerequisite claims by runtime
    prereq_claims = [c for c in claims if c.claim_type == ClaimType.ENVIRONMENT_PREREQUISITE]
    by_runtime: defaultdict[str, list[Claim]] = defaultdict(list)
    for claim in prereq_claims:
        runtime = _extract_runtime_name(claim.content)
        if runtime is not None:
            by_runtime[runtime].append(claim)

    for runtime, runtime_claims in by_runtime.items():
        if len(runtime_claims) < 2:
            continue
        # Compare each pair
        for i, claim_a in enumerate(runtime_claims):
            for claim_b in runtime_claims[i + 1 :]:
                version_a = _normalize_version(claim_a.content)
                version_b = _normalize_version(claim_b.content)
                if version_a is None or version_b is None:
                    continue
                if _versions_conflict(claim_a.content, claim_b.content):
                    authority = _highest_authority([claim_a, claim_b])
                    evidence_a = ", ".join(claim_a.evidence) if claim_a.evidence else "unknown"
                    evidence_b = ", ".join(claim_b.evidence) if claim_b.evidence else "unknown"
                    conflicts.append(
                        ConflictClaimInput(
                            content=(
                                f"{runtime.capitalize()} version conflict: "
                                f"'{claim_a.content}' (from {evidence_a}) vs "
                                f"'{claim_b.content}' (from {evidence_b})"
                            ),
                            source_authority=authority,
                            scope="**",
                            confidence=1.0,
                            evidence_claim_ids=(claim_a.id, claim_b.id),
                            conflict_type="version",
                        )
                    )

    # 2. Command conflicts — docs commands vs config commands
    docs_commands = [
        c
        for c in claims
        if c.claim_type == ClaimType.VALIDATED_COMMAND
        and c.source_authority == SourceAuthority.CHECKED_IN_DOCS
    ]
    config_commands = [
        c
        for c in claims
        if c.claim_type == ClaimType.VALIDATED_COMMAND
        and c.source_authority in (SourceAuthority.EXECUTABLE_CONFIG, SourceAuthority.CI_OBSERVED)
    ]

    # Build a set of known config command keys
    config_keys: set[str] = set()
    for cmd in config_commands:
        key = _extract_command_key(cmd.content)
        if key is not None:
            config_keys.add(key)

    # Also collect all raw config command content for fuzzy matching
    config_contents: set[str] = {cmd.content.strip().lower() for cmd in config_commands}

    for docs_cmd in docs_commands:
        docs_key = _extract_command_key(docs_cmd.content)
        if docs_key is None:
            continue

        # Check for "npm test" / "npm run test" style — docs says it exists but config doesn't have it
        if docs_key in ("npm test", "npm run", "yarn test", "pnpm test"):
            # Check if there's actually a test script in config
            has_test = any("test" in key for key in config_keys) or any(
                "test" in c for c in config_contents
            )
            if not has_test and config_commands:
                authority = _highest_authority([docs_cmd, *config_commands[:1]])
                conflicts.append(
                    ConflictClaimInput(
                        content=(
                            f"README references '{docs_cmd.content}' but no test command "
                            f"found in package.json scripts"
                        ),
                        source_authority=authority,
                        scope="**",
                        confidence=1.0,
                        evidence_claim_ids=(docs_cmd.id,),
                        conflict_type="command",
                    )
                )

    # 3. Convention conflicts — same topic, different conclusions
    convention_claims = [
        c for c in claims if c.claim_type in (ClaimType.ALWAYS_ON_RULE, ClaimType.SCOPED_RULE)
    ]
    # Group by a rough topic: extract what the convention is about
    by_topic: defaultdict[str, list[Claim]] = defaultdict(list)
    for claim in convention_claims:
        topic = _extract_convention_topic(claim.content)
        if topic is not None:
            by_topic[topic].append(claim)

    for topic, topic_claims in by_topic.items():
        if len(topic_claims) < 2:
            continue
        # Check if claims actually contradict (different dominant style, etc.)
        contents = [c.content for c in topic_claims]
        if len(set(contents)) > 1 and _conventions_contradict(contents):
            authority = _highest_authority(topic_claims)
            conflicts.append(
                ConflictClaimInput(
                    content=(
                        f"Convention conflict on '{topic}': "
                        + " vs ".join(f"'{c}'" for c in contents[:3])
                    ),
                    source_authority=authority,
                    scope="**",
                    confidence=1.0,
                    evidence_claim_ids=tuple(c.id for c in topic_claims[:3]),
                    conflict_type="convention",
                )
            )

    # 4. Import-vs-extraction conflicts — imported claims vs extracted evidence
    imported_commands = [
        c
        for c in claims
        if c.claim_type == ClaimType.VALIDATED_COMMAND
        and c.source_authority == SourceAuthority.DECLARED_IMPORTED_UNREVIEWED
    ]

    # Check imported commands against config commands (stale instruction detection)
    if imported_commands and config_commands:
        for imp_cmd in imported_commands:
            imp_key = _extract_command_key(imp_cmd.content)
            if imp_key is None:
                continue
            # If the imported command's base key isn't in any config
            if (
                imp_key not in config_keys
                and imp_cmd.content.strip().lower() not in config_contents
            ):
                authority = _highest_authority([imp_cmd, *config_commands[:1]])
                conflicts.append(
                    ConflictClaimInput(
                        content=(
                            f"Stale instruction: imported file references "
                            f"'{imp_cmd.content}' but no matching command found in config files"
                        ),
                        source_authority=authority,
                        scope="**",
                        confidence=0.8,
                        evidence_claim_ids=(imp_cmd.id,),
                        conflict_type="stale-import",
                    )
                )

    # Check imported prerequisites against extracted prerequisites
    imported_prereqs = [
        c
        for c in claims
        if c.claim_type == ClaimType.ENVIRONMENT_PREREQUISITE
        and c.source_authority == SourceAuthority.DECLARED_IMPORTED_UNREVIEWED
    ]

    if imported_prereqs:
        extracted_prereqs = [
            c
            for c in prereq_claims
            if c.source_authority != SourceAuthority.DECLARED_IMPORTED_UNREVIEWED
        ]

        imported_by_runtime: defaultdict[str, list[Claim]] = defaultdict(list)
        for claim in imported_prereqs:
            runtime = _extract_runtime_name(claim.content)
            if runtime is not None:
                imported_by_runtime[runtime].append(claim)

        extracted_by_runtime: defaultdict[str, list[Claim]] = defaultdict(list)
        for claim in extracted_prereqs:
            runtime = _extract_runtime_name(claim.content)
            if runtime is not None:
                extracted_by_runtime[runtime].append(claim)

        for runtime, imp_claims in imported_by_runtime.items():
            ext_claims = extracted_by_runtime.get(runtime, [])
            if not ext_claims:
                continue
            for imp_claim in imp_claims:
                for ext_claim in ext_claims:
                    if _versions_conflict(imp_claim.content, ext_claim.content):
                        authority = _highest_authority([imp_claim, ext_claim])
                        imp_evidence = imp_claim.evidence[0] if imp_claim.evidence else "imported"
                        ext_evidence = ext_claim.evidence[0] if ext_claim.evidence else "extracted"
                        conflicts.append(
                            ConflictClaimInput(
                                content=(
                                    f"Imported instruction says '{imp_claim.content}' "
                                    f"(from {imp_evidence}) but extracted evidence shows "
                                    f"'{ext_claim.content}' (from {ext_evidence})"
                                ),
                                source_authority=authority,
                                scope="**",
                                confidence=1.0,
                                evidence_claim_ids=(imp_claim.id, ext_claim.id),
                                conflict_type="import-vs-extraction",
                            )
                        )

    logger.info("Conflict detection complete", conflicts_found=len(conflicts))

    return ConflictResult(conflicts=tuple(conflicts))


def _extract_convention_topic(content: str) -> str | None:
    """Extract a rough topic from a convention claim content."""
    content_lower = content.lower()
    if "function name" in content_lower or "naming" in content_lower:
        return "function naming"
    if "class name" in content_lower:
        return "class naming"
    if "import" in content_lower:
        return "import style"
    if "docstring" in content_lower:
        return "docstrings"
    if "type annotation" in content_lower or "return type" in content_lower:
        return "type annotations"
    if "test" in content_lower and "place" in content_lower:
        return "test placement"
    if "test framework" in content_lower:
        return "test framework"
    if "lint" in content_lower:
        return "linting"
    if "format" in content_lower:
        return "formatting"
    return None


def _conventions_contradict(contents: list[str]) -> bool:
    """Check if convention contents actually contradict each other.

    Conservative: only flag clear contradictions, not minor wording differences.
    """
    # Extract the key pattern being asserted
    styles_found: set[str] = set()
    for content in contents:
        # Look for naming style assertions
        for style in ("snake_case", "camelCase", "PascalCase", "SCREAMING_SNAKE"):
            if style in content:
                styles_found.add(style)
        # Look for yes/no assertions
        if "prefer absolute" in content.lower():
            styles_found.add("absolute_imports")
        if "prefer relative" in content.lower():
            styles_found.add("relative_imports")

    # If we found multiple distinct styles, that's a contradiction
    return len(styles_found) > 1
