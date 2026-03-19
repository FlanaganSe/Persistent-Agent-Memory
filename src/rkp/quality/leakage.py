"""Sensitivity leakage tests across all output boundaries."""

from __future__ import annotations

import sqlite3
from dataclasses import replace

from rkp.core.claim_builder import ClaimBuilder
from rkp.core.models import Claim
from rkp.core.types import ClaimType, Sensitivity, SourceAuthority
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.adapters.copilot import CopilotAdapter
from rkp.projection.adapters.cursor import CursorAdapter
from rkp.projection.adapters.windsurf import WindsurfAdapter
from rkp.projection.capability_matrix import (
    AGENTS_MD_CAPABILITY,
    CLAUDE_CODE_CAPABILITY,
    COPILOT_CAPABILITY,
    CURSOR_CAPABILITY,
    WINDSURF_CAPABILITY,
)
from rkp.projection.engine import ProjectionPolicy, project
from rkp.quality.types import LeakageResult
from rkp.server.tools import (
    get_claim,
    get_conflicts,
    get_conventions,
    get_guardrails,
    get_instruction_preview,
    get_preflight_context,
    get_prerequisites,
    get_repo_overview,
    get_validated_commands,
)
from rkp.store.claims import SqliteClaimStore

# Unique marker strings for leakage detection
_LOCAL_MARKER = "LOCAL_ONLY_SECRET_MARKER_xk9q"
_TEAM_MARKER = "TEAM_ONLY_RESTRICTED_MARKER_p7zr"


def _create_test_claims(
    builder: ClaimBuilder,
    db: sqlite3.Connection,
) -> tuple[Claim, Claim, Claim]:
    """Create claims at each sensitivity level with detectable markers."""
    store = SqliteClaimStore(db)

    public_claim = builder.build(
        content="Public convention: use snake_case",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        scope="**",
        applicability=("all",),
        confidence=0.95,
        evidence=("pyproject.toml",),
    )
    public_claim = replace(public_claim, sensitivity=Sensitivity.PUBLIC)
    store.save(public_claim)

    team_claim = builder.build(
        content=f"Team-only convention: {_TEAM_MARKER}",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        scope="**",
        applicability=("all",),
        confidence=0.95,
        evidence=("pyproject.toml",),
    )
    team_claim = replace(team_claim, sensitivity=Sensitivity.TEAM_ONLY)
    store.save(team_claim)

    local_claim = builder.build(
        content=f"Local-only secret: {_LOCAL_MARKER}",
        claim_type=ClaimType.ALWAYS_ON_RULE,
        source_authority=SourceAuthority.EXECUTABLE_CONFIG,
        scope="**",
        applicability=("all",),
        confidence=0.95,
        evidence=("pyproject.toml",),
    )
    local_claim = replace(local_claim, sensitivity=Sensitivity.LOCAL_ONLY)
    store.save(local_claim)

    return public_claim, team_claim, local_claim


def _check_content_for_markers(content: str) -> tuple[bool, bool]:
    """Check if content contains local or team markers.

    Returns (has_local_marker, has_team_marker).
    """
    return _LOCAL_MARKER in content, _TEAM_MARKER in content


def _test_projection_leakage(
    claims: list[Claim],
) -> list[LeakageResult]:
    """Test all projection adapters for sensitivity leakage."""
    results: list[LeakageResult] = []

    adapters: list[
        tuple[
            str,
            AgentsMdAdapter | ClaudeMdAdapter | CopilotAdapter | CursorAdapter | WindsurfAdapter,
            object,
        ]
    ] = [
        ("agents-md", AgentsMdAdapter(), AGENTS_MD_CAPABILITY),
        ("claude", ClaudeMdAdapter(), CLAUDE_CODE_CAPABILITY),
        ("copilot", CopilotAdapter(), COPILOT_CAPABILITY),
        ("cursor", CursorAdapter(), CURSOR_CAPABILITY),
        ("windsurf", WindsurfAdapter(), WINDSURF_CAPABILITY),
    ]

    policy = ProjectionPolicy(target_sensitivity=Sensitivity.PUBLIC)

    for adapter_name, adapter, capability in adapters:
        result = project(claims, adapter, capability, policy)  # type: ignore[arg-type]
        all_content = "\n".join(result.adapter_result.files.values())
        has_local, has_team = _check_content_for_markers(all_content)

        results.append(
            LeakageResult(
                boundary=f"projection:{adapter_name}",
                sensitivity_level="local-only",
                leaked=has_local,
                details=f"Local marker {'FOUND' if has_local else 'not found'} in {adapter_name} output",
            )
        )
        results.append(
            LeakageResult(
                boundary=f"projection:{adapter_name}",
                sensitivity_level="team-only",
                leaked=has_team,
                details=f"Team marker {'FOUND' if has_team else 'not found'} in {adapter_name} output",
            )
        )

    return results


def _test_mcp_tool_leakage(
    db: sqlite3.Connection,
) -> list[LeakageResult]:
    """Test all MCP tools for sensitivity leakage."""
    results: list[LeakageResult] = []

    # Tool functions that return ToolResponse with data containing claim content
    tool_calls: list[tuple[str, object]] = [
        ("get_validated_commands", get_validated_commands(db)),
        ("get_conventions", get_conventions(db)),
        ("get_conflicts", get_conflicts(db)),
        ("get_guardrails", get_guardrails(db)),
        ("get_prerequisites", get_prerequisites(db)),
        ("get_repo_overview", get_repo_overview(db)),
        ("get_preflight_context", get_preflight_context(db, path_or_symbol="**")),
        (
            "get_instruction_preview:agents-md",
            get_instruction_preview(db, consumer="agents-md"),
        ),
        (
            "get_instruction_preview:claude",
            get_instruction_preview(db, consumer="claude"),
        ),
        (
            "get_instruction_preview:copilot",
            get_instruction_preview(db, consumer="copilot"),
        ),
        (
            "get_instruction_preview:cursor",
            get_instruction_preview(db, consumer="cursor"),
        ),
        (
            "get_instruction_preview:windsurf",
            get_instruction_preview(db, consumer="windsurf"),
        ),
    ]

    for tool_name, response in tool_calls:
        response_str = str(response.to_dict())  # type: ignore[union-attr]
        has_local, has_team = _check_content_for_markers(response_str)

        results.append(
            LeakageResult(
                boundary=f"mcp:{tool_name}",
                sensitivity_level="local-only",
                leaked=has_local,
                details=f"Local marker {'FOUND' if has_local else 'not found'} in {tool_name}",
            )
        )
        results.append(
            LeakageResult(
                boundary=f"mcp:{tool_name}",
                sensitivity_level="team-only",
                leaked=has_team,
                details=f"Team marker {'FOUND' if has_team else 'not found'} in {tool_name}",
            )
        )

    return results


def _test_get_claim_leakage(
    db: sqlite3.Connection,
    local_claim: Claim,
) -> list[LeakageResult]:
    """Test that get_claim blocks local-only claims entirely."""
    results: list[LeakageResult] = []

    response = get_claim(db, claim_id=local_claim.id)
    resp_dict = response.to_dict()

    # get_claim should return an error for local-only claims
    leaked = resp_dict.get("status") != "error"

    results.append(
        LeakageResult(
            boundary="mcp:get_claim",
            sensitivity_level="local-only",
            leaked=leaked,
            details=f"get_claim for local-only claim: status={resp_dict.get('status')}",
        )
    )

    return results


def test_leakage(
    db: sqlite3.Connection,
    repo_id: str = "leakage-test",
) -> list[LeakageResult]:
    """Run comprehensive leakage tests across all output boundaries.

    Creates claims at each sensitivity level with detectable markers,
    then verifies they are filtered at every boundary.
    """
    builder = ClaimBuilder(repo_id=repo_id, branch="main")
    public_claim, team_claim, local_claim = _create_test_claims(builder, db)

    all_claims = [public_claim, team_claim, local_claim]
    results: list[LeakageResult] = []

    # 1. Test projection boundaries
    results.extend(_test_projection_leakage(all_claims))

    # 2. Test MCP tool boundaries
    results.extend(_test_mcp_tool_leakage(db))

    # 3. Test get_claim blocks local-only
    results.extend(_test_get_claim_leakage(db, local_claim))

    return results
