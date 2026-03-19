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
def quality(session: nox.Session) -> None:
    """Run the full quality harness."""
    session.install(".[dev]")
    session.run(
        "python",
        "-m",
        "rkp.quality",
        "--fixtures",
        "tests/fixtures/",
        "--report",
        "quality-report.json",
        "--skip-performance",
    )


@nox.session(python="3.12")
def docs(session: nox.Session) -> None:
    """Build documentation."""
    session.install(".[dev]")
    session.run("mkdocs", "build", "--strict")


@nox.session(python="3.12")
def ci(session: nox.Session) -> None:
    """Run all CI checks."""
    session.notify("lint")
    session.notify("typecheck")
    session.notify("test")
