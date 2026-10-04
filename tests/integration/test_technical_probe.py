"""Integration tests for technical_probe Job and technical_metadata persistence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from koffer.domain import JobState, JobType, SampleAvailability
from koffer.jobs import JobScheduler
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories import SampleRepository, TechnicalMetadataRepository
from koffer.services import SourceService

# Clear marker when ffprobe is absent (Order 2-3: skip/xfail gracefully).
requires_ffprobe = pytest.mark.skipif(
    shutil.which("ffprobe") is None,
    reason="ffprobe_absent: ffprobe binary not on PATH",
)


def _build_service(tmp_path: Path) -> tuple[SourceService, JobScheduler, ConnectionFactory]:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    conn = factory.get_connection()
    apply_migrations(conn)
    scheduler = JobScheduler(factory, io_workers=2)
    service = SourceService(factory, scheduler)
    return service, scheduler, factory


def _wait_probe_jobs(scheduler: JobScheduler, *, timeout: float = 30.0) -> list:
    terminal = {
        JobState.COMPLETED,
        JobState.COMPLETED_WITH_ERRORS,
        JobState.FAILED,
        JobState.CANCELLED,
    }
    probes = [job for job in scheduler.list() if job.type is JobType.TECHNICAL_PROBE]
    finished = []
    for job in probes:
        finished.append(scheduler.wait(job.id, timeout=timeout))
    # Newly queued probes may appear after scan; re-list once.
    for job in scheduler.list():
        if job.type is not JobType.TECHNICAL_PROBE:
            continue
        if job.state in terminal:
            if all(str(item.id) != str(job.id) for item in finished):
                finished.append(job)
            continue
        finished.append(scheduler.wait(job.id, timeout=timeout))
    return finished


@requires_ffprobe
def test_successful_probe_persists_duration_rate_channels(tmp_path: Path) -> None:
    from koffer.audio.wav_fixtures import write_sine_wav

    service, scheduler, factory = _build_service(tmp_path)
    try:
        tree = tmp_path / "probe-ok"
        tree.mkdir()
        wav = write_sine_wav(
            tree / "kick.wav",
            duration_s=1.0,
            sample_rate=44100,
            channels=1,
        )
        assert wav.is_file()

        source = service.add_source(tree, display_name="Probe OK")
        scan_id = service.scan(source.id)
        scan_job = scheduler.wait(scan_id, timeout=30.0)
        assert scan_job.state is JobState.COMPLETED

        probe_jobs = _wait_probe_jobs(scheduler)
        assert probe_jobs
        assert any(job.state is JobState.COMPLETED for job in probe_jobs), [
            job.summary_json for job in probe_jobs
        ]

        samples = SampleRepository(factory.get_connection()).list_by_source(source.id)
        assert len(samples) == 1
        meta = TechnicalMetadataRepository(factory.get_connection()).get(samples[0].id)
        assert meta is not None
        assert meta.duration_ms == pytest.approx(1000, abs=50)
        assert meta.sample_rate_hz == 44100
        assert meta.channels == 1
        assert meta.container_format
        assert meta.codec
    finally:
        scheduler.shutdown(wait=True)


@requires_ffprobe
def test_probe_failure_does_not_delete_sample_or_crash_scan(tmp_path: Path) -> None:
    from koffer.audio.wav_fixtures import write_malformed_wav, write_sine_wav

    service, scheduler, factory = _build_service(tmp_path)
    try:
        tree = tmp_path / "probe-mixed"
        tree.mkdir()
        write_sine_wav(tree / "good.wav", duration_s=0.5, sample_rate=48000, channels=2)
        write_malformed_wav(tree / "bad.wav")

        source = service.add_source(tree)
        scan_id = service.scan(source.id)
        scan_job = scheduler.wait(scan_id, timeout=30.0)
        assert scan_job.state is JobState.COMPLETED

        probe_jobs = _wait_probe_jobs(scheduler)
        assert probe_jobs
        # Probe Job may complete with errors; scan already completed successfully.
        assert any(
            job.state in {JobState.COMPLETED_WITH_ERRORS, JobState.FAILED, JobState.COMPLETED}
            for job in probe_jobs
        )
        assert any(
            job.state in {JobState.COMPLETED_WITH_ERRORS, JobState.FAILED} for job in probe_jobs
        ) or any(json.loads(job.summary_json or "{}").get("failed", 0) > 0 for job in probe_jobs)

        samples = SampleRepository(factory.get_connection()).list_by_source(source.id)
        assert len(samples) == 2
        assert all(sample.availability is SampleAvailability.ONLINE for sample in samples)
        by_name = {sample.filename: sample for sample in samples}
        assert by_name["good.wav"].id
        assert by_name["bad.wav"].id

        technical = TechnicalMetadataRepository(factory.get_connection())
        good_meta = technical.get(by_name["good.wav"].id)
        bad_meta = technical.get(by_name["bad.wav"].id)
        assert good_meta is not None
        assert good_meta.sample_rate_hz == 48000
        assert good_meta.channels == 2
        assert bad_meta is None
    finally:
        scheduler.shutdown(wait=True)


def test_probe_marker_documents_ffprobe_absence() -> None:
    """Keep a stable pytest marker name when CI hosts lack ffprobe."""
    assert requires_ffprobe.kwargs["reason"].startswith("ffprobe_absent:")
