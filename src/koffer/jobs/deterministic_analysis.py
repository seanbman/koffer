"""deterministic_analysis Job runner (docs/18, docs/19)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace

from koffer.analysis.pipeline import DETERMINISTIC_PIPELINE_VERSION
from koffer.domain.enums import JobState
from koffer.domain.ids import EntityId
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs.cancel import is_cancel_requested, mark_cancelled, persist_progress
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.jobs import JobRepository


def run_deterministic_analysis_job(
    conn: sqlite3.Connection,
    job: Job,
    *,
    connection_factory: ConnectionFactory,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Analyze scoped Samples; never mutates classifications or embedded tags."""
    # Lazy import avoids scheduler ↔ AnalysisService circular import at module load.
    from koffer.services.analysis import AnalysisService

    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json)
    raw_ids = scope.get("sample_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        single = scope.get("sample_id")
        raw_ids = [single] if single else []
    sample_ids = [EntityId(str(item)) for item in raw_ids if item]

    now = utc_now_iso()
    running = replace(
        job,
        state=JobState.RUNNING,
        stage="deterministic_analysis",
        started_at=now,
        progress_current=0,
        progress_total=len(sample_ids),
    )
    jobs.update(running)
    _emit(progress, running, succeeded=0, failed=0, skipped=0, force=True)

    service = AnalysisService(connection_factory)
    succeeded = 0
    failed = 0
    skipped = 0
    failures: list[dict[str, str]] = []

    for index, sample_id in enumerate(sample_ids, start=1):
        if is_cancel_requested(conn, job.id):
            cancel_summary = json.dumps(
                {
                    "succeeded": succeeded,
                    "failed": failed,
                    "skipped": skipped,
                    "total": len(sample_ids),
                    "failures": failures,
                    "pipeline_version": DETERMINISTIC_PIPELINE_VERSION,
                    "cancelled": True,
                }
            )
            cancelled = mark_cancelled(
                conn,
                replace(
                    running,
                    progress_current=index - 1,
                    progress_total=len(sample_ids),
                    summary_json=cancel_summary,
                ),
                summary_json=cancel_summary,
            )
            _emit(
                progress,
                cancelled,
                succeeded=succeeded,
                failed=failed,
                skipped=skipped,
                force=True,
            )
            return cancelled

        try:
            service.analyze_sample(sample_id)
            succeeded += 1
        except Exception as exc:  # noqa: BLE001 — per-item failure must not abort batch
            failed += 1
            failures.append(
                {
                    "sample_id": str(sample_id),
                    "error": type(exc).__name__,
                    "detail": str(exc)[:200],
                }
            )

        _progress(
            conn,
            running,
            index,
            len(sample_ids),
            progress=progress,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
        )

    summary = json.dumps(
        {
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "total": len(sample_ids),
            "failures": failures,
            "pipeline_version": DETERMINISTIC_PIPELINE_VERSION,
        }
    )
    if failed == 0:
        final_state = JobState.COMPLETED
        error_code = None
    elif succeeded > 0:
        final_state = JobState.COMPLETED_WITH_ERRORS
        error_code = "item_failures"
    else:
        final_state = JobState.FAILED
        error_code = "item_failures"

    completed = replace(
        running,
        state=final_state,
        progress_current=len(sample_ids),
        progress_total=len(sample_ids),
        completed_at=utc_now_iso(),
        summary_json=summary,
        error_code=error_code,
    )
    jobs.update(completed)
    _emit(
        progress,
        completed,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        force=True,
    )
    return completed


def _progress(
    conn: sqlite3.Connection,
    job: Job,
    current: int,
    total: int,
    *,
    progress: ProgressThrottle | None,
    succeeded: int,
    failed: int,
    skipped: int,
) -> None:
    updated = persist_progress(
        conn,
        job,
        stage="deterministic_analysis",
        progress_current=current,
        progress_total=total,
    )
    _emit(
        progress,
        updated,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
    )


def _emit(
    progress: ProgressThrottle | None,
    job: Job,
    *,
    succeeded: int,
    failed: int,
    skipped: int,
    force: bool = False,
) -> None:
    if progress is None:
        return
    progress.publish(
        ProgressEvent(
            job_id=job.id,
            state=job.state,
            stage=job.stage,
            current=job.progress_current,
            total=job.progress_total,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
        ),
        force=force,
    )
