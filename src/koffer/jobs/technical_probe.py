"""technical_probe Job runner: argv ffprobe into technical_metadata (docs/19)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from koffer.audio.ffprobe import PROBE_VERSION, FfprobeError, probe_file
from koffer.domain.enums import JobState
from koffer.domain.ids import EntityId
from koffer.domain.models import Job, TechnicalMetadata
from koffer.domain.timestamps import utc_now_iso
from koffer.jobs.cancel import is_cancel_requested, mark_cancelled, persist_progress
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.repositories.jobs import JobRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.repositories.technical_metadata import TechnicalMetadataRepository


def run_technical_probe(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Probe scoped Samples; failures are recorded and never delete Sample rows."""
    jobs = JobRepository(conn)
    samples = SampleRepository(conn)
    sources = SourceRepository(conn)
    technical = TechnicalMetadataRepository(conn)

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
        stage="probe",
        started_at=now,
        progress_current=0,
        progress_total=len(sample_ids),
    )
    jobs.update(running)
    _emit(progress, running, succeeded=0, failed=0, skipped=0, force=True)

    succeeded = 0
    failed = 0
    skipped = 0
    failures: list[dict[str, str]] = []
    playable_sample_ids: list[EntityId] = []

    for index, sample_id in enumerate(sample_ids, start=1):
        if is_cancel_requested(conn, job.id):
            cancel_summary = json.dumps(
                {
                    "succeeded": succeeded,
                    "failed": failed,
                    "skipped": skipped,
                    "total": len(sample_ids),
                    "failures": failures,
                    "probe_version": PROBE_VERSION,
                    "playable_sample_ids": [str(item) for item in playable_sample_ids],
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

        sample = samples.get(sample_id)
        if sample is None:
            failed += 1
            failures.append({"sample_id": str(sample_id), "error": "sample_not_found"})
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
            continue
        if sample.source_id is None:
            skipped += 1
            failures.append({"sample_id": str(sample_id), "error": "sample_has_no_source"})
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
            continue
        source = sources.get(sample.source_id)
        if source is None:
            failed += 1
            failures.append({"sample_id": str(sample_id), "error": "source_not_found"})
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
            continue

        media_path = Path(source.root_path) / sample.relative_path
        try:
            result = probe_file(media_path)
        except FfprobeError as exc:
            failed += 1
            failures.append(
                {
                    "sample_id": str(sample_id),
                    "path": str(media_path),
                    "error": exc.message,
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
            continue

        latest_sample = samples.get(sample_id)
        latest_source = (
            sources.get(latest_sample.source_id)
            if latest_sample is not None and latest_sample.source_id is not None
            else None
        )
        if latest_sample is None or latest_source is None:
            skipped += 1
            failures.append(
                {
                    "sample_id": str(sample_id),
                    "error": "sample_or_source_removed_during_probe",
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
            continue

        technical.upsert(
            TechnicalMetadata(
                sample_id=sample_id,
                container_format=result.container_format,
                codec=result.codec,
                duration_ms=result.duration_ms,
                sample_rate_hz=result.sample_rate_hz,
                channels=result.channels,
                probe_version=PROBE_VERSION,
                probed_at=utc_now_iso(),
                bit_depth=result.bit_depth,
                channel_layout=result.channel_layout,
                bitrate=result.bitrate,
            )
        )
        # Sample row is never deleted on probe success or failure.
        playable_sample_ids.append(sample_id)
        succeeded += 1
        _progress(
            conn,
            running,
            index,
            len(sample_ids),
            progress=progress,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            active_item=str(media_path),
        )

    if is_cancel_requested(conn, job.id):
        cancel_summary = json.dumps(
            {
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
                "total": len(sample_ids),
                "failures": failures,
                "probe_version": PROBE_VERSION,
                "playable_sample_ids": [str(item) for item in playable_sample_ids],
                "cancelled": True,
            }
        )
        cancelled = mark_cancelled(
            conn,
            replace(
                running,
                progress_current=succeeded + failed + skipped,
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

    completed_at = utc_now_iso()
    summary = {
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "total": len(sample_ids),
        "failures": failures,
        "probe_version": PROBE_VERSION,
        "playable_sample_ids": [str(item) for item in playable_sample_ids],
    }
    if failed or skipped:
        state = JobState.COMPLETED_WITH_ERRORS if succeeded else JobState.FAILED
        error_code = "probe_partial_failure" if succeeded else "probe_failed"
    else:
        state = JobState.COMPLETED
        error_code = None

    completed = replace(
        running,
        state=state,
        stage="commit",
        completed_at=completed_at,
        error_code=error_code,
        progress_current=len(sample_ids),
        progress_total=len(sample_ids),
        summary_json=json.dumps(summary),
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
    active_item: str | None = None,
) -> None:
    updated = persist_progress(
        conn,
        job,
        stage="probe",
        progress_current=current,
        progress_total=total,
    )
    _emit(
        progress,
        updated,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        active_item=active_item,
    )


def _emit(
    progress: ProgressThrottle | None,
    job: Job,
    *,
    succeeded: int,
    failed: int,
    skipped: int,
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
            current=job.progress_current,
            total=job.progress_total,
            active_item=active_item,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
        ),
        force=force,
    )
