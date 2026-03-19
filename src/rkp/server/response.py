"""MCP response envelope for all tool responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ResponseProvenance:
    """Provenance metadata for MCP responses."""

    index_version: str = ""
    repo_head: str = ""
    branch: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class ToolResponse:
    """Standard envelope for every MCP tool response.

    JSON-serializable via dataclasses.asdict().
    """

    status: str
    supported: bool = True
    unsupported_reason: str | None = None
    data: object = None
    warnings: tuple[str, ...] = ()
    provenance: ResponseProvenance = ResponseProvenance()

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-compatible dict."""
        result: dict[str, object] = {
            "status": self.status,
            "supported": self.supported,
        }
        if self.unsupported_reason is not None:
            result["unsupported_reason"] = self.unsupported_reason
        result["data"] = self.data
        if self.warnings:
            result["warnings"] = list(self.warnings)
        result["provenance"] = {
            "index_version": self.provenance.index_version,
            "repo_head": self.provenance.repo_head,
            "branch": self.provenance.branch,
            "timestamp": self.provenance.timestamp,
        }
        return result


def make_ok_response(
    data: object,
    *,
    repo_head: str = "",
    branch: str = "",
    warnings: tuple[str, ...] = (),
) -> ToolResponse:
    """Create a successful response with provenance."""
    return ToolResponse(
        status="ok",
        data=data,
        warnings=warnings,
        provenance=ResponseProvenance(
            index_version="0.1.0",
            repo_head=repo_head,
            branch=branch,
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )


def make_error_response(message: str) -> ToolResponse:
    """Create an error response."""
    return ToolResponse(
        status="error",
        supported=True,
        data=None,
        warnings=(message,),
        provenance=ResponseProvenance(
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
