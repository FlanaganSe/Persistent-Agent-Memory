"""Typed exception hierarchy for the Repo Knowledge Plane."""

from __future__ import annotations


class RkpError(Exception):
    """Base exception for all RKP errors."""


class ClaimError(RkpError):
    """Error related to claim operations."""


class ClaimNotFoundError(ClaimError):
    """Raised when a claim cannot be found by ID."""

    def __init__(self, claim_id: str) -> None:
        self.claim_id = claim_id
        super().__init__(f"Claim not found: {claim_id}")


class DuplicateClaimError(ClaimError):
    """Raised when attempting to create a claim that already exists."""

    def __init__(self, claim_id: str) -> None:
        self.claim_id = claim_id
        super().__init__(f"Duplicate claim: {claim_id}")


class ClaimConflictError(ClaimError):
    """Raised when conflicting claims are detected."""

    def __init__(self, claim_ids: tuple[str, ...], reason: str) -> None:
        self.claim_ids = claim_ids
        self.reason = reason
        super().__init__(f"Conflicting claims {claim_ids}: {reason}")


class StoreError(RkpError):
    """Error related to storage operations."""


class MigrationError(StoreError):
    """Error during database migration."""


class SecurityError(RkpError):
    """Error related to security violations."""


class PathTraversalError(SecurityError):
    """Raised when a path escapes the repo root."""

    def __init__(self, path: str, repo_root: str) -> None:
        self.path = path
        self.repo_root = repo_root
        super().__init__(f"Path '{path}' escapes repo root '{repo_root}'")


class UnsafeYamlError(SecurityError):
    """Raised when unsafe YAML operations are detected."""


class InjectionDetectedError(SecurityError):
    """Raised when injection markers are found in content."""

    def __init__(self, markers: list[str]) -> None:
        self.markers = markers
        super().__init__(f"Injection markers detected: {markers}")


class ConfigError(RkpError):
    """Error related to configuration."""
