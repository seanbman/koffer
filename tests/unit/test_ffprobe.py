"""Unit tests for argv-based ffprobe wrapper."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from koffer.audio.ffprobe import FfprobeError, FfprobeNotFoundError, probe_file


def test_probe_file_invokes_subprocess_with_argv_and_shell_false(tmp_path: Path) -> None:
    media = tmp_path / "tone.wav"
    media.write_bytes(b"RIFF")
    payload = {
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "44100",
                "channels": 1,
                "channel_layout": "mono",
                "bits_per_sample": 16,
                "duration": "1.000000",
                "bit_rate": "705600",
            }
        ],
        "format": {"format_name": "wav", "duration": "1.000000", "bit_rate": "705600"},
    }
    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = json.dumps(payload)
    completed.stderr = ""

    with patch("koffer.audio.ffprobe.subprocess.run", return_value=completed) as run:
        result = probe_file(media, ffprobe_bin="/usr/bin/ffprobe")

    run.assert_called_once()
    args, kwargs = run.call_args
    argv = args[0]
    assert argv[0] == "/usr/bin/ffprobe"
    assert str(media) in argv
    assert kwargs["shell"] is False
    assert isinstance(argv, list)
    assert result.duration_ms == 1000
    assert result.sample_rate_hz == 44100
    assert result.channels == 1
    assert result.container_format == "wav"
    assert result.codec == "pcm_s16le"


def test_probe_file_raises_when_ffprobe_missing(tmp_path: Path) -> None:
    media = tmp_path / "missing-bin.wav"
    media.write_bytes(b"RIFF")
    with (
        patch("koffer.audio.ffprobe.resolve_ffprobe", return_value=None),
        pytest.raises(FfprobeNotFoundError),
    ):
        probe_file(media)


def test_probe_file_raises_on_nonzero_exit(tmp_path: Path) -> None:
    media = tmp_path / "bad.wav"
    media.write_bytes(b"RIFF")
    completed = MagicMock()
    completed.returncode = 1
    completed.stdout = ""
    completed.stderr = "Invalid data"
    with (
        patch("koffer.audio.ffprobe.subprocess.run", return_value=completed),
        pytest.raises(FfprobeError, match="exit 1"),
    ):
        probe_file(media, ffprobe_bin="/usr/bin/ffprobe")


def test_probe_file_timeout_is_visible(tmp_path: Path) -> None:
    media = tmp_path / "slow.wav"
    media.write_bytes(b"RIFF")
    with (
        patch(
            "koffer.audio.ffprobe.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["ffprobe"], timeout=0.1),
        ),
        pytest.raises(FfprobeError, match="timed out"),
    ):
        probe_file(media, ffprobe_bin="/usr/bin/ffprobe", timeout=0.1)
