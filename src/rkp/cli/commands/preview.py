"""rkp preview — show projected instruction artifact without writing."""

from __future__ import annotations

import json
import sys
from typing import Any, cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from rkp.cli.app import AppState
from rkp.cli.ui.output import console as err_console
from rkp.cli.ui.output import print_error
from rkp.core.types import ReviewState
from rkp.projection.adapters.agents_md import AgentsMdAdapter
from rkp.projection.adapters.claude_md import ClaudeMdAdapter
from rkp.projection.adapters.copilot import CopilotAdapter
from rkp.projection.adapters.cursor import CursorAdapter
from rkp.projection.adapters.windsurf import WindsurfAdapter
from rkp.projection.capability_matrix import get_capability
from rkp.projection.engine import ProjectionPolicy, project
from rkp.store.claims import SqliteClaimStore

_SUPPORTED_HOSTS = ("codex", "agents-md", "claude", "copilot", "cursor", "windsurf")


def preview(
    ctx: typer.Context,
    host: str = typer.Option(
        "codex", help="Target host (codex, agents-md, claude, copilot, cursor, windsurf)"
    ),
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
                config=state.config,
            )
            git_backend = state.ensure_git()
            if git_backend is not None:
                from rkp.store.metadata import IndexMetadata, SqliteMetadataStore

                SqliteMetadataStore(db).save(
                    IndexMetadata(
                        last_indexed=SqliteMetadataStore.now_iso(),
                        repo_head=git_backend.head(),
                        branch=git_backend.current_branch(),
                        file_count=summary.files_parsed,
                        claim_count=summary.claims_created,
                    )
                )
            claims = claim_store.list_claims(repo_id=repo_id)
            if state.verbose > 0 and not state.quiet:
                err_console.print(
                    f"[dim]Extracted {summary.claims_created} claims from "
                    f"{summary.files_parsed} files[/dim]"
                )
        claims = [
            c
            for c in claims
            if c.review_state not in {ReviewState.SUPPRESSED, ReviewState.TOMBSTONED}
        ]

        # Select adapter
        adapter: (
            AgentsMdAdapter | ClaudeMdAdapter | CopilotAdapter | CursorAdapter | WindsurfAdapter
        )
        if host == "claude":
            adapter = ClaudeMdAdapter()
        elif host == "copilot":
            adapter = CopilotAdapter()
        elif host == "cursor":
            adapter = CursorAdapter()
        elif host == "windsurf":
            from rkp.server.tools import get_agents_md_claim_ids

            agents_ids = get_agents_md_claim_ids(claims)
            adapter = WindsurfAdapter(agents_md_claim_ids=agents_ids)
        else:
            adapter = AgentsMdAdapter()

        policy = ProjectionPolicy()
        result = project(claims, adapter, capability, policy)

        # Output
        files = result.adapter_result.files

        if state.json_output:
            output: dict[str, object] = {
                "host": host,
                "files": files,
                "excluded_sensitive": result.excluded_sensitive,
                "excluded_low_confidence": result.excluded_low_confidence,
                "overflow_report": result.adapter_result.overflow_report,
            }
            sys.stdout.write(json.dumps(output, indent=2) + "\n")
        elif host == "claude":
            _display_claude_output(files, state.quiet)
        elif host == "copilot":
            _display_copilot_output(files, result.adapter_result.overflow_report, state.quiet)
        elif host in ("cursor", "windsurf"):
            _display_rules_output(files, result.adapter_result.overflow_report, host, state.quiet)
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


def _display_copilot_output(
    files: dict[str, str], overflow_report: dict[str, object], quiet: bool
) -> None:
    """Display multi-file Copilot output with Rich panels."""
    out = Console()

    # copilot-instructions.md
    instructions = files.get(".github/copilot-instructions.md", "")
    if instructions:
        if not quiet:
            lines = instructions.count("\n") + 1
            err_console.print(
                f"[dim]copilot-instructions.md: {lines} lines (300-line budget)[/dim]"
            )
        out.print(
            Panel(instructions, title=".github/copilot-instructions.md", border_style="green")
        )

    # .github/instructions/ files
    instruction_files = {
        k: v for k, v in sorted(files.items()) if k.startswith(".github/instructions/")
    }
    for path, content in instruction_files.items():
        out.print(Panel(content, title=path, border_style="blue"))

    # copilot-setup-steps.yml
    setup_steps = files.get(".github/workflows/copilot-setup-steps.yml", "")
    if setup_steps:
        # Show validation status
        validation: object = overflow_report.get("setup_steps_validation", {})
        if isinstance(validation, dict):
            val_dict = cast(dict[str, Any], validation)
            is_valid: bool = bool(val_dict.get("valid", True))
            errors_raw: list[str] = cast(list[str], val_dict.get("errors", []))
            if is_valid:
                status_str = "[green]Valid[/green]"
            else:
                status_str = f"[red]⚠ {len(errors_raw)} validation error(s)[/red]"
            if not quiet:
                err_console.print(f"[dim]copilot-setup-steps.yml: {status_str}[/dim]")

        syntax = Syntax(setup_steps, "yaml", theme="monokai")
        out.print(
            Panel(
                syntax,
                title=".github/workflows/copilot-setup-steps.yml",
                border_style="cyan",
            )
        )

    # Tool allowlist
    allowlist = files.get(".copilot-tool-allowlist.json", "")
    if allowlist:
        syntax = Syntax(allowlist, "json", theme="monokai")
        out.print(Panel(syntax, title="Tool Allowlist (suggested config)", border_style="yellow"))


def _display_rules_output(
    files: dict[str, str],
    overflow_report: dict[str, object],
    host: str,
    quiet: bool,
) -> None:
    """Display Cursor or Windsurf rule files with Rich panels."""
    out = Console()
    prefix = ".cursor/rules/" if host == "cursor" else ".windsurf/rules/"

    if not quiet:
        total_chars = sum(len(v) for k, v in files.items() if k.startswith(prefix))
        file_count = sum(1 for k in files if k.startswith(prefix))
        err_console.print(
            f"[dim]{host}: {file_count} rule file(s), {total_chars:,} characters total[/dim]"
        )

        # Show Windsurf budget info
        if host == "windsurf":
            ws_budget_raw: object = overflow_report.get("windsurf_budget")
            if isinstance(ws_budget_raw, dict):
                ws_dict = cast(dict[str, Any], ws_budget_raw)
                ws_used_val: int = int(ws_dict.get("workspace_used", 0))
                ws_limit_val: int = int(ws_dict.get("workspace_limit", 12288))
                pct = int(ws_used_val / ws_limit_val * 100) if ws_limit_val else 0
                err_console.print(
                    f"[dim]Workspace budget: {ws_used_val:,} / {ws_limit_val:,} chars ({pct}%)[/dim]"
                )

    for path, content in sorted(files.items()):
        if not path.startswith(prefix):
            continue
        border = "green" if "guardrails" in path else "blue" if "commands" in path else "cyan"
        out.print(Panel(content, title=path, border_style=border))
