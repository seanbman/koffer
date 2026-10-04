"""Append-only SQL migration runner with checksum tracking."""

from __future__ import annotations

import contextlib
import hashlib
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from koffer.domain.timestamps import utc_now_iso

_MIGRATION_NAME_RE = re.compile(r"^(\d{3})_.+\.sql$")
_PACKAGE_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


class MigrationError(RuntimeError):
    """Raised when migrations cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class MigrationFile:
    version: int
    name: str
    sql: str
    checksum: str


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _iter_sql_statements(script: str) -> Iterator[str]:
    """Yield executable statements from a controlled migration script."""
    lines: list[str] = []
    for line in script.splitlines():
        if line.lstrip().startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    for part in cleaned.split(";"):
        statement = part.strip()
        if statement:
            yield statement


def _load_migrations_from_dir(directory: Path) -> list[MigrationFile]:
    if not directory.is_dir():
        msg = f"migrations directory missing: {directory}"
        raise MigrationError(msg)
    files: list[MigrationFile] = []
    for path in sorted(directory.glob("*.sql")):
        match = _MIGRATION_NAME_RE.match(path.name)
        if match is None:
            msg = f"invalid migration filename: {path.name}"
            raise MigrationError(msg)
        sql = path.read_text(encoding="utf-8")
        files.append(
            MigrationFile(
                version=int(match.group(1)),
                name=path.name,
                sql=sql,
                checksum=_checksum(sql),
            )
        )
    return files


def discover_migrations(migrations_dir: Path | None = None) -> list[MigrationFile]:
    """Load migration SQL files in ascending version order."""
    return _load_migrations_from_dir(migrations_dir or _PACKAGE_MIGRATIONS_DIR)


def ensure_schema_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY NOT NULL,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        )
        """
    )


def _applied_versions(conn: sqlite3.Connection) -> dict[int, str]:
    rows = conn.execute(
        "SELECT version, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    return {int(row[0]): str(row[1]) for row in rows}


class MigrationRunner:
    """Apply pending migrations inside explicit transactions."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        migrations: list[MigrationFile] | None = None,
        migrations_dir: Path | None = None,
    ) -> None:
        self._conn = conn
        self._migrations = (
            migrations if migrations is not None else discover_migrations(migrations_dir)
        )

    @property
    def migrations(self) -> list[MigrationFile]:
        return list(self._migrations)

    def current_version(self) -> int:
        ensure_schema_migrations_table(self._conn)
        applied = _applied_versions(self._conn)
        return max(applied) if applied else 0

    def apply_pending(self) -> list[int]:
        """Apply all pending migrations; return newly applied version numbers."""
        ensure_schema_migrations_table(self._conn)
        applied = _applied_versions(self._conn)
        known_versions = {migration.version for migration in self._migrations}
        max_known = max(known_versions) if known_versions else 0

        for version, checksum in applied.items():
            if version > max_known:
                msg = f"database schema version {version} is newer than supported max {max_known}"
                raise MigrationError(msg)
            if version in known_versions:
                expected = next(m.checksum for m in self._migrations if m.version == version)
                if checksum != expected:
                    msg = f"checksum mismatch for applied migration {version:03d}"
                    raise MigrationError(msg)

        applied_now: list[int] = []
        for migration in self._migrations:
            if migration.version in applied:
                continue
            self._apply_one(migration)
            applied_now.append(migration.version)
        return applied_now

    def _apply_one(self, migration: MigrationFile) -> None:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _iter_sql_statements(migration.sql):
                conn.execute(statement)
            conn.execute(
                """
                INSERT INTO schema_migrations (version, applied_at, checksum)
                VALUES (?, ?, ?)
                """,
                (migration.version, utc_now_iso(), migration.checksum),
            )
            conn.execute("COMMIT")
        except Exception:
            with contextlib.suppress(sqlite3.Error):
                conn.execute("ROLLBACK")
            raise


def apply_migrations(conn: sqlite3.Connection, *, migrations_dir: Path | None = None) -> list[int]:
    """Convenience wrapper used by tests and future startup wiring."""
    return MigrationRunner(conn, migrations_dir=migrations_dir).apply_pending()
