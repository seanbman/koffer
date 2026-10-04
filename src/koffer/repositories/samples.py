"""Typed Sample repository. Caller owns the connection/transaction scope."""

from __future__ import annotations

import sqlite3

from koffer.domain.enums import SampleAvailability
from koffer.domain.ids import EntityId
from koffer.domain.models import Sample
from koffer.repositories._sqlite import (
    as_entity_id,
    as_optional_entity_id,
    bool_to_int,
    int_to_bool,
    optional_int,
    optional_str,
    row_count,
)


def _from_row(row: sqlite3.Row) -> Sample:
    return Sample(
        id=as_entity_id(row["id"]),
        relative_path=str(row["relative_path"]),
        normalized_path_cache=str(row["normalized_path_cache"]),
        filename=str(row["filename"]),
        extension=str(row["extension"]),
        size_bytes=int(row["size_bytes"]),
        mtime_ns=int(row["mtime_ns"]),
        availability=SampleAvailability(str(row["availability"])),
        favorite=int_to_bool(row["favorite"]),
        first_seen_at=str(row["first_seen_at"]),
        last_seen_at=str(row["last_seen_at"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        source_id=as_optional_entity_id(row["source_id"]),
        device_id=optional_int(row["device_id"]),
        inode=optional_int(row["inode"]),
        quick_hash=optional_str(row["quick_hash"]),
        content_hash=optional_str(row["content_hash"]),
        last_previewed_at=optional_str(row["last_previewed_at"]),
    )


class SampleRepository:
    """CRUD for indexed audio file identity rows."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, sample: Sample) -> None:
        self._conn.execute(
            """
            INSERT INTO samples (
                id, source_id, relative_path, normalized_path_cache, filename, extension,
                size_bytes, mtime_ns, device_id, inode, quick_hash, content_hash,
                availability, favorite, first_seen_at, last_seen_at, last_previewed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(sample.id),
                None if sample.source_id is None else str(sample.source_id),
                sample.relative_path,
                sample.normalized_path_cache,
                sample.filename,
                sample.extension,
                sample.size_bytes,
                sample.mtime_ns,
                sample.device_id,
                sample.inode,
                sample.quick_hash,
                sample.content_hash,
                str(sample.availability),
                bool_to_int(sample.favorite),
                sample.first_seen_at,
                sample.last_seen_at,
                sample.last_previewed_at,
                sample.created_at,
                sample.updated_at,
            ),
        )

    def get(self, sample_id: EntityId) -> Sample | None:
        row = self._conn.execute(
            "SELECT * FROM samples WHERE id = ?",
            (str(sample_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def list_by_source(self, source_id: EntityId) -> list[Sample]:
        rows = self._conn.execute(
            """
            SELECT * FROM samples
            WHERE source_id = ?
            ORDER BY relative_path ASC, id ASC
            """,
            (str(source_id),),
        ).fetchall()
        return [_from_row(row) for row in rows]

    def update(self, sample: Sample) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE samples SET
                    source_id = ?,
                    relative_path = ?,
                    normalized_path_cache = ?,
                    filename = ?,
                    extension = ?,
                    size_bytes = ?,
                    mtime_ns = ?,
                    device_id = ?,
                    inode = ?,
                    quick_hash = ?,
                    content_hash = ?,
                    availability = ?,
                    favorite = ?,
                    first_seen_at = ?,
                    last_seen_at = ?,
                    last_previewed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    None if sample.source_id is None else str(sample.source_id),
                    sample.relative_path,
                    sample.normalized_path_cache,
                    sample.filename,
                    sample.extension,
                    sample.size_bytes,
                    sample.mtime_ns,
                    sample.device_id,
                    sample.inode,
                    sample.quick_hash,
                    sample.content_hash,
                    str(sample.availability),
                    bool_to_int(sample.favorite),
                    sample.first_seen_at,
                    sample.last_seen_at,
                    sample.last_previewed_at,
                    sample.updated_at,
                    str(sample.id),
                ),
            )
            > 0
        )

    def delete(self, sample_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                "DELETE FROM samples WHERE id = ?",
                (str(sample_id),),
            )
            > 0
        )
