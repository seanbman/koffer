"""Cooperative cancellation helpers for Job runners."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from typing import Any

from koffer.domain.enums import JobState
from koffer.domain.ids import EntityId
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories.jobs import JobRepository


def load_job(conn: sqlite3.Connection, job_id: EntityId) -> Job:
    job = JobRepository(conn).get(job_id)
    if job is None:
        msg = f"Job not found: {job_id}"
        raise LookupError(msg)
    return job


def is_cancel_requested(conn: sqlite3.Connection, job_id: EntityId) -> bool:
    """True when the durable Job row asks runners to stop between items."""
    job = JobRepository(conn).get(job_id)
    return job is not None and job.state is JobState.CANCEL_REQUESTED


def persist_progress(
    conn: sqlite3.Connection,
    base: Job,
    **changes: Any,
) -> Job:
    """Persist progress fields without clobbering CANCEL_REQUESTED from the UI thread."""
    repo = JobRepository(conn)
    latest = repo.get(base.id)
    if latest is None:
        msg = f"Job not found: {base.id}"
        raise LookupError(msg)
    # Never overwrite a cooperative cancel request with RUNNING progress snapshots.
    if latest.state is JobState.CANCEL_REQUESTED:
        merged = replace(latest, **changes)
        if merged.state is not JobState.CANCEL_REQUESTED:
            merged = replace(merged, state=JobState.CANCEL_REQUESTED)
        repo.update(merged)
        return merged
    updated = replace(latest, **changes)
    repo.update(updated)
    return updated


def mark_cancelled(
    conn: sqlite3.Connection,
    job: Job,
    *,
    stage: str = "cancelled",
    summary_json: str | None = None,
) -> Job:
    """Persist cooperative CANCELLED terminal state."""
    cancelled = replace(
        job,
        state=JobState.CANCELLED,
        stage=stage,
        completed_at=utc_now_iso(),
        summary_json=summary_json if summary_json is not None else job.summary_json,
    )
    JobRepository(conn).update(cancelled)
    return cancelled
