"""Integration tests for migration 001 core schema apply."""

from __future__ import annotations

from pathlib import Path

import pytest

from koffer.persistence import ConnectionFactory, MigrationError, MigrationRunner, apply_migrations

REQUIRED_TABLES = {
    "schema_migrations",
    "sources",
    "source_exclusions",
    "samples",
    "technical_metadata",
    "embedded_metadata",
    "classifications",
    "user_tags",
    "sample_tags",
    "suggestions",
    "collections",
    "collection_samples",
    "saved_searches",
    "preparation_recipes",
    "jobs",
    "job_items",
    "analysis_runs",
    "analysis_features",
    "model_registry",
    "audit_events",
    "settings",
}


def test_fresh_temp_db_applies_migration_001(tmp_path: Path) -> None:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    conn = factory.get_connection()
    try:
        applied = apply_migrations(conn)
        assert applied == [1]
        runner = MigrationRunner(conn)
        assert runner.current_version() == 1
        assert apply_migrations(conn) == []

        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        names = {str(row[0]) for row in rows}
        missing = REQUIRED_TABLES - names
        assert missing == set()

        version_row = conn.execute(
            "SELECT version, checksum FROM schema_migrations WHERE version = 1"
        ).fetchone()
        assert version_row is not None
        assert int(version_row[0]) == 1
        assert len(str(version_row[1])) == 64
    finally:
        factory.close_thread_connection()


def test_newer_unsupported_schema_is_rejected(tmp_path: Path) -> None:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    conn = factory.get_connection()
    try:
        apply_migrations(conn)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at, checksum) VALUES (999, ?, ?)",
            ("2026-10-04T00:00:00+00:00", "deadbeef"),
        )
        with pytest.raises(MigrationError, match="newer than supported"):
            apply_migrations(conn)
    finally:
        factory.close_thread_connection()
