"""Nox sessions for repo-knowledge-plane."""

import nox

nox.options.sessions = ["lint", "typecheck", "test"]


@nox.session(python="3.12")
def lint(session: nox.Session) -> None:
    """Run ruff linter and formatter check."""
    session.install("ruff>=0.9.0")
    session.run("ruff", "check", "src", "tests", "noxfile.py")
    session.run("ruff", "format", "--check", "src", "tests", "noxfile.py")


@nox.session(python="3.12")
def typecheck(session: nox.Session) -> None:
    """Run pyright in strict mode."""
    session.install(".[dev]")
    session.run("pyright")


@nox.session(python="3.12")
def test(session: nox.Session) -> None:
    """Run pytest."""
    session.install(".[dev]")
    session.run("pytest")


@nox.session(python="3.12")
def ci(session: nox.Session) -> None:
    """Run all CI checks."""
    session.notify("lint")
    session.notify("typecheck")
    session.notify("test")
