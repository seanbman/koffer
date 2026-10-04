"""Unit tests for Mutagen metadata writer and capability matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from koffer.audio.metadata import (
    capabilities_for_extension,
    read_embedded,
    write_embedded,
)
from koffer.audio.wav_fixtures import write_sine_wav, write_tagged_wav
from koffer.domain.errors import ValidationError
from koffer.domain.metadata_write import ArtworkPayload


def test_capability_matrix_covers_required_formats() -> None:
    expected = {
        "wav": True,
        "aiff": True,
        "flac": True,
        "mp3": True,
        "ogg": True,
        "m4a": True,
        "xyz": False,
    }
    for ext, supported in expected.items():
        caps = capabilities_for_extension(ext)
        assert caps.supported is supported
        if supported:
            assert "title" in caps.writable_fields
    ogg = capabilities_for_extension("ogg")
    assert ogg.artwork_support is False
    assert "artwork" not in ogg.writable_fields


def test_write_embedded_wav_roundtrip_and_verify(tmp_path: Path) -> None:
    media = write_sine_wav(tmp_path / "tone.wav", duration_s=0.2)
    result = write_embedded(
        media,
        {
            "title": "Round Trip",
            "artist": "Writer",
            "album": "Tests",
            "genre": "Electronic",
            "comment": "hello",
        },
    )
    assert result.verified is True
    assert result.written_fields["title"] == "Round Trip"
    snap = read_embedded(media)
    assert snap.fields["title"] == "Round Trip"
    assert snap.fields["artist"] == "Writer"
    assert snap.fields["comment"] == "hello"


def test_write_embedded_refuses_unsupported_field(tmp_path: Path) -> None:
    media = write_tagged_wav(tmp_path / "x.wav")
    with pytest.raises(ValidationError, match="unknown metadata fields"):
        write_embedded(media, {"bpm": "120"})


def test_write_embedded_artwork_add_replace_remove(tmp_path: Path) -> None:
    media = write_sine_wav(tmp_path / "art.wav", duration_s=0.2)
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    write_embedded(
        media,
        {"title": "Covered"},
        artwork=ArtworkPayload(data=png, mime="image/png"),
    )
    assert read_embedded(media).has_artwork is True
    write_embedded(media, {"title": "Bare"}, remove_artwork=True)
    assert read_embedded(media).has_artwork is False
