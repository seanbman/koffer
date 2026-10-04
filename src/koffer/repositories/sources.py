"""Typed Source repository. Caller owns the connection/transaction scope."""

from __future__ import annotations

import sqlite3

from koffer.domain.enums import SourceStatus
from koffer.domain.ids import EntityId
from koffer.domain.models import Source
from koffer.repositories._sqlite import (
    as_entity_id,
    bool_to_int,
    int_to_bool,
    optional_str,
    row_count,
)


def _from_row(row: sqlite3.Row) -> Source:
    return Source(
        id=as_entity_id(row["id"]),
        display_name=str(row["display_name"]),
        root_path=str(row["root_path"]),
        enabled=int_to_bool(row["enabled"]),
        recursive=int_to_bool(row["recursive"]),
        status=SourceStatus(str(row["status"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        storage_fingerprint=optional_str(row["storage_fingerprint"]),
        last_scan_started_at=optional_str(row["last_scan_started_at"]),
        last_scan_completed_at=optional_str(row["last_scan_completed_at"]),
        last_seen_at=optional_str(row["last_seen_at"]),
    )


class SourceRepository:
    """CRUD for authorized scan roots."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, source: Source) -> None:
        self._conn.execute(
            """
            INSERT INTO sources (
                id, display_name, root_path, storage_fingerprint, enabled, recursive,
                status, last_scan_started_at, last_scan_completed_at, last_seen_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(source.id),
                source.display_name,
                source.root_path,
                source.storage_fingerprint,
                bool_to_int(source.enabled),
                bool_to_int(source.recursive),
                str(source.status),
                source.last_scan_started_at,
                source.last_scan_completed_at,
                source.last_seen_at,
                source.created_at,
                source.updated_at,
            ),
        )

    def get(self, source_id: EntityId) -> Source | None:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE id = ?",
            (str(source_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def list_all(self) -> list[Source]:
        rows = self._conn.execute(
            "SELECT * FROM sources ORDER BY created_at ASC, id ASC"
        ).fetchall()
        return [_from_row(row) for row in rows]

    def update(self, source: Source) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE sources SET
                    display_name = ?,
                    root_path = ?,
                    storage_fingerprint = ?,
                    enabled = ?,
                    recursive = ?,
                    status = ?,
                    last_scan_started_at = ?,
                    last_scan_completed_at = ?,
                    last_seen_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    source.display_name,
                    source.root_path,
                    source.storage_fingerprint,
                    bool_to_int(source.enabled),
                    bool_to_int(source.recursive),
                    str(source.status),
                    source.last_scan_started_at,
                    source.last_scan_completed_at,
                    source.last_seen_at,
                    source.updated_at,
                    str(source.id),
                ),
            )
            > 0
        )

    def delete(self, source_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                "DELETE FROM sources WHERE id = ?",
                (str(source_id),),
            )
            > 0
        )
