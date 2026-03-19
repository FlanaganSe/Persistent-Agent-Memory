"""rkp review — interactive claim governance interface."""

from __future__ import annotations

import contextlib
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from rkp.cli.app import AppState
from rkp.cli.ui.output import console, print_error, print_info, print_json, print_success
from rkp.core.ids import generate_claim_id
from rkp.core.models import Claim
from rkp.core.types import ClaimType, ReviewState, Sensitivity, SourceAuthority
from rkp.store.claims import SqliteClaimStore
from rkp.store.history import SqliteHistoryStore
from rkp.store.overrides import FileSystemOverrideStore, Override


def review(
    ctx: typer.Context,
    approve_all: bool = typer.Option(
        False, "--approve-all", help="Batch-approve high-confidence claims"
    ),
    threshold: float = typer.Option(
        0.95, "--threshold", help="Confidence threshold for --approve-all"
    ),
    claim_type: str | None = typer.Option(
        None, "--type", help="Filter by claim type (e.g. always-on-rule, validated-command)"
    ),
    scope_filter: str | None = typer.Option(None, "--scope", help="Filter by scope path"),
    state_filter: str | None = typer.Option(
        None, "--state", help="Filter by review state (unreviewed, needs-declaration)"
    ),
) -> None:
    """Review claims interactively or batch-approve high-confidence ones."""
    state: AppState = ctx.obj

    try:
        db = state.ensure_db()
        claim_store = SqliteClaimStore(db)
        history_store = SqliteHistoryStore(db)
        overrides_dir = state.repo_path / ".rkp" / "overrides"
        repo_id = str(state.repo_path)
        override_store = FileSystemOverrideStore(
            overrides_dir,
            history_store=history_store,
            claim_store=claim_store,
            repo_id=repo_id,
        )

        # Build filters.
        review_state: ReviewState | None = None
        if state_filter:
            try:
                review_state = ReviewState(state_filter)
            except ValueError:
                print_error(f"Invalid review state: {state_filter}")
                raise typer.Exit(code=2) from None

        ct: ClaimType | None = None
        if claim_type:
            try:
                ct = ClaimType(claim_type)
            except ValueError:
                print_error(f"Invalid claim type: {claim_type}")
                raise typer.Exit(code=2) from None

        # Load claims.
        all_claims = claim_store.list_claims(repo_id=repo_id)

        # Apply filters.
        candidates = _filter_claims(all_claims, review_state, ct, scope_filter)

        if not candidates:
            if state.json_output:
                print_json({"status": "empty", "message": "No claims to review."})
            elif not state.quiet:
                print_info("No claims to review.")
            raise typer.Exit(code=0)

        if approve_all:
            _batch_approve(candidates, threshold, override_store, state.json_output, state.quiet)
            raise typer.Exit(code=0)

        # Interactive review.
        _interactive_review(candidates, override_store, state)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Review failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc


def _filter_claims(
    claims: list[Claim],
    review_state: ReviewState | None,
    claim_type: ClaimType | None,
    scope_filter: str | None,
) -> list[Claim]:
    """Filter claims for review."""
    result: list[Claim] = []
    for claim in claims:
        # Default filter: unreviewed or needs-declaration.
        if review_state is None:
            if claim.review_state not in (ReviewState.UNREVIEWED, ReviewState.NEEDS_DECLARATION):
                continue
        elif claim.review_state != review_state:
            continue

        if claim_type is not None and claim.claim_type != claim_type:
            continue

        if scope_filter is not None and not claim.scope.startswith(scope_filter):
            continue

        result.append(claim)

    # Stable sort: needs-declaration first, then by confidence desc.
    return sorted(
        result,
        key=lambda c: (
            0 if c.review_state == ReviewState.NEEDS_DECLARATION else 1,
            -c.confidence,
            c.id,
        ),
    )


def _batch_approve(
    candidates: list[Claim],
    threshold: float,
    override_store: FileSystemOverrideStore,
    json_output: bool,
    quiet: bool,
) -> None:
    """Batch-approve claims meeting the threshold."""
    _strong_sources = frozenset(
        {
            SourceAuthority.HUMAN_OVERRIDE,
            SourceAuthority.DECLARED_REVIEWED,
            SourceAuthority.EXECUTABLE_CONFIG,
            SourceAuthority.CI_OBSERVED,
        }
    )

    approved: list[Claim] = []
    skipped: list[Claim] = []

    for claim in candidates:
        if (
            claim.confidence >= threshold
            and claim.source_authority in _strong_sources
            and claim.review_state == ReviewState.UNREVIEWED
        ):
            now = datetime.now(UTC)
            override = Override(
                claim_id=claim.id,
                action="approved",
                timestamp=now,
                actor="human",
            )
            override_store.save_override(override)
            approved.append(claim)
        else:
            skipped.append(claim)

    if json_output:
        print_json(
            {
                "status": "batch_approved",
                "approved": len(approved),
                "skipped": len(skipped),
                "threshold": threshold,
                "approved_ids": [c.id for c in approved],
            }
        )
    elif not quiet:
        console.print(
            f"Batch approved {len(approved)} claims "
            f"(confidence >= {threshold:.0%}, strong authority)"
        )
        if skipped:
            console.print(
                f"[dim]{len(skipped)} claims skipped (below threshold or weak authority)[/dim]"
            )


def _interactive_review(
    candidates: list[Claim],
    override_store: FileSystemOverrideStore,
    state: AppState,
) -> None:
    """Run the interactive review loop."""
    total = len(candidates)
    approved = 0
    edited = 0
    suppressed = 0
    tombstoned = 0
    declared = 0
    skipped = 0

    for i, claim in enumerate(candidates, 1):
        # Display the claim.
        if claim.review_state == ReviewState.NEEDS_DECLARATION:
            panel = _build_declaration_panel(claim, i, total)
            console.print(panel)
            action = Prompt.ask(
                "[bold]Action[/bold]",
                choices=["r", "s", "n", "q"],
                default="n",
                console=console,
            )
        else:
            panel = _build_claim_panel(claim, i, total)
            console.print(panel)
            action = Prompt.ask(
                "[bold]Action[/bold]",
                choices=["a", "e", "s", "t", "d", "n", "q"],
                default="n",
                console=console,
            )

        now = datetime.now(UTC)

        if action == "a":
            override = Override(claim_id=claim.id, action="approved", timestamp=now)
            override_store.save_override(override)
            approved += 1
            print_success("Approved")

        elif action == "e":
            new_content = _edit_content(claim.content)
            if new_content is None or new_content == claim.content:
                skipped += 1
                print_info("Edit cancelled or unchanged — skipping")
            else:
                override = Override(
                    claim_id=claim.id,
                    action="edited",
                    timestamp=now,
                    original_content=claim.content,
                    edited_content=new_content,
                )
                override_store.save_override(override)
                edited += 1
                print_success("Edited")

        elif action == "s":
            override = Override(claim_id=claim.id, action="suppressed", timestamp=now)
            override_store.save_override(override)
            suppressed += 1
            console.print("[yellow]Suppressed (hidden from outputs, evidence retained)[/yellow]")

        elif action == "t":
            reason = Prompt.ask("[dim]Reason (optional)[/dim]", default="", console=console)
            override = Override(
                claim_id=claim.id,
                action="tombstoned",
                timestamp=now,
                reason=reason if reason else None,
            )
            override_store.save_override(override)
            tombstoned += 1
            console.print("[red]Tombstoned[/red]")

        elif action == "d":
            decl = _prompt_declaration()
            if decl is not None:
                content, ct_str, scope, applicability = decl
                claim_id = generate_claim_id(ct_str, scope, content)
                override = Override(
                    claim_id=claim_id,
                    action="declared",
                    timestamp=now,
                    content=content,
                    claim_type=ct_str,
                    scope=scope,
                    applicability=applicability,
                    sensitivity=Sensitivity.PUBLIC.value,
                )
                override_store.save_override(override)
                declared += 1
                print_success("Declared new rule")
            else:
                skipped += 1
                print_info("Declaration cancelled")

        elif action == "r":
            # Respond to declaration prompt.
            answer = Prompt.ask("[bold]Your answer[/bold]", console=console)
            if answer.strip():
                claim_id = generate_claim_id(
                    ClaimType.ALWAYS_ON_RULE.value, claim.scope, answer.strip()
                )
                override = Override(
                    claim_id=claim_id,
                    action="declared",
                    timestamp=now,
                    content=answer.strip(),
                    claim_type=ClaimType.ALWAYS_ON_RULE.value,
                    scope=claim.scope,
                    applicability=claim.applicability or ("all",),
                    sensitivity=Sensitivity.PUBLIC.value,
                )
                override_store.save_override(override)
                # Suppress the original needs-declaration claim.
                suppress_override = Override(claim_id=claim.id, action="suppressed", timestamp=now)
                override_store.save_override(suppress_override)
                declared += 1
                print_success("Declaration recorded")
            else:
                skipped += 1
                print_info("Empty response — skipping")

        elif action == "n":
            skipped += 1

        elif action == "q":
            skipped += total - i
            break

        # Running totals.
        reviewed = approved + edited + suppressed + tombstoned
        console.print(
            f"[dim]Reviewed {reviewed}/{total} "
            f"({approved} approved, {edited} edited, "
            f"{suppressed} suppressed, {tombstoned} tombstoned)[/dim]"
        )
        console.print()

    # Final summary.
    if state.json_output:
        print_json(
            {
                "status": "review_complete",
                "approved": approved,
                "edited": edited,
                "suppressed": suppressed,
                "tombstoned": tombstoned,
                "declared": declared,
                "skipped": skipped,
                "total": total,
            }
        )
    elif not state.quiet:
        summary = _build_summary_table(approved, edited, suppressed, tombstoned, declared, skipped)
        console.print(summary)


def _build_claim_panel(claim: Claim, index: int, total: int) -> Panel:
    """Build a Rich Panel displaying claim details for review."""
    lines: list[str] = [
        f"[bold]Type:[/bold] {claim.claim_type.value} ({claim.source_authority.value})",
        f"[bold]Scope:[/bold] {claim.scope}",
        f"[bold]Confidence:[/bold] {claim.confidence:.0%}",
        "",
        "[bold]Content:[/bold]",
        f"  {claim.content}",
        "",
    ]

    if claim.evidence:
        lines.append("[bold]Evidence:[/bold]")
        lines.extend(f"  {ev}" for ev in claim.evidence[:3])
        if len(claim.evidence) > 3:
            lines.append(f"  ... and {len(claim.evidence) - 3} more files")
        lines.append("")

    if claim.applicability:
        lines.append(f"[bold]Applicability:[/bold] {', '.join(claim.applicability)}")

    lines.append(f"[bold]Review state:[/bold] {claim.review_state.value}")
    lines.append("")
    lines.append("[a]pprove [e]dit [s]uppress [t]ombstone [d]eclare [n]ext [q]uit")

    body = "\n".join(lines)
    return Panel(
        body,
        title=f"Claim {claim.id} ({index}/{total})",
        border_style="yellow" if claim.review_state == ReviewState.UNREVIEWED else "dim",
    )


def _build_declaration_panel(claim: Claim, index: int, total: int) -> Panel:
    """Build a Rich Panel for needs-declaration claims."""
    lines: list[str] = [
        "RKP detected conflicting signals and needs your input:",
        "",
        f"[bold]Question:[/bold] {claim.content}",
        "",
    ]

    if claim.evidence:
        lines.append("[bold]Evidence:[/bold]")
        lines.extend(f"  {ev}" for ev in claim.evidence[:5])
        if len(claim.evidence) > 5:
            lines.append(f"  ... and {len(claim.evidence) - 5} more")
        lines.append("")

    lines.append("[r]espond [s]uppress [n]ext [q]uit")

    body = "\n".join(lines)
    return Panel(
        body,
        title=f"Declaration Needed ({index}/{total})",
        border_style="red",
    )


def _build_summary_table(
    approved: int,
    edited: int,
    suppressed: int,
    tombstoned: int,
    declared: int,
    skipped: int,
) -> Table:
    """Build a summary table of the review session."""
    table = Table(title="Review Summary")
    table.add_column("Action", style="cyan")
    table.add_column("Count", justify="right")

    if approved:
        table.add_row("Approved", str(approved))
    if edited:
        table.add_row("Edited", str(edited))
    if suppressed:
        table.add_row("Suppressed", str(suppressed))
    if tombstoned:
        table.add_row("Tombstoned", str(tombstoned))
    if declared:
        table.add_row("Declared", str(declared))
    if skipped:
        table.add_row("Skipped", str(skipped))

    total = approved + edited + suppressed + tombstoned + declared + skipped
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    return table


def _edit_content(current_content: str) -> str | None:
    """Open content in $EDITOR for editing. Returns new content or None on failure."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")

    if editor:
        return _edit_with_editor(editor, current_content)

    # Fallback: simple prompt.
    return Prompt.ask("[bold]New content[/bold]", default=current_content, console=console)


def _edit_with_editor(editor: str, current_content: str) -> str | None:
    """Open a temp file in the editor, return modified content."""
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(current_content)
            tmp_path = f.name

        import shlex

        result = subprocess.run([*shlex.split(editor), tmp_path], check=False)
        if result.returncode != 0:
            return None

        new_content = Path(tmp_path).read_text(encoding="utf-8")
        return new_content.strip() if new_content.strip() else None
    except Exception:
        return None
    finally:
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                Path(tmp_path).unlink()


def _prompt_declaration() -> tuple[str, str, str, tuple[str, ...]] | None:
    """Prompt user for a new declaration. Returns (content, claim_type, scope, applicability)."""
    content = Prompt.ask("[bold]Rule content[/bold]", console=console)
    if not content.strip():
        return None

    claim_type_str = Prompt.ask(
        "[bold]Claim type[/bold]",
        default="always-on-rule",
        console=console,
    )
    scope = Prompt.ask("[bold]Scope[/bold]", default="**", console=console)
    app_str = Prompt.ask(
        "[bold]Applicability (comma-separated)[/bold]", default="all", console=console
    )
    applicability = tuple(tag.strip() for tag in app_str.split(",") if tag.strip())

    return content.strip(), claim_type_str, scope, applicability
