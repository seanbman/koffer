"""SimilarityService foundations with FakeSemanticProvider (no weight download)."""

from __future__ import annotations

from pathlib import Path

import pytest

from koffer.analysis.semantic import FakeSemanticProvider
from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import JobState, SampleAvailability
from koffer.domain.errors import ModelUnavailableError
from koffer.domain.query import PageRequest, SampleFilters, SampleQuery
from koffer.repositories.samples import SampleRepository
from koffer.services.similarity import SimilarityService, SimilarityStatusKind


def test_library_remains_usable_when_model_absent(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "absent")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "kick.wav", duration_s=0.15)
    try:
        source = context.source_service.add_source(pack)
        job = context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0)
        assert job.state is JobState.COMPLETED
        page = context.search_service.search(SampleQuery(), PageRequest())
        assert page.total >= 1
        collections = context.collection_service.list()
        assert isinstance(collections, list)
        status = context.similarity_service.status()
        assert status.kind is SimilarityStatusKind.MODEL_UNAVAILABLE
        sample_id = page.items[0].id
        with pytest.raises(ModelUnavailableError):
            context.similarity_service.find_similar(sample_id, limit=5)
    finally:
        context.close()


def test_similarity_service_builds_and_queries_fixture_embeddings(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "sim")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "kick_a.wav", duration_s=0.12)
    write_sine_wav(pack / "kick_b.wav", duration_s=0.12)
    write_sine_wav(pack / "pad_c.wav", duration_s=0.12)
    try:
        source = context.source_service.add_source(pack)
        assert (
            context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0).state
            is JobState.COMPLETED
        )
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        assert len(samples) == 3

        service = SimilarityService(
            context.connection_factory,
            context.paths.cache_dir,
            provider=FakeSemanticProvider(embedding_dim=32),
            scheduler=context.scheduler,
            media_resolver=context.resolve_sample_media_path,
        )
        for sample in samples:
            assert service.ensure_embedding(sample.id) is None
            cached = service.embedding_store.get(sample.id, service.provider.model_version)
            assert cached is not None

        size = service.rebuild_index_sync()
        assert size == 3
        seed = next(item for item in samples if "kick_a" in item.filename)
        results = service.find_similar(seed.id, limit=2)
        assert len(results) == 2
        assert all(row.sample_id != seed.id for row in results)
        assert results[0].score >= results[1].score
        # Metadata filter narrows without replacing similarity ranking.
        filtered = service.find_similar(
            seed.id,
            limit=5,
            filters=SampleQuery(filters=SampleFilters(extensions=("wav",))),
        )
        assert filtered
        assert all(row.availability is SampleAvailability.ONLINE for row in filtered)
    finally:
        context.close()
