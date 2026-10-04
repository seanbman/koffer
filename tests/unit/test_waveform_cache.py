"""Unit tests for peak-envelope waveform cache and fingerprint keys."""

from __future__ import annotations

from pathlib import Path

from koffer.audio.wav_fixtures import write_sine_wav
from koffer.audio.waveform import (
    WAVEFORM_PIPELINE_VERSION,
    WaveformCache,
    build_peak_envelope,
    deserialize_envelope,
    serialize_envelope,
)
from koffer.domain.ids import new_entity_id
from koffer.filesystem.hashing import content_fingerprint


def test_build_peak_envelope_from_sine_fixture(tmp_path: Path) -> None:
    wav = write_sine_wav(tmp_path / "tone.wav", duration_s=0.2, frequency_hz=440.0)
    before = wav.read_bytes()
    envelope = build_peak_envelope(wav, bucket_count=64)
    after = wav.read_bytes()

    assert after == before
    assert envelope.bucket_count == 64
    assert envelope.pipeline_version == WAVEFORM_PIPELINE_VERSION
    assert envelope.fingerprint == content_fingerprint(wav)
    assert len(envelope.mins) == 64
    assert len(envelope.maxs) == 64
    assert any(value > 0.0 for value in envelope.maxs)
    assert any(value < 0.0 for value in envelope.mins)


def test_waveform_cache_reuses_envelope_for_unchanged_fingerprint(tmp_path: Path) -> None:
    wav = write_sine_wav(tmp_path / "cached.wav", duration_s=0.15)
    sample_id = new_entity_id()
    cache = WaveformCache(tmp_path / "cache", bucket_count=128)
    before = wav.read_bytes()

    first = cache.get_or_build(sample_id, wav)
    cache_path = cache.cache_path(sample_id)
    assert cache_path.is_file()
    mtime_ns = cache_path.stat().st_mtime_ns
    blob = cache_path.read_bytes()

    second = cache.get_or_build(sample_id, wav)
    assert second.fingerprint == first.fingerprint
    assert second.mins == first.mins
    assert second.maxs == first.maxs
    assert cache_path.read_bytes() == blob
    assert cache_path.stat().st_mtime_ns == mtime_ns
    assert wav.read_bytes() == before

    # Versioned key path includes pipeline version.
    assert WAVEFORM_PIPELINE_VERSION in cache_path.parts


def test_waveform_cache_rebuilds_when_fingerprint_changes(tmp_path: Path) -> None:
    wav = write_sine_wav(tmp_path / "mutate.wav", duration_s=0.1, frequency_hz=220.0)
    sample_id = new_entity_id()
    cache = WaveformCache(tmp_path / "cache", bucket_count=32)
    first = cache.get_or_build(sample_id, wav)
    first_fp = first.fingerprint

    write_sine_wav(wav, duration_s=0.1, frequency_hz=880.0, amplitude=0.4)
    second = cache.get_or_build(sample_id, wav)
    assert second.fingerprint != first_fp
    assert second.fingerprint == content_fingerprint(wav)


def test_serialize_roundtrip(tmp_path: Path) -> None:
    wav = write_sine_wav(tmp_path / "round.wav", duration_s=0.05)
    envelope = build_peak_envelope(wav, bucket_count=16)
    restored = deserialize_envelope(serialize_envelope(envelope))
    assert restored == envelope
