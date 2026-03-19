"""rkp preview — show projected instruction artifact without writing."""

from __future__ import annotations

import json
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from rkp.cli.app import AppState
from rkp.cli.ui.output import console as err_console
from rkp.cli.ui.output import print_error
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.store.claims import SqliteClaimStore

_SUPPORTED_HOSTS = ("codex", "agents-md", "claude")


def preview(
    ctx: typer.Context,
    host: str = typer.Option("codex", help="Target host (codex, agents-md, claude)"),
) -> None:
    """Preview projected instruction artifact for a target host."""
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

        if not claims:
            if not state.quiet and not state.json_output:
                err_console.print("[dim]No claims found, running extraction...[/dim]")
            from rkp.indexer.orchestrator import run_extraction

            summary = run_extraction(
                state.repo_path,
                claim_store,
                repo_id=repo_id,
                git_backend=state.ensure_git(),
            )
            claims = claim_store.list_claims(repo_id=repo_id)
            if state.verbose > 0 and not state.quiet:
                err_console.print(
                    f"[dim]Extracted {summary.claims_created} claims from "
                    f"{summary.files_parsed} files[/dim]"
                )

        # Select adapter
        adapter = ClaudeMdAdapter() if host == "claude" else AgentsMdAdapter()

        policy = ProjectionPolicy()
        result = project(claims, adapter, capability, policy)

        # Output
        files = result.adapter_result.files

        if state.json_output:
            output = {
                "host": host,
                "files": files,
                "excluded_sensitive": result.excluded_sensitive,
                "excluded_low_confidence": result.excluded_low_confidence,
                "overflow_report": result.adapter_result.overflow_report,
            }
            sys.stdout.write(json.dumps(output, indent=2) + "\n")
        elif host == "claude":
            _display_claude_output(files, state.quiet)
        else:
            content = files.get("AGENTS.md", "")
            if not state.quiet:
                # Show size info to stderr
                lines = content.count("\n") + (1 if content else 0)
                byte_count = len(content.encode("utf-8"))
                err_console.print(
                    f"[dim]AGENTS.md: {lines} lines, {byte_count:,} bytes (32 KiB budget)[/dim]"
                )
            sys.stdout.write(content)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    except Exception as exc:
        print_error(f"Preview failed: {exc}")
        if state.verbose > 0:
            err_console.print_exception()
        raise typer.Exit(code=2) from exc


def _display_claude_output(files: dict[str, str], quiet: bool) -> None:
    """Display multi-file Claude output with Rich panels."""
    out = Console()

    # CLAUDE.md
    claude_md = files.get("CLAUDE.md", "")
    if claude_md:
        if not quiet:
            lines = claude_md.count("\n") + 1
            err_console.print(f"[dim]CLAUDE.md: {lines} lines (200-line budget)[/dim]")
        out.print(Panel(claude_md, title="CLAUDE.md", border_style="green"))

    # .claude/rules/ files
    rule_files = {k: v for k, v in sorted(files.items()) if k.startswith(".claude/rules/")}
    for path, content in rule_files.items():
        out.print(Panel(content, title=path, border_style="blue"))

    # .claude/skills/ files
    skill_files = {k: v for k, v in sorted(files.items()) if k.startswith(".claude/skills/")}
    for path, content in skill_files.items():
        out.print(Panel(content, title=path, border_style="cyan"))

    # Settings snippet
    settings = files.get(".claude/settings-snippet.json", "")
    if settings:
        syntax = Syntax(settings, "json", theme="monokai")
        out.print(Panel(syntax, title=".claude/settings-snippet.json", border_style="yellow"))
