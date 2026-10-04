"""Integration tests for scheduler lanes, cancel, and interrupted recovery."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from koffer.domain.enums import JobLane, JobState, JobType
from koffer.domain.ids import new_entity_id
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs import JobScheduler, JobSpec, lane_for_job_type
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories.jobs import JobRepository


def _factory(tmp_path: Path) -> ConnectionFactory:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    apply_migrations(factory.get_connection())
    return factory


def test_scheduler_exposes_bounded_lanes(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    scheduler = JobScheduler(
        factory,
        io_workers=3,
        analysis_workers=2,
        mutation_workers=1,
        render_workers=1,
        maintenance_workers=1,
        recover_on_start=False,
    )
    try:
        workers = scheduler.lane_workers()
        assert workers[JobLane.IO] == 3
        assert workers[JobLane.ANALYSIS] == 2
        assert workers[JobLane.MUTATION] == 1
        assert workers[JobLane.RENDER] == 1
        assert workers[JobLane.MAINTENANCE] == 1
        assert lane_for_job_type(JobType.SOURCE_SCAN) is JobLane.IO
        assert lane_for_job_type(JobType.DETERMINISTIC_ANALYSIS) is JobLane.ANALYSIS
        assert lane_for_job_type(JobType.COPY_FILES) is JobLane.MUTATION
        assert lane_for_job_type(JobType.RENDER) is JobLane.RENDER
        assert lane_for_job_type(JobType.DATABASE_VERIFY) is JobLane.MAINTENANCE
    finally:
        scheduler.shutdown(wait=True)


def test_cooperative_cancel_between_synthetic_items(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    scheduler = JobScheduler(
        factory,
        io_workers=1,
        progress_min_interval_s=0.0,
        recover_on_start=False,
    )
    try:
        job_id = scheduler.submit(
            JobSpec(
                type=JobType.SYNTHETIC_ITEMS,
                scope={"item_count": 40, "sleep_ms": 40, "label": "cancel-harness"},
            )
        )
        # Wait until the Job is observably running with some progress.
        deadline_job = None
        for _ in range(200):
            deadline_job = scheduler.get(job_id)
            if (
                deadline_job.state is JobState.RUNNING and deadline_job.progress_current >= 1
            ) or deadline_job.state in {
                JobState.COMPLETED,
                JobState.CANCELLED,
            }:
                break
            import time

            time.sleep(0.02)

        assert deadline_job is not None
        assert deadline_job.state is JobState.RUNNING
        assert deadline_job.progress_current >= 1

        scheduler.cancel(job_id)
        finished = scheduler.wait(job_id, timeout=10.0)
        assert finished.state is JobState.CANCELLED
        assert finished.progress_current < 40
        assert finished.progress_current >= 1
        summary = json.loads(finished.summary_json or "{}")
        assert summary.get("succeeded", 0) >= 1
        assert summary.get("succeeded", 0) < 40
        assert "cancelled_at_item" in summary
    finally:
        scheduler.shutdown(wait=True)


def test_recover_interrupted_marks_abandoned_running_jobs(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    conn = factory.get_connection()
    now = utc_now_iso()
    abandoned_id = new_entity_id()
    JobRepository(conn).create(
        Job(
            id=abandoned_id,
            type=JobType.SYNTHETIC_ITEMS,
            state=JobState.RUNNING,
            scope_json=json.dumps({"item_count": 3, "label": "abandoned"}),
            progress_current=1,
            progress_total=3,
            stage="items",
            created_at=now,
            started_at=now,
        )
    )
    queued_id = new_entity_id()
    JobRepository(conn).create(
        Job(
            id=queued_id,
            type=JobType.SYNTHETIC_ITEMS,
            state=JobState.QUEUED,
            scope_json=json.dumps({"item_count": 1}),
            progress_current=0,
            created_at=now,
            stage="queued",
        )
    )

    # Simulated process restart: new scheduler recovers abandoned rows.
    scheduler = JobScheduler(factory, recover_on_start=True)
    try:
        abandoned = scheduler.get(abandoned_id)
        assert abandoned.state is JobState.INTERRUPTED
        assert abandoned.error_code == "interrupted_by_restart"
        assert abandoned.stage == "interrupted"
        queued = scheduler.get(queued_id)
        assert queued.state is JobState.QUEUED
    finally:
        scheduler.shutdown(wait=True)


def test_recover_interrupted_is_idempotent_for_already_terminal(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    scheduler = JobScheduler(factory, recover_on_start=False)
    try:
        job_id = scheduler.submit(
            JobSpec(type=JobType.SYNTHETIC_ITEMS, scope={"item_count": 2, "sleep_ms": 0})
        )
        done = scheduler.wait(job_id, timeout=5.0)
        assert done.state is JobState.COMPLETED
        marked = scheduler.recover_interrupted()
        still_completed = scheduler.get(job_id)
        assert still_completed.state is JobState.COMPLETED
        assert job_id not in marked
        # Force a fake running row then recover again.
        conn = factory.get_connection()
        JobRepository(conn).update(replace(done, state=JobState.RUNNING, completed_at=None))
        second = JobScheduler(factory, recover_on_start=True)
        try:
            assert second.get(job_id).state is JobState.INTERRUPTED
        finally:
            second.shutdown(wait=True)
    finally:
        scheduler.shutdown(wait=True)
