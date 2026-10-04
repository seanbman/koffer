"""Audio capability adapters (ffprobe, waveform cache, future FFmpeg/render)."""

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
from koffer.audio.waveform import (
    DEFAULT_BUCKET_COUNT,
    WAVEFORM_PIPELINE_VERSION,
    PeakEnvelope,
    WaveformCache,
    build_peak_envelope,
)

__all__ = [
    "DEFAULT_BUCKET_COUNT",
    "PROBE_VERSION",
    "WAVEFORM_PIPELINE_VERSION",
    "FfprobeError",
    "FfprobeNotFoundError",
    "PeakEnvelope",
    "ProbeResult",
    "WaveformCache",
    "build_peak_envelope",
    "generate_default_set",
    "probe_file",
    "resolve_ffprobe",
    "write_malformed_wav",
    "write_silence_wav",
    "write_sine_wav",
]
