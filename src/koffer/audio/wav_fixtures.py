"""Deterministic PCM WAV writers for tests and ``scripts/generate_test_audio``."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def write_sine_wav(
    path: Path,
    *,
    duration_s: float = 1.0,
    sample_rate: int = 44100,
    channels: int = 1,
    frequency_hz: float = 440.0,
    amplitude: float = 0.2,
) -> Path:
    """Write a PCM16 WAV sine tone; returns ``path``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(round(duration_s * sample_rate)))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            sample = int(
                32767.0 * amplitude * math.sin(2.0 * math.pi * frequency_hz * index / sample_rate)
            )
            packed = struct.pack("<h", sample)
            for _ in range(channels):
                frames.extend(packed)
        handle.writeframes(frames)
    return path


def write_silence_wav(
    path: Path,
    *,
    duration_s: float = 0.25,
    sample_rate: int = 44100,
    channels: int = 1,
) -> Path:
    """Write a silent PCM16 WAV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, int(round(duration_s * sample_rate)))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frame_count * channels)
    return path


def write_malformed_wav(path: Path) -> Path:
    """Write bytes that look audio-ish but are not a valid WAV container."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF....NOTAWAVEFILE")
    return path


def generate_default_set(output_dir: Path) -> dict[str, Path]:
    """Generate the Phase-2 probe fixture set under ``output_dir``."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    return {
        "mono_sine": write_sine_wav(root / "mono_sine_1s.wav", channels=1, duration_s=1.0),
        "stereo_sine": write_sine_wav(root / "stereo_sine_1s.wav", channels=2, duration_s=1.0),
        "silence": write_silence_wav(root / "silence_250ms.wav", duration_s=0.25),
        "malformed": write_malformed_wav(root / "malformed.wav"),
    }
