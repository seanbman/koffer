"""Argv-based ffprobe wrapper (docs/19). Never shell-interpolates paths."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROBE_VERSION = "ffprobe-json-v1"


class FfprobeError(Exception):
    """ffprobe invocation or parse failure for one media path."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


class FfprobeNotFoundError(FfprobeError):
    """ffprobe binary is not available on PATH."""


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Normalized technical facts from one successful probe."""

    container_format: str
    codec: str
    duration_ms: int
    sample_rate_hz: int
    channels: int
    bit_depth: int | None = None
    channel_layout: str | None = None
    bitrate: int | None = None


def resolve_ffprobe() -> str | None:
    """Return absolute ffprobe path via ``shutil.which``, or None if absent."""
    return shutil.which("ffprobe")


def probe_file(path: Path, *, ffprobe_bin: str | None = None, timeout: float = 30.0) -> ProbeResult:
    """Probe ``path`` with ffprobe using an argv list and ``shell=False``."""
    binary = ffprobe_bin if ffprobe_bin is not None else resolve_ffprobe()
    if binary is None:
        raise FfprobeNotFoundError("ffprobe not found on PATH", path=path)

    target = Path(path)
    argv = [
        binary,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(target),
    ]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise FfprobeError(f"ffprobe timed out after {timeout}s", path=target) from exc
    except OSError as exc:
        raise FfprobeError(f"ffprobe could not be executed: {exc}", path=target) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise FfprobeError(
            f"ffprobe failed with exit {completed.returncode}: {detail or 'no output'}",
            path=target,
        )

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise FfprobeError("ffprobe returned non-JSON output", path=target) from exc

    return _parse_probe_payload(payload, path=target)


def _parse_probe_payload(payload: dict[str, Any], *, path: Path) -> ProbeResult:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        streams = []
    audio = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "audio"
        ),
        None,
    )
    if audio is None:
        raise FfprobeError("no audio stream in ffprobe output", path=path)

    fmt = payload.get("format")
    if not isinstance(fmt, dict):
        fmt = {}

    container = str(fmt.get("format_name") or audio.get("codec_name") or "unknown")
    codec = str(audio.get("codec_name") or "unknown")

    sample_rate_raw = audio.get("sample_rate")
    if sample_rate_raw is None:
        raise FfprobeError("missing sample_rate in ffprobe output", path=path)
    sample_rate_hz = int(float(sample_rate_raw))

    channels_raw = audio.get("channels")
    if channels_raw is None:
        raise FfprobeError("missing channels in ffprobe output", path=path)
    channels = int(channels_raw)

    duration_raw = audio.get("duration")
    if duration_raw is None:
        duration_raw = fmt.get("duration")
    if duration_raw is None:
        raise FfprobeError("missing duration in ffprobe output", path=path)
    duration_ms = int(round(float(duration_raw) * 1000.0))

    bit_depth = _optional_int(audio.get("bits_per_sample"))
    if bit_depth is None or bit_depth == 0:
        bit_depth = _bits_from_sample_fmt(audio.get("sample_fmt"))

    channel_layout = audio.get("channel_layout")
    layout = str(channel_layout) if channel_layout else None

    bitrate = _optional_int(audio.get("bit_rate"))
    if bitrate is None:
        bitrate = _optional_int(fmt.get("bit_rate"))

    return ProbeResult(
        container_format=container,
        codec=codec,
        duration_ms=duration_ms,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        bit_depth=bit_depth,
        channel_layout=layout,
        bitrate=bitrate,
    )


def _optional_int(value: object | None) -> int | None:
    if value is None or value == "N/A":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _bits_from_sample_fmt(sample_fmt: object | None) -> int | None:
    if not isinstance(sample_fmt, str):
        return None
    # Common FFmpeg PCM sample formats: s16, s16p, s24, s32, flt, fltp, dbl.
    digits = "".join(ch for ch in sample_fmt if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None
