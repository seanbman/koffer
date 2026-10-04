"""Maintenance Job runners: backup/restore/verify/rebuild/cache_clear (docs/24)."""

from __future__ import annotations

import contextlib
import json
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path

from koffer.domain.enums import CacheCategory, JobState, JobType, ScanMode
from koffer.domain.ids import EntityId
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs.cancel import is_cancel_requested, mark_cancelled
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.persistence.backup import BackupError, backup_database, restore_database
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.jobs import JobRepository
from koffer.repositories.sources import SourceRepository


def run_maintenance_job(
    conn: sqlite3.Connection,
    job: Job,
    *,
    connection_factory: ConnectionFactory,
    progress: ProgressThrottle | None = None,
    scheduler: object | None = None,
) -> Job:
    """Dispatch a maintenance Job type to its runner."""
    if job.type is JobType.BACKUP:
        return _run_backup(conn, job, progress=progress)
    if job.type is JobType.RESTORE:
        return _run_restore(conn, job, connection_factory=connection_factory, progress=progress)
    if job.type is JobType.DATABASE_VERIFY:
        return _run_verify(conn, job, progress=progress)
    if job.type is JobType.REBUILD_FILESYSTEM_INDEX:
        return _run_rebuild_filesystem_index(conn, job, scheduler=scheduler, progress=progress)
    if job.type is JobType.REBUILD_WAVEFORMS:
        return _run_clear_named_cache(
            conn,
            job,
            names=("waveforms",),
            stage="rebuild_waveforms",
            progress=progress,
        )
    if job.type is JobType.REBUILD_ANALYSIS:
        return _run_clear_named_cache(
            conn,
            job,
            names=("analysis",),
            stage="rebuild_analysis",
            progress=progress,
            extra_summary={"preserved": ["collections", "classifications", "recipes"]},
        )
    if job.type is JobType.CACHE_CLEAR:
        return _run_cache_clear(conn, job, progress=progress)
    failed = replace(
        job,
        state=JobState.FAILED,
        stage="unsupported",
        completed_at=utc_now_iso(),
        error_code="unsupported_maintenance_type",
        summary_json=json.dumps({"error": "unsupported_maintenance_type"}),
    )
    JobRepository(conn).update(failed)
    _emit(progress, failed, force=True)
    return failed


def _run_backup(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None,
) -> Job:
    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json or "{}")
    destination = Path(str(scope.get("destination", "")))
    running = _mark_running(jobs, job, stage="backup", total=1)
    _emit(progress, running, force=True)
    if is_cancel_requested(conn, job.id):
        cancelled = mark_cancelled(conn, running)
        _emit(progress, cancelled, force=True)
        return cancelled
    try:
        backup_dir = backup_database(conn, destination)
    except BackupError as exc:
        return _fail(jobs, running, error_code="backup_failed", detail=str(exc), progress=progress)
    completed = replace(
        running,
        state=JobState.COMPLETED,
        stage="backup",
        progress_current=1,
        progress_total=1,
        completed_at=utc_now_iso(),
        summary_json=json.dumps(
            {
                "ok": True,
                "backup_dir": str(backup_dir),
                "preserve_note": scope.get("preserve_note", ""),
            }
        ),
    )
    jobs.update(completed)
    _emit(progress, completed, force=True)
    return completed


def _run_restore(
    conn: sqlite3.Connection,
    job: Job,
    *,
    connection_factory: ConnectionFactory,
    progress: ProgressThrottle | None,
) -> Job:
    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json or "{}")
    backup_path = Path(str(scope.get("backup_path", "")))
    database_path = Path(str(scope.get("database_path", connection_factory.database_path)))
    safety_parent = Path(str(scope.get("safety_backup_parent", database_path.parent)))
    job_id = job.id
    running = _mark_running(jobs, job, stage="restore", total=1)
    _emit(progress, running, force=True)
    if is_cancel_requested(conn, job.id):
        cancelled = mark_cancelled(conn, running)
        _emit(progress, cancelled, force=True)
        return cancelled

    # Close active connections before replacing the database file.
    with contextlib.suppress(sqlite3.Error):
        conn.close()
    connection_factory.close_thread_connection()

    try:
        manifest = restore_database(
            backup_path,
            database_path,
            safety_backup_parent=safety_parent,
        )
    except BackupError as exc:
        # Reopen and record failure in whatever DB is present.
        fail_conn = connection_factory.open_connection()
        try:
            failed = replace(
                running,
                state=JobState.FAILED,
                stage="restore",
                completed_at=utc_now_iso(),
                error_code="restore_failed",
                summary_json=json.dumps({"error": str(exc)}),
            )
            JobRepository(fail_conn).update(failed)
            _emit(progress, failed, force=True)
            return failed
        finally:
            fail_conn.close()

    # Persist a COMPLETED restore record into the restored database.
    post = connection_factory.open_connection()
    try:
        completed = Job(
            id=EntityId(str(job_id)),
            type=JobType.RESTORE,
            state=JobState.COMPLETED,
            scope_json=running.scope_json,
            progress_current=1,
            progress_total=1,
            stage="restore",
            created_at=running.created_at,
            started_at=running.started_at,
            completed_at=utc_now_iso(),
            summary_json=json.dumps(
                {
                    "ok": True,
                    "schema_version": manifest.schema_version,
                    "koffer_version": manifest.koffer_version,
                    "preserve_note": scope.get("preserve_note", ""),
                }
            ),
        )
        repo = JobRepository(post)
        if repo.get(completed.id) is None:
            repo.create(completed)
        else:
            repo.update(completed)
        _emit(progress, completed, force=True)
        return completed
    finally:
        post.close()


def _run_verify(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None,
) -> Job:
    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json or "{}")
    deep = bool(scope.get("deep", False))
    running = _mark_running(jobs, job, stage="verify", total=1)
    _emit(progress, running, force=True)
    pragma = "PRAGMA integrity_check" if deep else "PRAGMA quick_check"
    row = conn.execute(pragma).fetchone()
    result = "ok" if row is not None and str(row[0]) == "ok" else str(row[0] if row else "failed")
    ok = result == "ok"
    completed = replace(
        running,
        state=JobState.COMPLETED if ok else JobState.COMPLETED_WITH_ERRORS,
        stage="verify",
        progress_current=1,
        progress_total=1,
        completed_at=utc_now_iso(),
        summary_json=json.dumps(
            {
                "ok": ok,
                "deep": deep,
                "result": result,
                "preserve_note": scope.get("preserve_note", ""),
            }
        ),
    )
    jobs.update(completed)
    _emit(progress, completed, force=True)
    return completed


def _run_rebuild_filesystem_index(
    conn: sqlite3.Connection,
    job: Job,
    *,
    scheduler: object | None,
    progress: ProgressThrottle | None,
) -> Job:
    from koffer.jobs.scheduler import JobScheduler, JobSpec

    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json or "{}")
    sources = SourceRepository(conn).list_all()
    enabled = [source for source in sources if source.enabled]
    running = _mark_running(jobs, job, stage="rebuild_filesystem_index", total=max(1, len(enabled)))
    _emit(progress, running, force=True)

    queued: list[str] = []
    for index, source in enumerate(enabled):
        if is_cancel_requested(conn, job.id):
            cancelled = mark_cancelled(conn, running)
            _emit(progress, cancelled, force=True)
            return cancelled
        if isinstance(scheduler, JobScheduler):
            child_id = scheduler.submit(
                JobSpec(
                    type=JobType.SOURCE_SCAN,
                    scope={"source_id": str(source.id), "mode": str(ScanMode.INCREMENTAL)},
                )
            )
            queued.append(str(child_id))
        running = replace(
            running,
            progress_current=index + 1,
            progress_total=max(1, len(enabled)),
        )
        jobs.update(running)
        _emit(progress, running)

    completed = replace(
        running,
        state=JobState.COMPLETED,
        stage="rebuild_filesystem_index",
        progress_current=max(1, len(enabled)),
        progress_total=max(1, len(enabled)),
        completed_at=utc_now_iso(),
        summary_json=json.dumps(
            {
                "ok": True,
                "sources_queued": len(enabled),
                "queued_job_ids": queued,
                "preserve_note": scope.get("preserve_note", ""),
            }
        ),
    )
    jobs.update(completed)
    _emit(progress, completed, force=True)
    return completed


def _run_clear_named_cache(
    conn: sqlite3.Connection,
    job: Job,
    *,
    names: tuple[str, ...],
    stage: str,
    progress: ProgressThrottle | None,
    extra_summary: dict[str, object] | None = None,
) -> Job:
    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json or "{}")
    cache_dir = Path(str(scope.get("cache_dir", "")))
    running = _mark_running(jobs, job, stage=stage, total=max(1, len(names)))
    _emit(progress, running, force=True)
    removed: list[str] = []
    for index, name in enumerate(names):
        if is_cancel_requested(conn, job.id):
            cancelled = mark_cancelled(conn, running)
            _emit(progress, cancelled, force=True)
            return cancelled
        target = cache_dir / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed.append(name)
        running = replace(running, progress_current=index + 1)
        jobs.update(running)
        _emit(progress, running)
    summary: dict[str, object] = {
        "ok": True,
        "removed": removed,
        "preserve_note": scope.get("preserve_note", ""),
    }
    if extra_summary:
        summary.update(extra_summary)
    completed = replace(
        running,
        state=JobState.COMPLETED,
        stage=stage,
        progress_current=max(1, len(names)),
        progress_total=max(1, len(names)),
        completed_at=utc_now_iso(),
        summary_json=json.dumps(summary),
    )
    jobs.update(completed)
    _emit(progress, completed, force=True)
    return completed


def _run_cache_clear(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None,
) -> Job:
    jobs = JobRepository(conn)
    scope = json.loads(job.scope_json or "{}")
    cache_dir = Path(str(scope.get("cache_dir", "")))
    raw_categories = scope.get("categories") or []
    categories = [CacheCategory(str(item)) for item in raw_categories]
    mapping = {
        CacheCategory.WAVEFORMS: "waveforms",
        CacheCategory.EMBEDDINGS: "embeddings",
        CacheCategory.SIMILARITY_INDEX: "similarity",
        CacheCategory.TEMP_RENDERS: "renders",
        CacheCategory.ANALYSIS_DERIVED: "analysis",
    }
    names = tuple(mapping[item] for item in categories if item in mapping)
    running = _mark_running(jobs, job, stage="cache_clear", total=max(1, len(names)))
    _emit(progress, running, force=True)
    removed: list[str] = []
    for index, name in enumerate(names):
        if is_cancel_requested(conn, job.id):
            cancelled = mark_cancelled(conn, running)
            _emit(progress, cancelled, force=True)
            return cancelled
        target = cache_dir / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed.append(name)
        running = replace(running, progress_current=index + 1)
        jobs.update(running)
        _emit(progress, running)
    completed = replace(
        running,
        state=JobState.COMPLETED,
        stage="cache_clear",
        progress_current=max(1, len(names)),
        progress_total=max(1, len(names)),
        completed_at=utc_now_iso(),
        summary_json=json.dumps(
            {
                "ok": True,
                "removed": removed,
                "categories": [str(item) for item in categories],
                "preserve_note": scope.get("preserve_note", ""),
                "preserved": ["collections", "classifications", "recipes", "sources"],
            }
        ),
    )
    jobs.update(completed)
    _emit(progress, completed, force=True)
    return completed


def _mark_running(jobs: JobRepository, job: Job, *, stage: str, total: int) -> Job:
    running = replace(
        job,
        state=JobState.RUNNING,
        stage=stage,
        started_at=utc_now_iso(),
        progress_current=0,
        progress_total=total,
    )
    jobs.update(running)
    return running


def _fail(
    jobs: JobRepository,
    job: Job,
    *,
    error_code: str,
    detail: str,
    progress: ProgressThrottle | None,
) -> Job:
    failed = replace(
        job,
        state=JobState.FAILED,
        completed_at=utc_now_iso(),
        error_code=error_code,
        summary_json=json.dumps({"error": detail}),
    )
    jobs.update(failed)
    _emit(progress, failed, force=True)
    return failed


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
