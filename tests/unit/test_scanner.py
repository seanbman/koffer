"""Unit tests for supported extensions and exclusion matching."""

from __future__ import annotations

from pathlib import Path

from koffer.domain import ExclusionPatternType, ExclusionRule, new_entity_id
from koffer.filesystem import (
    SUPPORTED_AUDIO_EXTENSIONS,
    enumerate_audio_files,
    is_supported_audio_extension,
    matches_exclusion,
)


def test_supported_extensions_match_docs() -> None:
    expected = {
        "wav",
        "aiff",
        "aif",
        "flac",
        "mp3",
        "ogg",
        "m4a",
    }
    assert expected == SUPPORTED_AUDIO_EXTENSIONS
    assert is_supported_audio_extension("Kick.WAV")
    assert is_supported_audio_extension("loop.aif")
    assert not is_supported_audio_extension("notes.txt")


def test_hidden_policy_and_glob_exclusions() -> None:
    source_id = new_entity_id()
    rules = [
        ExclusionRule(
            id=new_entity_id(),
            source_id=source_id,
            pattern="hidden",
            pattern_type=ExclusionPatternType.HIDDEN_POLICY,
        ),
        ExclusionRule(
            id=new_entity_id(),
            source_id=source_id,
            pattern="skip/**",
            pattern_type=ExclusionPatternType.GLOB,
        ),
    ]
    assert matches_exclusion(".hidden/kick.wav", rules)
    assert matches_exclusion("skip/nested/kick.wav", rules)
    assert not matches_exclusion("drums/kick.wav", rules)


def test_enumerate_filters_unsupported_and_exclusions(tmp_path: Path) -> None:
    (tmp_path / "drums").mkdir()
    (tmp_path / "drums" / "kick.wav").write_bytes(b"RIFF")
    (tmp_path / "drums" / "readme.txt").write_text("nope", encoding="utf-8")
    (tmp_path / ".secret").mkdir()
    (tmp_path / ".secret" / "hidden.wav").write_bytes(b"RIFF")
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "hat.mp3").write_bytes(b"ID3")

    source_id = new_entity_id()
    rules = [
        ExclusionRule(
            id=new_entity_id(),
            source_id=source_id,
            pattern="hidden",
            pattern_type=ExclusionPatternType.HIDDEN_POLICY,
        ),
        ExclusionRule(
            id=new_entity_id(),
            source_id=source_id,
            pattern="skip/**",
            pattern_type=ExclusionPatternType.GLOB,
        ),
    ]
    found = enumerate_audio_files(tmp_path, recursive=True, rules=rules)
    assert [item.relative_path for item in found] == ["drums/kick.wav"]
