"""SQLite online backup API primitives with versioned manifest (docs/17, docs/24)."""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from koffer import __version__ as KOFFER_VERSION
from koffer.domain.timestamps import utc_now_iso
from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.migrations import apply_migrations

_MANIFEST_NAME = "manifest.json"
_DATABASE_NAME = "library.sqlite3"


def _backup_stamp(prefix: str = "") -> str:
    stamp = utc_now_iso().replace(":", "").replace("+", "p")
    return f"{prefix}{stamp}" if prefix else stamp


class BackupError(RuntimeError):
    """Raised when backup or restore cannot complete safely."""


@dataclass(frozen=True, slots=True)
class BackupManifest:
    """Versioned backup metadata stored beside the backed-up database file."""

    format_version: int
    koffer_version: str
    schema_version: int
    created_at: str
    database_filename: str

    def to_dict(self) -> dict[str, object]:
        return {
            "format_version": self.format_version,
            "koffer_version": self.koffer_version,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "database_filename": self.database_filename,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> BackupManifest:
        try:
            format_version = payload["format_version"]
            schema_version = payload["schema_version"]
            if not isinstance(format_version, int):
                format_version = int(str(format_version))
            if not isinstance(schema_version, int):
                schema_version = int(str(schema_version))
            return cls(
                format_version=format_version,
                koffer_version=str(payload["koffer_version"]),
                schema_version=schema_version,
                created_at=str(payload["created_at"]),
                database_filename=str(payload["database_filename"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"invalid backup manifest: {exc}"
            raise BackupError(msg) from exc


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'schema_migrations'
        """
    ).fetchone()
    if row is None:
        return 0
    version_row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if version_row is None or version_row[0] is None:
        return 0
    return int(version_row[0])


def _integrity_ok(conn: sqlite3.Connection) -> bool:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    return row is not None and str(row[0]) == "ok"


def _remove_sqlite_sidecars(database_path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(database_path) + suffix)
        if sidecar.exists():
            sidecar.unlink()


def _write_manifest(path: Path, manifest: BackupManifest) -> None:
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_manifest(path: Path) -> BackupManifest:
    if not path.is_file():
        msg = f"backup manifest missing: {path}"
        raise BackupError(msg)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"backup manifest is not valid JSON: {path}"
        raise BackupError(msg) from exc
    if not isinstance(payload, dict):
        msg = "backup manifest root must be an object"
        raise BackupError(msg)
    return BackupManifest.from_dict(payload)


def _online_backup(source: sqlite3.Connection, destination_db: Path) -> None:
    destination_db.parent.mkdir(parents=True, exist_ok=True)
    if destination_db.exists():
        destination_db.unlink()
    _remove_sqlite_sidecars(destination_db)
    dest = sqlite3.connect(destination_db)
    try:
        source.backup(dest)
        dest.commit()
    finally:
        dest.close()


def backup_database(
    source_conn: sqlite3.Connection,
    destination_parent: Path,
    *,
    stamp: str | None = None,
) -> Path:
    """Create a versioned backup directory using the SQLite online backup API.

    Layout:
      destination_parent/koffer-backup-<stamp>/
        library.sqlite3
        manifest.json
    """
    destination_parent = Path(destination_parent)
    destination_parent.mkdir(parents=True, exist_ok=True)
    created_at = utc_now_iso()
    backup_stamp = stamp or _backup_stamp()
    backup_dir = destination_parent / f"koffer-backup-{backup_stamp}"
    if backup_dir.exists():
        msg = f"backup destination already exists: {backup_dir}"
        raise BackupError(msg)
    backup_dir.mkdir(parents=True, exist_ok=False)

    db_path = backup_dir / _DATABASE_NAME
    try:
        _online_backup(source_conn, db_path)
        verify = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            if not _integrity_ok(verify):
                msg = "backup database failed integrity_check"
                raise BackupError(msg)
            schema_version = _schema_version(verify)
        finally:
            verify.close()

        manifest = BackupManifest(
            format_version=1,
            koffer_version=KOFFER_VERSION,
            schema_version=schema_version,
            created_at=created_at,
            database_filename=_DATABASE_NAME,
        )
        _write_manifest(backup_dir / _MANIFEST_NAME, manifest)
    except Exception:
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise
    return backup_dir


def restore_database(
    backup_dir: Path,
    destination_db: Path,
    *,
    safety_backup_parent: Path | None = None,
) -> BackupManifest:
    """Restore a versioned backup into destination_db with docs/24 safety steps.

    Caller must close active app connections to destination_db before restore.
    When destination_db already exists, an automatic safety backup is written
    under safety_backup_parent (default: destination parent).
    """
    backup_dir = Path(backup_dir)
    destination_db = Path(destination_db)
    if not backup_dir.is_dir():
        msg = f"backup directory missing: {backup_dir}"
        raise BackupError(msg)

    manifest = _read_manifest(backup_dir / _MANIFEST_NAME)
    if manifest.format_version != 1:
        msg = f"unsupported backup format_version: {manifest.format_version}"
        raise BackupError(msg)
    if manifest.database_filename != _DATABASE_NAME:
        msg = f"unexpected database_filename in manifest: {manifest.database_filename}"
        raise BackupError(msg)

    backup_db = backup_dir / manifest.database_filename
    if not backup_db.is_file():
        msg = f"backup database missing: {backup_db}"
        raise BackupError(msg)

    source = sqlite3.connect(f"file:{backup_db}?mode=ro", uri=True)
    try:
        if not _integrity_ok(source):
            msg = "backup database failed integrity_check"
            raise BackupError(msg)
    finally:
        source.close()

    if destination_db.exists():
        if safety_backup_parent is not None:
            parent = Path(safety_backup_parent)
        else:
            parent = destination_db.parent
        safety_factory = ConnectionFactory(destination_db)
        safety_conn = safety_factory.open_connection()
        try:
            backup_database(
                safety_conn,
                parent,
                stamp=_backup_stamp("pre-restore-"),
            )
        finally:
            safety_conn.close()

    temp_db = destination_db.with_name(destination_db.name + ".restore-tmp")
    if temp_db.exists():
        temp_db.unlink()
    _remove_sqlite_sidecars(temp_db)

    source = sqlite3.connect(f"file:{backup_db}?mode=ro", uri=True)
    try:
        _online_backup(source, temp_db)
    finally:
        source.close()

    temp_factory = ConnectionFactory(temp_db)
    temp_conn = temp_factory.open_connection()
    try:
        apply_migrations(temp_conn)
        if not _integrity_ok(temp_conn):
            msg = "restored database failed integrity_check after migrate"
            raise BackupError(msg)
    finally:
        temp_factory.close_thread_connection()

    destination_db.parent.mkdir(parents=True, exist_ok=True)
    _remove_sqlite_sidecars(destination_db)
    temp_db.replace(destination_db)
    _remove_sqlite_sidecars(destination_db)
    return manifest
