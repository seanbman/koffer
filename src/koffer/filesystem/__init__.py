"""Filesystem helpers: scanning, extensions, exclusion matching, hashing, safe ops."""

from koffer.filesystem.extensions import SUPPORTED_AUDIO_EXTENSIONS, is_supported_audio_extension
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import (
    keep_both_destination,
    path_fingerprint,
    same_filesystem,
    verified_copy,
    verified_move,
)
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
    "keep_both_destination",
    "matches_exclusion",
    "path_fingerprint",
    "preview_exclusions",
    "same_filesystem",
    "verified_copy",
    "verified_move",
]
