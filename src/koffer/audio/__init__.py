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
    MetadataWriteResult,
    capabilities_for_extension,
    capabilities_for_path,
    read_embedded,
    write_embedded,
)
from koffer.audio.render import (
    RENDER_PIPELINE_VERSION,
    FfmpegError,
    FfmpegNotFoundError,
    RenderCommand,
    build_filter_graph,
    build_render_command,
    resolve_ffmpeg,
    run_ffmpeg_render,
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
    "RENDER_PIPELINE_VERSION",
    "WAVEFORM_PIPELINE_VERSION",
    "EmbeddedMetadataSnapshot",
    "FfmpegError",
    "FfmpegNotFoundError",
    "FfprobeError",
    "FfprobeNotFoundError",
    "FormatCapabilities",
    "MetadataWriteResult",
    "PeakEnvelope",
    "ProbeResult",
    "RenderCommand",
    "WaveformCache",
    "build_filter_graph",
    "build_peak_envelope",
    "build_render_command",
    "capabilities_for_extension",
    "capabilities_for_path",
    "generate_default_set",
    "probe_file",
    "read_embedded",
    "resolve_ffmpeg",
    "resolve_ffprobe",
    "run_ffmpeg_render",
    "write_embedded",
    "write_malformed_wav",
    "write_silence_wav",
    "write_sine_wav",
    "write_tagged_wav",
]
