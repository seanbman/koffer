"""FULL analysis: semantic Suggestions + embeddings without overwriting confirmed."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from koffer.analysis.embeddings import EmbeddingStore
from koffer.analysis.manifest import load_model_manifest, sha256_file
from koffer.analysis.panns import PannsSemanticProvider
from koffer.analysis.semantic import SemanticInferenceResult, SemanticLabel
from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import AnalysisDepth, JobState, SuggestionStatus
from koffer.domain.ids import EntityId
from koffer.repositories.classifications import ClassificationRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.suggestions import SuggestionRepository
from koffer.services.analysis import FULL_PIPELINE_VERSION, AnalysisService


def _scan_fixture(context: AppContext, pack: Path) -> EntityId:
    source = context.source_service.add_source(pack)
    job_id = context.source_service.scan(source.id)
    assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
    samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
        source.id
    )
    assert samples
    return samples[0].id


def _provider_with_runner(tmp_path: Path, cache_dir: Path) -> PannsSemanticProvider:
    artifact = tmp_path / "Cnn14_fixture.pth"
    artifact.write_bytes(b"semantic-full-fixture")
    digest = sha256_file(artifact)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "panns",
                "model": "Cnn14",
                "sample_rate_hz": 32000,
                "artifact": artifact.name,
                "version": "fixture-full",
                "source_url": "https://example.invalid/model.pth",
                "sha256": digest,
                "size_bytes": artifact.stat().st_size,
                "embedding_dim": 2048,
                "license_note": "test",
            }
        ),
        encoding="utf-8",
    )
    manifest = load_model_manifest(manifest_path)

    def runner(
        waveform: np.ndarray,
        class_labels: tuple[str, ...],
        top_k: int,
    ) -> tuple[list[tuple[str, float]], np.ndarray]:
        emb = np.zeros(2048, dtype=np.float32)
        emb[7] = 1.0
        return [("Bass drum", 0.94), ("Synthesizer", 0.33)], emb

    return PannsSemanticProvider(
        cache_dir,
        manifest=manifest,
        artifact_path=artifact,
        inference_runner=runner,
    )


def test_full_analysis_persists_suggestions_evidence_and_embedding(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "full")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "tone.wav", duration_s=0.2)
    try:
        sample_id = _scan_fixture(context, pack)
        provider = _provider_with_runner(tmp_path, context.paths.cache_dir)
        store = EmbeddingStore(context.paths.cache_dir)
        service = AnalysisService(
            context.connection_factory,
            scheduler=context.scheduler,
            semantic_provider=provider,
            embedding_store=store,
            cache_dir=context.paths.cache_dir,
        )
        before = Path(context.paths.cache_dir).parent / "pack" / "tone.wav"
        # Resolve actual media path bytes for immutability check.
        media = context.resolve_sample_media_path(sample_id)
        assert media is not None
        media_before = media.read_bytes()

        run_id = service.analyze_sample(sample_id, depth=AnalysisDepth.FULL)
        assert run_id

        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        semantic = [
            s
            for s in pending
            if s.provider == "panns"
            and s.dimension == "instrument_source"
            and s.proposed_value == "Kick"
        ]
        assert semantic
        evidence = json.loads(semantic[0].evidence_json)
        assert evidence["semantic"]["provider"] == "panns"
        assert evidence["semantic"]["model_version"] == "fixture-full"
        assert "source_fingerprint" in evidence["semantic"]
        assert "plain_language" in evidence

        record = store.get(sample_id, "fixture-full")
        assert record is not None
        assert record.vector.shape == (2048,)
        assert record.source_fingerprint

        assert media.read_bytes() == media_before
        _ = before  # silence lint if unused in some layouts
    finally:
        context.close()


def test_full_reanalysis_preserves_confirmed_and_reuses_embedding(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "reuse")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "kick_oneshot.wav", duration_s=0.2)
    try:
        sample_id = _scan_fixture(context, pack)
        provider = _provider_with_runner(tmp_path, context.paths.cache_dir)
        store = EmbeddingStore(context.paths.cache_dir)
        service = AnalysisService(
            context.connection_factory,
            semantic_provider=provider,
            embedding_store=store,
            cache_dir=context.paths.cache_dir,
        )
        service.analyze_sample(sample_id, depth=AnalysisDepth.FULL)
        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        kick = next(s for s in pending if s.proposed_value == "Kick")
        service.accept_suggestion(kick.id)

        confirmed_before = ClassificationRepository(
            context.connection_factory.get_connection()
        ).list_for_sample(sample_id)
        assert len(confirmed_before) >= 1
        confirmed_id = confirmed_before[0].id
        embedding_before = store.get(sample_id, "fixture-full")
        assert embedding_before is not None

        # Re-run FULL; confirmed classification stays; embedding reused (same fingerprint).
        infer_calls = {"n": 0}
        original_infer = provider.infer

        def counted_infer(path: Path) -> SemanticInferenceResult:
            infer_calls["n"] += 1
            return original_infer(path)

        provider.infer = counted_infer  # type: ignore[method-assign]
        service.analyze_sample(sample_id, depth=AnalysisDepth.FULL)
        assert infer_calls["n"] == 0

        confirmed_after = ClassificationRepository(
            context.connection_factory.get_connection()
        ).list_for_sample(sample_id)
        assert any(c.id == confirmed_id for c in confirmed_after)
        embedding_after = store.get(sample_id, "fixture-full")
        assert embedding_after is not None
        assert np.allclose(embedding_before.vector, embedding_after.vector)
    finally:
        context.close()


def test_full_unavailable_provider_keeps_deterministic_usable(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "degraded")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "snare_oneshot.wav", duration_s=0.15)
    try:
        sample_id = _scan_fixture(context, pack)
        # Default context provider has no weights — FULL still completes deterministic path.
        run_id = context.analysis_service.analyze_sample(sample_id, depth=AnalysisDepth.FULL)
        assert run_id
        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        assert any(s.proposed_value == "Snare" for s in pending)
        state = context.analysis_service.get_analysis_state(sample_id)
        assert state.pipeline_version == FULL_PIPELINE_VERSION
    finally:
        context.close()


def test_one_failed_sample_does_not_abort_batch(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "batch")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "ok_oneshot.wav", duration_s=0.1)
    write_sine_wav(pack / "also_ok_loop.wav", duration_s=0.1)
    try:
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        assert len(samples) >= 2

        provider = _provider_with_runner(tmp_path, context.paths.cache_dir)
        store = EmbeddingStore(context.paths.cache_dir)
        service = AnalysisService(
            context.connection_factory,
            semantic_provider=provider,
            embedding_store=store,
            cache_dir=context.paths.cache_dir,
        )

        # Force failure on first sample by temporarily breaking infer, then restore.
        fail_ids = {samples[0].id}
        original = provider.infer

        def flaky(path: Path) -> SemanticInferenceResult:
            # Deterministic path still succeeds; semantic failure is non-fatal per sample.
            sample = next(s for s in samples if (Path(source.root_path) / s.relative_path) == path)
            if sample.id in fail_ids:
                raise RuntimeError("forced semantic failure")
            return original(path)

        # Attach source root for path compare via resolve
        source_row = context.source_service  # keep reference
        _ = source_row

        def flaky_infer(path: Path) -> SemanticInferenceResult:
            rel = path.name
            if rel.startswith("ok_"):
                raise RuntimeError("forced semantic failure")
            return SemanticInferenceResult(
                labels=(SemanticLabel("Synthesizer", 0.7),),
                embedding=np.ones(2048, dtype=np.float32) / np.sqrt(2048.0),
                model_version="fixture-full",
                provider="panns",
            )

        provider.infer = flaky_infer  # type: ignore[method-assign]
        # Both samples must complete analysis_run even if semantic fails on one.
        for sample in samples:
            run_id = service.analyze_sample(sample.id, depth=AnalysisDepth.FULL)
            assert run_id
    finally:
        context.close()
