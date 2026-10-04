"""SQLite connection factory with WAL, FKs, busy timeout, and thread ownership.

Connections are cached per calling thread and must never be handed across threads.
``sqlite3`` ``check_same_thread=True`` reinforces that invariant.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

DEFAULT_BUSY_TIMEOUT_MS = 5000


class ConnectionFactory:
    """Create and cache per-thread SQLite connections for one database path."""

    def __init__(
        self,
        database_path: Path | str,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self._database_path = Path(database_path)
        self._busy_timeout_ms = busy_timeout_ms
        self._local = threading.local()

    @property
    def database_path(self) -> Path:
        return self._database_path

    def get_connection(self) -> sqlite3.Connection:
        """Return the calling thread's connection, creating it on first use."""
        existing: sqlite3.Connection | None = getattr(self._local, "connection", None)
        if existing is not None:
            owner: int | None = getattr(self._local, "owner_ident", None)
            if owner != threading.get_ident():
                msg = "thread-local connection ownership violated"
                raise RuntimeError(msg)
            return existing

        conn = self.open_connection()
        self._local.connection = conn
        self._local.owner_ident = threading.get_ident()
        return conn

    def open_connection(self) -> sqlite3.Connection:
        """Open a new connection owned exclusively by the calling thread."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self._database_path,
            check_same_thread=True,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
        # journal_mode=WAL is persistent; ignore return value shape differences.
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close_thread_connection(self) -> None:
        """Close and drop the connection cached for the calling thread."""
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            conn.close()
        self._local.connection = None
        self._local.owner_ident = None
