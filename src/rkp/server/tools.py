"""MCP tool implementations."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from rkp.core.types import ClaimType, source_authority_precedence
from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.server.response import ToolResponse, make_ok_response
from rkp.store.claims import SqliteClaimStore


def get_validated_commands(
    db: sqlite3.Connection,
    *,
    scope: str = "**",
    repo_id: str = "",
    branch: str = "main",
) -> ToolResponse:
    """Return validated commands with source, evidence level, risk class."""
    store = SqliteClaimStore(db)
    claims = store.list_claims(
        claim_type=ClaimType.VALIDATED_COMMAND,
        repo_id=repo_id if repo_id else None,
    )

    # Filter by scope if not wildcard
    if scope != "**":
        claims = [c for c in claims if c.scope == scope or c.scope == "**"]

    commands: list[dict[str, Any]] = [
        {
            "id": claim.id,
            "command": claim.content,
            "risk_class": claim.risk_class.value if claim.risk_class else None,
            "evidence_level": "discovered",
            "source": list(claim.evidence),
            "confidence": claim.confidence,
            "scope": claim.scope,
            "review_state": claim.review_state.value,
        }
        for claim in claims
    ]

    return make_ok_response(
        data=commands,
        repo_head="",
        branch=branch,
    )


def get_conventions(
    db: sqlite3.Connection,
    *,
    path_or_symbol: str = "**",
    include_evidence: bool = False,
    task_context: str | None = None,
    repo_id: str = "",
    branch: str = "main",
) -> ToolResponse:
    """Return convention claims scoped to a path.

    Filters by applicability if task_context is provided.
    """
    store = SqliteClaimStore(db)

    # Get convention claims (always-on-rule and scoped-rule)
    always_on = store.list_claims(
        claim_type=ClaimType.ALWAYS_ON_RULE,
        repo_id=repo_id if repo_id else None,
    )
    scoped = store.list_claims(
        claim_type=ClaimType.SCOPED_RULE,
        repo_id=repo_id if repo_id else None,
    )
    all_conventions = always_on + scoped

    # Filter by scope
    if path_or_symbol != "**":
        all_conventions = [
            c for c in all_conventions if c.scope == path_or_symbol or c.scope == "**"
        ]

    # Filter by task_context (applicability)
    if task_context is not None:
        all_conventions = [
            c
            for c in all_conventions
            if "all" in c.applicability or task_context in c.applicability
        ]

    # Sort by authority precedence (highest first)
    all_conventions.sort(key=lambda c: (source_authority_precedence(c.source_authority), c.id))

    conventions: list[dict[str, Any]] = []
    for claim in all_conventions:
        entry: dict[str, Any] = {
            "id": claim.id,
            "content": claim.content,
            "claim_type": claim.claim_type.value,
            "source_authority": claim.source_authority.value,
            "confidence": claim.confidence,
            "applicability": list(claim.applicability),
            "review_state": claim.review_state.value,
            "scope": claim.scope,
        }
        if include_evidence:
            entry["evidence"] = list(claim.evidence)
        conventions.append(entry)

    return make_ok_response(
        data=conventions,
        repo_head="",
        branch=branch,
    )


def get_prerequisites(
    db: sqlite3.Connection,
    *,
    command_or_scope: str | None = None,
    repo_id: str = "",
    branch: str = "main",
) -> ToolResponse:
    """Return environment prerequisites, structured as environment profiles.

    If command_or_scope is a specific command: return the profile linked to that command.
    If it's a path scope: return aggregated prerequisites for all commands in that scope.
    If None: return all profiles and prerequisite claims.
    """
    store = SqliteClaimStore(db)

    # Get environment prerequisite claims
    prereq_claims = store.list_claims(
        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
        repo_id=repo_id if repo_id else None,
    )

    # Filter by scope if specified
    if command_or_scope is not None:
        prereq_claims = [
            c for c in prereq_claims if c.scope == command_or_scope or c.scope == "**"
        ]

    # Get environment profiles from database
    profiles = _get_profiles(db, repo_id=repo_id)

    prerequisites: list[dict[str, Any]] = [
        {
            "id": claim.id,
            "content": claim.content,
            "source_authority": claim.source_authority.value,
            "confidence": claim.confidence,
            "applicability": list(claim.applicability),
            "evidence": list(claim.evidence),
            "sensitivity": claim.sensitivity.value,
        }
        for claim in prereq_claims
    ]

    return make_ok_response(
        data={
            "prerequisites": prerequisites,
            "profiles": profiles,
        },
        repo_head="",
        branch=branch,
    )


def _get_profiles(db: sqlite3.Connection, *, repo_id: str = "") -> list[dict[str, Any]]:
    """Retrieve environment profiles from the database."""
    if repo_id:
        rows = db.execute(
            "SELECT * FROM environment_profiles WHERE repo_id = ?", (repo_id,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM environment_profiles").fetchall()

    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "runtime": row["runtime"],
            "tools": json.loads(str(row["tools"])) if row["tools"] else [],
            "services": json.loads(str(row["services"])) if row["services"] else [],
            "env_vars": json.loads(str(row["env_vars"])) if row["env_vars"] else [],
            "setup_commands": (
                json.loads(str(row["setup_commands"])) if row["setup_commands"] else []
            ),
        }
        for row in rows
    ]


def get_module_info(
    db: sqlite3.Connection,
    *,
    path_or_symbol: str,
    repo_id: str = "",
    branch: str = "main",
) -> ToolResponse:
    """Return module boundary info, dependencies, dependents, and test locations.

    Uses RepoGraph for traversal. If path_or_symbol doesn't match a known module,
    returns status: ok with a note (graceful degradation per AC-16).
    """
    graph = SqliteRepoGraph(db, repo_id=repo_id, branch=branch)
    store = SqliteClaimStore(db)

    # Try to find the module by path or symbol
    module = graph.path_to_module(path_or_symbol)

    # Also try exact match
    if module is None and path_or_symbol in graph.get_modules():
        module = path_or_symbol

    if module is None:
        return make_ok_response(
            data={
                "path_or_symbol": path_or_symbol,
                "module": None,
                "note": f"'{path_or_symbol}' is not in a detected module boundary",
                "dependencies": [],
                "dependents": [],
                "test_locations": [],
            },
            repo_head="",
            branch=branch,
        )

    dependencies = graph.get_dependencies(module)
    dependents = graph.get_dependents(module)
    test_locations = graph.get_test_locations(module)

    # Get module boundary claims for this module
    boundary_claims = store.list_claims(
        claim_type=ClaimType.MODULE_BOUNDARY,
        repo_id=repo_id if repo_id else None,
    )
    module_claims = [c for c in boundary_claims if c.scope == module or module in c.content]

    # Get scoped rules for this module
    scoped_rules = store.list_claims(
        claim_type=ClaimType.SCOPED_RULE,
        repo_id=repo_id if repo_id else None,
    )
    applicable_rules = [
        {
            "id": r.id,
            "content": r.content,
            "confidence": r.confidence,
        }
        for r in scoped_rules
        if r.scope == module or r.scope == "**"
    ]

    return make_ok_response(
        data={
            "path_or_symbol": path_or_symbol,
            "module": module,
            "boundary": {
                "content": module_claims[0].content if module_claims else f"Module '{module}'",
                "source_authority": (
                    module_claims[0].source_authority.value if module_claims else "inferred-high"
                ),
                "confidence": module_claims[0].confidence if module_claims else 0.0,
                "evidence": list(module_claims[0].evidence) if module_claims else [],
            },
            "dependencies": dependencies,
            "dependents": dependents,
            "test_locations": test_locations,
            "scoped_rules": applicable_rules,
        },
        repo_head="",
        branch=branch,
    )


def get_conflicts(
    db: sqlite3.Connection,
    *,
    path_or_scope: str = "**",
    repo_id: str = "",
    branch: str = "main",
) -> ToolResponse:
    """Return conflict claims, optionally scoped to a path.

    Each conflict includes the conflicting claims referenced and suggested resolution type.
    """
    store = SqliteClaimStore(db)

    conflict_claims = store.list_claims(
        claim_type=ClaimType.CONFLICT,
        repo_id=repo_id if repo_id else None,
    )

    # Filter by scope if not wildcard
    if path_or_scope != "**":
        conflict_claims = [
            c for c in conflict_claims if c.scope == path_or_scope or c.scope == "**"
        ]

    conflicts: list[dict[str, Any]] = [
        {
            "id": claim.id,
            "content": claim.content,
            "source_authority": claim.source_authority.value,
            "confidence": claim.confidence,
            "evidence_claim_ids": list(claim.evidence),
            "review_state": claim.review_state.value,
            "scope": claim.scope,
            "suggested_resolution": "Review and resolve the conflicting claims",
        }
        for claim in conflict_claims
    ]

    return make_ok_response(
        data=conflicts,
        repo_head="",
        branch=branch,
    )
