"""Typed JobItem repository for per-item batch outcomes (docs/18)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from koffer.domain.enums import JobItemState
from koffer.domain.ids import EntityId
from koffer.repositories._sqlite import (
    as_entity_id,
    as_optional_entity_id,
    optional_str,
    row_count,
)


@dataclass(frozen=True, slots=True)
class JobItem:
    """One planned/executed item inside a batch Job."""

    job_id: EntityId
    item_key: str
    state: JobItemState
    sample_id: EntityId | None = None
    source_path: str | None = None
    destination_path: str | None = None
    error_code: str | None = None
    detail_json: str | None = None


def _from_row(row: sqlite3.Row) -> JobItem:
    return JobItem(
        job_id=as_entity_id(row["job_id"]),
        item_key=str(row["item_key"]),
        state=JobItemState(str(row["state"])),
        sample_id=as_optional_entity_id(row["sample_id"]),
        source_path=optional_str(row["source_path"]),
        destination_path=optional_str(row["destination_path"]),
        error_code=optional_str(row["error_code"]),
        detail_json=optional_str(row["detail_json"]),
    )


class JobItemRepository:
    """CRUD for job_items rows (caller owns connection/transaction)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, item: JobItem) -> None:
        self._conn.execute(
            """
            INSERT INTO job_items (
                job_id, item_key, sample_id, source_path, destination_path,
                state, error_code, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, item_key) DO UPDATE SET
                sample_id = excluded.sample_id,
                source_path = excluded.source_path,
                destination_path = excluded.destination_path,
                state = excluded.state,
                error_code = excluded.error_code,
                detail_json = excluded.detail_json
            """,
            (
                str(item.job_id),
                item.item_key,
                None if item.sample_id is None else str(item.sample_id),
                item.source_path,
                item.destination_path,
                str(item.state),
                item.error_code,
                item.detail_json,
            ),
        )

    def list_for_job(self, job_id: EntityId) -> list[JobItem]:
        rows = self._conn.execute(
            """
            SELECT * FROM job_items
            WHERE job_id = ?
            ORDER BY item_key ASC
            """,
            (str(job_id),),
        ).fetchall()
        return [_from_row(row) for row in rows]

    def delete_for_job(self, job_id: EntityId) -> int:
        return row_count(
            self._conn,
            "DELETE FROM job_items WHERE job_id = ?",
            (str(job_id),),
        )
