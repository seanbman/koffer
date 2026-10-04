"""Unit tests for preparation recipe JSON v1 and FFmpeg filter argv safety."""

from __future__ import annotations

from pathlib import Path

import pytest

from koffer.audio.render import build_filter_graph, build_render_command, resolve_ffmpeg
from koffer.domain.errors import ValidationError
from koffer.domain.preparation import PreparationRecipe, TrimSpec


def test_default_recipe_roundtrip_json() -> None:
    recipe = PreparationRecipe.default()
    payload = recipe.to_json()
    assert payload["version"] == 1
    restored = PreparationRecipe.from_json(payload)
    assert restored == recipe


def test_recipe_validation_rejects_inverted_trim() -> None:
    with pytest.raises(ValidationError, match="trim.end_ms"):
        PreparationRecipe(trim=TrimSpec(start_ms=500, end_ms=100)).validate()


def test_filter_graph_order_includes_trim_reverse_fade() -> None:
    recipe = PreparationRecipe(
        trim=TrimSpec(start_ms=100, end_ms=900),
        reverse=True,
        fade_in_ms=10,
        fade_out_ms=20,
        gain_db=-3.0,
        time_stretch_ratio=1.25,
        transpose_semitones=-2.0,
        channels="mono",
        sample_rate_hz=48000,
    )
    graph = build_filter_graph(recipe, source_sample_rate_hz=44100)
    # Authoritative order markers: trim before reverse before stretch/pitch/fades.
    assert graph.index("atrim=") < graph.index("areverse")
    assert "atempo=" in graph
    assert "asetrate=" in graph
    assert "afade=t=in" in graph
    # Fade-out is implemented as reverse+fade-in+reverse (duration-agnostic).
    assert graph.count("areverse") >= 2
    assert "volume=-3" in graph
    assert "aformat=channel_layouts=mono" in graph
    assert "aresample=48000" in graph


def test_build_render_command_uses_argv_not_shell(tmp_path: Path) -> None:
    ffmpeg = resolve_ffmpeg()
    if ffmpeg is None:
        pytest.skip("ffmpeg not available")
    source = tmp_path / "in.wav"
    source.write_bytes(b"RIFF....")  # argv construction does not open the file
    output = tmp_path / "out.wav"
    recipe = PreparationRecipe(reverse=True, fade_in_ms=5)
    command = build_render_command(source, output, recipe, ffmpeg_bin=ffmpeg)
    assert command.argv[0] == ffmpeg
    assert "-i" in command.argv
    assert str(source) in command.argv
    assert str(output) in command.argv
    assert "-af" in command.argv
    # No shell metacharacters joined into a single command string.
    assert all(isinstance(part, str) for part in command.argv)
    with pytest.raises(ValidationError, match="differ from source"):
        build_render_command(source, source, recipe, ffmpeg_bin=ffmpeg)
