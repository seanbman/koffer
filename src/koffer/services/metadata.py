"""MetadataService: embedded capability reporting and read (docs/19, docs/27).

Write targets (Update Original / Write to Copy) are intentionally out of scope
for Order 5-1; this service only reads and reports capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from koffer.audio.metadata import (
    EmbeddedMetadataSnapshot,
    FormatCapabilities,
    capabilities_for_extension,
    capabilities_for_path,
    read_embedded,
)
from koffer.domain.errors import NotFoundError
from koffer.domain.ids import EntityId
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository


@dataclass(frozen=True, slots=True)
class MetadataCapabilities:
    """Per-Sample format capability report (docs/19/27)."""

    sample_id: EntityId
    format_id: str
    supported: bool
    readable_fields: tuple[str, ...]
    writable_fields: tuple[str, ...]
    artwork_support: bool
    limitations: tuple[str, ...]
    media_path: str | None = None


class MetadataService:
    """Read embedded metadata and report format capabilities via Mutagen."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._factory = connection_factory

    def resolve_media_path(self, sample_id: EntityId) -> Path | None:
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None or sample.source_id is None:
            return None
        source = SourceRepository(conn).get(sample.source_id)
        if source is None:
            return None
        return Path(source.root_path) / sample.relative_path

    def read_capabilities(self, sample_id: EntityId) -> MetadataCapabilities:
        """Return readable/writable/artwork capabilities for the Sample's format."""
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")

        media = self.resolve_media_path(sample_id)
        caps: FormatCapabilities
        if media is not None:
            caps = capabilities_for_path(media)
        else:
            caps = capabilities_for_extension(sample.extension)

        return MetadataCapabilities(
            sample_id=sample_id,
            format_id=caps.format_id,
            supported=caps.supported,
            readable_fields=caps.readable_fields,
            writable_fields=caps.writable_fields,
            artwork_support=caps.artwork_support,
            limitations=caps.limitations,
            media_path=str(media) if media is not None else None,
        )

    def read_embedded(self, sample_id: EntityId) -> EmbeddedMetadataSnapshot:
        """Read normalized embedded tags for ``sample_id`` (never crashes)."""
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")

        media = self.resolve_media_path(sample_id)
        if media is None:
            caps = capabilities_for_extension(sample.extension)
            return EmbeddedMetadataSnapshot(
                format_id=caps.format_id,
                fields={name: None for name in caps.readable_fields if name != "artwork"},
                has_artwork=False,
                ok=False,
                error_code="path_unavailable",
                error_message="Sample media path could not be resolved",
            )
        return read_embedded(media)
