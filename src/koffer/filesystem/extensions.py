"""Supported audio extension detection for Source scanning (docs/19)."""

from __future__ import annotations

# Extensions without leading dot; lowercase. AIFF accepts both aiff and aif.
SUPPORTED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {
        "wav",
        "aiff",
        "aif",
        "flac",
        "mp3",
        "ogg",
        "m4a",
    }
)


def normalize_extension(filename_or_extension: str) -> str:
    """Return a lowercase extension without a leading dot."""
    value = filename_or_extension.strip().lower()
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    return value.lstrip(".")


def is_supported_audio_extension(filename_or_extension: str) -> bool:
    """True when the path/extension is in the V1 supported read/index set."""
    return normalize_extension(filename_or_extension) in SUPPORTED_AUDIO_EXTENSIONS
