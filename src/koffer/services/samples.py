"""SampleService: Sample detail read model with provenance categories (docs/05, docs/27)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from koffer.audio.metadata import EmbeddedMetadataSnapshot
from koffer.domain.errors import NotFoundError
from koffer.domain.ids import EntityId
from koffer.domain.models import Classification, Sample, Suggestion, TechnicalMetadata
from koffer.domain.timestamps import utc_now_iso
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.classifications import ClassificationRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.repositories.suggestions import SuggestionRepository
from koffer.repositories.tags import TagRepository
from koffer.repositories.technical_metadata import TechnicalMetadataRepository
from koffer.services.metadata import MetadataCapabilities, MetadataService


class ProvenanceCategory(StrEnum):
    """Distinct Sample Detail provenance lanes (docs/05, S07 acceptance)."""

    TECHNICAL = "technical"
    EMBEDDED = "embedded"
    CONFIRMED = "confirmed"
    SUGGESTED = "suggested"
    TAGS = "tags"


@dataclass(frozen=True, slots=True)
class SampleDetail:
    """S07 read model: Sample facts grouped by provenance category."""

    sample: Sample
    media_path: str | None
    path_available: bool
    technical: TechnicalMetadata | None
    embedded: EmbeddedMetadataSnapshot
    classifications: tuple[Classification, ...]
    suggestions: tuple[Suggestion, ...]
    tags: tuple[str, ...]
    collection_names: tuple[str, ...]
    has_preparation_recipe: bool
    capabilities: MetadataCapabilities

    def provenance(self) -> dict[str, object]:
        """Explicit provenance map required by Order 5-1 / S07 acceptance."""
        return {
            ProvenanceCategory.TECHNICAL.value: self.technical,
            ProvenanceCategory.EMBEDDED.value: self.embedded,
            ProvenanceCategory.CONFIRMED.value: self.classifications,
            ProvenanceCategory.SUGGESTED.value: self.suggestions,
            ProvenanceCategory.TAGS.value: self.tags,
        }


class SampleService:
    """Sample-facing use cases; get_detail is the Phase 5 foundation."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        metadata_service: MetadataService | None = None,
    ) -> None:
        self._factory = connection_factory
        self._metadata = metadata_service or MetadataService(connection_factory)

    def get_detail(self, sample_id: EntityId) -> SampleDetail:
        """Assemble SampleDetail with distinct provenance categories."""
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")

        media_path: str | None = None
        path_available = False
        if sample.source_id is not None:
            source = SourceRepository(conn).get(sample.source_id)
            if source is not None:
                resolved = Path(source.root_path) / sample.relative_path
                media_path = str(resolved)
                path_available = resolved.is_file()

        technical = TechnicalMetadataRepository(conn).get(sample_id)
        classifications = tuple(ClassificationRepository(conn).list_for_sample(sample_id))
        suggestions = tuple(SuggestionRepository(conn).list_for_sample(sample_id))
        tags = tuple(TagRepository(conn).list_display_names_for_sample(sample_id))
        collection_names = tuple(self._collection_names_for_sample(conn, sample_id))
        has_recipe = self._has_preparation_recipe(conn, sample_id)

        # Embedded read is best-effort: malformed/unsupported never raises here.
        try:
            embedded = self._metadata.read_embedded(sample_id)
        except NotFoundError:
            raise
        except Exception as exc:  # noqa: BLE001 — detail view must stay crash-free
            embedded = EmbeddedMetadataSnapshot(
                format_id=sample.extension or "unknown",
                fields={},
                has_artwork=False,
                ok=False,
                error_code="read_failed",
                error_message=str(exc) or type(exc).__name__,
            )

        capabilities = self._metadata.read_capabilities(sample_id)

        return SampleDetail(
            sample=sample,
            media_path=media_path,
            path_available=path_available,
            technical=technical,
            embedded=embedded,
            classifications=classifications,
            suggestions=suggestions,
            tags=tags,
            collection_names=collection_names,
            has_preparation_recipe=has_recipe,
            capabilities=capabilities,
        )

    def set_favorite(self, sample_id: EntityId, favorite: bool) -> Sample:
        """Toggle favourite flag without touching audio files (docs/27)."""
        conn = self._factory.get_connection()
        repo = SampleRepository(conn)
        sample = repo.get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        updated = replace(sample, favorite=bool(favorite), updated_at=utc_now_iso())
        repo.update(updated)
        return updated

    def toggle_favorite(self, sample_id: EntityId) -> Sample:
        """Invert the favourite flag for the given Sample."""
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        return self.set_favorite(sample_id, not sample.favorite)

    @staticmethod
    def _has_preparation_recipe(conn: sqlite3.Connection, sample_id: EntityId) -> bool:
        row = conn.execute(
            "SELECT 1 FROM preparation_recipes WHERE sample_id = ?",
            (str(sample_id),),
        ).fetchone()
        return row is not None

    @staticmethod
    def _collection_names_for_sample(conn: sqlite3.Connection, sample_id: EntityId) -> list[str]:
        rows = conn.execute(
            """
            SELECT c.name AS name
            FROM collection_samples AS cs
            INNER JOIN collections AS c ON c.id = cs.collection_id
            WHERE cs.sample_id = ?
            ORDER BY c.name ASC, c.id ASC
            """,
            (str(sample_id),),
        ).fetchall()
        return [str(row["name"]) for row in rows]
