"""Audio capability adapters (ffprobe, future FFmpeg/render)."""

from koffer.audio.ffprobe import (
    PROBE_VERSION,
    FfprobeError,
    FfprobeNotFoundError,
    ProbeResult,
    probe_file,
    resolve_ffprobe,
)
from koffer.audio.wav_fixtures import (
    generate_default_set,
    write_malformed_wav,
    write_silence_wav,
    write_sine_wav,
)

__all__ = [
    "PROBE_VERSION",
    "FfprobeError",
    "FfprobeNotFoundError",
    "ProbeResult",
    "generate_default_set",
    "probe_file",
    "resolve_ffprobe",
    "write_malformed_wav",
    "write_silence_wav",
    "write_sine_wav",
]
