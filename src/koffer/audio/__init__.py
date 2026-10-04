"""Audio capability adapters (ffprobe, waveform, Mutagen metadata)."""

from koffer.audio.ffprobe import (
    PROBE_VERSION,
    FfprobeError,
    FfprobeNotFoundError,
    ProbeResult,
    probe_file,
    resolve_ffprobe,
)
from koffer.audio.metadata import (
    NORMALIZED_FIELDS,
    EmbeddedMetadataSnapshot,
    FormatCapabilities,
    capabilities_for_extension,
    capabilities_for_path,
    read_embedded,
)
from koffer.audio.wav_fixtures import (
    generate_default_set,
    write_malformed_wav,
    write_silence_wav,
    write_sine_wav,
    write_tagged_wav,
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
    "NORMALIZED_FIELDS",
    "PROBE_VERSION",
    "WAVEFORM_PIPELINE_VERSION",
    "EmbeddedMetadataSnapshot",
    "FfprobeError",
    "FfprobeNotFoundError",
    "FormatCapabilities",
    "PeakEnvelope",
    "ProbeResult",
    "WaveformCache",
    "build_peak_envelope",
    "capabilities_for_extension",
    "capabilities_for_path",
    "generate_default_set",
    "probe_file",
    "read_embedded",
    "resolve_ffprobe",
    "write_malformed_wav",
    "write_silence_wav",
    "write_sine_wav",
    "write_tagged_wav",
]
