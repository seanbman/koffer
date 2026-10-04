"""Integration: deterministic analysis, accept/reject, reanalysis safety."""

from __future__ import annotations

from pathlib import Path

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import (
    ClassificationSource,
    JobState,
    SuggestionStatus,
)
from koffer.domain.ids import EntityId
from koffer.repositories.classifications import ClassificationRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.suggestions import SuggestionRepository
from koffer.services.analysis import SuggestionAction, SuggestionActionKind


def _scan_fixture(context: AppContext, pack: Path) -> EntityId:
    source = context.source_service.add_source(pack)
    job_id = context.source_service.scan(source.id)
    assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
    samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
        source.id
    )
    assert samples
    return samples[0].id


def test_deterministic_analysis_creates_pending_suggestions_with_evidence(
    tmp_path: Path,
) -> None:
    context = AppContext.open_temp(tmp_path / "analysis")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "punchy_kick_oneshot.wav", duration_s=0.2)
    try:
        sample_id = _scan_fixture(context, pack)
        # Content fingerprint for short sine; analysis should still propose path heuristics.
        run_id = context.analysis_service.analyze_sample(sample_id)
        assert run_id

        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        assert pending
        by_dim = {s.dimension: s for s in pending}
        assert by_dim["instrument_source"].proposed_value == "Kick"
        assert 0.0 < by_dim["instrument_source"].confidence <= 1.0
        assert "filename" in by_dim["instrument_source"].evidence_json
        assert by_dim["sample_type"].proposed_value == "One-shot"

        state = context.analysis_service.get_analysis_state(sample_id)
        assert state.pending_suggestion_count >= 2
    finally:
        context.close()


def test_accept_creates_confirmed_classification_without_embedded_write(
    tmp_path: Path,
) -> None:
    context = AppContext.open_temp(tmp_path / "accept")
    pack = tmp_path / "pack"
    pack.mkdir()
    media = write_sine_wav(pack / "snr_oneshot.wav", duration_s=0.15)
    before = media.read_bytes()
    try:
        sample_id = _scan_fixture(context, pack)
        context.analysis_service.analyze_sample(sample_id)
        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        snare = next(s for s in pending if s.dimension == "instrument_source")
        context.analysis_service.accept_suggestion(snare.id)

        classifications = ClassificationRepository(
            context.connection_factory.get_connection()
        ).list_for_sample(sample_id)
        assert any(
            c.dimension.value == "instrument_source"
            and c.value == "Snare"
            and c.source is ClassificationSource.ACCEPTED_SUGGESTION
            for c in classifications
        )
        accepted = SuggestionRepository(context.connection_factory.get_connection()).get(snare.id)
        assert accepted is not None
        assert accepted.status is SuggestionStatus.ACCEPTED
        assert accepted.reviewed_at is not None
        # Embedded bytes untouched.
        assert media.read_bytes() == before
    finally:
        context.close()


def test_reanalysis_does_not_overwrite_confirmed_classifications(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "reanalysis")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "kick_loop.wav", duration_s=0.25)
    try:
        sample_id = _scan_fixture(context, pack)
        context.analysis_service.analyze_sample(sample_id)
        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        kick = next(s for s in pending if s.dimension == "instrument_source")
        context.analysis_service.accept_suggestion(kick.id, edited_value="Kick")

        classifications_before = ClassificationRepository(
            context.connection_factory.get_connection()
        ).list_for_sample(sample_id)
        assert len(classifications_before) == 1
        confirmed_id = classifications_before[0].id
        confirmed_value = classifications_before[0].value

        # Re-run analysis; confirmed row must remain intact; no duplicate Kick pending.
        context.analysis_service.analyze_sample(sample_id)
        classifications_after = ClassificationRepository(
            context.connection_factory.get_connection()
        ).list_for_sample(sample_id)
        assert len(classifications_after) == 1
        assert classifications_after[0].id == confirmed_id
        assert classifications_after[0].value == confirmed_value
        assert classifications_after[0].source is ClassificationSource.ACCEPTED_SUGGESTION

        pending_after = SuggestionRepository(
            context.connection_factory.get_connection()
        ).list_for_sample(sample_id, status=SuggestionStatus.PENDING)
        assert not any(
            s.dimension == "instrument_source" and s.proposed_value == "Kick" for s in pending_after
        )
    finally:
        context.close()


def test_reject_retains_provenance_and_batch_review(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "batch")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "vox_loop_120bpm.wav", duration_s=0.3)
    try:
        sample_id = _scan_fixture(context, pack)
        context.analysis_service.analyze_sample(sample_id)
        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        assert len(pending) >= 2
        first, second = pending[0], pending[1]
        context.analysis_service.batch_review(
            [
                SuggestionAction(first.id, SuggestionActionKind.REJECT),
                SuggestionAction(second.id, SuggestionActionKind.ACCEPT),
            ]
        )
        rejected = SuggestionRepository(context.connection_factory.get_connection()).get(first.id)
        assert rejected is not None
        assert rejected.status is SuggestionStatus.REJECTED
        assert rejected.reviewed_at is not None
        # Rejection does not erase the row.
        assert SuggestionRepository(context.connection_factory.get_connection()).get(first.id)
    finally:
        context.close()


def test_queue_deterministic_analysis_job(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "job")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "clap_oneshot.wav", duration_s=0.2)
    try:
        sample_id = _scan_fixture(context, pack)
        job_id = context.analysis_service.queue_for_sample(sample_id)
        finished = context.scheduler.wait(job_id, timeout=60.0)
        assert finished.state in {JobState.COMPLETED, JobState.COMPLETED_WITH_ERRORS}
        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            sample_id, status=SuggestionStatus.PENDING
        )
        assert any(s.proposed_value == "Clap" for s in pending)
    finally:
        context.close()
