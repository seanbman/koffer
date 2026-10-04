"""Typed Job repository for durable background work units."""

from __future__ import annotations

import sqlite3

from koffer.domain.enums import JobState, JobType
from koffer.domain.ids import EntityId
from koffer.domain.models import Job
from koffer.repositories._sqlite import as_entity_id, optional_int, optional_str, row_count


def _from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=as_entity_id(row["id"]),
        type=JobType(str(row["type"])),
        state=JobState(str(row["state"])),
        scope_json=str(row["scope_json"]),
        progress_current=int(row["progress_current"]),
        created_at=str(row["created_at"]),
        progress_total=optional_int(row["progress_total"]),
        stage=optional_str(row["stage"]),
        started_at=optional_str(row["started_at"]),
        completed_at=optional_str(row["completed_at"]),
        error_code=optional_str(row["error_code"]),
        summary_json=optional_str(row["summary_json"]),
    )


class JobRepository:
    """CRUD for persisted Jobs (scheduler state only; no Qt types)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, job: Job) -> None:
        self._conn.execute(
            """
            INSERT INTO jobs (
                id, type, state, scope_json, progress_current, progress_total, stage,
                created_at, started_at, completed_at, error_code, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(job.id),
                str(job.type),
                str(job.state),
                job.scope_json,
                job.progress_current,
                job.progress_total,
                job.stage,
                job.created_at,
                job.started_at,
                job.completed_at,
                job.error_code,
                job.summary_json,
            ),
        )

    def get(self, job_id: EntityId) -> Job | None:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (str(job_id),),
        ).fetchone()
        return None if row is None else _from_row(row)

    def list_by_state(self, state: JobState) -> list[Job]:
        rows = self._conn.execute(
            """
            SELECT * FROM jobs
            WHERE state = ?
            ORDER BY created_at ASC, id ASC
            """,
            (str(state),),
        ).fetchall()
        return [_from_row(row) for row in rows]

    def update(self, job: Job) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE jobs SET
                    type = ?,
                    state = ?,
                    scope_json = ?,
                    progress_current = ?,
                    progress_total = ?,
                    stage = ?,
                    started_at = ?,
                    completed_at = ?,
                    error_code = ?,
                    summary_json = ?
                WHERE id = ?
                """,
                (
                    str(job.type),
                    str(job.state),
                    job.scope_json,
                    job.progress_current,
                    job.progress_total,
                    job.stage,
                    job.started_at,
                    job.completed_at,
                    job.error_code,
                    job.summary_json,
                    str(job.id),
                ),
            )
            > 0
        )

    def delete(self, job_id: EntityId) -> bool:
        return (
            row_count(
                self._conn,
                "DELETE FROM jobs WHERE id = ?",
                (str(job_id),),
            )
            > 0
        )
