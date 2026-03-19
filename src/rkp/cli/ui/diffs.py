"""Diff rendering utilities (stub for M9 review flow)."""

from __future__ import annotations

import difflib

from rich.syntax import Syntax


def render_diff(old: str, new: str, filename: str = "") -> Syntax:
    """Render a unified diff with syntax highlighting."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{filename}" if filename else "a",
        tofile=f"b/{filename}" if filename else "b",
    )
    diff_text = "".join(diff)
    return Syntax(diff_text or "(no changes)", "diff", theme="monokai")
