"""Mutagen-backed embedded metadata reader and format capability adapter (docs/19)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mutagen import MutagenError
from mutagen.aiff import AIFF
from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

from koffer.filesystem.extensions import normalize_extension

# Normalized fields exposed by the capability adapter (docs/19).
NORMALIZED_FIELDS: tuple[str, ...] = (
    "title",
    "artist",
    "album",
    "album_artist",
    "genre",
    "date",
    "track_number",
    "comment",
    "composer",
    "copyright",
    "artwork",
)

_TEXT_FIELDS: tuple[str, ...] = tuple(f for f in NORMALIZED_FIELDS if f != "artwork")

# ID3 frame map for WAVE/AIFF/MP3.
_ID3_FRAMES: dict[str, str] = {
    "title": "TIT2",
    "artist": "TPE1",
    "album": "TALB",
    "album_artist": "TPE2",
    "genre": "TCON",
    "date": "TDRC",
    "track_number": "TRCK",
    "comment": "COMM",
    "composer": "TCOM",
    "copyright": "TCOP",
}

_VORBIS_KEYS: dict[str, tuple[str, ...]] = {
    "title": ("title",),
    "artist": ("artist",),
    "album": ("album",),
    "album_artist": ("albumartist",),
    "genre": ("genre",),
    "date": ("date",),
    "track_number": ("tracknumber",),
    "comment": ("comment", "description"),
    "composer": ("composer",),
    "copyright": ("copyright",),
}

_MP4_KEYS: dict[str, str] = {
    "title": "\xa9nam",
    "artist": "\xa9ART",
    "album": "\xa9alb",
    "album_artist": "aART",
    "genre": "\xa9gen",
    "date": "\xa9day",
    "track_number": "trkn",
    "comment": "\xa9cmt",
    "composer": "\xa9wrt",
    "copyright": "cprt",
}


@dataclass(frozen=True, slots=True)
class FormatCapabilities:
    """Per-format read/write capability report for the metadata adapter."""

    format_id: str
    supported: bool
    readable_fields: tuple[str, ...]
    writable_fields: tuple[str, ...]
    artwork_support: bool
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EmbeddedMetadataSnapshot:
    """Normalized embedded tag snapshot for one media file."""

    format_id: str
    fields: dict[str, str | None]
    has_artwork: bool
    ok: bool
    error_code: str | None = None
    error_message: str | None = None


def _empty_fields() -> dict[str, str | None]:
    return {name: None for name in _TEXT_FIELDS}


def capabilities_for_extension(extension: str) -> FormatCapabilities:
    """Return static capability report for a file extension (no I/O)."""
    ext = normalize_extension(extension)
    if ext in {"wav", "wave"}:
        return FormatCapabilities(
            format_id="wav",
            supported=True,
            readable_fields=NORMALIZED_FIELDS,
            writable_fields=NORMALIZED_FIELDS,
            artwork_support=True,
            limitations=("WAV tags stored as ID3; INFO-chunk-only tags may be incomplete.",),
        )
    if ext in {"aiff", "aif"}:
        return FormatCapabilities(
            format_id="aiff",
            supported=True,
            readable_fields=NORMALIZED_FIELDS,
            writable_fields=NORMALIZED_FIELDS,
            artwork_support=True,
            limitations=("AIFF tags stored as ID3 where present.",),
        )
    if ext == "flac":
        return FormatCapabilities(
            format_id="flac",
            supported=True,
            readable_fields=NORMALIZED_FIELDS,
            writable_fields=NORMALIZED_FIELDS,
            artwork_support=True,
            limitations=(),
        )
    if ext == "mp3":
        return FormatCapabilities(
            format_id="mp3",
            supported=True,
            readable_fields=NORMALIZED_FIELDS,
            writable_fields=NORMALIZED_FIELDS,
            artwork_support=True,
            limitations=("ID3v2 preferred; ID3v1-only files expose a reduced field set.",),
        )
    if ext == "ogg":
        return FormatCapabilities(
            format_id="ogg",
            supported=True,
            readable_fields=_TEXT_FIELDS + ("artwork",),
            writable_fields=_TEXT_FIELDS,
            artwork_support=False,
            limitations=("Ogg/Vorbis artwork is not supported in V1.",),
        )
    if ext == "m4a":
        return FormatCapabilities(
            format_id="m4a",
            supported=True,
            readable_fields=NORMALIZED_FIELDS,
            writable_fields=NORMALIZED_FIELDS,
            artwork_support=True,
            limitations=("M4A/AAC depends on container atoms present in the file.",),
        )
    return FormatCapabilities(
        format_id=ext or "unknown",
        supported=False,
        readable_fields=(),
        writable_fields=(),
        artwork_support=False,
        limitations=(f"Extension '.{ext or '?'}' is not a supported embedded-metadata format.",),
    )


def capabilities_for_path(path: Path) -> FormatCapabilities:
    """Capability report derived from ``path`` suffix."""
    return capabilities_for_extension(path.suffix)


def read_embedded(path: Path) -> EmbeddedMetadataSnapshot:
    """Read normalized embedded tags from ``path``.

    Never raises for malformed/unsupported media: returns ``ok=False`` with an
    error code so Sample Detail / MetadataService stay crash-free.
    """
    target = Path(path)
    caps = capabilities_for_path(target)
    empty_fields = _empty_fields()

    if not caps.supported:
        return EmbeddedMetadataSnapshot(
            format_id=caps.format_id,
            fields=empty_fields,
            has_artwork=False,
            ok=False,
            error_code="unsupported_format",
            error_message=caps.limitations[0] if caps.limitations else "Unsupported format",
        )

    if not target.is_file():
        return EmbeddedMetadataSnapshot(
            format_id=caps.format_id,
            fields=empty_fields,
            has_artwork=False,
            ok=False,
            error_code="path_unavailable",
            error_message=f"Media path is not a readable file: {target}",
        )

    try:
        if caps.format_id == "wav":
            return _read_id3_container(WAVE(str(target)), caps.format_id)  # type: ignore[no-untyped-call]
        if caps.format_id == "aiff":
            return _read_id3_container(AIFF(str(target)), caps.format_id)  # type: ignore[no-untyped-call]
        if caps.format_id == "mp3":
            return _read_mp3(target, caps.format_id)
        if caps.format_id == "flac":
            return _read_vorbis_like(FLAC(str(target)), caps.format_id, artwork=True)  # type: ignore[no-untyped-call]
        if caps.format_id == "ogg":
            return _read_vorbis_like(
                OggVorbis(str(target)),  # type: ignore[no-untyped-call]
                caps.format_id,
                artwork=False,
            )
        if caps.format_id == "m4a":
            return _read_mp4(MP4(str(target)), caps.format_id)  # type: ignore[no-untyped-call]
    except MutagenError as exc:
        return EmbeddedMetadataSnapshot(
            format_id=caps.format_id,
            fields=empty_fields,
            has_artwork=False,
            ok=False,
            error_code="malformed_metadata",
            error_message=str(exc) or "Mutagen could not parse embedded metadata",
        )
    except OSError as exc:
        return EmbeddedMetadataSnapshot(
            format_id=caps.format_id,
            fields=empty_fields,
            has_artwork=False,
            ok=False,
            error_code="io_error",
            error_message=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 — malformed media must not crash callers
        return EmbeddedMetadataSnapshot(
            format_id=caps.format_id,
            fields=empty_fields,
            has_artwork=False,
            ok=False,
            error_code="malformed_metadata",
            error_message=str(exc) or type(exc).__name__,
        )

    return EmbeddedMetadataSnapshot(
        format_id=caps.format_id,
        fields=empty_fields,
        has_artwork=False,
        ok=False,
        error_code="unsupported_format",
        error_message=f"No reader for format '{caps.format_id}'",
    )


def _first_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace").strip() or None
        except Exception:  # noqa: BLE001
            return None
    if isinstance(value, list | tuple):
        if not value:
            return None
        return _first_text(value[0])
    text = str(value).strip()
    return text or None


def _id3_text(tags: ID3, frame_id: str) -> str | None:
    frames = tags.getall(frame_id)  # type: ignore[no-untyped-call]
    if not frames:
        return None
    frame = frames[0]
    if frame_id == "COMM":
        text = getattr(frame, "text", None)
        return _first_text(text)
    text = getattr(frame, "text", None)
    return _first_text(text)


def _read_id3_tags(tags: ID3 | None, format_id: str) -> EmbeddedMetadataSnapshot:
    fields = _empty_fields()
    has_artwork = False
    if tags is not None:
        for field, frame_id in _ID3_FRAMES.items():
            fields[field] = _id3_text(tags, frame_id)
        has_artwork = bool(tags.getall("APIC"))  # type: ignore[no-untyped-call]
    return EmbeddedMetadataSnapshot(
        format_id=format_id,
        fields=fields,
        has_artwork=has_artwork,
        ok=True,
    )


def _read_id3_container(audio: Any, format_id: str) -> EmbeddedMetadataSnapshot:
    tags = getattr(audio, "tags", None)
    if tags is None:
        return _read_id3_tags(None, format_id)
    if isinstance(tags, ID3):
        return _read_id3_tags(tags, format_id)
    # Some mutagen containers expose EasyID3-like mapping.
    fields = _empty_fields()
    for field in _TEXT_FIELDS:
        try:
            fields[field] = _first_text(tags.get(field))
        except Exception:  # noqa: BLE001
            fields[field] = None
    has_artwork = False
    try:
        has_artwork = bool(tags.getall("APIC")) if hasattr(tags, "getall") else False
    except Exception:  # noqa: BLE001
        has_artwork = False
    return EmbeddedMetadataSnapshot(
        format_id=format_id,
        fields=fields,
        has_artwork=has_artwork,
        ok=True,
    )


def _read_mp3(path: Path, format_id: str) -> EmbeddedMetadataSnapshot:
    try:
        audio = MP3(str(path))  # type: ignore[no-untyped-call]
    except MutagenError:
        # Fall back to bare ID3 header read.
        try:
            return _read_id3_tags(ID3(str(path)), format_id)  # type: ignore[no-untyped-call]
        except ID3NoHeaderError:
            return EmbeddedMetadataSnapshot(
                format_id=format_id,
                fields=_empty_fields(),
                has_artwork=False,
                ok=True,
            )
    tags = audio.tags
    if tags is None:
        return EmbeddedMetadataSnapshot(
            format_id=format_id,
            fields=_empty_fields(),
            has_artwork=False,
            ok=True,
        )
    if isinstance(tags, ID3):
        return _read_id3_tags(tags, format_id)
    return _read_id3_container(audio, format_id)


def _read_vorbis_like(audio: Any, format_id: str, *, artwork: bool) -> EmbeddedMetadataSnapshot:
    fields = _empty_fields()
    tags = getattr(audio, "tags", None) or {}
    for field, keys in _VORBIS_KEYS.items():
        value = None
        for key in keys:
            if key in tags:
                value = _first_text(tags.get(key))
                if value is not None:
                    break
        fields[field] = value
    has_artwork = False
    if artwork:
        pictures = getattr(audio, "pictures", None) or []
        has_artwork = len(pictures) > 0
    return EmbeddedMetadataSnapshot(
        format_id=format_id,
        fields=fields,
        has_artwork=has_artwork,
        ok=True,
    )


def _read_mp4(audio: Any, format_id: str) -> EmbeddedMetadataSnapshot:
    fields = _empty_fields()
    tags: dict[Any, Any] = audio.tags or {}
    for field, key in _MP4_KEYS.items():
        raw = tags.get(key)
        if field == "track_number" and isinstance(raw, list) and raw:
            first = raw[0]
            if isinstance(first, tuple) and first:
                fields[field] = str(first[0])
            else:
                fields[field] = _first_text(first)
        else:
            fields[field] = _first_text(raw)
    has_artwork = bool(tags.get("covr"))
    return EmbeddedMetadataSnapshot(
        format_id=format_id,
        fields=fields,
        has_artwork=has_artwork,
        ok=True,
    )
