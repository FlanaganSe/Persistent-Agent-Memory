"""rkp refresh — re-analyze repo and present diff of what changed."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import typer
from rich.table import Table

from rkp.cli.app import AppState
from rkp.cli.ui.output import console, print_error, print_info, print_json


def refresh(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show diff without updating DB"),
) -> None:
    """Re-analyze the repo and present what changed in the claim model."""
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
        git_backend = state.ensure_git()

        from rkp.core.config import RkpConfig
        from rkp.core.freshness import check_all_freshness
        from rkp.store.claims import SqliteClaimStore
        from rkp.store.evidence import SqliteEvidenceStore
        from rkp.store.history import SqliteHistoryStore
        from rkp.store.metadata import IndexMetadata, SqliteMetadataStore

        claim_store = SqliteClaimStore(db)
        evidence_store = SqliteEvidenceStore(db)
        history_store = SqliteHistoryStore(db)
        metadata_store = SqliteMetadataStore(db)
        repo_id = str(repo_path)

        # Suppress structlog in JSON/quiet mode
        if state.json_output or state.quiet:
            import logging

            logging.getLogger().setLevel(logging.CRITICAL)

        # 1. Load index metadata
        metadata = metadata_store.load()

        # 2. Snapshot current state (claim IDs + content hashes for diff)
        pre_claims = claim_store.list_claims(repo_id=repo_id)
        pre_claim_map = {c.id: c.content for c in pre_claims}
        pre_claim_set = set(pre_claim_map.keys())

        # 3. Run freshness check
        config = RkpConfig(staleness_window_days=state.config.staleness_window_days)
        freshness_report = (
            check_all_freshness(
                claim_store,
                evidence_store,
                git_backend,
                config,
                index_metadata=metadata,
                repo_id=repo_id,
            )
            if git_backend
            else None
        )

        # 4. Record staleness events in audit trail
        if freshness_report and not dry_run:
            for claim_id in freshness_report.stale_claim_ids:
                detail = freshness_report.stale_details.get(claim_id)
                reason = detail.staleness_reason if detail else "Evidence changed"
                history_store.record(
                    claim_id=claim_id,
                    action="stale",
                    actor="system",
                    reason=reason,
                )
                # Update claim's stale flag
                claim = claim_store.get(claim_id)
                if claim is not None:
                    updated = replace(
                        claim,
                        stale=True,
                        revalidation_trigger=detail.revalidation_trigger
                        if detail
                        else "evidence-changed",
                    )
                    claim_store.update(updated)

        # 5. Run incremental extraction (skip if dry_run)
        if not dry_run:
            from rkp.graph.repo_graph import SqliteRepoGraph
            from rkp.indexer.orchestrator import run_extraction

            branch = git_backend.current_branch() if git_backend else "main"
            graph = SqliteRepoGraph(db)

            if not state.quiet and not state.json_output:
                print_info("Running extraction...")

            summary = run_extraction(
                repo_path,
                claim_store,
                repo_id=repo_id,
                branch=branch,
                git_backend=git_backend,
                graph=graph,
            )

            # Mark revalidated claims (existed before, still exist, content unchanged)
            post_claims = claim_store.list_claims(repo_id=repo_id)
            post_claim_map = {c.id: c.content for c in post_claims}

            for claim_id in pre_claim_set:
                if (
                    claim_id in post_claim_map
                    and pre_claim_map[claim_id] == post_claim_map[claim_id]
                ):
                    # Claim unchanged — revalidate if it was stale
                    claim = claim_store.get(claim_id)
                    if claim is not None and claim.stale:
                        revalidated = replace(
                            claim,
                            stale=False,
                            revalidation_trigger=None,
                            last_validated=datetime.now(UTC),
                        )
                        claim_store.update(revalidated)
                        history_store.record(
                            claim_id=claim_id,
                            action="revalidated",
                            actor="system",
                            reason="Evidence unchanged after refresh",
                        )
        else:
            post_claims = pre_claims
            post_claim_map = pre_claim_map
            summary = None

        # 6. Compute diff
        post_claim_set = set(post_claim_map.keys())
        new_ids = post_claim_set - pre_claim_set
        removed_ids = pre_claim_set - post_claim_set
        updated_ids = {
            cid
            for cid in pre_claim_set & post_claim_set
            if pre_claim_map[cid] != post_claim_map[cid]
        }
        stale_ids: set[str] = set(freshness_report.stale_claim_ids) if freshness_report else set()
        # Stale claims not counting those already in new/updated/removed
        stale_only_ids: set[str] = stale_ids - new_ids - updated_ids - removed_ids
        stable_ids: set[str] = (pre_claim_set & post_claim_set) - updated_ids - stale_only_ids

        has_changes = bool(new_ids or updated_ids or stale_only_ids or removed_ids)

        # 7. Update index metadata
        if not dry_run and git_backend:
            metadata_store.save(
                IndexMetadata(
                    last_indexed=SqliteMetadataStore.now_iso(),
                    repo_head=git_backend.head(),
                    branch=git_backend.current_branch(),
                    file_count=summary.files_parsed if summary else 0,
                    claim_count=len(post_claims),
                )
            )

        # 8. Present results
        files_analyzed = summary.files_parsed if summary else 0

        if state.json_output:
            print_json(
                {
                    "status": "changes_found" if has_changes else "no_changes",
                    "files_analyzed": files_analyzed,
                    "new_claims": len(new_ids),
                    "updated_claims": len(updated_ids),
                    "stale_claims": len(stale_only_ids),
                    "stable_claims": len(stable_ids),
                    "removed_claims": len(removed_ids),
                    "new_claim_ids": sorted(new_ids),
                    "updated_claim_ids": sorted(updated_ids),
                    "stale_claim_ids": sorted(stale_only_ids),
                    "removed_claim_ids": sorted(removed_ids),
                    "freshness": {
                        "branch_changed": freshness_report.branch_changed
                        if freshness_report
                        else False,
                        "head_changed": freshness_report.head_changed
                        if freshness_report
                        else False,
                        "stale_by_trigger": freshness_report.stale_by_trigger
                        if freshness_report
                        else {},
                    },
                    "dry_run": dry_run,
                }
            )
        elif not state.quiet:
            if not has_changes:
                console.print("No changes detected.")
            else:
                console.print(
                    f"Refresh complete (analyzed {files_analyzed} files"
                    + (", dry run" if dry_run else "")
                    + ")"
                )
                console.print()

                table = Table(show_lines=True)
                table.add_column("Change", style="cyan")
                table.add_column("Count", justify="right")

                table.add_row("New claims", str(len(new_ids)))
                table.add_row("Updated claims", str(len(updated_ids)))
                table.add_row("Stale claims", str(len(stale_only_ids)))
                table.add_row("Stable claims", str(len(stable_ids)))
                if removed_ids:
                    table.add_row("Removed claims", str(len(removed_ids)))

                console.print(table)

                if stale_only_ids:
                    console.print()
                    console.print("[yellow]Stale claims (evidence changed):[/yellow]")
                    for cid in sorted(stale_only_ids)[:10]:
                        claim = claim_store.get(cid)
                        detail = (
                            freshness_report.stale_details.get(cid) if freshness_report else None
                        )
                        content = claim.content[:60] if claim else "?"
                        reason = detail.staleness_reason if detail else ""
                        console.print(f'  {cid}: "{content}" — {reason}')
                    if len(stale_only_ids) > 10:
                        console.print(f"  ... and {len(stale_only_ids) - 10} more")

                if new_ids:
                    console.print()
                    console.print("[green]New claims:[/green]")
                    for cid in sorted(new_ids)[:10]:
                        claim = claim_store.get(cid)
                        content = claim.content[:60] if claim else "?"
                        console.print(f'  {cid}: "{content}"')
                    if len(new_ids) > 10:
                        console.print(f"  ... and {len(new_ids) - 10} more")

                console.print()
                console.print(
                    "Run [bold]rkp review[/bold] to review changes, "
                    "or [bold]rkp apply[/bold] to update projections."
                )

        exit_code = 1 if has_changes else 0
        raise typer.Exit(code=exit_code)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Refresh failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc
