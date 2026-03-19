"""Host capability descriptors for projection targets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizeConstraints:
    """Size limits for a host's instruction surface."""

    hard_budget_bytes: int
    soft_budget_lines: int | None = None


@dataclass(frozen=True)
class HostCapability:
    """Describes what a host supports for instruction projection."""

    host_name: str
    supports_always_on: bool
    supports_scoped_rules: bool
    supports_skills: bool
    supports_env: bool
    supports_permissions: bool
    size_constraints: SizeConstraints


AGENTS_MD_CAPABILITY = HostCapability(
    host_name="agents-md",
    supports_always_on=True,
    supports_scoped_rules=True,
    supports_skills=True,
    supports_env=False,
    supports_permissions=False,
    size_constraints=SizeConstraints(hard_budget_bytes=32768),
)

_CAPABILITIES: dict[str, HostCapability] = {
    "agents-md": AGENTS_MD_CAPABILITY,
    "codex": AGENTS_MD_CAPABILITY,
}


def get_capability(host: str) -> HostCapability | None:
    """Look up the capability descriptor for a host."""
    return _CAPABILITIES.get(host)
