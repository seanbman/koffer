"""Offscreen pytest-qt coverage for S16 Activity Center foundations."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QPushButton

from koffer.app_context import AppContext
from koffer.domain.enums import JobState, JobType
from koffer.domain.ids import new_entity_id
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs import JobSpec
from koffer.repositories.jobs import JobRepository
from koffer.ui.shell import MainWindow


def test_s16_lists_jobs_and_states_from_scheduler(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "activity")
    try:
        # Seed durable Jobs representing each Activity Center group.
        conn = context.connection_factory.get_connection()
        repo = JobRepository(conn)
        now = utc_now_iso()
        repo.create(
            Job(
                id=new_entity_id(),
                type=JobType.SOURCE_SCAN,
                state=JobState.RUNNING,
                scope_json=json.dumps({"source_id": "src-running", "label": "Studio SSD"}),
                progress_current=10,
                progress_total=100,
                stage="upsert",
                created_at=now,
                started_at=now,
            )
        )
        repo.create(
            Job(
                id=new_entity_id(),
                type=JobType.TECHNICAL_PROBE,
                state=JobState.QUEUED,
                scope_json=json.dumps({"sample_ids": ["a", "b"]}),
                progress_current=0,
                created_at=now,
                stage="queued",
            )
        )
        repo.create(
            Job(
                id=new_entity_id(),
                type=JobType.BACKUP,
                state=JobState.COMPLETED,
                scope_json=json.dumps({"label": "library.db"}),
                progress_current=1,
                progress_total=1,
                stage="commit",
                created_at=now,
                completed_at=now,
                summary_json=json.dumps({"succeeded": 1, "failed": 0, "skipped": 0}),
            )
        )
        repo.create(
            Job(
                id=new_entity_id(),
                type=JobType.METADATA_WRITE,
                state=JobState.FAILED,
                scope_json=json.dumps({"label": "1 item failed"}),
                progress_current=1,
                progress_total=1,
                stage="write",
                created_at=now,
                completed_at=now,
                error_code="unsupported_artwork",
                summary_json=json.dumps({"succeeded": 0, "failed": 1, "skipped": 0}),
            )
        )
        repo.create(
            Job(
                id=new_entity_id(),
                type=JobType.SYNTHETIC_ITEMS,
                state=JobState.INTERRUPTED,
                scope_json=json.dumps({"item_count": 5, "label": "interrupted"}),
                progress_current=2,
                progress_total=5,
                stage="interrupted",
                created_at=now,
                completed_at=now,
                error_code="interrupted_by_restart",
            )
        )

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S16")
        assert window.current_screen_id() == "S16"

        job_list = window.findChild(QListWidget, "activityJobList")
        assert job_list is not None
        texts = [job_list.item(i).text() for i in range(job_list.count())]
        joined = "\n".join(texts)
        assert "RUNNING" in joined
        assert "QUEUED" in joined
        assert "NEEDS ATTENTION" in joined
        assert "COMPLETED" in joined
        assert "running" in joined
        assert "queued" in joined
        assert "completed" in joined
        assert "failed" in joined
        assert "interrupted" in joined
        assert "source scan" in joined.lower() or "source_scan" in joined.lower()

        from PySide6.QtWidgets import QLabel

        badge_running = window.findChild(QLabel, "activityBadgeRunning")
        badge_attention = window.findChild(QLabel, "activityBadgeAttention")
        assert badge_running is not None
        assert badge_attention is not None
        assert "1 RUNNING" in badge_running.text()
        assert "2 NEEDS ATTENTION" in badge_attention.text()
    finally:
        context.close()


def test_s16_closing_does_not_cancel_running_job(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "activity-close")
    try:
        job_id = context.scheduler.submit(
            JobSpec(
                type=JobType.SYNTHETIC_ITEMS,
                scope={"item_count": 30, "sleep_ms": 30, "label": "keep-running"},
            )
        )
        # Let it start.
        import time

        for _ in range(100):
            job = context.scheduler.get(job_id)
            if job.state is JobState.RUNNING and job.progress_current >= 1:
                break
            time.sleep(0.02)

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S16")
        assert window.current_screen_id() == "S16"
        # Navigate away — must not cancel the Job.
        window.navigate("S01")
        assert window.current_screen_id() == "S01"
        mid = context.scheduler.get(job_id)
        assert mid.state in {JobState.RUNNING, JobState.QUEUED, JobState.COMPLETED}
        assert mid.state is not JobState.CANCELLED
        assert mid.state is not JobState.CANCEL_REQUESTED

        finished = context.scheduler.wait(job_id, timeout=15.0)
        assert finished.state is JobState.COMPLETED
    finally:
        context.close()


def test_s16_cancel_button_requests_cooperative_cancel(qtbot: object, tmp_path: Path) -> None:
    """Cancel must win the race against completion; build UI before submitting work."""
    import time

    context = AppContext.open_temp(tmp_path / "activity-cancel")
    try:
        # Build the Activity Center first so MainWindow/setup cost cannot eat the
        # job's remaining runtime (the prior flake: job completed before click).
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S16")

        # Long runway: ~20s if never cancelled; cancel should land early.
        item_count = 200
        job_id = context.scheduler.submit(
            JobSpec(
                type=JobType.SYNTHETIC_ITEMS,
                scope={"item_count": item_count, "sleep_ms": 100, "label": "ui-cancel"},
            )
        )

        running: Job | None = None
        for _ in range(300):
            running = context.scheduler.get(job_id)
            if running.state is JobState.RUNNING and running.progress_current >= 1:
                break
            if running.state in {JobState.COMPLETED, JobState.CANCELLED}:
                break
            time.sleep(0.02)

        assert running is not None
        assert running.state is JobState.RUNNING, f"job finished before cancel UI: {running.state}"
        assert running.progress_current < item_count

        # Refresh list so the newly submitted job is selectable.
        window.navigate("S16")

        job_list = window.findChild(QListWidget, "activityJobList")
        assert job_list is not None
        # Select the synthetic job row (skip section headers with no UserRole).
        selected = False
        for index in range(job_list.count()):
            item = job_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == str(job_id):
                job_list.setCurrentItem(item)
                selected = True
                break
        assert selected

        # Guard: still running at the moment we click Cancel.
        pre_click = context.scheduler.get(job_id)
        assert pre_click.state is JobState.RUNNING, f"pre-click state={pre_click.state}"

        cancel_btn = window.findChild(QPushButton, "activityCancelButton")
        assert cancel_btn is not None
        qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

        finished = context.scheduler.wait(job_id, timeout=15.0)
        assert finished.state is JobState.CANCELLED
        assert finished.progress_current < item_count
    finally:
        context.close()
