"""MCP tool implementations."""

from __future__ import annotations

import sqlite3
from typing import Any

from rkp.core.types import ClaimType
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
    from rkp.core.types import source_authority_precedence

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
