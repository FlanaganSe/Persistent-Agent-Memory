"""rkp apply — write approved projections to disk."""

from __future__ import annotations

import difflib
import hashlib
import sqlite3
from datetime import UTC, datetime
from typing import Any, cast

import typer
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from rkp.cli.app import AppState
from rkp.cli.ui.output import (
    console,
    print_error,
    print_info,
    print_json,
    print_success,
    print_warning,
)
from rkp.core.types import ReviewState
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.adapters.copilot import CopilotAdapter, validate_setup_steps
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.store.claims import SqliteClaimStore

_SUPPORTED_HOSTS = ("codex", "agents-md", "claude", "copilot")

_MAX_PREVIEW_LINES = 20


def _sha256(content: str) -> str:
    """Compute SHA-256 hex digest of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _artifact_type_for_path(path: str) -> str:
    """Derive artifact type from the file path."""
    if path.endswith(".json"):
        return "settings-snippet"
    if path.startswith(".claude/skills/"):
        return "skill"
    if path.startswith(".claude/rules/"):
        return "scoped-rule"
    if path.startswith(".github/instructions/"):
        return "scoped-instruction"
    if "copilot-setup-steps" in path:
        return "setup-steps"
    if path in ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md"):
        return "instruction-file"
    return "projected-file"


def _load_existing_artifacts(
    db: sqlite3.Connection,
) -> dict[str, str]:
    """Load managed artifacts from the DB, returning {path: expected_hash}."""
    rows = db.execute("SELECT path, expected_hash FROM managed_artifacts").fetchall()
    return {str(row["path"]): str(row["expected_hash"]) for row in rows}


def _load_owned_artifacts(
    db: sqlite3.Connection,
) -> set[str]:
    """Load paths of imported-human-owned artifacts that should not be overwritten."""
    rows = db.execute(
        "SELECT path FROM managed_artifacts WHERE ownership_mode = ?",
        ("imported-human-owned",),
    ).fetchall()
    return {str(row["path"]) for row in rows}


def apply(
    ctx: typer.Context,
    host: str = typer.Option("claude", help="Target host (codex, agents-md, claude, copilot)"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change without writing"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Write approved projections to disk as instruction files."""
    state: AppState = ctx.obj

    capability = get_capability(host)
    if capability is None:
        supported = ", ".join(_SUPPORTED_HOSTS)
        print_error(f"Unsupported host: {host}. Supported: {supported}")
        raise typer.Exit(code=2)

    try:
        db = state.ensure_db()
        claim_store = SqliteClaimStore(db)
        repo_id = str(state.repo_path)
        claims = claim_store.list_claims(repo_id=repo_id)

        # Filter to only approved/edited claims
        approved_claims = [
            c for c in claims if c.review_state in (ReviewState.APPROVED, ReviewState.EDITED)
        ]

        if not approved_claims:
            if state.json_output:
                print_json(
                    {
                        "status": "no_approved_claims",
                        "message": "No approved claims to project. Run rkp review first.",
                    }
                )
            else:
                print_error("No approved claims to project. Run rkp review first.")
            raise typer.Exit(code=1)

        # Select adapter
        adapter: AgentsMdAdapter | ClaudeMdAdapter | CopilotAdapter
        if host == "claude":
            adapter = ClaudeMdAdapter()
        elif host == "copilot":
            adapter = CopilotAdapter()
        else:
            adapter = AgentsMdAdapter()

        policy = ProjectionPolicy()
        result = project(approved_claims, adapter, capability, policy)
        files = result.adapter_result.files

        if not files:
            if state.json_output:
                print_json({"status": "no_files", "message": "Projection produced no files."})
            else:
                print_info("Projection produced no files.")
            raise typer.Exit(code=0)

        # Copilot-specific: validate setup-steps before writing
        setup_steps_path = ".github/workflows/copilot-setup-steps.yml"
        copilot_setup_errors: list[str] = []
        if host == "copilot" and setup_steps_path in files:
            import yaml as _yaml

            try:
                parsed: object = _yaml.safe_load(files[setup_steps_path])
                if isinstance(parsed, dict):
                    copilot_setup_errors = validate_setup_steps(cast(dict[str, Any], parsed))
            except _yaml.YAMLError as exc:
                copilot_setup_errors = [f"Invalid YAML: {exc}"]

            if copilot_setup_errors:
                if not state.json_output and not state.quiet:
                    print_warning("copilot-setup-steps.yml validation failed:")
                    for err in copilot_setup_errors:
                        print_warning(f"  - {err}")
                    print_warning("Setup-steps will NOT be written. Other files will proceed.")
                # Remove setup-steps from files to write
                del files[setup_steps_path]

        # Copilot-specific: respect artifact ownership for imported-human-owned files
        if host == "copilot":
            owned_artifacts = _load_owned_artifacts(db)
            for owned_path in owned_artifacts:
                if owned_path in files:
                    if not state.json_output and not state.quiet:
                        print_warning(f"{owned_path}: imported-human-owned, skipping overwrite")
                    del files[owned_path]

        # Load existing managed artifact hashes for drift detection
        existing_hashes = _load_existing_artifacts(db)

        # Build per-file change info
        file_actions: list[dict[str, str]] = []
        files_to_write: dict[str, str] = {}
        drift_warnings: list[str] = []

        for rel_path, content in sorted(files.items()):
            abs_path = state.repo_path / rel_path

            if abs_path.exists():
                disk_content = abs_path.read_text(encoding="utf-8")
                disk_hash = _sha256(disk_content)

                # Check for manual drift on managed files
                if rel_path in existing_hashes:
                    expected = existing_hashes[rel_path]
                    if disk_hash != expected:
                        msg = (
                            f"{rel_path}: file was manually edited since last apply "
                            f"(expected {expected[:12]}..., found {disk_hash[:12]}...)"
                        )
                        drift_warnings.append(msg)

                if disk_content == content:
                    file_actions.append({"path": rel_path, "action": "unchanged"})
                    continue

                file_actions.append({"path": rel_path, "action": "updated"})
                files_to_write[rel_path] = content

                if not state.json_output and not state.quiet:
                    old_lines = disk_content.splitlines(keepends=True)
                    new_lines = content.splitlines(keepends=True)
                    diff_text = "".join(
                        difflib.unified_diff(
                            old_lines,
                            new_lines,
                            fromfile=f"a/{rel_path}",
                            tofile=f"b/{rel_path}",
                        )
                    )
                    if diff_text:
                        console.print(
                            Panel(
                                Syntax(diff_text, "diff", theme="monokai"),
                                title=f"UPDATE {rel_path}",
                                border_style="yellow",
                            )
                        )
            else:
                file_actions.append({"path": rel_path, "action": "new"})
                files_to_write[rel_path] = content

                if not state.json_output and not state.quiet:
                    preview_lines = content.splitlines()[:_MAX_PREVIEW_LINES]
                    preview_text = "\n".join(preview_lines)
                    if len(content.splitlines()) > _MAX_PREVIEW_LINES:
                        preview_text += (
                            f"\n... ({len(content.splitlines()) - _MAX_PREVIEW_LINES} more lines)"
                        )
                    console.print(
                        Panel(
                            preview_text,
                            title=f"NEW FILE {rel_path}",
                            border_style="green",
                        )
                    )

        # Show drift warnings
        for warning in drift_warnings:
            if state.json_output:
                pass  # included in JSON output below
            else:
                print_warning(warning)

        # Summary
        new_count = sum(1 for f in file_actions if f["action"] == "new")
        updated_count = sum(1 for f in file_actions if f["action"] == "updated")
        unchanged_count = sum(1 for f in file_actions if f["action"] == "unchanged")

        if not state.json_output and not state.quiet:
            console.print(
                f"\n[bold]Summary:[/bold] {new_count} new, "
                f"{updated_count} updated, {unchanged_count} unchanged"
            )

        if not files_to_write:
            if state.json_output:
                print_json(
                    {
                        "status": "no_changes",
                        "files": file_actions,
                        "drift_warnings": drift_warnings,
                    }
                )
            elif not state.quiet:
                print_info("All files are already up to date.")
            raise typer.Exit(code=0)

        # Dry run: show what would happen and exit
        if dry_run:
            if state.json_output:
                print_json(
                    {
                        "status": "dry_run",
                        "files": file_actions,
                        "drift_warnings": drift_warnings,
                        "would_write": len(files_to_write),
                    }
                )
            elif not state.quiet:
                print_info("Dry run — no files written.")
            raise typer.Exit(code=0)

        # Confirmation
        if not yes and not state.json_output:
            write_count = len(files_to_write)
            if not Confirm.ask(
                f"Write {write_count} file{'s' if write_count != 1 else ''}?",
                default=False,
                console=console,
            ):
                print_info("Aborted.")
                raise typer.Exit(code=0)

        # Write files
        now = datetime.now(UTC).isoformat()
        written_summaries: list[str] = []

        for rel_path, content in sorted(files_to_write.items()):
            abs_path = state.repo_path / rel_path
            action = "new" if not abs_path.exists() else "updated"

            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content, encoding="utf-8")

            content_hash = _sha256(content)
            artifact_type = _artifact_type_for_path(rel_path)

            # Upsert managed artifact record
            db.execute(
                """INSERT OR REPLACE INTO managed_artifacts
                   (path, artifact_type, target_host, expected_hash, last_projected, ownership_mode)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rel_path, artifact_type, host, content_hash, now, "managed-by-rkp"),
            )

            written_summaries.append(f"{rel_path} ({action})")

        db.commit()

        # Output
        if state.json_output:
            print_json(
                {
                    "status": "success",
                    "files": file_actions,
                    "written": len(files_to_write),
                    "drift_warnings": drift_warnings,
                    "managed_artifacts": [
                        {
                            "path": rel_path,
                            "artifact_type": _artifact_type_for_path(rel_path),
                            "target_host": host,
                            "hash": _sha256(files_to_write[rel_path]),
                        }
                        for rel_path in sorted(files_to_write)
                    ],
                }
            )
        elif not state.quiet:
            summary_str = ", ".join(written_summaries)
            print_success(
                f"Wrote {len(files_to_write)} file{'s' if len(files_to_write) != 1 else ''}: "
                f"{summary_str}"
            )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Apply failed: {exc}")
        if state.verbose > 0:
            console.print_exception()
        raise typer.Exit(code=2) from exc
