"""Bounded multi-lane JobScheduler with cancel, recovery, and progress throttle."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Any

from koffer.domain.enums import JobLane, JobState, JobType
from koffer.domain.errors import NotFoundError, UnsupportedOperationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs.cancel import mark_cancelled
from koffer.jobs.deterministic_analysis import run_deterministic_analysis_job
from koffer.jobs.file_ops import run_file_operation
from koffer.jobs.lanes import default_analysis_workers, lane_for_job_type
from koffer.jobs.metadata_write import run_metadata_write
from koffer.jobs.progress import ProgressEvent, ProgressListener, ProgressThrottle
from koffer.jobs.render import run_render
from koffer.jobs.similarity_rebuild import run_similarity_rebuild_job
from koffer.jobs.source_scan import run_source_scan
from koffer.jobs.synthetic import run_synthetic_items
from koffer.jobs.technical_probe import run_technical_probe
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.jobs import JobRepository

_ABANDONED_STATES = frozenset(
    {
        JobState.RUNNING,
        JobState.PAUSE_REQUESTED,
        JobState.PAUSED,
        JobState.CANCEL_REQUESTED,
    }
)

_TERMINAL_STATES = frozenset(
    {
        JobState.COMPLETED,
        JobState.COMPLETED_WITH_ERRORS,
        JobState.FAILED,
        JobState.CANCELLED,
        JobState.INTERRUPTED,
    }
)


@dataclass(frozen=True, slots=True)
class JobSpec:
    """Request to enqueue durable background work."""

    type: JobType
    scope: dict[str, Any]


@dataclass(frozen=True, slots=True)
class JobFilter:
    """Optional list filter for persisted Jobs."""

    state: JobState | None = None
    type: JobType | None = None


class JobScheduler:
    """Persist Jobs and execute supported types on bounded worker lanes."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        io_workers: int = 4,
        analysis_workers: int | None = None,
        mutation_workers: int = 1,
        render_workers: int = 1,
        maintenance_workers: int = 1,
        progress_min_interval_s: float = 0.05,
        recover_on_start: bool = True,
    ) -> None:
        self._factory = connection_factory
        analysis_n = (
            default_analysis_workers() if analysis_workers is None else max(1, analysis_workers)
        )
        self._lane_max_workers: dict[JobLane, int] = {
            JobLane.IO: max(1, io_workers),
            JobLane.ANALYSIS: analysis_n,
            JobLane.MUTATION: max(1, mutation_workers),
            JobLane.RENDER: max(1, render_workers),
            JobLane.MAINTENANCE: max(1, maintenance_workers),
        }
        self._pools: dict[JobLane, ThreadPoolExecutor] = {
            lane: ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix=f"koffer-{lane}",
            )
            for lane, workers in self._lane_max_workers.items()
        }
        self._lock = threading.RLock()
        self._futures: dict[str, Future[Job]] = {}
        self._closed = False
        self._progress = ProgressThrottle(min_interval_s=progress_min_interval_s)
        if recover_on_start:
            self.recover_interrupted()

    @property
    def progress(self) -> ProgressThrottle:
        return self._progress

    def add_progress_listener(self, listener: ProgressListener) -> None:
        self._progress.add_listener(listener)

    def remove_progress_listener(self, listener: ProgressListener) -> None:
        self._progress.remove_listener(listener)

    def lane_workers(self) -> dict[JobLane, int]:
        """Return configured max workers per lane (tests/diagnostics)."""
        return dict(self._lane_max_workers)

    def recover_interrupted(self) -> list[EntityId]:
        """Mark abandoned in-flight Jobs interrupted (startup / simulated restart)."""
        conn = self._factory.open_connection()
        try:
            repo = JobRepository(conn)
            marked: list[EntityId] = []
            now = utc_now_iso()
            for state in _ABANDONED_STATES:
                for job in repo.list_by_state(state):
                    interrupted = replace(
                        job,
                        state=JobState.INTERRUPTED,
                        stage="interrupted",
                        completed_at=now,
                        error_code="interrupted_by_restart",
                        summary_json=json.dumps(
                            {
                                "previous_state": str(state),
                                "reason": "abandoned_on_startup",
                            }
                        ),
                    )
                    repo.update(interrupted)
                    marked.append(job.id)
                    self._progress.publish(
                        ProgressEvent(
                            job_id=job.id,
                            state=JobState.INTERRUPTED,
                            stage="interrupted",
                            current=job.progress_current,
                            total=job.progress_total,
                            message="interrupted_by_restart",
                        ),
                        force=True,
                    )
            return marked
        finally:
            conn.close()

    def submit(self, spec: JobSpec) -> EntityId:
        """Persist a queued Job and schedule execution; return Job ID."""
        with self._lock:
            if self._closed:
                msg = "JobScheduler is shut down"
                raise RuntimeError(msg)
            now = utc_now_iso()
            job_id = new_entity_id()
            job = Job(
                id=job_id,
                type=spec.type,
                state=JobState.QUEUED,
                scope_json=json.dumps(spec.scope, sort_keys=True),
                progress_current=0,
                created_at=now,
                progress_total=None,
                stage="queued",
            )
            conn = self._factory.get_connection()
            JobRepository(conn).create(job)
            future = self._dispatch(job)
            self._futures[str(job_id)] = future
            self._progress.publish(
                ProgressEvent(
                    job_id=job_id,
                    state=JobState.QUEUED,
                    stage="queued",
                    current=0,
                    total=None,
                ),
                force=True,
            )
            return job_id

    def get(self, job_id: EntityId) -> Job:
        conn = self._factory.get_connection()
        job = JobRepository(conn).get(job_id)
        if job is None:
            raise NotFoundError(f"Job not found: {job_id}")
        return job

    def list(self, job_filter: JobFilter | None = None) -> list[Job]:
        conn = self._factory.get_connection()
        repo = JobRepository(conn)
        if job_filter is not None and job_filter.state is not None:
            jobs = repo.list_by_state(job_filter.state)
        else:
            jobs = [job for state in JobState for job in repo.list_by_state(state)]
        if job_filter is not None and job_filter.type is not None:
            jobs = [job for job in jobs if job.type is job_filter.type]
        jobs.sort(key=lambda item: (item.created_at, str(item.id)))
        return jobs

    def cancel(self, job_id: EntityId) -> None:
        conn = self._factory.get_connection()
        repo = JobRepository(conn)
        job = repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Job not found: {job_id}")
        if job.state in _TERMINAL_STATES:
            return
        # Cooperative cancel: runners check CANCEL_REQUESTED between items.
        updated = replace(job, state=JobState.CANCEL_REQUESTED, stage="cancel_requested")
        repo.update(updated)
        self._progress.publish(
            ProgressEvent(
                job_id=job_id,
                state=JobState.CANCEL_REQUESTED,
                stage="cancel_requested",
                current=job.progress_current,
                total=job.progress_total,
            ),
            force=True,
        )
        with self._lock:
            future = self._futures.get(str(job_id))
            if future is not None and not future.done():
                # Cancels only if the worker has not started; running Jobs cooperate.
                future.cancel()

    def pause(self, job_id: EntityId) -> None:
        del job_id
        raise UnsupportedOperationError("pause is not supported for this Job type")

    def resume(self, job_id: EntityId) -> None:
        del job_id
        raise UnsupportedOperationError("resume is not supported for this Job type")

    def wait(self, job_id: EntityId, *, timeout: float | None = 30.0) -> Job:
        """Block until the Job finishes or ``timeout`` elapses (tests/helpers)."""
        with self._lock:
            future = self._futures.get(str(job_id))
        if future is not None:
            try:
                future.result(timeout=timeout)
            except TimeoutError:
                pass
            except Exception:
                # Runner persists FAILED/COMPLETED_WITH_ERRORS; surface via get().
                pass
        else:
            deadline = None if timeout is None else time.monotonic() + timeout
            while True:
                job = self.get(job_id)
                if job.state in _TERMINAL_STATES:
                    return job
                if deadline is not None and time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        return self.get(job_id)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
        for pool in self._pools.values():
            pool.shutdown(wait=wait, cancel_futures=not wait)

    def _dispatch(self, job: Job) -> Future[Job]:
        lane = lane_for_job_type(job.type)
        pool = self._pools[lane]
        if job.type is JobType.SOURCE_SCAN:
            return pool.submit(self._run_source_scan, job.id)
        if job.type is JobType.TECHNICAL_PROBE:
            return pool.submit(self._run_technical_probe, job.id)
        if job.type is JobType.DETERMINISTIC_ANALYSIS:
            return pool.submit(self._run_deterministic_analysis, job.id)
        if job.type is JobType.SYNTHETIC_ITEMS:
            return pool.submit(self._run_synthetic_items, job.id)
        if job.type in {
            JobType.REFERENCE_SAMPLES,
            JobType.COPY_FILES,
            JobType.MOVE_FILES,
        }:
            return pool.submit(self._run_file_operation, job.id)
        if job.type is JobType.METADATA_WRITE:
            return pool.submit(self._run_metadata_write, job.id)
        if job.type is JobType.RENDER:
            return pool.submit(self._run_render, job.id)
        if job.type in {JobType.REBUILD_SIMILARITY, JobType.SIMILARITY_INDEX_BUILD}:
            return pool.submit(self._run_similarity_rebuild, job.id)
        return pool.submit(self._fail_unsupported, job.id)

    def _run_source_scan(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_source_scan(conn, job, progress=self._progress)
            self._emit_job(completed, force=True)
            self._queue_technical_probes(completed)
            return completed
        finally:
            conn.close()

    def _queue_technical_probes(self, scan_job: Job) -> None:
        """Enqueue technical_probe for new/changed Samples discovered by a scan."""
        if scan_job.state is not JobState.COMPLETED:
            return
        try:
            summary = json.loads(scan_job.summary_json or "{}")
        except json.JSONDecodeError:
            return
        raw_ids = summary.get("probe_sample_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return
        sample_ids = [str(item) for item in raw_ids if item]
        if not sample_ids:
            return
        try:
            scope = json.loads(scan_job.scope_json)
        except json.JSONDecodeError:
            scope = {}
        source_id = scope.get("source_id")
        probe_scope: dict[str, Any] = {"sample_ids": sample_ids}
        if isinstance(source_id, str) and source_id:
            probe_scope["source_id"] = source_id
        self.submit(JobSpec(type=JobType.TECHNICAL_PROBE, scope=probe_scope))

    def _run_technical_probe(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_technical_probe(conn, job, progress=self._progress)
            self._emit_job(completed, force=True)
            return completed
        finally:
            conn.close()

    def _run_deterministic_analysis(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_deterministic_analysis_job(
                conn,
                job,
                connection_factory=self._factory,
                progress=self._progress,
            )
            self._emit_job(completed, force=True)
            return completed
        finally:
            conn.close()

    def _run_synthetic_items(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_synthetic_items(conn, job, progress=self._progress)
            self._emit_job(completed, force=True)
            return completed
        finally:
            conn.close()

    def _run_file_operation(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_file_operation(conn, job, progress=self._progress)
            self._emit_job(completed, force=True)
            return completed
        finally:
            conn.close()

    def _run_metadata_write(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_metadata_write(conn, job, progress=self._progress)
            self._emit_job(completed, force=True)
            return completed
        finally:
            conn.close()

    def _run_render(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_render(conn, job, progress=self._progress)
            self._emit_job(completed, force=True)
            return completed
        finally:
            conn.close()

    def _run_similarity_rebuild(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = mark_cancelled(conn, job)
                self._emit_job(cancelled, force=True)
                return cancelled
            completed = run_similarity_rebuild_job(
                conn,
                job,
                connection_factory=self._factory,
                progress=self._progress,
            )
            self._emit_job(completed, force=True)
            return completed
        finally:
            conn.close()

    def _fail_unsupported(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            repo = JobRepository(conn)
            job = repo.get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            failed = replace(
                job,
                state=JobState.FAILED,
                stage="unsupported",
                completed_at=utc_now_iso(),
                error_code="unsupported_job_type",
                summary_json=json.dumps({"error": "unsupported_job_type"}),
            )
            repo.update(failed)
            self._emit_job(failed, force=True)
            return failed
        finally:
            conn.close()

    def _emit_job(self, job: Job, *, force: bool = False) -> None:
        self._progress.publish(
            ProgressEvent(
                job_id=job.id,
                state=job.state,
                stage=job.stage,
                current=job.progress_current,
                total=job.progress_total,
            ),
            force=force,
        )
