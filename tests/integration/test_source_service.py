"""Integration tests for SourceService scanning and offline safety."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from koffer.domain import (
    ExclusionPatternType,
    ExclusionRule,
    JobState,
    SampleAvailability,
    SourceStatus,
    ValidationError,
    new_entity_id,
)
from koffer.jobs import JobScheduler
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories import SampleRepository, SourceRepository
from koffer.services import SourceService


def _build_service(tmp_path: Path) -> tuple[SourceService, JobScheduler, ConnectionFactory]:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    conn = factory.get_connection()
    apply_migrations(conn)
    scheduler = JobScheduler(factory, io_workers=2)
    service = SourceService(factory, scheduler)
    return service, scheduler, factory


def _write_fixture_tree(root: Path) -> None:
    (root / "drums").mkdir(parents=True)
    (root / "drums" / "kick.wav").write_bytes(b"RIFF....WAVE")
    (root / "drums" / "snare.flac").write_bytes(b"fLaC")
    (root / "loops").mkdir()
    (root / "loops" / "groove.mp3").write_bytes(b"ID3")
    (root / "loops" / "notes.txt").write_text("ignore", encoding="utf-8")
    (root / ".cache").mkdir()
    (root / ".cache" / "temp.wav").write_bytes(b"RIFF")
    (root / "keys").mkdir()
    (root / "keys" / "rhodes.aiff").write_bytes(b"FORM")
    (root / "keys" / "pad.ogg").write_bytes(b"OggS")
    (root / "keys" / "bell.m4a").write_bytes(b"ftyp")


def test_add_and_scan_produces_sample_rows_for_supported_files(tmp_path: Path) -> None:
    service, scheduler, factory = _build_service(tmp_path)
    try:
        tree = tmp_path / "fixture-pack"
        tree.mkdir()
        _write_fixture_tree(tree)

        source = service.add_source(tree, display_name="Fixture Pack")
        job_id = service.scan(source.id)
        job = scheduler.wait(job_id, timeout=30.0)

        assert job.state is JobState.COMPLETED
        samples = SampleRepository(factory.get_connection()).list_by_source(source.id)
        relative_paths = sorted(sample.relative_path for sample in samples)
        assert relative_paths == [
            "drums/kick.wav",
            "drums/snare.flac",
            "keys/bell.m4a",
            "keys/pad.ogg",
            "keys/rhodes.aiff",
            "loops/groove.mp3",
        ]
        assert all(sample.availability is SampleAvailability.ONLINE for sample in samples)
        assert ".cache/temp.wav" not in relative_paths
        assert "loops/notes.txt" not in relative_paths
    finally:
        scheduler.shutdown(wait=True)


def test_remove_source_does_not_delete_filesystem_audio(tmp_path: Path) -> None:
    service, scheduler, factory = _build_service(tmp_path)
    try:
        tree = tmp_path / "keep-files"
        tree.mkdir()
        audio = tree / "kick.wav"
        audio.write_bytes(b"RIFF....WAVE")

        source = service.add_source(tree)
        job_id = service.scan(source.id)
        assert scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED

        service.remove_source(source.id)
        assert SourceRepository(factory.get_connection()).get(source.id) is None
        assert SampleRepository(factory.get_connection()).list_by_source(source.id) == []
        assert audio.is_file()
        assert audio.read_bytes() == b"RIFF....WAVE"
    finally:
        scheduler.shutdown(wait=True)


def test_offline_enumeration_preserves_sample_records(tmp_path: Path) -> None:
    service, scheduler, factory = _build_service(tmp_path)
    try:
        tree = tmp_path / "removable"
        tree.mkdir()
        (tree / "kick.wav").write_bytes(b"RIFF....WAVE")
        (tree / "hat.wav").write_bytes(b"RIFF....WAVE")

        source = service.add_source(tree)
        first = scheduler.wait(service.scan(source.id), timeout=30.0)
        assert first.state is JobState.COMPLETED

        before = SampleRepository(factory.get_connection()).list_by_source(source.id)
        assert len(before) == 2
        before_ids = {sample.id for sample in before}

        # Simulate offline / failed enumeration by removing the Source root.
        shutil.rmtree(tree)
        assert not tree.exists()

        second = scheduler.wait(service.scan(source.id), timeout=30.0)
        assert second.state is JobState.COMPLETED_WITH_ERRORS
        assert second.error_code == "source_offline"

        after = SampleRepository(factory.get_connection()).list_by_source(source.id)
        assert {sample.id for sample in after} == before_ids
        assert all(sample.availability is SampleAvailability.SOURCE_OFFLINE for sample in after)
        assert not any(sample.availability is SampleAvailability.MISSING for sample in after)

        refreshed = service.get(source.id)
        assert refreshed.status is SourceStatus.OFFLINE
    finally:
        scheduler.shutdown(wait=True)


def test_update_exclusions_and_disable(tmp_path: Path) -> None:
    service, scheduler, factory = _build_service(tmp_path)
    try:
        tree = tmp_path / "excl"
        (tree / "keep").mkdir(parents=True)
        (tree / "drop").mkdir()
        (tree / "keep" / "a.wav").write_bytes(b"RIFF")
        (tree / "drop" / "b.wav").write_bytes(b"RIFF")

        source = service.add_source(tree)
        preview = service.update_exclusions(
            source.id,
            [
                ExclusionRule(
                    id=new_entity_id(),
                    source_id=source.id,
                    pattern="drop/**",
                    pattern_type=ExclusionPatternType.GLOB,
                    enabled=True,
                )
            ],
        )
        assert preview.excluded_count == 1
        assert "drop/b.wav" in preview.matched_relative_paths

        job = scheduler.wait(service.scan(source.id), timeout=30.0)
        assert job.state is JobState.COMPLETED
        samples = SampleRepository(factory.get_connection()).list_by_source(source.id)
        assert [s.relative_path for s in samples] == ["keep/a.wav"]

        service.set_enabled(source.id, False)
        assert service.get(source.id).enabled is False
        assert service.get(source.id).status is SourceStatus.DISABLED
        with pytest.raises(ValidationError):
            service.scan(source.id)
    finally:
        scheduler.shutdown(wait=True)
