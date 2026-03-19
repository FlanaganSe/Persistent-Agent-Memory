"""rkp audit — query the audit trail for claims."""

from __future__ import annotations

import typer
from rich.table import Table

from rkp.cli.app import AppState
from rkp.cli.ui.output import console, print_error, print_json


def audit(
    ctx: typer.Context,
    claim_id: str | None = typer.Option(None, "--claim-id", help="Filter to a specific claim"),
    scope: str | None = typer.Option(None, "--scope", help="Filter to claims in scope"),
    action: str | None = typer.Option(None, "--action", help="Filter to a specific action"),
    since: str | None = typer.Option(None, "--since", help="Only entries since this ISO date"),
    limit: int = typer.Option(100, "--limit", help="Max entries to return"),
) -> None:
    """Query the audit trail for a claim or scope."""
    state: AppState = ctx.obj
    repo_path = state.repo_path
    config_path = repo_path / ".rkp" / "config.yaml"

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

        from rkp.store.history import SqliteHistoryStore

        history_store = SqliteHistoryStore(db)

        # Query based on filters
        if scope is not None:
            entries = history_store.query_by_scope(scope, limit=limit)
            # Apply additional filters on the result
            if action is not None:
                entries = [e for e in entries if e.action == action]
            if since is not None:
                entries = [
                    e
                    for e in entries
                    if e.timestamp is not None and e.timestamp.isoformat() >= since
                ]
            if claim_id is not None:
                entries = [e for e in entries if e.claim_id == claim_id]
        else:
            entries = history_store.query(
                claim_id=claim_id,
                action=action,
                since=since,
                limit=limit,
            )

        if state.json_output:
            print_json(
                {
                    "status": "ok",
                    "count": len(entries),
                    "entries": [
                        {
                            "claim_id": e.claim_id,
                            "action": e.action,
                            "actor": e.actor,
                            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                            "reason": e.reason,
                            "content_before": e.content_before,
                            "content_after": e.content_after,
                        }
                        for e in entries
                    ],
                }
            )
        elif not state.quiet:
            if not entries:
                console.print("No audit trail entries found.")
            else:
                console.print(f"Audit trail ({len(entries)} entries)")
                console.print()

                table = Table(show_lines=True)
                table.add_column("Timestamp", style="dim")
                table.add_column("Claim", style="cyan")
                table.add_column("Action")
                table.add_column("Details")

                for entry in entries:
                    ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "—"
                    cid = entry.claim_id[:16] if len(entry.claim_id) > 16 else entry.claim_id
                    action_str = entry.action

                    details_parts: list[str] = []
                    if entry.actor and entry.actor != "system":
                        details_parts.append(f"by {entry.actor}")
                    if entry.reason:
                        details_parts.append(entry.reason)
                    if entry.content_before and entry.content_after:
                        before_preview = entry.content_before[:30]
                        after_preview = entry.content_after[:30]
                        details_parts.append(f'"{before_preview}" -> "{after_preview}"')

                    details = "; ".join(details_parts) if details_parts else "by system"
                    table.add_row(ts, cid, action_str, details)

                console.print(table)

        raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Audit query failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc
