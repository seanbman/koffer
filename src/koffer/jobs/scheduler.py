"""Bounded JobScheduler with durable Job rows (docs/18)."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Any

from koffer.domain.enums import JobState, JobType
from koffer.domain.errors import NotFoundError, UnsupportedOperationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs.source_scan import run_source_scan
from koffer.jobs.technical_probe import run_technical_probe
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.jobs import JobRepository


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
    ) -> None:
        self._factory = connection_factory
        self._io_pool = ThreadPoolExecutor(
            max_workers=max(1, io_workers),
            thread_name_prefix="koffer-io",
        )
        self._lock = threading.RLock()
        self._futures: dict[str, Future[Job]] = {}
        self._closed = False

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
        if job.state in {
            JobState.COMPLETED,
            JobState.COMPLETED_WITH_ERRORS,
            JobState.FAILED,
            JobState.CANCELLED,
        }:
            return
        # Cooperative cancel: source_scan checks CANCEL_REQUESTED before start.
        repo.update(replace(job, state=JobState.CANCEL_REQUESTED))
        with self._lock:
            future = self._futures.get(str(job_id))
            if future is not None and not future.done():
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
            # Job may have been submitted in another process; poll DB.
            deadline = None if timeout is None else time.monotonic() + timeout
            while True:
                job = self.get(job_id)
                if job.state in {
                    JobState.COMPLETED,
                    JobState.COMPLETED_WITH_ERRORS,
                    JobState.FAILED,
                    JobState.CANCELLED,
                }:
                    return job
                if deadline is not None and time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        return self.get(job_id)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
        self._io_pool.shutdown(wait=wait, cancel_futures=not wait)

    def _dispatch(self, job: Job) -> Future[Job]:
        if job.type is JobType.SOURCE_SCAN:
            return self._io_pool.submit(self._run_source_scan, job.id)
        if job.type is JobType.TECHNICAL_PROBE:
            return self._io_pool.submit(self._run_technical_probe, job.id)
        # Persist failure for unsupported types submitted early.
        return self._io_pool.submit(self._fail_unsupported, job.id)

    def _run_source_scan(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = replace(
                    job,
                    state=JobState.CANCELLED,
                    completed_at=utc_now_iso(),
                    stage="cancelled",
                )
                JobRepository(conn).update(cancelled)
                return cancelled
            completed = run_source_scan(conn, job)
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
        # Probe failures are visible on the probe Job; they never fail the scan Job.
        self.submit(JobSpec(type=JobType.TECHNICAL_PROBE, scope=probe_scope))

    def _run_technical_probe(self, job_id: EntityId) -> Job:
        conn = self._factory.open_connection()
        try:
            job = JobRepository(conn).get(job_id)
            if job is None:
                raise NotFoundError(f"Job not found: {job_id}")
            if job.state is JobState.CANCEL_REQUESTED:
                cancelled = replace(
                    job,
                    state=JobState.CANCELLED,
                    completed_at=utc_now_iso(),
                    stage="cancelled",
                )
                JobRepository(conn).update(cancelled)
                return cancelled
            return run_technical_probe(conn, job)
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
            return failed
        finally:
            conn.close()
