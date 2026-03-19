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
    """Return validated commands with source, evidence level, risk class.

    This is the only MCP tool for M2.
    """
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
