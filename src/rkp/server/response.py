"""MCP response envelope for all tool responses.

Every response includes: status, supported, unsupported_reason, data,
warnings, provenance. No field is conditionally omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ResponseProvenance:
    """Provenance metadata for MCP responses."""

    index_version: str = ""
    repo_head: str = ""
    branch: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class ResponseFreshness:
    """Freshness metadata for MCP responses."""

    index_age_seconds: int = 0
    stale_claims_in_response: int = 0
    head_current: bool = True


@dataclass(frozen=True)
class ToolResponse:
    """Standard envelope for every MCP tool response.

    JSON-serializable via to_dict(). All fields are always present
    in the serialized output — no conditional omission.
    """

    status: str
    supported: bool = True
    unsupported_reason: str | None = None
    data: object = None
    warnings: tuple[str, ...] = ()
    provenance: ResponseProvenance = ResponseProvenance()
    freshness: ResponseFreshness = ResponseFreshness()

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict with consistent envelope."""
        return {
            "status": self.status,
            "supported": self.supported,
            "unsupported_reason": self.unsupported_reason,
            "data": self.data,
            "warnings": list(self.warnings),
            "provenance": {
                "index_version": self.provenance.index_version,
                "repo_head": self.provenance.repo_head,
                "branch": self.provenance.branch,
                "timestamp": self.provenance.timestamp,
            },
            "freshness": {
                "index_age_seconds": self.freshness.index_age_seconds,
                "stale_claims_in_response": self.freshness.stale_claims_in_response,
                "head_current": self.freshness.head_current,
            },
        }


def make_ok_response(
    data: object,
    *,
    repo_head: str = "",
    branch: str = "",
    index_version: str = "",
    warnings: tuple[str, ...] = (),
    freshness: ResponseFreshness | None = None,
) -> ToolResponse:
    """Create a successful response with provenance."""
    return ToolResponse(
        status="ok",
        data=data,
        warnings=warnings,
        provenance=ResponseProvenance(
            index_version=index_version,
            repo_head=repo_head,
            branch=branch,
            timestamp=_now_iso(),
        ),
        freshness=freshness or ResponseFreshness(),
    )


def make_partial_response(
    data: object,
    *,
    repo_head: str = "",
    branch: str = "",
    index_version: str = "",
    warnings: tuple[str, ...] = (),
) -> ToolResponse:
    """Create a partial response (e.g., index incomplete)."""
    return ToolResponse(
        status="partial",
        data=data,
        warnings=warnings,
        provenance=ResponseProvenance(
            index_version=index_version,
            repo_head=repo_head,
            branch=branch,
            timestamp=_now_iso(),
        ),
    )


def make_unsupported_response(
    reason: str,
    *,
    repo_head: str = "",
    branch: str = "",
) -> ToolResponse:
    """Create an unsupported response for out-of-envelope queries."""
    return ToolResponse(
        status="unsupported",
        supported=False,
        unsupported_reason=reason,
        data=None,
        provenance=ResponseProvenance(
            repo_head=repo_head,
            branch=branch,
            timestamp=_now_iso(),
        ),
    )


def make_error_response(message: str) -> ToolResponse:
    """Create an error response."""
    return ToolResponse(
        status="error",
        data={"error": message},
        warnings=(message,),
        provenance=ResponseProvenance(
            timestamp=_now_iso(),
        ),
    )
