"""Offscreen PlaybackService load/control tests (Qt Multimedia adapter)."""

from __future__ import annotations

from pathlib import Path

import pytest

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.errors import PathUnavailableError, ValidationError
from koffer.domain.ids import new_entity_id
from koffer.services.playback import PlaybackService, PlaybackState, gain_db_to_linear


def test_playback_service_loads_fixture_without_crash(qtbot: object, tmp_path: Path) -> None:
    del qtbot  # Ensures QApplication exists under QT_QPA_PLATFORM=offscreen.
    wav = write_sine_wav(tmp_path / "play.wav", duration_s=0.25)
    before = wav.read_bytes()
    service = PlaybackService()

    sample_id = new_entity_id()
    service.load(sample_id, wav)

    assert service.sample_id == sample_id
    assert service.path == wav.resolve()
    assert service.state == PlaybackState.STOPPED
    assert wav.read_bytes() == before

    service.set_gain_db(-6.0)
    assert service.gain_db == -6.0
    service.set_loop(10, 100)
    assert service.loop_region == (10, 100)
    service.seek(0)
    service.play()
    service.pause()
    service.stop()
    assert wav.read_bytes() == before


def test_playback_service_rejects_missing_path(qtbot: object, tmp_path: Path) -> None:
    del qtbot
    service = PlaybackService()
    with pytest.raises(PathUnavailableError):
        service.load(new_entity_id(), tmp_path / "missing.wav")


def test_playback_service_requires_media_before_play(qtbot: object) -> None:
    del qtbot
    service = PlaybackService()
    with pytest.raises(ValidationError):
        service.play()


def test_app_context_wires_playback_and_waveform(qtbot: object, tmp_path: Path) -> None:
    del qtbot
    context = AppContext.open_temp(tmp_path / "ctx")
    try:
        wav = write_sine_wav(tmp_path / "ctx-tone.wav", duration_s=0.1)
        before = wav.read_bytes()
        sample_id = new_entity_id()
        context.playback_service.load(sample_id, wav)
        envelope = context.waveform_cache.get_or_build(sample_id, wav)
        assert envelope.bucket_count >= 1
        assert wav.read_bytes() == before
        assert context.waveform_cache.cache_path(sample_id).is_file()
    finally:
        context.close()


def test_gain_db_to_linear_unity_and_mute() -> None:
    assert gain_db_to_linear(0.0) == pytest.approx(1.0)
    assert gain_db_to_linear(-120.0) == pytest.approx(0.0, abs=1e-5)
    assert gain_db_to_linear(12.0) == 1.0
