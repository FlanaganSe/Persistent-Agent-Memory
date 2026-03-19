"""SQLite connection factory, PRAGMAs, migration runner, and WAL checkpoint."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from rkp.core.errors import MigrationError

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def open_database(path: Path, *, check_same_thread: bool = True) -> sqlite3.Connection:
    """Open (or create) a SQLite database with production PRAGMAs.

    Creates parent directories if needed. Returns a connection with
    WAL mode, busy_timeout, and other performance settings applied.

    Set check_same_thread=False when the connection will be shared across
    threads (e.g., MCP server where FastMCP dispatches tools to a threadpool).
    This is safe with WAL mode + busy_timeout.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply production PRAGMAs for performance and correctness."""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA mmap_size = 268435456")


def get_user_version(conn: sqlite3.Connection) -> int:
    """Read the current schema version from PRAGMA user_version."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending migrations from the migrations directory.

    Reads PRAGMA user_version, then applies all migration files with
    version numbers higher than the current version.
    """
    current_version = get_user_version(conn)
    migration_files = sorted(
        _MIGRATIONS_DIR.glob("*.sql"),
        key=lambda p: _extract_version(p),
    )

    for migration_file in migration_files:
        version = _extract_version(migration_file)
        if version > current_version:
            sql = migration_file.read_text()
            try:
                conn.executescript(sql)
            except sqlite3.Error as exc:
                msg = f"Migration {migration_file.name} failed"
                raise MigrationError(msg) from exc
            conn.execute(f"PRAGMA user_version = {version}")


def _extract_version(path: Path) -> int:
    """Extract the integer version from a migration filename like 0001_init.sql."""
    try:
        return int(path.stem.split("_")[0])
    except (ValueError, IndexError) as exc:
        msg = f"Invalid migration filename: {path.name}"
        raise MigrationError(msg) from exc


def checkpoint_wal(conn: sqlite3.Connection) -> None:
    """Run a WAL checkpoint to flush WAL to the main database file."""
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
