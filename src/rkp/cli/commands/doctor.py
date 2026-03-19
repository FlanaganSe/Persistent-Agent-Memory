"""rkp doctor — system health check."""

from __future__ import annotations

import platform
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import typer

from rkp.cli.app import AppState
from rkp.cli.ui.output import console, print_json


@dataclass
class CheckResult:
    """Result of a single doctor check."""

    name: str
    passed: bool
    message: str
    critical: bool = False


def _check_python_version() -> CheckResult:
    """Verify Python >= 3.12."""
    version = platform.python_version()
    major, minor = sys.version_info.major, sys.version_info.minor
    if major >= 3 and minor >= 12:
        return CheckResult("python", True, f"Python {version}")
    return CheckResult("python", False, f"Python {version} (requires >= 3.12)", critical=True)


def _check_git() -> CheckResult:
    """Verify git is available."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip().replace("git version ", "")
            return CheckResult("git", True, f"Git {version}")
        return CheckResult("git", False, "Git not found (required)", critical=True)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return CheckResult("git", False, "Git not found (required)", critical=True)


def _check_sqlite() -> CheckResult:
    """Verify SQLite supports WAL and FTS5."""
    version = sqlite3.sqlite_version
    try:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                "CREATE VIRTUAL TABLE test_fts USING fts5(content, tokenize='porter unicode61')"
            )
            conn.close()
        return CheckResult("sqlite", True, f"SQLite {version} (WAL + FTS5)")
    except sqlite3.OperationalError as exc:
        return CheckResult("sqlite", False, f"SQLite {version}: {exc}", critical=True)


def _check_tree_sitter() -> CheckResult:
    """Verify tree-sitter parsers load."""
    try:
        from tree_sitter_language_pack import get_parser

        available: list[str] = []
        for lang in ("python", "javascript", "typescript"):
            try:
                get_parser(lang)
                available.append(lang)
            except Exception:
                pass

        if len(available) == 3:
            return CheckResult("tree_sitter", True, f"tree-sitter parsers: {', '.join(available)}")
        return CheckResult(
            "tree_sitter",
            False,
            f"tree-sitter parsers: only {', '.join(available) or 'none'} available",
        )
    except ImportError:
        return CheckResult("tree_sitter", False, "tree-sitter-language-pack not installed")


def _check_database(db_path: Path) -> CheckResult:
    """Verify database health if it exists."""
    if not db_path.exists():
        return CheckResult("database", True, "No database (not initialized yet)")

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Schema version
        version_row = conn.execute("PRAGMA user_version").fetchone()
        schema_version = version_row[0] if version_row else 0

        # Integrity check
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity and integrity[0] != "ok":
            return CheckResult(
                "database",
                False,
                "Database corrupted. Delete .rkp/local/ and run rkp init",
            )

        # Claim count
        try:
            count_row = conn.execute("SELECT COUNT(*) FROM claims").fetchone()
            claim_count = count_row[0] if count_row else 0
        except sqlite3.OperationalError:
            claim_count = 0

        return CheckResult(
            "database",
            True,
            f"Database healthy (schema v{schema_version}, {claim_count} claims)",
        )
    except sqlite3.Error as exc:
        return CheckResult(
            "database",
            False,
            f"Database error: {exc}. Delete .rkp/local/ and run rkp init",
        )
    finally:
        if conn is not None:
            conn.close()


def _check_mcp() -> CheckResult:
    """Verify MCP server can be constructed."""
    try:
        from fastmcp import FastMCP

        server = FastMCP("doctor-test", version="0.0.0")
        _ = server  # just verify construction
        return CheckResult("mcp", True, "MCP server constructable")
    except Exception as exc:
        return CheckResult("mcp", False, f"MCP server: {exc}")


def _check_repo(repo_path: Path) -> CheckResult:
    """Check repo detection and support envelope."""
    from rkp.cli.commands.init import detect_languages

    try:
        from rkp.git.cli_backend import CliGitBackend, NotAGitRepoError

        try:
            git = CliGitBackend(repo_path)
            branch = git.current_branch()
            repo_msg = f"Git repository detected ({branch} branch)"
        except NotAGitRepoError:
            repo_msg = "Not a git repository (filesystem-only mode)"
    except Exception:
        repo_msg = "Git detection failed"

    supported, unsupported = detect_languages(repo_path)
    if supported:
        langs = ", ".join(f"{lang} (full)" for lang in sorted(supported))
        envelope_msg = f"Support envelope: {langs}"
        if unsupported:
            envelope_msg += f" | unsupported: {', '.join(sorted(unsupported))}"
        return CheckResult("repo", True, f"{repo_msg}. {envelope_msg}")
    return CheckResult("repo", True, f"{repo_msg}. No source files detected")


def doctor(
    ctx: typer.Context,
) -> None:
    """Validate runtime, DB health, parser availability, and MCP boot health."""
    state: AppState = ctx.obj

    checks = [
        _check_python_version(),
        _check_git(),
        _check_sqlite(),
        _check_tree_sitter(),
        _check_database(state.db_path),
        _check_mcp(),
        _check_repo(state.repo_path),
    ]

    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    has_critical = any(not c.passed and c.critical for c in checks)

    if state.json_output:
        print_json(
            {
                "checks": [
                    {
                        "name": c.name,
                        "passed": c.passed,
                        "message": c.message,
                        "critical": c.critical,
                    }
                    for c in checks
                ],
                "summary": {"passed": passed, "total": total, "has_critical": has_critical},
            }
        )
    elif not state.quiet:
        for check in checks:
            mark = "\u2713" if check.passed else "\u2717"
            style = "green" if check.passed else "red"
            console.print(f"[{style}]{mark}[/{style}] {check.message}")

        console.print()
        if passed == total:
            console.print(f"[green]{passed}/{total} checks passed[/green]")
        else:
            failed = total - passed
            console.print(
                f"[yellow]{passed}/{total} checks passed \u2014 "
                f"{failed} issue{'s' if failed != 1 else ''} found[/yellow]"
            )

    if has_critical:
        raise typer.Exit(code=2)
    if passed < total:
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)
