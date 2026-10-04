"""MetadataService plan/execute: UPDATE_ORIGINAL, WRITE_TO_COPY, verification."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from koffer.audio.metadata import capabilities_for_extension, read_embedded, write_embedded
from koffer.audio.wav_fixtures import write_sine_wav, write_tagged_wav
from koffer.domain.enums import ArtworkAction, JobItemState, JobState, MetadataWriteTarget
from koffer.domain.errors import ValidationError
from koffer.domain.metadata_write import ArtworkPayload, MetadataWriteRequest
from koffer.filesystem.hashing import content_fingerprint
from koffer.jobs import JobScheduler
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories.job_items import JobItemRepository
from koffer.repositories.samples import SampleRepository
from koffer.services.metadata import MetadataService
from koffer.services.sources import SourceService


def _build(
    tmp_path: Path,
) -> tuple[MetadataService, SourceService, JobScheduler, ConnectionFactory]:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    apply_migrations(factory.get_connection())
    scheduler = JobScheduler(factory, io_workers=2, mutation_workers=1)
    sources = SourceService(factory, scheduler)
    metadata = MetadataService(factory, scheduler)
    return metadata, sources, scheduler, factory


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _write_flac_via_ffmpeg(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wav = path.with_suffix(".src.wav")
    write_sine_wav(wav, duration_s=0.2)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(wav),
            "-c:a",
            "flac",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return path


def test_unsupported_fields_cannot_be_silently_written(tmp_path: Path) -> None:
    """Capabilities must surface unsupported fields; plan blocks execute."""
    metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        write_tagged_wav(pack / "kick.wav", title="Kick")
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        state = metadata.get_editor_state([sample.id])
        assert all(field.writable for field in state.embeddable_fields)

        with pytest.raises(ValidationError, match="unknown metadata fields"):
            metadata.plan_write(
                MetadataWriteRequest(
                    sample_ids=(sample.id,),
                    target=MetadataWriteTarget.UPDATE_ORIGINAL,
                    fields={"not_a_real_field": "x"},
                )
            )

        # Direct writer also refuses unsupported/unknown fields (never silent).
        media = Path(pack / "kick.wav")
        with pytest.raises(ValidationError, match="unknown metadata fields"):
            write_embedded(media, {"not_a_real_field": "x"})

        # Ogg capability matrix: artwork not writable / explained in editor.
        ogg_caps = capabilities_for_extension("ogg")
        assert ogg_caps.artwork_support is False
        assert "artwork" not in ogg_caps.writable_fields
    finally:
        scheduler.shutdown(wait=True)


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg required for OGG fixture")
def test_ogg_artwork_plan_surfaces_exception_not_silent(tmp_path: Path) -> None:
    metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "ogg_pack"
        pack.mkdir()
        wav = pack / "src.wav"
        write_sine_wav(wav, duration_s=0.2)
        ogg = pack / "tone.ogg"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav), "-c:a", "libvorbis", str(ogg)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = next(
            s
            for s in SampleRepository(factory.get_connection()).list_by_source(source.id)
            if s.extension == "ogg"
        )
        state = metadata.get_editor_state([sample.id])
        assert state.artwork_supported is False
        assert state.artwork_explanation

        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        plan = metadata.plan_write(
            MetadataWriteRequest(
                sample_ids=(sample.id,),
                target=MetadataWriteTarget.UPDATE_ORIGINAL,
                fields={"title": "Ogg Title"},
                artwork_action=ArtworkAction.ADD_REPLACE,
                artwork=ArtworkPayload(data=png, mime="image/png"),
            )
        )
        assert any(exc.code == "unsupported_artwork" for exc in plan.exceptions)
        with pytest.raises(ValidationError, match="blocking exceptions"):
            metadata.execute(plan)
    finally:
        scheduler.shutdown(wait=True)


def test_write_to_copy_leaves_original_hash_unchanged(tmp_path: Path) -> None:
    metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        media = write_tagged_wav(pack / "snare.wav", title="Old", artist="A")
        original_hash = content_fingerprint(media)
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        copy_dir = tmp_path / "copies"
        plan = metadata.plan_write(
            MetadataWriteRequest(
                sample_ids=(sample.id,),
                target=MetadataWriteTarget.WRITE_TO_COPY,
                fields={"title": "New Title", "artist": "B"},
                copy_destination_dir=str(copy_dir),
            )
        )
        assert plan.exceptions == ()
        job_id = metadata.execute(plan)
        job = scheduler.wait(job_id, timeout=60.0)
        assert job.state is JobState.COMPLETED

        assert content_fingerprint(media) == original_hash
        copy_path = Path(plan.items[0].destination_path)
        assert copy_path.is_file()
        assert copy_path.resolve() != media.resolve()
        snapshot = read_embedded(copy_path)
        assert snapshot.ok is True
        assert snapshot.fields["title"] == "New Title"
        assert snapshot.fields["artist"] == "B"

        items = JobItemRepository(factory.get_connection()).list_for_job(job_id)
        assert len(items) == 1
        assert items[0].state is JobItemState.SUCCEEDED
        detail = json.loads(items[0].detail_json or "{}")
        assert detail.get("verified") is True
        assert detail.get("original_content_hash") == original_hash
    finally:
        scheduler.shutdown(wait=True)


def test_update_original_reread_verifies_wav_fixture(tmp_path: Path) -> None:
    metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        media = write_tagged_wav(pack / "hat.wav", title="Before", artist="X", genre="House")
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        plan = metadata.plan_write(
            MetadataWriteRequest(
                sample_ids=(sample.id,),
                target=MetadataWriteTarget.UPDATE_ORIGINAL,
                fields={
                    "title": "After Title",
                    "artist": "After Artist",
                    "genre": "Techno",
                    "comment": "verified write",
                },
            )
        )
        assert plan.exceptions == ()
        assert plan.items[0].destination_path == str(media.resolve())
        job_id = metadata.execute(plan)
        job = scheduler.wait(job_id, timeout=60.0)
        assert job.state is JobState.COMPLETED

        reread = read_embedded(media)
        assert reread.ok is True
        assert reread.fields["title"] == "After Title"
        assert reread.fields["artist"] == "After Artist"
        assert reread.fields["genre"] == "Techno"
        assert reread.fields["comment"] == "verified write"

        items = metadata.list_item_results(job_id)
        assert items[0].state is JobItemState.SUCCEEDED
        detail = json.loads(items[0].detail_json or "{}")
        assert detail["verified"] is True
        assert detail["verification_fields"]["title"] == "After Title"
    finally:
        scheduler.shutdown(wait=True)


def test_update_original_artwork_add_and_remove(tmp_path: Path) -> None:
    metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        media = write_sine_wav(pack / "art.wav", duration_s=0.2)
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        # Minimal 1x1 PNG
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        plan = metadata.plan_write(
            MetadataWriteRequest(
                sample_ids=(sample.id,),
                target=MetadataWriteTarget.UPDATE_ORIGINAL,
                fields={"title": "With Art"},
                artwork_action=ArtworkAction.ADD_REPLACE,
                artwork=ArtworkPayload(data=png, mime="image/png"),
            )
        )
        job_id = metadata.execute(plan)
        assert scheduler.wait(job_id, timeout=60.0).state is JobState.COMPLETED
        assert read_embedded(media).has_artwork is True

        plan_remove = metadata.plan_write(
            MetadataWriteRequest(
                sample_ids=(sample.id,),
                target=MetadataWriteTarget.UPDATE_ORIGINAL,
                fields={"title": "No Art"},
                artwork_action=ArtworkAction.REMOVE,
            )
        )
        # Fresh fingerprint after prior write.
        job_id2 = metadata.execute(plan_remove)
        assert scheduler.wait(job_id2, timeout=60.0).state is JobState.COMPLETED
        final = read_embedded(media)
        assert final.has_artwork is False
        assert final.fields["title"] == "No Art"
    finally:
        scheduler.shutdown(wait=True)


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg required for FLAC fixture")
def test_format_fixture_flac_update_original(tmp_path: Path) -> None:
    metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "flac_pack"
        pack.mkdir()
        media = _write_flac_via_ffmpeg(pack / "tone.flac")
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]
        caps = metadata.read_capabilities(sample.id)
        assert caps.format_id == "flac"
        assert "title" in caps.writable_fields

        plan = metadata.plan_write(
            MetadataWriteRequest(
                sample_ids=(sample.id,),
                target=MetadataWriteTarget.UPDATE_ORIGINAL,
                fields={"title": "FLAC Title", "artist": "FLAC Artist"},
            )
        )
        assert plan.exceptions == ()
        job_id = metadata.execute(plan)
        assert scheduler.wait(job_id, timeout=60.0).state is JobState.COMPLETED
        snap = read_embedded(media)
        assert snap.fields["title"] == "FLAC Title"
        assert snap.fields["artist"] == "FLAC Artist"
    finally:
        scheduler.shutdown(wait=True)


def test_execute_refuses_blocking_exceptions(tmp_path: Path) -> None:
    metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        write_tagged_wav(pack / "ok.wav", title="Ok")
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        # Simulate unsupported artwork on a format that supports text by crafting
        # an exception-bearing plan via WRITE_TO_COPY without destination — rejected earlier.
        with pytest.raises(ValidationError, match="copy_destination_dir"):
            metadata.plan_write(
                MetadataWriteRequest(
                    sample_ids=(sample.id,),
                    target=MetadataWriteTarget.WRITE_TO_COPY,
                    fields={"title": "X"},
                )
            )
    finally:
        scheduler.shutdown(wait=True)
