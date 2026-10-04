"""Thread-local SQLite connection ownership tests."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from koffer.persistence import ConnectionFactory


def test_get_connection_reuses_same_object_on_same_thread(tmp_path: Path) -> None:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    first = factory.get_connection()
    second = factory.get_connection()
    assert first is second
    row = first.execute("PRAGMA foreign_keys").fetchone()
    assert row is not None
    assert int(row[0]) == 1
    mode = first.execute("PRAGMA journal_mode").fetchone()
    assert mode is not None
    assert str(mode[0]).lower() == "wal"
    factory.close_thread_connection()


def test_connections_are_not_shared_across_threads(tmp_path: Path) -> None:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    main_conn = factory.get_connection()
    worker_conn_id: int | None = None
    errors: list[BaseException] = []

    def worker() -> None:
        nonlocal worker_conn_id
        try:
            conn = factory.get_connection()
            worker_conn_id = id(conn)
            # Prove the main thread's connection object is not usable here.
            with pytest.raises(sqlite3.ProgrammingError):
                main_conn.execute("SELECT 1")
        except BaseException as exc:  # noqa: BLE001 - collect for main thread assertion
            errors.append(exc)
        finally:
            factory.close_thread_connection()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert errors == []
    assert worker_conn_id is not None
    assert worker_conn_id != id(main_conn)
    factory.close_thread_connection()
