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
from koffer.repositories.jobs import JobRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.repositories.technical_metadata import TechnicalMetadataRepository


def run_technical_probe(conn: sqlite3.Connection, job: Job) -> Job:
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

    succeeded = 0
    failed = 0
    skipped = 0
    failures: list[dict[str, str]] = []

    for index, sample_id in enumerate(sample_ids, start=1):
        sample = samples.get(sample_id)
        if sample is None:
            failed += 1
            failures.append({"sample_id": str(sample_id), "error": "sample_not_found"})
            _progress(jobs, running, index, len(sample_ids))
            continue
        if sample.source_id is None:
            skipped += 1
            failures.append({"sample_id": str(sample_id), "error": "sample_has_no_source"})
            _progress(jobs, running, index, len(sample_ids))
            continue
        source = sources.get(sample.source_id)
        if source is None:
            failed += 1
            failures.append({"sample_id": str(sample_id), "error": "source_not_found"})
            _progress(jobs, running, index, len(sample_ids))
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
            _progress(jobs, running, index, len(sample_ids))
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
        succeeded += 1
        _progress(jobs, running, index, len(sample_ids))

    completed_at = utc_now_iso()
    summary = {
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "total": len(sample_ids),
        "failures": failures,
        "probe_version": PROBE_VERSION,
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
    return completed


def _progress(jobs: JobRepository, job: Job, current: int, total: int) -> None:
    jobs.update(
        replace(
            job,
            stage="probe",
            progress_current=current,
            progress_total=total,
        )
    )
