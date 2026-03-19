"""MCP tool implementations.

Pure functions: each takes a sqlite3.Connection (and optional params),
returns a ToolResponse. MCP handlers in mcp.py wrap these as FastMCP tools.
"""

from __future__ import annotations

import json
import sqlite3
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from rkp.core.config import SourceAllowlist
from rkp.core.models import Claim
from rkp.core.types import ClaimType, source_authority_precedence
from rkp.graph.repo_graph import SqliteRepoGraph
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter, is_enforceable_restriction
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.server.response import (
    ToolResponse,
    make_error_response,
    make_ok_response,
    make_unsupported_response,
)
from rkp.store.claims import SqliteClaimStore
from rkp.store.evidence import SqliteEvidenceStore
from rkp.store.history import SqliteHistoryStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_index_version(db: sqlite3.Connection) -> str:
    """Most recent claim update timestamp, used as index version."""
    row = db.execute("SELECT MAX(updated_at) as latest FROM claims").fetchone()
    if row and row["latest"]:
        return str(row["latest"])
    return ""


def _has_claims(db: sqlite3.Connection) -> bool:
    row = db.execute("SELECT COUNT(*) as cnt FROM claims").fetchone()
    return bool(row and int(row["cnt"]) > 0)


def render_claim(
    claim: Claim,
    detail_level: str = "normal",
    evidence_store: SqliteEvidenceStore | None = None,
) -> dict[str, Any]:
    """Render a claim dict at the specified detail level.

    terse   — id, content_preview (100 chars), claim_type, confidence
    normal  — all claim fields except raw evidence blobs (default)
    detailed — all fields + evidence chain from EvidenceStore
    """
    if detail_level == "terse":
        return {
            "id": claim.id,
            "content_preview": claim.content[:100],
            "claim_type": claim.claim_type.value,
            "confidence": claim.confidence,
        }

    result: dict[str, Any] = {
        "id": claim.id,
        "content": claim.content,
        "claim_type": claim.claim_type.value,
        "source_authority": claim.source_authority.value,
        "confidence": claim.confidence,
        "scope": claim.scope,
        "applicability": list(claim.applicability),
        "review_state": claim.review_state.value,
    }

    if claim.risk_class is not None:
        result["risk_class"] = claim.risk_class.value

    if detail_level == "detailed":
        result["evidence"] = list(claim.evidence)
        result["stale"] = claim.stale
        result["last_validated"] = (
            claim.last_validated.isoformat() if claim.last_validated else None
        )
        result["revalidation_trigger"] = claim.revalidation_trigger
        if evidence_store is not None:
            evidence_records = evidence_store.get_for_claim(claim.id)
            result["evidence_chain"] = [
                {
                    "file_path": e.file_path,
                    "file_hash": e.file_hash,
                    "line_start": e.line_start,
                    "line_end": e.line_end,
                    "evidence_level": e.evidence_level.value,
                    "extraction_version": e.extraction_version,
                }
                for e in evidence_records
            ]

    return result


def paginate_claims(
    claims: list[Claim],
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[Claim], str | None, bool, int]:
    """Cursor-based pagination on a sorted claim list.

    Returns (page_items, next_cursor, has_more, total_count).
    """
    total = len(claims)
    # Stable ordering by ID (lexicographic on content-addressable hash)
    claims = sorted(claims, key=lambda c: c.id)
    if cursor is not None:
        claims = [c for c in claims if c.id > cursor]
    has_more = len(claims) > limit
    page = claims[:limit]
    next_cursor = page[-1].id if has_more and page else None
    return page, next_cursor, has_more, total


def enforce_allowlist(
    claims: list[Claim],
    allowlist: SourceAllowlist | None,
) -> list[Claim]:
    """Filter claims whose source authority is not in the trusted set."""
    if allowlist is None:
        return claims
    return [c for c in claims if _passes_allowlist(c, allowlist)]


def _passes_allowlist(claim: Claim, allowlist: SourceAllowlist) -> bool:
    if claim.source_authority.value not in allowlist.trusted_evidence_sources:
        return False
    if claim.evidence and allowlist.allowed_directories != ("**",):
        has_allowed = any(
            any(fnmatch(ev, pat) for pat in allowlist.allowed_directories) for ev in claim.evidence
        )
        if not has_allowed:
            return False
    return True


def _paginated_data(
    items: list[dict[str, Any]],
    next_cursor: str | None,
    total_count: int,
    has_more: bool,
) -> dict[str, Any]:
    return {
        "items": items,
        "next_cursor": next_cursor,
        "total_count": total_count,
        "has_more": has_more,
    }


# ---------------------------------------------------------------------------
# Existing tools — updated with pagination + detail levels
# ---------------------------------------------------------------------------


def get_validated_commands(
    db: sqlite3.Connection,
    *,
    scope: str = "**",
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Validated commands with source, evidence level, risk class."""
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)
    ev_store = SqliteEvidenceStore(db) if detail_level == "detailed" else None

    claims = store.list_claims(
        claim_type=ClaimType.VALIDATED_COMMAND,
        repo_id=repo_id if repo_id else None,
    )
    if scope != "**":
        claims = [c for c in claims if c.scope == scope or c.scope == "**"]
    claims = enforce_allowlist(claims, allowlist)

    page, nc, hm, total = paginate_claims(claims, limit=limit, cursor=cursor)

    items: list[dict[str, Any]] = []
    for claim in page:
        item = render_claim(claim, detail_level, ev_store)
        if detail_level != "terse":
            item["command"] = claim.content
            item["risk_class"] = claim.risk_class.value if claim.risk_class else None
            item["evidence_level"] = "discovered"
            item["source"] = list(claim.evidence)
        items.append(item)

    return make_ok_response(
        data=_paginated_data(items, nc, total, hm),
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


def get_conventions(
    db: sqlite3.Connection,
    *,
    path_or_symbol: str = "**",
    include_evidence: bool = False,
    task_context: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Convention claims scoped to a path, filtered by applicability."""
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)
    ev_store = SqliteEvidenceStore(db) if detail_level == "detailed" else None

    always_on = store.list_claims(
        claim_type=ClaimType.ALWAYS_ON_RULE,
        repo_id=repo_id if repo_id else None,
    )
    scoped = store.list_claims(
        claim_type=ClaimType.SCOPED_RULE,
        repo_id=repo_id if repo_id else None,
    )
    all_conventions = always_on + scoped

    if path_or_symbol != "**":
        all_conventions = [
            c for c in all_conventions if c.scope == path_or_symbol or c.scope == "**"
        ]
    if task_context is not None:
        all_conventions = [
            c
            for c in all_conventions
            if "all" in c.applicability or task_context in c.applicability
        ]

    all_conventions.sort(key=lambda c: (source_authority_precedence(c.source_authority), c.id))
    all_conventions = enforce_allowlist(all_conventions, allowlist)

    page, nc, hm, total = paginate_claims(all_conventions, limit=limit, cursor=cursor)

    items: list[dict[str, Any]] = []
    for claim in page:
        entry = render_claim(claim, detail_level, ev_store)
        if detail_level != "terse" and include_evidence:
            entry["evidence"] = list(claim.evidence)
        items.append(entry)

    return make_ok_response(
        data=_paginated_data(items, nc, total, hm),
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


def get_prerequisites(
    db: sqlite3.Connection,
    *,
    command_or_scope: str | None = None,
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Environment prerequisites and profiles (non-paginated)."""
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)

    prereq_claims = store.list_claims(
        claim_type=ClaimType.ENVIRONMENT_PREREQUISITE,
        repo_id=repo_id if repo_id else None,
    )
    if command_or_scope is not None:
        prereq_claims = [
            c for c in prereq_claims if c.scope == command_or_scope or c.scope == "**"
        ]
    prereq_claims = enforce_allowlist(prereq_claims, allowlist)

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
        data={"prerequisites": prerequisites, "profiles": profiles},
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
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
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Module boundary info, dependencies, dependents, test locations (non-paginated)."""
    idx = _get_index_version(db)
    graph = SqliteRepoGraph(db, repo_id=repo_id, branch=branch)
    store = SqliteClaimStore(db)

    module = graph.path_to_module(path_or_symbol)
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
            repo_head=repo_head,
            branch=branch,
            index_version=idx,
        )

    dependencies = graph.get_dependencies(module)
    dependents = graph.get_dependents(module)
    test_locations = graph.get_test_locations(module)

    boundary_claims = store.list_claims(
        claim_type=ClaimType.MODULE_BOUNDARY,
        repo_id=repo_id if repo_id else None,
    )
    boundary_claims = enforce_allowlist(boundary_claims, allowlist)
    module_claims = [c for c in boundary_claims if c.scope == module or module in c.content]

    scoped_rules = store.list_claims(
        claim_type=ClaimType.SCOPED_RULE,
        repo_id=repo_id if repo_id else None,
    )
    scoped_rules = enforce_allowlist(scoped_rules, allowlist)
    applicable_rules = [
        {"id": r.id, "content": r.content, "confidence": r.confidence}
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
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


def get_conflicts(
    db: sqlite3.Connection,
    *,
    path_or_scope: str = "**",
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Conflict claims, optionally scoped."""
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)
    ev_store = SqliteEvidenceStore(db) if detail_level == "detailed" else None

    conflict_claims = store.list_claims(
        claim_type=ClaimType.CONFLICT,
        repo_id=repo_id if repo_id else None,
    )
    if path_or_scope != "**":
        conflict_claims = [
            c for c in conflict_claims if c.scope == path_or_scope or c.scope == "**"
        ]
    conflict_claims = enforce_allowlist(conflict_claims, allowlist)

    page, nc, hm, total = paginate_claims(conflict_claims, limit=limit, cursor=cursor)

    items: list[dict[str, Any]] = []
    for claim in page:
        entry = render_claim(claim, detail_level, ev_store)
        if detail_level != "terse":
            entry["evidence_claim_ids"] = list(claim.evidence)
            entry["suggested_resolution"] = "Review and resolve the conflicting claims"
        items.append(entry)

    return make_ok_response(
        data=_paginated_data(items, nc, total, hm),
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


def get_guardrails(
    db: sqlite3.Connection,
    *,
    path_or_scope: str = "**",
    limit: int = 50,
    cursor: str | None = None,
    detail_level: str = "normal",
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Permission/restriction claims with enforcement info."""
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)
    ev_store = SqliteEvidenceStore(db) if detail_level == "detailed" else None

    guardrail_claims = store.list_claims(
        claim_type=ClaimType.PERMISSION_RESTRICTION,
        repo_id=repo_id if repo_id else None,
    )
    if path_or_scope != "**":
        guardrail_claims = [
            c for c in guardrail_claims if c.scope == path_or_scope or c.scope == "**"
        ]
    guardrail_claims = enforce_allowlist(guardrail_claims, allowlist)

    page, nc, hm, total = paginate_claims(guardrail_claims, limit=limit, cursor=cursor)

    items: list[dict[str, Any]] = []
    for claim in page:
        is_enforceable = is_enforceable_restriction(claim)
        entry = render_claim(claim, detail_level, ev_store)
        if detail_level != "terse":
            entry["evidence"] = list(claim.evidence)
            entry["enforceable_on"] = ["claude"] if is_enforceable else []
            entry["enforcement_mechanism"] = (
                "settings.json permissions.deny" if is_enforceable else "advisory text only"
            )
        items.append(entry)

    return make_ok_response(
        data=_paginated_data(items, nc, total, hm),
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


def get_instruction_preview(
    db: sqlite3.Connection,
    *,
    consumer: str,
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Preview projected instruction artifacts for a target consumer."""
    idx = _get_index_version(db)
    capability = get_capability(consumer)
    if capability is None:
        return make_unsupported_response(
            f"Consumer '{consumer}' is not supported. Supported: codex, agents-md, claude",
            repo_head=repo_head,
            branch=branch,
        )

    store = SqliteClaimStore(db)
    claims = store.list_claims(repo_id=repo_id if repo_id else None)
    claims = enforce_allowlist(claims, allowlist)

    if consumer in ("codex", "agents-md"):
        adapter = AgentsMdAdapter()
    elif consumer == "claude":
        adapter = ClaudeMdAdapter()
    else:
        adapter = AgentsMdAdapter()

    policy = ProjectionPolicy()
    result = project(claims, adapter, capability, policy)

    data: dict[str, Any] = {
        "consumer": consumer,
        "files": result.adapter_result.files,
        "excluded_sensitive": result.excluded_sensitive,
        "excluded_low_confidence": result.excluded_low_confidence,
        "overflow_report": result.adapter_result.overflow_report,
    }

    return make_ok_response(
        data=data,
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


# ---------------------------------------------------------------------------
# New tools — M7
# ---------------------------------------------------------------------------


def get_repo_overview(
    db: sqlite3.Connection,
    *,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """High-level repository summary: languages, modules, claim stats."""
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)

    if not _has_claims(db):
        return make_ok_response(
            data={
                "languages": [],
                "language_coverage": {},
                "modules": [],
                "build_test_entrypoints": [],
                "indexing_status": "not_indexed",
                "support_envelope": {
                    "supported_languages": ["python", "javascript", "typescript"],
                    "unsupported_detected": [],
                    "file_count": 0,
                    "indexed_file_count": 0,
                    "excluded_count": 0,
                    "exclusion_reasons": {},
                },
                "claim_summary": {
                    "total": 0,
                    "by_type": {},
                    "by_review_state": {},
                    "conflicts": 0,
                },
            },
            repo_head=repo_head,
            branch=branch,
            index_version=idx,
        )

    # Claim counts by type
    type_rows = db.execute(
        "SELECT claim_type, COUNT(*) as cnt FROM claims WHERE 1=1"
        + (" AND repo_id = ?" if repo_id else "")
        + " GROUP BY claim_type",
        (repo_id,) if repo_id else (),
    ).fetchall()
    by_type = {str(r["claim_type"]): int(r["cnt"]) for r in type_rows}

    # Claim counts by review state
    state_rows = db.execute(
        "SELECT review_state, COUNT(*) as cnt FROM claims WHERE 1=1"
        + (" AND repo_id = ?" if repo_id else "")
        + " GROUP BY review_state",
        (repo_id,) if repo_id else (),
    ).fetchall()
    by_review_state = {str(r["review_state"]): int(r["cnt"]) for r in state_rows}

    total_claims = sum(by_type.values())
    conflict_count = by_type.get("conflict", 0)

    # Detect languages from evidence file extensions
    evidence_rows = db.execute("SELECT DISTINCT file_path FROM claim_evidence").fetchall()
    extensions: set[str] = set()
    for row in evidence_rows:
        fp = str(row["file_path"])
        if "." in fp:
            extensions.add(fp[fp.rfind(".") :].lower())

    supported_langs = ["python", "javascript", "typescript"]
    ext_to_lang: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }
    detected_langs = sorted({ext_to_lang[e] for e in extensions if e in ext_to_lang})
    language_coverage = dict.fromkeys(detected_langs, "full")

    # Modules from graph
    try:
        graph = SqliteRepoGraph(db, repo_id=repo_id, branch=branch)
        modules = [{"name": m, "path": m, "type": "package"} for m in graph.get_modules()]
    except Exception:
        modules = []

    # Build/test entrypoints from validated commands
    cmd_claims = store.list_claims(
        claim_type=ClaimType.VALIDATED_COMMAND,
        repo_id=repo_id if repo_id else None,
    )
    entrypoints = [c.content for c in cmd_claims]

    return make_ok_response(
        data={
            "languages": detected_langs,
            "language_coverage": language_coverage,
            "modules": modules,
            "build_test_entrypoints": entrypoints,
            "indexing_status": "complete",
            "support_envelope": {
                "supported_languages": supported_langs,
                "unsupported_detected": [],
                "file_count": 0,
                "indexed_file_count": len(evidence_rows),
                "excluded_count": 0,
                "exclusion_reasons": {},
            },
            "claim_summary": {
                "total": total_claims,
                "by_type": by_type,
                "by_review_state": by_review_state,
                "conflicts": conflict_count,
            },
        },
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


def get_claim(
    db: sqlite3.Connection,
    *,
    claim_id: str,
    repo_head: str = "",
    branch: str = "main",
) -> ToolResponse:
    """Full detail on a single claim — evidence chain + review history."""
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)
    claim = store.get(claim_id)

    if claim is None:
        return make_error_response(f"Claim not found: {claim_id}")

    ev_store = SqliteEvidenceStore(db)
    hist_store = SqliteHistoryStore(db)

    evidence_records = ev_store.get_for_claim(claim_id)
    history_records = hist_store.get_for_claim(claim_id)

    data: dict[str, Any] = {
        "id": claim.id,
        "content": claim.content,
        "claim_type": claim.claim_type.value,
        "source_authority": claim.source_authority.value,
        "confidence": claim.confidence,
        "scope": claim.scope,
        "applicability": list(claim.applicability),
        "review_state": claim.review_state.value,
        "sensitivity": claim.sensitivity.value,
        "evidence": list(claim.evidence),
        "evidence_chain": [
            {
                "file_path": e.file_path,
                "file_hash": e.file_hash,
                "line_start": e.line_start,
                "line_end": e.line_end,
                "evidence_level": e.evidence_level.value,
                "extraction_version": e.extraction_version,
            }
            for e in evidence_records
        ],
        "review_history": [
            {
                "action": h.action,
                "actor": h.actor,
                "timestamp": h.timestamp.isoformat() if h.timestamp else None,
                "reason": h.reason,
                "content_before": h.content_before,
                "content_after": h.content_after,
            }
            for h in history_records
        ],
        "freshness": {
            "last_validated": (claim.last_validated.isoformat() if claim.last_validated else None),
            "stale": claim.stale,
            "revalidation_trigger": claim.revalidation_trigger,
        },
    }

    if claim.risk_class is not None:
        data["risk_class"] = claim.risk_class.value

    return make_ok_response(
        data=data,
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
    )


def get_preflight_context(
    db: sqlite3.Connection,
    *,
    path_or_symbol: str,
    task_context: str | None = None,
    host: str | None = None,
    detail_level: str = "terse",
    allowlist: SourceAllowlist | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Minimum actionable bundle an agent needs before starting work.

    Combines scoped rules, validated commands, guardrails, environment,
    and unsupported area warnings into a single bounded response.
    """
    idx = _get_index_version(db)
    store = SqliteClaimStore(db)
    ev_store = SqliteEvidenceStore(db) if detail_level == "detailed" else None

    # Scoped conventions/rules
    always_on = store.list_claims(
        claim_type=ClaimType.ALWAYS_ON_RULE,
        repo_id=repo_id if repo_id else None,
    )
    scoped = store.list_claims(
        claim_type=ClaimType.SCOPED_RULE,
        repo_id=repo_id if repo_id else None,
    )
    rules = always_on + scoped
    rules = [c for c in rules if c.scope == path_or_symbol or c.scope == "**"]
    if task_context is not None:
        rules = [c for c in rules if "all" in c.applicability or task_context in c.applicability]
    rules = enforce_allowlist(rules, allowlist)
    rules.sort(key=lambda c: (source_authority_precedence(c.source_authority), c.id))

    # Validated commands for this scope
    commands = store.list_claims(
        claim_type=ClaimType.VALIDATED_COMMAND,
        repo_id=repo_id if repo_id else None,
    )
    commands = [c for c in commands if c.scope == path_or_symbol or c.scope == "**"]
    commands = enforce_allowlist(commands, allowlist)

    # Guardrails
    guardrails_raw = store.list_claims(
        claim_type=ClaimType.PERMISSION_RESTRICTION,
        repo_id=repo_id if repo_id else None,
    )
    guardrails_raw = [c for c in guardrails_raw if c.scope == path_or_symbol or c.scope == "**"]
    guardrails_raw = enforce_allowlist(guardrails_raw, allowlist)

    guardrail_items: list[dict[str, Any]] = []
    for g in guardrails_raw:
        gi = render_claim(g, detail_level, ev_store)
        is_enforceable = is_enforceable_restriction(g)
        if detail_level != "terse":
            gi["enforceable_on"] = (
                [host] if host and is_enforceable else (["claude"] if is_enforceable else [])
            )
        guardrail_items.append(gi)

    # Environment profiles
    profiles = _get_profiles(db, repo_id=repo_id)

    # Detect unsupported areas
    unsupported_areas: list[str] = []
    warnings: list[str] = []

    # Check for stale claims
    stale_claims = [c for c in rules + commands if c.stale]
    if stale_claims:
        warnings.append(f"{len(stale_claims)} stale claim(s) in scope — consider refreshing")

    # Check for conflicts in scope
    conflicts = store.list_claims(
        claim_type=ClaimType.CONFLICT,
        repo_id=repo_id if repo_id else None,
    )
    scope_conflicts = [c for c in conflicts if c.scope == path_or_symbol or c.scope == "**"]
    if scope_conflicts:
        warnings.append(f"{len(scope_conflicts)} unresolved conflict(s) in scope")

    return make_ok_response(
        data={
            "scoped_rules": [render_claim(r, detail_level, ev_store) for r in rules],
            "validated_commands": [render_claim(c, detail_level, ev_store) for c in commands],
            "guardrails": guardrail_items,
            "environment": {"profiles": profiles},
            "unsupported_areas": unsupported_areas,
            "warnings": warnings,
        },
        repo_head=repo_head,
        branch=branch,
        index_version=idx,
        warnings=tuple(warnings),
    )


def refresh_index(
    db: sqlite3.Connection,
    *,
    repo_root: Path | None = None,
    paths: list[str] | None = None,
    repo_id: str = "",
    branch: str = "main",
    repo_head: str = "",
) -> ToolResponse:
    """Trigger re-indexing. Returns extraction summary.

    For M7, runs full extraction synchronously.
    """
    if repo_root is None:
        return make_error_response("Repository root not configured — run rkp init first")

    from rkp.git.cli_backend import CliGitBackend
    from rkp.indexer.orchestrator import run_extraction

    warnings: list[str] = []
    if paths:
        warnings.append(
            f"Path-scoped refresh requested ({paths}) — "
            "full extraction performed (incremental path filtering not yet implemented)"
        )

    start = time.monotonic()
    try:
        git = CliGitBackend(repo_root)
        graph = SqliteRepoGraph(db, repo_id=repo_id, branch=branch)
        store = SqliteClaimStore(db)
        summary = run_extraction(
            repo_root,
            store,
            repo_id=repo_id,
            branch=branch,
            git_backend=git,
            graph=graph,
        )
        elapsed = time.monotonic() - start

        data: dict[str, Any] = {
            "files_parsed": summary.files_parsed,
            "claims_created": summary.claims_created,
            "claims_deduplicated": summary.claims_deduplicated,
            "elapsed_seconds": round(elapsed, 2),
        }
        if summary.warnings:
            warnings.extend(summary.warnings)

        return make_ok_response(
            data=data,
            repo_head=repo_head,
            branch=branch,
            index_version=_get_index_version(db),
            warnings=tuple(warnings),
        )
    except Exception as exc:
        return make_error_response(f"Refresh failed: {exc}")
