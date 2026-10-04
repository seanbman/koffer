"""CollectionService CRUD/membership with filesystem safety proofs."""

from __future__ import annotations

from pathlib import Path

import pytest

from koffer.domain import (
    CollectionSortMode,
    JobState,
    NotFoundError,
    SampleAvailability,
    ValidationError,
    new_entity_id,
    utc_now_iso,
)
from koffer.domain.models import Sample
from koffer.jobs import JobScheduler
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories import SampleRepository, SourceRepository
from koffer.services.collections import CollectionService
from koffer.services.sources import SourceService


def _build(
    tmp_path: Path,
) -> tuple[CollectionService, SourceService, JobScheduler, ConnectionFactory]:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    apply_migrations(factory.get_connection())
    scheduler = JobScheduler(factory, io_workers=2)
    sources = SourceService(factory, scheduler)
    collections = CollectionService(factory)
    return collections, sources, scheduler, factory


def _file_fingerprint(path: Path) -> tuple[int, bytes]:
    return path.stat().st_size, path.read_bytes()


def test_create_add_remove_membership_without_touching_audio(tmp_path: Path) -> None:
    collections, sources, scheduler, factory = _build(tmp_path)
    try:
        tree = tmp_path / "pack"
        tree.mkdir()
        kick = tree / "kick.wav"
        snare = tree / "snare.wav"
        kick.write_bytes(b"RIFF-KICK-WAVE")
        snare.write_bytes(b"RIFF-SNARE-WAVE")
        before = {kick: _file_fingerprint(kick), snare: _file_fingerprint(snare)}

        source = sources.add_source(tree)
        job = scheduler.wait(sources.scan(source.id), timeout=30.0)
        assert job.state is JobState.COMPLETED
        samples = SampleRepository(factory.get_connection()).list_by_source(source.id)
        assert len(samples) == 2
        sample_ids = [sample.id for sample in samples]

        collection = collections.create("Favourite Breaks", description="No copies")
        collections.add_samples(collection.id, sample_ids)
        assert set(collections.list_sample_ids(collection.id)) == set(sample_ids)

        collections.remove_samples(collection.id, [sample_ids[0]])
        remaining = collections.list_sample_ids(collection.id)
        assert sample_ids[0] not in remaining
        assert sample_ids[1] in remaining

        # Audio bytes and paths untouched by create/add/remove.
        for path, fingerprint in before.items():
            assert path.is_file()
            assert _file_fingerprint(path) == fingerprint
    finally:
        scheduler.shutdown(wait=True)


def test_delete_collection_leaves_samples_and_files_intact(tmp_path: Path) -> None:
    collections, sources, scheduler, factory = _build(tmp_path)
    try:
        tree = tmp_path / "keep"
        tree.mkdir()
        audio = tree / "loop.wav"
        audio.write_bytes(b"RIFF-LOOP-WAVE")
        before = _file_fingerprint(audio)

        source = sources.add_source(tree)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(factory.get_connection()).list_by_source(source.id)
        assert len(samples) == 1
        sample = samples[0]

        collection = collections.create("Temp Group")
        collections.add_samples(collection.id, [sample.id])
        collections.delete(collection.id)

        assert collections.list() == []
        with pytest.raises(NotFoundError):
            collections.get(collection.id)

        # Sample record remains.
        still = SampleRepository(factory.get_connection()).get(sample.id)
        assert still is not None
        assert still.id == sample.id
        assert SourceRepository(factory.get_connection()).get(source.id) is not None

        # Filesystem untouched.
        assert audio.is_file()
        assert _file_fingerprint(audio) == before
    finally:
        scheduler.shutdown(wait=True)


def test_reorder_sets_manual_sort_without_file_side_effects(tmp_path: Path) -> None:
    collections, sources, scheduler, factory = _build(tmp_path)
    try:
        tree = tmp_path / "order"
        tree.mkdir()
        a = tree / "a.wav"
        b = tree / "b.wav"
        c = tree / "c.wav"
        for path, payload in ((a, b"A"), (b, b"B"), (c, b"C")):
            path.write_bytes(payload)
        before = {path: _file_fingerprint(path) for path in (a, b, c)}

        source = sources.add_source(tree)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(factory.get_connection()).list_by_source(source.id)
        by_name = {sample.filename: sample.id for sample in samples}
        collection = collections.create("Ordered")
        original_order = [by_name["a.wav"], by_name["b.wav"], by_name["c.wav"]]
        collections.add_samples(collection.id, original_order)

        new_order = [by_name["c.wav"], by_name["a.wav"], by_name["b.wav"]]
        collections.reorder(collection.id, new_order)
        detail = collections.get_detail(collection.id)
        assert detail.collection.sort_mode == str(CollectionSortMode.MANUAL)
        assert [sample.id for sample in detail.samples] == new_order

        for path, fingerprint in before.items():
            assert _file_fingerprint(path) == fingerprint
    finally:
        scheduler.shutdown(wait=True)


def test_add_samples_is_idempotent_and_rejects_unknown(tmp_path: Path) -> None:
    collections, _sources, scheduler, factory = _build(tmp_path)
    try:
        now = utc_now_iso()
        sample = Sample(
            id=new_entity_id(),
            relative_path="solo.wav",
            normalized_path_cache="solo.wav",
            filename="solo.wav",
            extension="wav",
            size_bytes=8,
            mtime_ns=1,
            availability=SampleAvailability.ONLINE,
            favorite=False,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        SampleRepository(factory.get_connection()).create(sample)
        collection = collections.create("Solo")
        collections.add_samples(collection.id, [sample.id])
        collections.add_samples(collection.id, [sample.id])
        assert collections.list_sample_ids(collection.id) == [sample.id]

        with pytest.raises(NotFoundError):
            collections.add_samples(collection.id, [new_entity_id()])
        with pytest.raises(ValidationError):
            collections.create("   ")
    finally:
        scheduler.shutdown(wait=True)
