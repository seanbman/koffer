"""SampleService.get_detail and MetadataService read foundations."""

from __future__ import annotations

from pathlib import Path

from koffer.audio.wav_fixtures import write_malformed_wav, write_tagged_wav
from koffer.domain import (
    ClassificationDimension,
    ClassificationSource,
    JobState,
    SuggestionStatus,
    new_entity_id,
    utc_now_iso,
)
from koffer.domain.models import Classification, Suggestion, TechnicalMetadata
from koffer.jobs import JobScheduler
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories import (
    ClassificationRepository,
    SampleRepository,
    SuggestionRepository,
    TagRepository,
    TechnicalMetadataRepository,
)
from koffer.services.metadata import MetadataService
from koffer.services.samples import ProvenanceCategory, SampleService
from koffer.services.sources import SourceService


def _build(
    tmp_path: Path,
) -> tuple[SampleService, MetadataService, SourceService, JobScheduler, ConnectionFactory]:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    apply_migrations(factory.get_connection())
    scheduler = JobScheduler(factory, io_workers=2)
    sources = SourceService(factory, scheduler)
    metadata = MetadataService(factory)
    samples = SampleService(factory, metadata)
    return samples, metadata, sources, scheduler, factory


def test_metadata_service_reads_supported_fixture(tmp_path: Path) -> None:
    samples, metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        write_tagged_wav(pack / "tone.wav", title="Tone Title", artist="Tone Artist")
        source = sources.add_source(pack)
        job = scheduler.wait(sources.scan(source.id), timeout=30.0)
        assert job.state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        caps = metadata.read_capabilities(sample.id)
        assert caps.supported is True
        assert "title" in caps.readable_fields

        embedded = metadata.read_embedded(sample.id)
        assert embedded.ok is True
        assert embedded.fields["title"] == "Tone Title"
        assert embedded.fields["artist"] == "Tone Artist"
    finally:
        scheduler.shutdown(wait=True)


def test_sample_detail_exposes_distinct_provenance_categories(tmp_path: Path) -> None:
    samples, _metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "prov"
        pack.mkdir()
        write_tagged_wav(pack / "snare.wav", title="Snare", artist="Kit")
        source = sources.add_source(pack)
        job = scheduler.wait(sources.scan(source.id), timeout=30.0)
        assert job.state is JobState.COMPLETED
        conn = factory.get_connection()
        sample = SampleRepository(conn).list_by_source(source.id)[0]
        now = utc_now_iso()

        TechnicalMetadataRepository(conn).upsert(
            TechnicalMetadata(
                sample_id=sample.id,
                container_format="wav",
                codec="pcm_s16le",
                duration_ms=250,
                sample_rate_hz=44100,
                channels=1,
                probe_version="test",
                probed_at=now,
                bit_depth=16,
            )
        )
        ClassificationRepository(conn).create(
            Classification(
                id=new_entity_id(),
                sample_id=sample.id,
                dimension=ClassificationDimension.SAMPLE_TYPE,
                value="One-shot",
                source=ClassificationSource.USER,
                created_at=now,
                updated_at=now,
            )
        )
        run_id = new_entity_id()
        conn.execute(
            """
            INSERT INTO analysis_runs (
                id, sample_id, pipeline_version, source_fingerprint, state, started_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(run_id), str(sample.id), "test-v1", "fp", "completed", now),
        )
        SuggestionRepository(conn).create(
            Suggestion(
                id=new_entity_id(),
                sample_id=sample.id,
                dimension="instrument_source",
                proposed_value="Snare",
                confidence=0.82,
                status=SuggestionStatus.PENDING,
                evidence_json="{}",
                provider="test",
                provider_version="1",
                analysis_run_id=run_id,
                created_at=now,
            )
        )
        tags = TagRepository(conn)
        tag_id = tags.ensure_tag("crunchy")
        tags.attach(sample.id, tag_id)

        detail = samples.get_detail(sample.id)
        provenance = detail.provenance()
        assert set(provenance.keys()) == {
            ProvenanceCategory.TECHNICAL.value,
            ProvenanceCategory.EMBEDDED.value,
            ProvenanceCategory.CONFIRMED.value,
            ProvenanceCategory.SUGGESTED.value,
            ProvenanceCategory.TAGS.value,
        }
        assert detail.technical is not None
        assert detail.technical.sample_rate_hz == 44100
        assert detail.embedded.ok is True
        assert detail.embedded.fields["title"] == "Snare"
        assert len(detail.classifications) == 1
        assert detail.classifications[0].value == "One-shot"
        assert len(detail.suggestions) == 1
        assert detail.tags == ("crunchy",)
        assert detail.path_available is True
    finally:
        scheduler.shutdown(wait=True)


def test_sample_detail_malformed_does_not_crash(tmp_path: Path) -> None:
    samples, metadata, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "bad"
        pack.mkdir()
        write_malformed_wav(pack / "broken.wav")
        source = sources.add_source(pack)
        # Scanner may or may not index malformed as supported extension .wav.
        job = scheduler.wait(sources.scan(source.id), timeout=30.0)
        assert job.state in {JobState.COMPLETED, JobState.COMPLETED_WITH_ERRORS}
        listed = SampleRepository(factory.get_connection()).list_by_source(source.id)
        if not listed:
            # If scanner skipped malformed, seed a Sample row pointing at it.
            from koffer.domain import SampleAvailability
            from koffer.domain.models import Sample

            now = utc_now_iso()
            sample = Sample(
                id=new_entity_id(),
                relative_path="broken.wav",
                normalized_path_cache="broken.wav",
                filename="broken.wav",
                extension="wav",
                size_bytes=20,
                mtime_ns=0,
                availability=SampleAvailability.ONLINE,
                favorite=False,
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
                source_id=source.id,
            )
            SampleRepository(factory.get_connection()).create(sample)
        else:
            sample = listed[0]

        embedded = metadata.read_embedded(sample.id)
        assert embedded.ok is False
        detail = samples.get_detail(sample.id)
        assert ProvenanceCategory.EMBEDDED.value in detail.provenance()
        assert detail.embedded.ok is False
    finally:
        scheduler.shutdown(wait=True)
