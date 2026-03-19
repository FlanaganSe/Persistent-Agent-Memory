"""rkp status — operational dashboard."""

from __future__ import annotations

from collections import Counter

import typer
from rich.table import Table

from rkp.cli.app import AppState
from rkp.cli.ui.output import console, print_error, print_json
from rkp.cli.ui.tables import CLAIM_TYPE_LABELS, render_review_state_table
from rkp.core.types import ClaimType, ReviewState


def status(
    ctx: typer.Context,
) -> None:
    """Show index health, pending reviews, and support envelope."""
    state: AppState = ctx.obj
    repo_path = state.repo_path
    config_path = repo_path / ".rkp" / "config.yaml"

    # Check initialization
    if not config_path.exists():
        if state.json_output:
            print_json(
                {
                    "status": "not_initialized",
                    "message": "RKP not initialized. Run rkp init first.",
                }
            )
        elif not state.quiet:
            print_error("RKP not initialized. Run rkp init first.")
        raise typer.Exit(code=3)

    try:
        db = state.ensure_db()
        from rkp.store.claims import SqliteClaimStore

        claim_store = SqliteClaimStore(db)
        repo_id = str(repo_path)
        claims = claim_store.list_claims(repo_id=repo_id)

        # Index health
        git_backend = state.ensure_git()
        current_head = git_backend.head() if git_backend else ""
        current_branch = git_backend.current_branch() if git_backend else ""

        # Metadata from DB (last indexed time from most recent claim)
        last_indexed = None
        if claims:
            timestamps = [c.created_at for c in claims if c.created_at]
            if timestamps:
                last_indexed = max(timestamps)

        # Claim summary by type
        type_counts: Counter[str] = Counter()
        type_confidence: dict[str, list[float]] = {}
        for claim in claims:
            ct = claim.claim_type.value
            type_counts[ct] += 1
            if ct not in type_confidence:
                type_confidence[ct] = []
            type_confidence[ct].append(claim.confidence)

        # Review state counts
        review_counts: Counter[str] = Counter()
        for claim in claims:
            review_counts[claim.review_state.value] += 1

        conflicts = type_counts.get(ClaimType.CONFLICT, 0)
        unreviewed = review_counts.get(ReviewState.UNREVIEWED, 0)
        needs_declaration = review_counts.get(ReviewState.NEEDS_DECLARATION, 0)

        # Support envelope
        from rkp.cli.commands.init import detect_languages

        supported_langs, unsupported_langs = detect_languages(repo_path)

        # Adapter state
        adapters = {
            "codex": "Preview available" if claims else "No claims indexed",
            "claude": "Preview available" if claims else "No claims indexed",
        }

        # Index staleness (simple HEAD-based; full staleness is M14)
        is_stale = False

        has_findings = conflicts > 0 or unreviewed > 0 or needs_declaration > 0

        if state.json_output:
            print_json(
                {
                    "status": "healthy" if not has_findings else "findings",
                    "index": {
                        "last_indexed": last_indexed.isoformat() if last_indexed else None,
                        "current_head": current_head,
                        "current_branch": current_branch,
                        "total_claims": len(claims),
                        "is_stale": is_stale,
                    },
                    "claims_by_type": dict(type_counts),
                    "claims_by_review_state": dict(review_counts),
                    "conflicts": conflicts,
                    "pending_reviews": {
                        "unreviewed": unreviewed,
                        "needs_declaration": needs_declaration,
                    },
                    "support_envelope": {
                        "supported": sorted(supported_langs),
                        "unsupported": sorted(unsupported_langs),
                    },
                    "adapters": adapters,
                }
            )
        elif not state.quiet:
            # Section 1: Index health
            console.print("[bold]Index Health[/bold]")
            if last_indexed:
                console.print(f"  Last indexed: {last_indexed:%Y-%m-%d %H:%M:%S}")
            if current_head:
                console.print(f"  HEAD: {current_head[:12]}")
            if current_branch:
                console.print(f"  Branch: {current_branch}")
            console.print(f"  Total claims: {len(claims)}")
            if is_stale:
                console.print(
                    "  [yellow]Index may be stale "
                    "(HEAD has changed since last extraction)[/yellow]"
                )
            else:
                console.print("  [green]Index is current[/green]")

            # Section 2: Claim summary
            console.print()
            table = Table(title="Claim Summary", show_lines=True)
            table.add_column("Claim Type", style="cyan")
            table.add_column("Count", justify="right")
            table.add_column("Confidence", justify="right")

            for ct_value in [ct.value for ct in ClaimType]:
                count = type_counts.get(ct_value, 0)
                if count == 0:
                    continue
                label = CLAIM_TYPE_LABELS.get(ct_value, ct_value)
                if ct_value == ClaimType.CONFLICT:
                    conf_str = "\u2014"
                else:
                    confs = type_confidence.get(ct_value, [])
                    avg = sum(confs) / len(confs) if confs else 0
                    conf_str = f"{avg:.0%} avg"
                table.add_row(label, str(count), conf_str)

            console.print(table)

            # Section 3: Review states
            if any(review_counts.get(s.value, 0) > 0 for s in ReviewState):
                console.print()
                console.print(render_review_state_table(claims))

            # Section 4: Pending reviews
            if unreviewed > 0 or needs_declaration > 0:
                console.print()
                total_pending = unreviewed + needs_declaration
                console.print(
                    f"[yellow]{total_pending} claim{'s' if total_pending != 1 else ''} "
                    f"awaiting review. Run rkp review to review them.[/yellow]"
                )

            # Section 5: Support envelope
            console.print()
            console.print("[bold]Support Envelope[/bold]")
            if supported_langs:
                console.print(f"  Supported: {', '.join(sorted(supported_langs))}")
            if unsupported_langs:
                console.print(f"  [dim]Unsupported: {', '.join(sorted(unsupported_langs))}[/dim]")

            # Section 6: Adapter state
            console.print()
            console.print("[bold]Adapters[/bold]")
            for host, adapter_status in adapters.items():
                console.print(f"  {host}: {adapter_status} (preview maturity)")

        if has_findings:
            raise typer.Exit(code=1)
        raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Status check failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc
