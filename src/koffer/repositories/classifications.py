"""Typed Classification repository for confirmed library axes."""

from __future__ import annotations

import sqlite3

from koffer.domain.enums import ClassificationDimension, ClassificationSource
from koffer.domain.ids import EntityId
from koffer.domain.models import Classification
from koffer.repositories._sqlite import as_entity_id, row_count


def _from_row(row: sqlite3.Row) -> Classification:
    return Classification(
        id=as_entity_id(row["id"]),
        sample_id=as_entity_id(row["sample_id"]),
        dimension=ClassificationDimension(str(row["dimension"])),
        value=str(row["value"]),
        source=ClassificationSource(str(row["source"])),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class ClassificationRepository:
    """CRUD for confirmed classifications (library metadata only)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, classification: Classification) -> None:
        self._conn.execute(
            """
            INSERT INTO classifications (
                id, sample_id, dimension, value, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(classification.id),
                str(classification.sample_id),
                str(classification.dimension),
                classification.value,
                str(classification.source),
                classification.created_at,
                classification.updated_at,
            ),
        )

    def get(self, classification_id: EntityId) -> Classification | None:
        row = self._conn.execute(
            "SELECT * FROM classifications WHERE id = ?",
            (str(classification_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def list_for_sample(self, sample_id: EntityId) -> list[Classification]:
        rows = self._conn.execute(
            """
            SELECT * FROM classifications
            WHERE sample_id = ?
            ORDER BY dimension ASC, value ASC, id ASC
            """,
            (str(sample_id),),
        ).fetchall()
        return [_from_row(row) for row in rows]

    def update(self, classification: Classification) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE classifications SET
                    sample_id = ?,
                    dimension = ?,
                    value = ?,
                    source = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    str(classification.sample_id),
                    str(classification.dimension),
                    classification.value,
                    str(classification.source),
                    classification.updated_at,
                    str(classification.id),
                ),
            )
            > 0
        )

    def delete(self, classification_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                "DELETE FROM classifications WHERE id = ?",
                (str(classification_id),),
            )
            > 0
        )
