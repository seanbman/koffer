"""Unit tests for Mutagen metadata reader and capability reporting."""

from __future__ import annotations

from pathlib import Path

from koffer.audio.metadata import (
    capabilities_for_extension,
    capabilities_for_path,
    read_embedded,
)
from koffer.audio.wav_fixtures import write_malformed_wav, write_tagged_wav


def test_capabilities_report_wav_readable_fields() -> None:
    caps = capabilities_for_extension("wav")
    assert caps.supported is True
    assert caps.format_id == "wav"
    assert "title" in caps.readable_fields
    assert "artwork" in caps.readable_fields
    assert caps.artwork_support is True


def test_capabilities_unsupported_extension() -> None:
    caps = capabilities_for_extension("xyz")
    assert caps.supported is False
    assert caps.readable_fields == ()
    assert caps.limitations


def test_read_embedded_supported_tagged_wav(tmp_path: Path) -> None:
    media = write_tagged_wav(
        tmp_path / "kick.wav",
        title="Dry Kick",
        artist="Pack Author",
        album="Drum Hits",
        genre="Hip-hop",
    )
    caps = capabilities_for_path(media)
    assert caps.supported is True

    snapshot = read_embedded(media)
    assert snapshot.ok is True
    assert snapshot.error_code is None
    assert snapshot.fields["title"] == "Dry Kick"
    assert snapshot.fields["artist"] == "Pack Author"
    assert snapshot.fields["album"] == "Drum Hits"
    assert snapshot.fields["genre"] == "Hip-hop"


def test_read_embedded_malformed_does_not_raise(tmp_path: Path) -> None:
    media = write_malformed_wav(tmp_path / "broken.wav")
    snapshot = read_embedded(media)
    assert snapshot.ok is False
    assert snapshot.error_code in {"malformed_metadata", "io_error"}
    assert snapshot.error_message


def test_read_embedded_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "absent.wav"
    snapshot = read_embedded(missing)
    assert snapshot.ok is False
    assert snapshot.error_code == "path_unavailable"
