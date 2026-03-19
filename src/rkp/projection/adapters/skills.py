"""Agent Skills (SKILL.md) cross-host generator."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from rkp.core.models import Claim
from rkp.core.types import ClaimType, source_authority_precedence

# Maximum number of skills per repo (consolidate if exceeded).
MAX_SKILLS = 10

# Minimum claims to form a skill (unless the single claim is high-value).
MIN_CLAIMS_FOR_SKILL = 2

# Maximum body size (approximate tokens via character count; 1 token ≈ 4 chars).
MAX_BODY_CHARS = 20000  # ~5000 tokens

# Tag-to-skill-name mapping.
_TAG_TO_SKILL: dict[str, str] = {
    "test": "validate-and-test",
    "testing": "validate-and-test",
    "ci": "ci-workflow",
    "security": "security-checks",
    "build": "build-and-deploy",
    "release": "build-and-deploy",
    "lint": "code-quality",
    "format": "code-quality",
    "docs": "documentation",
    "onboarding": "getting-started",
    "debug": "debugging",
    "review": "code-review",
    "refactor": "refactoring",
}

# Tag-to-human-readable-title mapping.
_TAG_TO_TITLE: dict[str, str] = {
    "test": "Validate and Test",
    "testing": "Validate and Test",
    "ci": "CI Workflow",
    "security": "Security Checks",
    "build": "Build and Deploy",
    "release": "Build and Deploy",
    "lint": "Code Quality",
    "format": "Code Quality",
    "docs": "Documentation",
    "onboarding": "Getting Started",
    "debug": "Debugging",
    "review": "Code Review",
    "refactor": "Refactoring",
}

_VALID_SKILL_NAME = re.compile(r"^[a-z][a-z0-9-]*$")

# Claim types ordered for rendering within a skill body.
_CLAIM_TYPE_ORDER: dict[ClaimType, int] = {
    ClaimType.VALIDATED_COMMAND: 0,
    ClaimType.ALWAYS_ON_RULE: 1,
    ClaimType.SCOPED_RULE: 2,
    ClaimType.PERMISSION_RESTRICTION: 3,
    ClaimType.SKILL_PLAYBOOK: 4,
    ClaimType.ENVIRONMENT_PREREQUISITE: 5,
    ClaimType.MODULE_BOUNDARY: 6,
    ClaimType.CONFLICT: 7,
}


@dataclass(frozen=True)
class SkillDescriptor:
    """Metadata for a generated skill (used as reference in always-on files)."""

    name: str
    description: str
    path: str


def _primary_tag(claim: Claim) -> str:
    """Return the primary applicability tag for grouping."""
    if not claim.applicability:
        return "general"
    # Prefer the first non-"all" tag
    for tag in claim.applicability:
        if tag != "all":
            return tag
    return "general"


def _is_high_value(claim: Claim) -> bool:
    """A claim is high-value if it has high authority or confidence."""
    return claim.confidence >= 0.9 and source_authority_precedence(claim.source_authority) <= 30


def _skill_name_for_tag(tag: str) -> str:
    """Derive a valid skill name from an applicability tag."""
    name = _TAG_TO_SKILL.get(tag, tag)
    # Sanitize: lowercase, replace non-alphanum with hyphens, collapse multiples
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    name = re.sub(r"-+", "-", name).strip("-")
    if not name or not _VALID_SKILL_NAME.match(name):
        name = "general"
    return name[:64]


def _skill_title_for_tag(tag: str) -> str:
    """Derive a human-readable title from an applicability tag."""
    return _TAG_TO_TITLE.get(tag, tag.replace("-", " ").title())


def _render_claim_in_skill(claim: Claim) -> str:
    """Render a claim as an instruction line with evidence attribution."""
    evidence_note = ""
    if claim.evidence:
        evidence_note = f" (source: {', '.join(claim.evidence[:3])})"
    if claim.claim_type == ClaimType.VALIDATED_COMMAND:
        risk_note = f" [{claim.risk_class.value}]" if claim.risk_class else ""
        return f"- `{claim.content}`{risk_note}{evidence_note}"
    return f"- {claim.content}{evidence_note}"


def _sort_claims_for_skill(claims: list[Claim]) -> list[Claim]:
    """Sort claims for rendering: commands first, then conventions, then guardrails."""
    return sorted(
        claims,
        key=lambda c: (
            _CLAIM_TYPE_ORDER.get(c.claim_type, 99),
            source_authority_precedence(c.source_authority),
            c.id,
        ),
    )


def project_skills(
    claims: list[Claim],
    *,
    path_prefix: str = ".claude/skills",
) -> tuple[dict[str, str], list[SkillDescriptor]]:
    """Generate skill files from claims grouped by applicability.

    Returns (files dict, skill descriptors for reference listing).
    """
    if not claims:
        return {}, []

    # Group claims by their primary applicability tag
    groups: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        tag = _primary_tag(claim)
        groups[tag].append(claim)

    # Merge groups that map to the same skill name
    merged: dict[str, list[Claim]] = defaultdict(list)
    for tag, tag_claims in groups.items():
        skill_name = _skill_name_for_tag(tag)
        merged[skill_name].extend(tag_claims)

    # Filter: skip groups below minimum threshold
    filtered: dict[str, list[Claim]] = {
        skill_name: skill_claims
        for skill_name, skill_claims in merged.items()
        if (
            len(skill_claims) >= MIN_CLAIMS_FOR_SKILL
            or (len(skill_claims) == 1 and _is_high_value(skill_claims[0]))
        )
    }

    # Consolidate if too many skills
    if len(filtered) > MAX_SKILLS:
        # Keep the largest groups, merge the rest into "general"
        sorted_groups = sorted(filtered.items(), key=lambda x: -len(x[1]))
        keep = dict(sorted_groups[: MAX_SKILLS - 1])
        overflow_claims: list[Claim] = []
        for _name, group_claims in sorted_groups[MAX_SKILLS - 1 :]:
            overflow_claims.extend(group_claims)
        if overflow_claims:
            keep["general"] = keep.get("general", []) + overflow_claims
        filtered = keep

    # Generate skill files
    files: dict[str, str] = {}
    descriptors: list[SkillDescriptor] = []

    for skill_name in sorted(filtered):
        skill_claims = _sort_claims_for_skill(filtered[skill_name])
        title = _skill_title_for_tag(skill_name)

        # Build description (first line summary)
        description = f"How to {title.lower()} in this repository."
        if len(description) > 1024:
            description = description[:1021] + "..."

        # Build body
        body_lines: list[str] = []
        for claim in skill_claims:
            line = _render_claim_in_skill(claim)
            body_lines.append(line)

        body = "\n".join(body_lines)
        if len(body) > MAX_BODY_CHARS:
            body = body[: MAX_BODY_CHARS - 3] + "..."

        content = (
            f"---\nname: {skill_name}\ndescription: {description}\n---\n\n# {title}\n\n{body}\n"
        )

        path = f"{path_prefix}/{skill_name}/SKILL.md"
        files[path] = content
        descriptors.append(
            SkillDescriptor(
                name=skill_name,
                description=description,
                path=path,
            )
        )

    return files, descriptors
