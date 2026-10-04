"""Typed Collection repository and membership (DB-only; never mutates filesystem)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from koffer.domain.ids import EntityId
from koffer.domain.models import Collection
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories._sqlite import as_entity_id, optional_int, optional_str, row_count


@dataclass(frozen=True, slots=True)
class CollectionMembership:
    """Membership row for a Sample inside a Collection."""

    collection_id: EntityId
    sample_id: EntityId
    added_at: str
    manual_position: int | None = None


def _from_row(row: sqlite3.Row) -> Collection:
    return Collection(
        id=as_entity_id(row["id"]),
        name=str(row["name"]),
        sort_mode=str(row["sort_mode"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        description=optional_str(row["description"]),
        color=optional_str(row["color"]),
        artwork_path=optional_str(row["artwork_path"]),
    )


def _membership_from_row(row: sqlite3.Row) -> CollectionMembership:
    return CollectionMembership(
        collection_id=as_entity_id(row["collection_id"]),
        sample_id=as_entity_id(row["sample_id"]),
        added_at=str(row["added_at"]),
        manual_position=optional_int(row["manual_position"]),
    )


class CollectionRepository:
    """CRUD for Collections and collection_samples membership.

    Membership changes only touch SQLite rows. They never imply copy/move/delete
    of audio files on disk.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, collection: Collection) -> None:
        self._conn.execute(
            """
            INSERT INTO collections (
                id, name, description, color, artwork_path, sort_mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(collection.id),
                collection.name,
                collection.description,
                collection.color,
                collection.artwork_path,
                collection.sort_mode,
                collection.created_at,
                collection.updated_at,
            ),
        )

    def get(self, collection_id: EntityId) -> Collection | None:
        row = self._conn.execute(
            "SELECT * FROM collections WHERE id = ?",
            (str(collection_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def list_all(self) -> list[Collection]:
        rows = self._conn.execute("SELECT * FROM collections ORDER BY name ASC, id ASC").fetchall()
        return [_from_row(row) for row in rows]

    def update(self, collection: Collection) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE collections SET
                    name = ?,
                    description = ?,
                    color = ?,
                    artwork_path = ?,
                    sort_mode = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    collection.name,
                    collection.description,
                    collection.color,
                    collection.artwork_path,
                    collection.sort_mode,
                    collection.updated_at,
                    str(collection.id),
                ),
            )
            > 0
        )

    def delete(self, collection_id: EntityId) -> bool:
        """Delete a Collection. Cascades membership only; Samples remain intact."""
        return (
            row_count(
                self._conn,
                "DELETE FROM collections WHERE id = ?",
                (str(collection_id),),
            )
            > 0
        )

    def add_sample(
        self,
        collection_id: EntityId,
        sample_id: EntityId,
        *,
        added_at: str | None = None,
        manual_position: int | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO collection_samples (
                collection_id, sample_id, manual_position, added_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                str(collection_id),
                str(sample_id),
                manual_position,
                added_at if added_at is not None else utc_now_iso(),
            ),
        )

    def remove_sample(self, collection_id: EntityId, sample_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                """
                DELETE FROM collection_samples
                WHERE collection_id = ? AND sample_id = ?
                """,
                (str(collection_id), str(sample_id)),
            )
            > 0
        )

    def list_memberships(self, collection_id: EntityId) -> list[CollectionMembership]:
        rows = self._conn.execute(
            """
            SELECT * FROM collection_samples
            WHERE collection_id = ?
            ORDER BY
                CASE WHEN manual_position IS NULL THEN 1 ELSE 0 END,
                manual_position ASC,
                added_at ASC,
                sample_id ASC
            """,
            (str(collection_id),),
        ).fetchall()
        return [_membership_from_row(row) for row in rows]

    def list_sample_ids(self, collection_id: EntityId) -> list[EntityId]:
        return [membership.sample_id for membership in self.list_memberships(collection_id)]

    def set_manual_positions(
        self,
        collection_id: EntityId,
        ordered_sample_ids: list[EntityId],
    ) -> None:
        """Assign contiguous manual_position values; DB-only, never touches files."""
        for index, sample_id in enumerate(ordered_sample_ids):
            self._conn.execute(
                """
                UPDATE collection_samples
                SET manual_position = ?
                WHERE collection_id = ? AND sample_id = ?
                """,
                (index, str(collection_id), str(sample_id)),
            )

    def has_membership(self, collection_id: EntityId, sample_id: EntityId) -> bool:
        row = self._conn.execute(
            """
            SELECT 1 FROM collection_samples
            WHERE collection_id = ? AND sample_id = ?
            """,
            (str(collection_id), str(sample_id)),
        ).fetchone()
        return row is not None
