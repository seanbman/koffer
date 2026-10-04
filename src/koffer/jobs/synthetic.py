"""Synthetic item-batch Job for cancel/recovery harnesses (no filesystem mutation)."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import replace

from koffer.domain.enums import JobState
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs.cancel import is_cancel_requested, mark_cancelled, persist_progress
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.repositories.jobs import JobRepository


def run_synthetic_items(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Process N in-memory items with optional sleep; cancel between items only."""
    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json)
    item_count = max(0, int(scope.get("item_count", 0)))
    sleep_ms = max(0, int(scope.get("sleep_ms", 0)))

    now = utc_now_iso()
    running = replace(
        job,
        state=JobState.RUNNING,
        stage="items",
        started_at=now,
        progress_current=0,
        progress_total=item_count,
    )
    jobs.update(running)
    _emit(
        progress,
        running,
        current=0,
        total=item_count,
        succeeded=0,
        failed=0,
        skipped=0,
        force=True,
    )

    succeeded = 0
    for index in range(1, item_count + 1):
        if is_cancel_requested(conn, job.id):
            summary = json.dumps(
                {
                    "succeeded": succeeded,
                    "failed": 0,
                    "skipped": 0,
                    "total": item_count,
                    "cancelled_at_item": index,
                }
            )
            cancelled = mark_cancelled(
                conn,
                replace(
                    running,
                    progress_current=succeeded,
                    progress_total=item_count,
                    summary_json=summary,
                ),
                summary_json=summary,
            )
            _emit(
                progress,
                cancelled,
                current=succeeded,
                total=item_count,
                succeeded=succeeded,
                force=True,
            )
            return cancelled

        if sleep_ms:
            time.sleep(sleep_ms / 1000.0)
        succeeded += 1
        # Persist every item so cancellation observability is durable.
        # Must not clobber CANCEL_REQUESTED written by the UI/scheduler thread.
        updated = persist_progress(
            conn,
            running,
            progress_current=succeeded,
            progress_total=item_count,
            stage="items",
        )
        _emit(
            progress,
            updated,
            current=succeeded,
            total=item_count,
            succeeded=succeeded,
            active_item=f"item-{index}",
        )

    completed = replace(
        running,
        state=JobState.COMPLETED,
        stage="commit",
        completed_at=utc_now_iso(),
        progress_current=item_count,
        progress_total=item_count,
        summary_json=json.dumps(
            {
                "succeeded": succeeded,
                "failed": 0,
                "skipped": 0,
                "total": item_count,
            }
        ),
    )
    jobs.update(completed)
    _emit(
        progress,
        completed,
        current=item_count,
        total=item_count,
        succeeded=succeeded,
        force=True,
    )
    return completed


def _emit(
    progress: ProgressThrottle | None,
    job: Job,
    *,
    current: int,
    total: int,
    succeeded: int = 0,
    failed: int = 0,
    skipped: int = 0,
    active_item: str | None = None,
    force: bool = False,
) -> None:
    if progress is None:
        return
    progress.publish(
        ProgressEvent(
            job_id=job.id,
            state=job.state,
            stage=job.stage,
            current=current,
            total=total,
            active_item=active_item,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
        ),
        force=force,
    )
