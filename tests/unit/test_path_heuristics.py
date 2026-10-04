"""Unit tests for filename/path heuristic Suggestions."""

from __future__ import annotations

from koffer.analysis.heuristics import propose_from_path


def test_kick_oneshot_path_produces_instrument_and_type() -> None:
    proposals = propose_from_path(
        relative_path="Drums/Kicks/punchy_kick_oneshot.wav",
        filename="punchy_kick_oneshot.wav",
    )
    by_dim = {p.dimension: p for p in proposals}
    assert by_dim["instrument_source"].proposed_value == "Kick"
    assert by_dim["instrument_source"].confidence >= 0.9
    assert "evidence" in by_dim["instrument_source"].evidence_json or "filename" in (
        by_dim["instrument_source"].evidence_json
    )
    assert by_dim["sample_type"].proposed_value == "One-shot"


def test_folder_context_infers_when_filename_generic() -> None:
    proposals = propose_from_path(
        relative_path="Soul/Rhodes/Chords/90 BPM/07.wav",
        filename="07.wav",
    )
    by_dim = {p.dimension: p for p in proposals}
    assert by_dim["instrument_source"].proposed_value == "Rhodes"
    assert by_dim["musical_role"].proposed_value == "Harmonic"
    assert by_dim["bpm"].proposed_value == "90"
    assert by_dim["genre_style"].proposed_value == "Soul"


def test_key_and_loop_tokens() -> None:
    proposals = propose_from_path(
        relative_path="Loops/pad_Cm_120bpm_loop.wav",
        filename="pad_Cm_120bpm_loop.wav",
    )
    by_dim = {p.dimension: p for p in proposals}
    assert by_dim["sample_type"].proposed_value == "Loop"
    assert by_dim["bpm"].proposed_value == "120"
    assert by_dim["key"].proposed_value == "Cmin"
