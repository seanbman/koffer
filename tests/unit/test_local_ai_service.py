"""Local AI status, enable persistence, backfill scope, and discovery depth."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from koffer.analysis.embeddings import EmbeddingStore
from koffer.analysis.manifest import load_model_manifest, sha256_file
from koffer.analysis.model_install import ModelInstallCancelled, install_model_artifact
from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import AnalysisDepth, JobType, SampleAvailability, SourceStatus
from koffer.domain.errors import ValidationError
from koffer.domain.ids import new_entity_id
from koffer.domain.models import Sample, Source
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.services.local_ai import (
    LocalAiStatusKind,
    discovery_analysis_depth,
    workload_for_count,
)


def _seed_source_with_samples(
    context: AppContext,
    root: Path,
    *,
    count: int = 2,
) -> list[str]:
    root.mkdir(parents=True, exist_ok=True)
    now = utc_now_iso()
    source = Source(
        id=new_entity_id(),
        display_name="Local AI Source",
        root_path=str(root.resolve()),
        enabled=True,
        recursive=True,
        status=SourceStatus.ONLINE,
        created_at=now,
        updated_at=now,
    )
    conn = context.connection_factory.get_connection()
    SourceRepository(conn).create(source)
    sample_ids: list[str] = []
    for index in range(count):
        name = f"tone_{index}.wav"
        write_sine_wav(root / name, duration_s=0.05)
        sample = Sample(
            id=new_entity_id(),
            source_id=source.id,
            relative_path=name,
            normalized_path_cache=name.lower(),
            filename=name,
            extension="wav",
            size_bytes=(root / name).stat().st_size,
            mtime_ns=(root / name).stat().st_mtime_ns,
            availability=SampleAvailability.ONLINE,
            favorite=False,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        SampleRepository(conn).create(sample)
        sample_ids.append(str(sample.id))
    return sample_ids


def test_discovery_depth_requires_enabled_and_available_provider() -> None:
    assert (
        discovery_analysis_depth(
            automatic_analysis=True,
            local_model_enabled=True,
            provider_available=True,
        )
        is AnalysisDepth.FULL
    )
    assert (
        discovery_analysis_depth(
            automatic_analysis=True,
            local_model_enabled=False,
            provider_available=True,
        )
        is AnalysisDepth.DETERMINISTIC
    )
    assert (
        discovery_analysis_depth(
            automatic_analysis=True,
            local_model_enabled=True,
            provider_available=False,
        )
        is AnalysisDepth.DETERMINISTIC
    )
    assert (
        discovery_analysis_depth(
            automatic_analysis=False,
            local_model_enabled=True,
            provider_available=True,
        )
        is None
    )


def test_absent_model_status_is_recoverable_and_does_not_auto_confirm(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "local-ai-absent")
    try:
        status = context.local_ai_service.status()
        assert status.kind in {
            LocalAiStatusKind.NOT_INSTALLED,
            LocalAiStatusKind.MANIFEST_BLOCKED,
            LocalAiStatusKind.ERROR,
        }
        assert "computer" in status.privacy_note.lower()
        assert status.can_analyze_existing is False
        assert status.enabled is False
        # Packaged blank checksum must block silent install success.
        packaged = load_model_manifest()
        if not packaged.checksum_recorded:
            assert status.kind is LocalAiStatusKind.MANIFEST_BLOCKED
            assert status.install_ready is False
            with pytest.raises(ValidationError, match="checksum|not available|not recorded"):
                context.local_ai_service.install_model()
        # Suggestions are never auto-confirmed by Local AI setup.
        assert context.analysis_service.pending_count() == 0
    finally:
        context.close()


def test_enable_persists_only_when_model_is_ready(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "local-ai-enable")
    try:
        status = context.local_ai_service.status()
        if status.kind is LocalAiStatusKind.MANIFEST_BLOCKED:
            with pytest.raises(ValidationError):
                context.local_ai_service.set_enabled(True)
            assert context.settings_service.load().library_analysis.local_model_enabled is False
            return
        # When install is blocked only by absent weights, enable stays refused.
        if not status.can_enable:
            with pytest.raises(ValidationError):
                context.local_ai_service.set_enabled(True)
            assert context.settings_service.load().library_analysis.local_model_enabled is False
    finally:
        context.close()


def test_backfill_queues_only_missing_semantic_and_tolerates_empty(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "local-ai-backfill")
    try:
        _seed_source_with_samples(context, tmp_path / "audio", count=3)
        # Without a verified enabled model, backfill refuses rather than inventing work.
        with pytest.raises(ValidationError, match="installed and enabled"):
            context.local_ai_service.plan_backfill()

        # Force enabled+artifact path with a fake verified provider by installing a
        # checksum-recorded temp manifest artifact into this cache, then marking enabled.
        # Blank packaged checksum remains blocked; use an isolated installable manifest.
        from koffer.analysis.manifest import ModelManifest
        from koffer.analysis.panns import PannsSemanticProvider

        payload = b"fake-local-ai-weights-for-backfill"
        artifact = tmp_path / "model.pth"
        artifact.write_bytes(payload)
        digest_hex = sha256_file(artifact)
        manifest = ModelManifest(
            provider="panns",
            model="Cnn14",
            sample_rate_hz=32000,
            artifact="model.pth",
            version="test-backfill-v1",
            source_url="https://example.invalid/model.pth",
            sha256=digest_hex,
            size_bytes=len(payload),
            embedding_dim=8,
            license_note="test",
        )
        installed = install_model_artifact(
            context.paths.cache_dir,
            manifest=manifest,
            source=artifact,
        )
        assert installed.is_file()

        # Inject a verified provider so status can reach enabled without torch.
        provider = PannsSemanticProvider(
            context.paths.cache_dir,
            manifest=manifest,
            artifact_path=installed,
            enabled=True,
            require_torch=False,
            inference_runner=lambda _w, _labels, _k: (
                [("Bass drum", 0.9)],
                np.zeros(8, dtype=np.float32),
            ),
        )
        context.local_ai_service._provider = provider  # noqa: SLF001 — test injection
        context.settings_service.update_library_analysis(local_model_enabled=True)

        status = context.local_ai_service.status()
        assert status.kind is LocalAiStatusKind.ENABLED
        plan = context.local_ai_service.plan_backfill()
        assert plan.sample_count == 3
        assert plan.workload.value == workload_for_count(3).value
        assert plan.depth is AnalysisDepth.FULL

        # Mark one Sample as already having a current embedding → excluded from backfill.
        sample_id = plan.sample_ids[0]
        store = EmbeddingStore(context.paths.cache_dir)
        media = context.resolve_sample_media_path(sample_id)
        assert media is not None
        from koffer.filesystem.hashing import content_fingerprint
        from koffer.filesystem.operations import path_fingerprint

        fingerprint = f"{path_fingerprint(media)}:{content_fingerprint(media)}"
        store.put(
            sample_id,
            model_version=manifest.model_version,
            source_fingerprint=fingerprint,
            vector=np.zeros(8, dtype=np.float32),
        )
        plan2 = context.local_ai_service.plan_backfill()
        assert plan2.sample_count == 2
        assert sample_id not in plan2.sample_ids

        job_id = context.local_ai_service.queue_backfill(plan2)
        job = context.scheduler.get(job_id)
        assert job.type is JobType.DETERMINISTIC_ANALYSIS
        scope = json.loads(job.scope_json)
        assert scope["depth"] == AnalysisDepth.FULL.value
        assert scope["purpose"] == "semantic_backfill"
        assert scope["sample_count"] == 2
        assert len(scope["sample_ids"]) == 2
    finally:
        context.close()


def test_install_cancel_leaves_no_trusted_partial(tmp_path: Path) -> None:
    from koffer.analysis.manifest import ModelManifest

    payload = b"partial-install-bytes"
    source = tmp_path / "source.pth"
    source.write_bytes(payload)
    from koffer.analysis.manifest import sha256_file as _sha

    digest_hex = _sha(source)
    manifest = ModelManifest(
        provider="panns",
        model="Cnn14",
        sample_rate_hz=32000,
        artifact="model.pth",
        version="cancel-v1",
        source_url="https://example.invalid/model.pth",
        sha256=digest_hex,
        size_bytes=len(payload),
        embedding_dim=8,
        license_note="test",
    )
    cache = tmp_path / "cache"
    with pytest.raises(ModelInstallCancelled):
        install_model_artifact(
            cache,
            manifest=manifest,
            source=source,
            cancel_check=lambda: True,
        )
    dest = cache / "models" / "panns" / "cancel-v1" / "model.pth"
    assert not dest.exists()
    leftovers = list(cache.rglob("*.koffer-install-*")) if cache.exists() else []
    assert leftovers == []


def test_queue_discovery_analysis_respects_settings(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "local-ai-discovery")
    try:
        sample_ids = _seed_source_with_samples(context, tmp_path / "audio", count=1)
        from koffer.domain.ids import EntityId

        ids = [EntityId(item) for item in sample_ids]
        context.settings_service.update_library_analysis(automatic_analysis=False)
        assert context.local_ai_service.queue_discovery_analysis(ids) is None

        context.settings_service.update_library_analysis(
            automatic_analysis=True,
            local_model_enabled=False,
        )
        job_id = context.local_ai_service.queue_discovery_analysis(ids)
        assert job_id is not None
        scope = json.loads(context.scheduler.get(job_id).scope_json)
        assert scope["depth"] == AnalysisDepth.DETERMINISTIC.value
    finally:
        context.close()
