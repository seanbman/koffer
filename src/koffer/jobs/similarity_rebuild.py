"""REBUILD_SIMILARITY / SIMILARITY_INDEX_BUILD Job runners (docs/18)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from koffer.domain.enums import JobState
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs.cancel import is_cancel_requested, mark_cancelled
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.jobs import JobRepository


def run_similarity_rebuild_job(
    conn: sqlite3.Connection,
    job: Job,
    *,
    connection_factory: ConnectionFactory,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Rebuild the similarity index from cached embeddings."""
    from koffer.services.similarity import SimilarityService

    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json or "{}")
    cache_raw = scope.get("cache_dir")
    if not isinstance(cache_raw, str) or not cache_raw:
        failed = replace(
            job,
            state=JobState.FAILED,
            stage="rebuild_similarity",
            completed_at=utc_now_iso(),
            error_code="missing_cache_dir",
            summary_json=json.dumps({"error": "missing_cache_dir"}),
        )
        jobs.update(failed)
        _emit(progress, failed, force=True)
        return failed

    now = utc_now_iso()
    running = replace(
        job,
        state=JobState.RUNNING,
        stage="rebuild_similarity",
        started_at=now,
        progress_current=0,
        progress_total=1,
    )
    jobs.update(running)
    _emit(progress, running, force=True)

    if is_cancel_requested(conn, job.id):
        cancelled = mark_cancelled(conn, running)
        _emit(progress, cancelled, force=True)
        return cancelled

    service = SimilarityService(connection_factory, Path(cache_raw))
    size = service.rebuild_index_sync()
    completed = replace(
        running,
        state=JobState.COMPLETED,
        stage="rebuild_similarity",
        progress_current=1,
        progress_total=1,
        completed_at=utc_now_iso(),
        summary_json=json.dumps({"index_size": size, "ok": True}),
    )
    jobs.update(completed)
    _emit(progress, completed, force=True)
    return completed


def _emit(progress: ProgressThrottle | None, job: Job, *, force: bool = False) -> None:
    if progress is None:
        return
    progress.publish(
        ProgressEvent(
            job_id=job.id,
            state=job.state,
            stage=job.stage,
            current=job.progress_current,
            total=job.progress_total,
        ),
        force=force,
    )
