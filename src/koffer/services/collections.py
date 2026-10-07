"""CollectionService: CRUD and membership (docs/04, docs/27). Never mutates audio files."""

from __future__ import annotations

import builtins
from dataclasses import dataclass, replace

from koffer.domain.enums import CollectionSortMode
from koffer.domain.errors import NotFoundError, ValidationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import Collection, Sample
from koffer.domain.timestamps import utc_now_iso
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.collections import CollectionMembership, CollectionRepository
from koffer.repositories.samples import SampleRepository


@dataclass(frozen=True, slots=True)
class CollectionListItem:
    """S03 row: Collection plus membership count (no filesystem reads)."""

    collection: Collection
    sample_count: int


@dataclass(frozen=True, slots=True)
class CollectionDetailView:
    """S04 foundation payload: Collection metadata and member Samples."""

    collection: Collection
    memberships: tuple[CollectionMembership, ...]
    samples: tuple[Sample, ...]


class CollectionService:
    """Organize Samples into Collections without copying, moving, or deleting audio."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._factory = connection_factory

    def create(self, name: str, description: str | None = None) -> Collection:
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Collection name is required")
        now = utc_now_iso()
        collection = Collection(
            id=new_entity_id(),
            name=cleaned,
            sort_mode=str(CollectionSortMode.ADDED_AT_DESC),
            created_at=now,
            updated_at=now,
            description=description.strip() if description and description.strip() else None,
        )
        conn = self._factory.get_connection()
        CollectionRepository(conn).create(collection)
        return collection

    def update(
        self,
        collection_id: EntityId,
        *,
        name: str | None = None,
        description: str | None = None,
        color: str | None = None,
        artwork_path: str | None = None,
        sort_mode: str | None = None,
        clear_description: bool = False,
        clear_color: bool = False,
        clear_artwork_path: bool = False,
    ) -> Collection:
        conn = self._factory.get_connection()
        repo = CollectionRepository(conn)
        existing = repo.get(collection_id)
        if existing is None:
            raise NotFoundError(f"Collection not found: {collection_id}")

        next_name = existing.name
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValidationError("Collection name is required")
            next_name = cleaned

        next_description = existing.description
        if clear_description:
            next_description = None
        elif description is not None:
            next_description = description.strip() or None

        next_color = None if clear_color else (color if color is not None else existing.color)
        next_artwork = (
            None
            if clear_artwork_path
            else (artwork_path if artwork_path is not None else existing.artwork_path)
        )
        next_sort = sort_mode if sort_mode is not None else existing.sort_mode
        if sort_mode is not None:
            try:
                CollectionSortMode(sort_mode)
            except ValueError as exc:
                raise ValidationError(
                    "Invalid Collection sort_mode",
                    detail=sort_mode,
                ) from exc

        updated = replace(
            existing,
            name=next_name,
            description=next_description,
            color=next_color,
            artwork_path=next_artwork,
            sort_mode=next_sort,
            updated_at=utc_now_iso(),
        )
        repo.update(updated)
        return updated

    def duplicate(
        self,
        collection_id: EntityId,
        *,
        name: str | None = None,
    ) -> Collection:
        """Duplicate Collection metadata and membership links, never audio files."""
        source = self.get(collection_id)
        duplicate_name = (name or f"{source.name} Copy").strip()
        if not duplicate_name:
            raise ValidationError("Collection name is required")
        duplicate = self.create(duplicate_name, description=source.description)
        duplicate = self.update(
            duplicate.id,
            color=source.color,
            artwork_path=source.artwork_path,
            sort_mode=source.sort_mode,
        )
        sample_ids = self.list_sample_ids(collection_id)
        if sample_ids:
            self.add_samples(duplicate.id, sample_ids)
        return self.get(duplicate.id)

    def delete(self, collection_id: EntityId) -> None:
        """Delete Collection membership rows only. Samples and audio files remain."""
        conn = self._factory.get_connection()
        repo = CollectionRepository(conn)
        if repo.get(collection_id) is None:
            raise NotFoundError(f"Collection not found: {collection_id}")
        repo.delete(collection_id)
        # Intentionally does not touch samples table or filesystem paths.

    def add_samples(self, collection_id: EntityId, sample_ids: list[EntityId]) -> None:
        """Add membership links. Idempotent; never copies or moves audio files."""
        if not sample_ids:
            return
        conn = self._factory.get_connection()
        collections = CollectionRepository(conn)
        samples = SampleRepository(conn)
        if collections.get(collection_id) is None:
            raise NotFoundError(f"Collection not found: {collection_id}")

        now = utc_now_iso()
        changed = False
        for sample_id in sample_ids:
            if samples.get(sample_id) is None:
                raise NotFoundError(f"Sample not found: {sample_id}")
            if collections.has_membership(collection_id, sample_id):
                continue
            collections.add_sample(collection_id, sample_id, added_at=now)
            changed = True
        if changed:
            self._touch(collections, collection_id)

    def remove_samples(self, collection_id: EntityId, sample_ids: list[EntityId]) -> None:
        """Remove membership links only. Never deletes Sample rows or audio files."""
        if not sample_ids:
            return
        conn = self._factory.get_connection()
        collections = CollectionRepository(conn)
        if collections.get(collection_id) is None:
            raise NotFoundError(f"Collection not found: {collection_id}")

        changed = False
        for sample_id in sample_ids:
            if collections.remove_sample(collection_id, sample_id):
                changed = True
        if changed:
            self._touch(collections, collection_id)

    def reorder(self, collection_id: EntityId, ordered_sample_ids: list[EntityId]) -> None:
        """Set manual order for current members and switch sort_mode to manual."""
        conn = self._factory.get_connection()
        collections = CollectionRepository(conn)
        existing = collections.get(collection_id)
        if existing is None:
            raise NotFoundError(f"Collection not found: {collection_id}")

        current = set(collections.list_sample_ids(collection_id))
        ordered = list(ordered_sample_ids)
        if len(ordered) != len(set(ordered)):
            raise ValidationError("reorder sample_ids must be unique")
        if set(ordered) != current:
            raise ValidationError(
                "reorder must include exactly the current Collection members",
                detail=f"expected={len(current)} got={len(ordered)}",
            )

        collections.set_manual_positions(collection_id, ordered)
        collections.update(
            replace(
                existing,
                sort_mode=str(CollectionSortMode.MANUAL),
                updated_at=utc_now_iso(),
            )
        )

    def get(self, collection_id: EntityId) -> Collection:
        conn = self._factory.get_connection()
        collection = CollectionRepository(conn).get(collection_id)
        if collection is None:
            raise NotFoundError(f"Collection not found: {collection_id}")
        return collection

    def list(self) -> builtins.list[Collection]:
        conn = self._factory.get_connection()
        return CollectionRepository(conn).list_all()

    def list_with_counts(self) -> builtins.list[CollectionListItem]:
        conn = self._factory.get_connection()
        collections = CollectionRepository(conn)
        items: builtins.list[CollectionListItem] = []
        for collection in collections.list_all():
            items.append(
                CollectionListItem(
                    collection=collection,
                    sample_count=len(collections.list_sample_ids(collection.id)),
                )
            )
        return items

    def get_detail(self, collection_id: EntityId) -> CollectionDetailView:
        conn = self._factory.get_connection()
        collections = CollectionRepository(conn)
        samples = SampleRepository(conn)
        collection = collections.get(collection_id)
        if collection is None:
            raise NotFoundError(f"Collection not found: {collection_id}")
        memberships = tuple(collections.list_memberships(collection_id))
        member_samples: builtins.list[Sample] = []
        for membership in memberships:
            sample = samples.get(membership.sample_id)
            if sample is not None:
                member_samples.append(sample)
        return CollectionDetailView(
            collection=collection,
            memberships=memberships,
            samples=tuple(member_samples),
        )

    def list_sample_ids(self, collection_id: EntityId) -> builtins.list[EntityId]:
        conn = self._factory.get_connection()
        if CollectionRepository(conn).get(collection_id) is None:
            raise NotFoundError(f"Collection not found: {collection_id}")
        return CollectionRepository(conn).list_sample_ids(collection_id)

    def _touch(self, collections: CollectionRepository, collection_id: EntityId) -> None:
        existing = collections.get(collection_id)
        if existing is None:
            return
        collections.update(replace(existing, updated_at=utc_now_iso()))
