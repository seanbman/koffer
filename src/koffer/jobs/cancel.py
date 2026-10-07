"""Cooperative cancellation helpers for Job runners."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import replace
from typing import Any

from koffer.domain.enums import JobState
from koffer.domain.ids import EntityId
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories.jobs import JobRepository

_CONTROL_STATES = frozenset(
    {
        JobState.PAUSE_REQUESTED,
        JobState.PAUSED,
        JobState.CANCEL_REQUESTED,
    }
)


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
    # Never overwrite cooperative control state with RUNNING progress snapshots.
    if latest.state in _CONTROL_STATES:
        control_state = latest.state
        merged = replace(latest, **changes)
        if merged.state is not control_state:
            merged = replace(merged, state=control_state)
        repo.update(merged)
        return merged
    updated = replace(latest, **changes)
    repo.update(updated)
    return updated


def wait_if_paused(
    conn: sqlite3.Connection,
    job_id: EntityId,
    *,
    poll_interval_s: float = 0.05,
) -> JobState:
    """Cooperatively block a runner while a durable pause request is active."""
    repo = JobRepository(conn)
    while True:
        current = repo.get(job_id)
        if current is None:
            msg = f"Job not found: {job_id}"
            raise LookupError(msg)
        if current.state is JobState.CANCEL_REQUESTED:
            return current.state
        if current.state is JobState.PAUSE_REQUESTED:
            paused = replace(current, state=JobState.PAUSED)
            repo.update(paused)
            current = paused
        if current.state is JobState.PAUSED:
            time.sleep(max(0.01, poll_interval_s))
            continue
        return current.state


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
