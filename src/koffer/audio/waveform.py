"""Peak-envelope waveform cache with versioned keys (docs/19).

Cache paths:
    ``$XDG_CACHE_HOME/koffer/waveforms/<pipeline-version>/<sample-id>.bin``

The on-disk payload embeds the source content fingerprint. Unchanged
fingerprints reuse the envelope; fingerprint or pipeline mismatches rebuild.
Source audio bytes are never modified.
"""

from __future__ import annotations

import struct
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from koffer.domain.errors import PathUnavailableError, ValidationError
from koffer.domain.ids import EntityId
from koffer.filesystem.hashing import content_fingerprint

WAVEFORM_PIPELINE_VERSION = "1"
DEFAULT_BUCKET_COUNT = 1024

_MAGIC = b"KFWV"
_FORMAT_VERSION = 1
_HEADER_STRUCT = struct.Struct("<4sIHHIIIH")
# magic, format_version, pipeline_len, fingerprint_len, bucket_count,
# sample_rate_hz, duration_ms, channels — variable strings follow lengths


@dataclass(frozen=True, slots=True)
class PeakEnvelope:
    """Compact min/max peak envelope for waveform display."""

    fingerprint: str
    pipeline_version: str
    bucket_count: int
    sample_rate_hz: int
    duration_ms: int
    channels: int
    mins: tuple[float, ...]
    maxs: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.mins) != self.bucket_count or len(self.maxs) != self.bucket_count:
            raise ValidationError(
                "Envelope bucket lengths must match bucket_count",
                detail=f"mins={len(self.mins)} maxs={len(self.maxs)} buckets={self.bucket_count}",
            )


def build_peak_envelope(
    path: Path,
    *,
    fingerprint: str | None = None,
    bucket_count: int = DEFAULT_BUCKET_COUNT,
    pipeline_version: str = WAVEFORM_PIPELINE_VERSION,
) -> PeakEnvelope:
    """Decode PCM (WAV) and build a min/max peak envelope. Read-only on ``path``."""
    media = Path(path)
    if bucket_count < 1:
        raise ValidationError("bucket_count must be >= 1", detail=str(bucket_count))
    if not media.is_file():
        raise PathUnavailableError(
            "Audio path is not a readable file",
            detail=str(media),
            retryable=False,
        )

    fp = fingerprint if fingerprint is not None else content_fingerprint(media)
    try:
        with wave.open(str(media), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frame_count = handle.getnframes()
            raw = handle.readframes(frame_count)
    except wave.Error as exc:
        raise ValidationError(
            "Unsupported or corrupt WAV for waveform generation",
            detail=str(exc),
        ) from exc

    if channels < 1 or sample_rate < 1:
        raise ValidationError(
            "Invalid WAV channel/sample-rate metadata",
            detail=f"channels={channels} rate={sample_rate}",
        )
    if sample_width != 2:
        raise ValidationError(
            "Waveform builder currently supports PCM16 WAV only",
            detail=f"sample_width={sample_width}",
        )

    samples = array("h")
    samples.frombytes(raw)
    if channels > 1:
        mono = array("f")
        for index in range(0, len(samples), channels):
            frame = samples[index : index + channels]
            if not frame:
                break
            mono.append(sum(frame) / (channels * 32768.0))
        floats = mono
    else:
        floats = array("f", (value / 32768.0 for value in samples))

    total = len(floats)
    duration_ms = int(round((frame_count / float(sample_rate)) * 1000.0)) if sample_rate else 0
    if total == 0:
        zeros = tuple(0.0 for _ in range(bucket_count))
        return PeakEnvelope(
            fingerprint=fp,
            pipeline_version=pipeline_version,
            bucket_count=bucket_count,
            sample_rate_hz=sample_rate,
            duration_ms=duration_ms,
            channels=channels,
            mins=zeros,
            maxs=zeros,
        )

    mins: list[float] = []
    maxs: list[float] = []
    for bucket in range(bucket_count):
        start = (bucket * total) // bucket_count
        end = ((bucket + 1) * total) // bucket_count
        if end <= start:
            end = min(start + 1, total)
        window = floats[start:end]
        mins.append(min(window))
        maxs.append(max(window))

    return PeakEnvelope(
        fingerprint=fp,
        pipeline_version=pipeline_version,
        bucket_count=bucket_count,
        sample_rate_hz=sample_rate,
        duration_ms=duration_ms,
        channels=channels,
        mins=tuple(mins),
        maxs=tuple(maxs),
    )


def serialize_envelope(envelope: PeakEnvelope) -> bytes:
    """Serialize a peak envelope to the versioned cache blob format."""
    pipeline_bytes = envelope.pipeline_version.encode("utf-8")
    fingerprint_bytes = envelope.fingerprint.encode("utf-8")
    if len(pipeline_bytes) > 0xFFFF or len(fingerprint_bytes) > 0xFFFF:
        raise ValidationError("pipeline_version or fingerprint too long for cache header")

    header = _HEADER_STRUCT.pack(
        _MAGIC,
        _FORMAT_VERSION,
        len(pipeline_bytes),
        len(fingerprint_bytes),
        envelope.bucket_count,
        envelope.sample_rate_hz,
        envelope.duration_ms,
        envelope.channels,
    )
    peaks = bytearray()
    for lo, hi in zip(envelope.mins, envelope.maxs, strict=True):
        peaks.extend(struct.pack("<ff", float(lo), float(hi)))
    return header + pipeline_bytes + fingerprint_bytes + bytes(peaks)


def deserialize_envelope(blob: bytes) -> PeakEnvelope:
    """Parse a cache blob; raises ValidationError on corruption."""
    if len(blob) < _HEADER_STRUCT.size:
        raise ValidationError("Waveform cache blob too small")
    (
        magic,
        format_version,
        pipeline_len,
        fingerprint_len,
        bucket_count,
        sample_rate_hz,
        duration_ms,
        channels,
    ) = _HEADER_STRUCT.unpack_from(blob, 0)
    if magic != _MAGIC:
        raise ValidationError("Waveform cache magic mismatch")
    if format_version != _FORMAT_VERSION:
        raise ValidationError(
            "Unsupported waveform cache format version",
            detail=str(format_version),
        )
    offset = _HEADER_STRUCT.size
    end_meta = offset + pipeline_len + fingerprint_len
    peaks_bytes = bucket_count * 8
    if len(blob) < end_meta + peaks_bytes:
        raise ValidationError("Waveform cache blob truncated")
    pipeline_version = blob[offset : offset + pipeline_len].decode("utf-8")
    fingerprint = blob[offset + pipeline_len : end_meta].decode("utf-8")
    mins: list[float] = []
    maxs: list[float] = []
    cursor = end_meta
    for _ in range(bucket_count):
        lo, hi = struct.unpack_from("<ff", blob, cursor)
        mins.append(float(lo))
        maxs.append(float(hi))
        cursor += 8
    return PeakEnvelope(
        fingerprint=fingerprint,
        pipeline_version=pipeline_version,
        bucket_count=bucket_count,
        sample_rate_hz=sample_rate_hz,
        duration_ms=duration_ms,
        channels=channels,
        mins=tuple(mins),
        maxs=tuple(maxs),
    )


class WaveformCache:
    """Filesystem-backed peak-envelope cache under an XDG cache root."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        pipeline_version: str = WAVEFORM_PIPELINE_VERSION,
        bucket_count: int = DEFAULT_BUCKET_COUNT,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._pipeline_version = pipeline_version
        self._bucket_count = bucket_count

    @property
    def pipeline_version(self) -> str:
        return self._pipeline_version

    def cache_path(self, sample_id: EntityId) -> Path:
        """Versioned cache path for ``sample_id`` (docs/17 layout)."""
        return self._cache_dir / "waveforms" / self._pipeline_version / f"{sample_id}.bin"

    def get_or_build(
        self,
        sample_id: EntityId,
        path: Path,
        *,
        fingerprint: str | None = None,
        bucket_count: int | None = None,
    ) -> PeakEnvelope:
        """Return cached envelope when fingerprint+version match; else rebuild."""
        media = Path(path)
        fp = fingerprint if fingerprint is not None else content_fingerprint(media)
        buckets = self._bucket_count if bucket_count is None else bucket_count
        target = self.cache_path(sample_id)
        if target.is_file():
            try:
                cached = deserialize_envelope(target.read_bytes())
            except (OSError, ValidationError, UnicodeDecodeError, struct.error):
                cached = None
            if (
                cached is not None
                and cached.fingerprint == fp
                and cached.pipeline_version == self._pipeline_version
                and cached.bucket_count == buckets
            ):
                return cached

        envelope = build_peak_envelope(
            media,
            fingerprint=fp,
            bucket_count=buckets,
            pipeline_version=self._pipeline_version,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".bin.tmp")
        tmp.write_bytes(serialize_envelope(envelope))
        tmp.replace(target)
        return envelope
