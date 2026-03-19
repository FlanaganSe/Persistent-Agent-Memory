"""rkp purge — hard-delete tombstoned claims."""

from __future__ import annotations

import json

import typer
from rich.prompt import Confirm
from rich.table import Table

from rkp.cli.app import AppState
from rkp.cli.ui.output import console, print_error, print_info, print_json, print_success
from rkp.core.models import Claim
from rkp.core.types import ReviewState
from rkp.store.claims import SqliteClaimStore
from rkp.store.evidence import SqliteEvidenceStore
from rkp.store.history import SqliteHistoryStore
from rkp.store.overrides import FileSystemOverrideStore


def purge(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be purged without purging"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Permanently delete all tombstoned claims, their evidence, and override files."""
    state: AppState = ctx.obj

    try:
        db = state.ensure_db()
        claim_store = SqliteClaimStore(db)
        evidence_store = SqliteEvidenceStore(db)
        history_store = SqliteHistoryStore(db)
        overrides_dir = state.repo_path / ".rkp" / "overrides"
        override_store = FileSystemOverrideStore(overrides_dir)

        tombstoned = claim_store.list_claims(review_state=ReviewState.TOMBSTONED)

        if not tombstoned:
            if state.json_output:
                print_json({"purged": 0, "message": "Nothing to purge."})
            elif not state.quiet:
                print_info("Nothing to purge.")
            raise typer.Exit(code=0)

        count = len(tombstoned)

        # Build a lookup for tombstone reasons from history.
        reasons: dict[str, str] = {}
        for claim in tombstoned:
            history = history_store.get_for_claim(claim.id)
            for entry in reversed(history):
                if entry.action == "tombstone" and entry.reason:
                    reasons[claim.id] = entry.reason
                    break

        if state.json_output:
            items = [
                {
                    "id": c.id,
                    "content": c.content[:60],
                    "review_state": c.review_state.value,
                    "reason": reasons.get(c.id),
                }
                for c in tombstoned
            ]
            if dry_run:
                print_json({"dry_run": True, "count": count, "claims": items})
                raise typer.Exit(code=0)

            if not yes and not Confirm.ask(
                f"Permanently delete {count} tombstoned claim{'s' if count != 1 else ''}? "
                "This cannot be undone.",
                console=console,
            ):
                print_json({"purged": 0, "message": "Purge cancelled."})
                raise typer.Exit(code=0)

            purged_ids = _execute_purge(
                tombstoned, claim_store, evidence_store, override_store, history_store
            )
            print_json(
                {
                    "purged": len(purged_ids),
                    "ids": purged_ids,
                    "message": f"Purged {len(purged_ids)} claims. Purge logged in audit trail.",
                }
            )
            raise typer.Exit(code=0)

        # Rich table display.
        if not state.quiet:
            table = Table(title="Tombstoned Claims", show_lines=True)
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Content", max_width=60)
            table.add_column("Review State", style="red")
            table.add_column("Reason", style="dim")

            for claim in tombstoned:
                content_display = claim.content[:60] + ("..." if len(claim.content) > 60 else "")
                table.add_row(
                    claim.id,
                    content_display,
                    claim.review_state.value,
                    reasons.get(claim.id, ""),
                )

            console.print(table)
            console.print(f"\nFound {count} tombstoned claim{'s' if count != 1 else ''}.")

        if dry_run:
            if not state.quiet:
                print_info("Dry run — no claims were purged.")
            raise typer.Exit(code=0)

        if not yes and not Confirm.ask(
            f"Permanently delete {count} tombstoned claim{'s' if count != 1 else ''}? "
            "This cannot be undone.",
            console=console,
        ):
            if not state.quiet:
                print_info("Purge cancelled.")
            raise typer.Exit(code=0)

        purged_ids = _execute_purge(
            tombstoned, claim_store, evidence_store, override_store, history_store
        )

        if not state.quiet:
            print_success(
                f"Purged {len(purged_ids)} claim{'s' if len(purged_ids) != 1 else ''}. "
                "Purge logged in audit trail."
            )
        raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Purge failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc


def _execute_purge(
    claims: list[Claim],
    claim_store: SqliteClaimStore,
    evidence_store: SqliteEvidenceStore,
    override_store: FileSystemOverrideStore,
    history_store: SqliteHistoryStore,
) -> list[str]:
    """Delete tombstoned claims, their evidence, and override files. Returns purged IDs."""
    db = claim_store.connection
    purged_ids: list[str] = []

    for claim in claims:
        evidence_store.delete_for_claim(claim.id)
        # Delete FK-constrained history rows before the claim itself.
        db.execute("DELETE FROM claim_history WHERE claim_id = ?", (claim.id,))
        claim_store.delete(claim.id)
        override_store.delete_override(claim.id)
        purged_ids.append(claim.id)

    # Record the purge event in session_log (no FK constraint on claims).
    db.execute(
        "INSERT INTO session_log (session_id, event_type, event_data) VALUES (?, ?, ?)",
        ("purge", "purge", json.dumps(purged_ids)),
    )
    db.commit()

    return purged_ids
