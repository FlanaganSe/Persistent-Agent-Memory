"""Rich UI helpers for the interactive claim review flow."""

from __future__ import annotations

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from rkp.cli.ui.output import console
from rkp.core.models import Claim
from rkp.core.types import ReviewState

# Border colour keyed by review state.
_BORDER_STYLES: dict[ReviewState, str] = {
    ReviewState.APPROVED: "green",
    ReviewState.UNREVIEWED: "yellow",
    ReviewState.NEEDS_DECLARATION: "red",
}

_DEFAULT_BORDER_STYLE = "dim"


def _border_for(state: ReviewState) -> str:
    return _BORDER_STYLES.get(state, _DEFAULT_BORDER_STYLE)


def _format_evidence(evidence: tuple[str, ...], limit: int = 3) -> str:
    """Format evidence items, truncating after *limit* entries."""
    if not evidence:
        return "(none)"
    lines = list(evidence[:limit])
    remaining = len(evidence) - limit
    if remaining > 0:
        lines.append(f"... and {remaining} more files")
    return "\n".join(f"  - {line}" for line in lines)


def _format_applicability(applicability: tuple[str, ...]) -> str:
    if not applicability:
        return "all"
    return ", ".join(applicability)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_claim_panel(claim: Claim, index: int, total: int) -> Panel:
    """Build a Rich Panel showing full claim details for review."""
    body_lines: list[str] = [
        f"[bold]Type:[/bold]        {claim.claim_type.value} ({claim.source_authority.value})",
        f"[bold]Scope:[/bold]       {claim.scope}",
        f"[bold]Confidence:[/bold]  {claim.confidence:.0%}",
        "",
        f"[bold]Content:[/bold]\n  {claim.content}",
        "",
        f"[bold]Evidence:[/bold]\n{_format_evidence(claim.evidence)}",
        "",
        f"[bold]Applicability:[/bold] {_format_applicability(claim.applicability)}",
        f"[bold]Review state:[/bold]  {claim.review_state.value}",
    ]
    return Panel(
        "\n".join(body_lines),
        title=f"Claim {claim.id} ({index}/{total})",
        border_style=_border_for(claim.review_state),
        expand=False,
    )


def render_declaration_panel(claim: Claim, index: int, total: int) -> Panel:
    """Build a special panel for claims that need a human declaration."""
    body_lines: list[str] = [
        "[bold red]RKP detected conflicting signals and needs your input:[/bold red]",
        "",
        f"  {claim.content}",
        "",
        f"[bold]Evidence:[/bold]\n{_format_evidence(claim.evidence)}",
    ]
    return Panel(
        "\n".join(body_lines),
        title=f"Declaration Needed ({index}/{total})",
        border_style="red",
        expand=False,
    )


def render_review_summary(
    approved: int,
    edited: int,
    suppressed: int,
    tombstoned: int,
    declared: int,
    skipped: int,
    total: int,
) -> Table:
    """Build a summary table for a completed review session."""
    table = Table(title="Review Session Summary")
    table.add_column("Action", style="cyan")
    table.add_column("Count", justify="right")

    table.add_row("Approved", str(approved))
    table.add_row("Edited", str(edited))
    table.add_row("Suppressed", str(suppressed))
    table.add_row("Tombstoned", str(tombstoned))
    table.add_row("Declared", str(declared))
    table.add_row("Skipped", str(skipped))
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    return table


def prompt_review_action(claim: Claim) -> str:
    """Prompt the reviewer for an action on *claim* and return the choice key."""
    if claim.review_state == ReviewState.NEEDS_DECLARATION:
        console.print(
            "[bold](r)[/bold]espond  "
            "[bold](s)[/bold]uppress  "
            "[bold](n)[/bold]ext  "
            "[bold](q)[/bold]uit"
        )
        return Prompt.ask(
            "Action",
            choices=["r", "s", "n", "q"],
            default="n",
            console=console,
        )
    console.print(
        "[bold](a)[/bold]pprove  "
        "[bold](e)[/bold]dit  "
        "[bold](s)[/bold]uppress  "
        "[bold](t)[/bold]ombstone  "
        "[bold](d)[/bold]eclare  "
        "[bold](n)[/bold]ext  "
        "[bold](q)[/bold]uit"
    )
    return Prompt.ask(
        "Action",
        choices=["a", "e", "s", "t", "d", "n", "q"],
        default="n",
        console=console,
    )


def prompt_declare_content() -> tuple[str, str, str, tuple[str, ...]]:
    """Interactively prompt for a new declaration.

    Returns:
        (content, claim_type, scope, applicability)
    """
    content = Prompt.ask("Content", console=console)
    claim_type = Prompt.ask("Claim type", default="always-on-rule", console=console)
    scope = Prompt.ask("Scope", default="**", console=console)
    raw_applicability = Prompt.ask(
        "Applicability (comma-separated)", default="all", console=console
    )
    applicability = tuple(s.strip() for s in raw_applicability.split(",") if s.strip())
    return (content, claim_type, scope, applicability)


def format_running_totals(
    approved: int,
    edited: int,
    suppressed: int,
    tombstoned: int,
    current: int,
    total: int,
) -> str:
    """Return a one-line progress string for the review loop."""
    parts: list[str] = []
    if approved:
        parts.append(f"{approved} approved")
    if edited:
        parts.append(f"{edited} edited")
    if suppressed:
        parts.append(f"{suppressed} suppressed")
    if tombstoned:
        parts.append(f"{tombstoned} tombstoned")
    detail = f" ({', '.join(parts)})" if parts else ""
    return f"Reviewed {current}/{total}{detail}"
