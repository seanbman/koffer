"""Filesystem helpers: scanning, extensions, exclusion matching, hashing."""

from koffer.filesystem.extensions import SUPPORTED_AUDIO_EXTENSIONS, is_supported_audio_extension
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.scanner import (
    DiscoveredFile,
    EnumerationFailed,
    enumerate_audio_files,
    matches_exclusion,
    preview_exclusions,
)

__all__ = [
    "SUPPORTED_AUDIO_EXTENSIONS",
    "DiscoveredFile",
    "EnumerationFailed",
    "content_fingerprint",
    "enumerate_audio_files",
    "is_supported_audio_extension",
    "matches_exclusion",
    "preview_exclusions",
]
