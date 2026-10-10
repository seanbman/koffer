"""MetadataService: capabilities, editor state, plan/execute writes (docs/19, docs/27)."""

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
from koffer.domain.enums import (
    ArtworkAction,
    ClassificationDimension,
    ClassificationSource,
    JobType,
    MetadataWriteTarget,
)
from koffer.domain.errors import NotFoundError, ValidationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.metadata_write import (
    MetadataEditFieldState,
    MetadataEditState,
    MetadataWriteException,
    MetadataWritePlan,
    MetadataWriteRequest,
    PlannedMetadataItem,
)
from koffer.domain.models import Classification
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import keep_both_destination, path_fingerprint
from koffer.jobs.scheduler import JobScheduler, JobSpec
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.classifications import ClassificationRepository
from koffer.repositories.job_items import JobItem, JobItemRepository
from koffer.repositories.jobs import JobRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.repositories.tags import TagRepository

__all__ = [
    "MetadataCapabilities",
    "MetadataEditState",
    "MetadataService",
    "MetadataWritePlan",
    "MetadataWriteRequest",
]


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


# Descriptive embeddable fields for S09 (docs/12 / docs/19).
_DESCRIPTIVE_FIELDS: tuple[str, ...] = (
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
)


class MetadataService:
    """Read/write embedded metadata with explicit Update Original / Write to Copy targets."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        scheduler: JobScheduler | None = None,
    ) -> None:
        self._factory = connection_factory
        self._scheduler = scheduler

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

    def get_editor_state(self, sample_ids: list[EntityId]) -> MetadataEditState:
        """Build S09 editor state; unsupported fields are disabled with explanations."""
        if not sample_ids:
            raise ValidationError("get_editor_state requires at least one sample_id")

        conn = self._factory.get_connection()
        samples_repo = SampleRepository(conn)
        tags_repo = TagRepository(conn)

        format_ids: list[str] = []
        limitations: list[str] = []
        snapshots: list[EmbeddedMetadataSnapshot] = []
        writable_sets: list[set[str]] = []
        artwork_flags: list[bool] = []
        artwork_present_flags: list[bool] = []
        all_tags: list[str] = []

        for sample_id in sample_ids:
            sample = samples_repo.get(sample_id)
            if sample is None:
                raise NotFoundError(f"Sample not found: {sample_id}")
            caps = self.read_capabilities(sample_id)
            format_ids.append(caps.format_id)
            limitations.extend(caps.limitations)
            writable_sets.append(set(caps.writable_fields))
            artwork_flags.append(caps.artwork_support)
            embedded = self.read_embedded(sample_id)
            snapshots.append(embedded)
            artwork_present_flags.append(embedded.has_artwork)
            all_tags.extend(tags_repo.list_display_names_for_sample(sample_id))

        common_writable = set.intersection(*writable_sets) if writable_sets else set()
        artwork_supported = all(artwork_flags)
        artwork_present = any(artwork_present_flags)
        artwork_explanation = None
        if not artwork_supported:
            artwork_explanation = (
                "Artwork embedding is not supported for every selected format "
                f"({', '.join(sorted(set(format_ids)))})."
            )

        field_states: list[MetadataEditFieldState] = []
        for name in _DESCRIPTIVE_FIELDS:
            values = [snap.fields.get(name) for snap in snapshots]
            unique = set(values)
            mixed = len(unique) > 1
            value = None if mixed else next(iter(unique))
            writable = name in common_writable
            explanation = None
            if not writable:
                explanation = (
                    f"Field '{name}' is not writable for the selected format(s): "
                    f"{', '.join(sorted(set(format_ids)))}."
                )
            field_states.append(
                MetadataEditFieldState(
                    name=name,
                    value=value,
                    writable=writable,
                    mixed=mixed,
                    explanation=explanation,
                )
            )

        seen: set[str] = set()
        ordered_tags: list[str] = []
        for tag in all_tags:
            if tag not in seen:
                seen.add(tag)
                ordered_tags.append(tag)

        return MetadataEditState(
            sample_ids=tuple(sample_ids),
            format_ids=tuple(dict.fromkeys(format_ids)),
            embeddable_fields=tuple(field_states),
            artwork_supported=artwork_supported,
            artwork_present=artwork_present,
            artwork_explanation=artwork_explanation,
            koffer_tags=tuple(ordered_tags),
            limitations=tuple(dict.fromkeys(limitations)),
        )

    def get_library_metadata(
        self, sample_ids: list[EntityId]
    ) -> tuple[dict[ClassificationDimension, tuple[str, ...]], tuple[str, ...]]:
        """Return editable Koffer classifications and tags for the selected Samples."""
        if not sample_ids:
            raise ValidationError("get_library_metadata requires at least one sample_id")
        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        classifications = ClassificationRepository(conn)
        tags = TagRepository(conn)
        values: dict[ClassificationDimension, list[str]] = {
            dimension: [] for dimension in ClassificationDimension
        }
        tag_values: list[str] = []
        for sample_id in sample_ids:
            if samples.get(sample_id) is None:
                raise NotFoundError(f"Sample not found: {sample_id}")
            for item in classifications.list_for_sample(sample_id):
                if item.value not in values[item.dimension]:
                    values[item.dimension].append(item.value)
            for tag in tags.list_display_names_for_sample(sample_id):
                if tag.casefold() not in {existing.casefold() for existing in tag_values}:
                    tag_values.append(tag)
        return {dimension: tuple(items) for dimension, items in values.items()}, tuple(tag_values)

    def save_library_metadata(
        self,
        sample_ids: list[EntityId],
        classifications: dict[ClassificationDimension, tuple[str, ...]],
        tags: tuple[str, ...],
    ) -> None:
        """Replace user-editable library metadata atomically; never writes audio."""
        if not sample_ids:
            raise ValidationError("save_library_metadata requires at least one sample_id")
        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        classification_repo = ClassificationRepository(conn)
        tag_repo = TagRepository(conn)
        normalized: dict[ClassificationDimension, tuple[str, ...]] = {}
        for dimension in ClassificationDimension:
            cleaned: list[str] = []
            seen: set[str] = set()
            for value in classifications.get(dimension, ()):
                text = value.strip()
                key = text.casefold()
                if text and key not in seen:
                    seen.add(key)
                    cleaned.append(text)
            normalized[dimension] = tuple(cleaned)
        clean_tags: list[str] = []
        seen_tags: set[str] = set()
        for tag in tags:
            text = tag.strip()
            key = text.casefold()
            if text and key not in seen_tags:
                seen_tags.add(key)
                clean_tags.append(text)

        # Claim the single SQLite writer slot before replacing rows.  The
        # scheduler may still be finishing probe/analysis jobs after the
        # source scan itself completes; an immediate transaction waits for
        # that writer cleanly instead of failing on the first INSERT.
        conn.execute("BEGIN IMMEDIATE")
        try:
            now = utc_now_iso()
            for sample_id in sample_ids:
                if samples.get(sample_id) is None:
                    raise NotFoundError(f"Sample not found: {sample_id}")
                existing = classification_repo.list_for_sample(sample_id)
                for dimension in ClassificationDimension:
                    for item in existing:
                        if item.dimension is dimension:
                            classification_repo.delete(item.id)
                    for value in normalized[dimension]:
                        classification_repo.create(
                            Classification(
                                id=new_entity_id(),
                                sample_id=sample_id,
                                dimension=dimension,
                                value=value,
                                source=ClassificationSource.USER,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                tag_repo.replace_for_sample(sample_id, tuple(clean_tags))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def plan_write(self, request: MetadataWriteRequest) -> MetadataWritePlan:
        """Plan an explicit UPDATE_ORIGINAL or WRITE_TO_COPY metadata mutation."""
        if not request.sample_ids:
            raise ValidationError("plan_write requires at least one sample_id")
        if request.target is MetadataWriteTarget.WRITE_TO_COPY and not request.copy_destination_dir:
            raise ValidationError("WRITE_TO_COPY requires copy_destination_dir")
        if request.artwork_action is ArtworkAction.ADD_REPLACE and request.artwork is None:
            raise ValidationError("ADD_REPLACE artwork_action requires artwork payload")
        if request.artwork_action is not ArtworkAction.ADD_REPLACE and request.artwork is not None:
            raise ValidationError("artwork payload requires ADD_REPLACE artwork_action")

        unknown = sorted(name for name in request.fields if name not in _DESCRIPTIVE_FIELDS)
        if unknown:
            raise ValidationError(
                "unknown metadata fields cannot be written",
                detail=",".join(unknown),
            )

        items: list[PlannedMetadataItem] = []
        exceptions: list[MetadataWriteException] = []
        copy_root: Path | None = None
        if request.target is MetadataWriteTarget.WRITE_TO_COPY:
            assert request.copy_destination_dir is not None
            copy_root = Path(request.copy_destination_dir).expanduser().resolve()
            if copy_root.exists() and not copy_root.is_dir():
                raise ValidationError(
                    "copy_destination_dir must be a directory",
                    detail=str(copy_root),
                )
            copy_root.mkdir(parents=True, exist_ok=True)

        for sample_id in request.sample_ids:
            caps = self.read_capabilities(sample_id)
            media = self.resolve_media_path(sample_id)
            if media is None or not media.is_file():
                exceptions.append(
                    MetadataWriteException(
                        sample_id=sample_id,
                        field="*",
                        code="path_unavailable",
                        message="Sample media path could not be resolved for writing",
                    )
                )
                continue
            if not caps.supported:
                exceptions.append(
                    MetadataWriteException(
                        sample_id=sample_id,
                        field="*",
                        code="unsupported_format",
                        message=(
                            caps.limitations[0]
                            if caps.limitations
                            else f"Unsupported format: {caps.format_id}"
                        ),
                    )
                )
                continue

            for field_name in request.fields:
                if field_name not in caps.writable_fields:
                    exceptions.append(
                        MetadataWriteException(
                            sample_id=sample_id,
                            field=field_name,
                            code="unsupported_field",
                            message=(
                                f"Field '{field_name}' is not writable for format "
                                f"'{caps.format_id}'"
                                + (f": {caps.limitations[0]}" if caps.limitations else "")
                            ),
                        )
                    )

            if request.artwork_action is not ArtworkAction.KEEP and not caps.artwork_support:
                exceptions.append(
                    MetadataWriteException(
                        sample_id=sample_id,
                        field="artwork",
                        code="unsupported_artwork",
                        message=(f"Artwork writes are not supported for format '{caps.format_id}'"),
                    )
                )

            if request.target is MetadataWriteTarget.UPDATE_ORIGINAL:
                destination = media
                note = "update_original"
            else:
                assert copy_root is not None
                destination = copy_root / media.name
                if destination.exists():
                    destination = keep_both_destination(destination)
                note = "write_to_copy"

            items.append(
                PlannedMetadataItem(
                    sample_id=sample_id,
                    source_path=str(media.resolve()),
                    source_fingerprint=path_fingerprint(media),
                    source_content_hash=content_fingerprint(media),
                    destination_path=str(destination.resolve()),
                    format_id=caps.format_id,
                    writable_fields=tuple(f for f in caps.writable_fields if f != "artwork"),
                    artwork_support=caps.artwork_support,
                    note=note,
                )
            )

        return MetadataWritePlan(
            id=str(new_entity_id()),
            target=request.target,
            items=tuple(items),
            fields=dict(request.fields),
            artwork_action=request.artwork_action,
            artwork=request.artwork,
            exceptions=tuple(exceptions),
            created_at=utc_now_iso(),
            copy_destination_dir=None if copy_root is None else str(copy_root),
        )

    def execute(self, plan: MetadataWritePlan) -> EntityId:
        """Execute a reviewed plan as a METADATA_WRITE Job (docs/18)."""
        if self._scheduler is None:
            raise ValidationError("MetadataService.execute requires a JobScheduler")
        if not plan.items:
            raise ValidationError("plan has no items")
        blocking = plan.blocking_exceptions()
        if blocking:
            raise ValidationError(
                "plan has blocking exceptions; unsupported fields cannot be written",
                detail=f"exceptions={len(blocking)}",
            )
        self._assert_fingerprints_fresh(plan)
        return self._scheduler.submit(JobSpec(type=JobType.METADATA_WRITE, scope=plan.to_scope()))

    def list_item_results(self, job_id: EntityId) -> list[JobItem]:
        conn = self._factory.get_connection()
        job = JobRepository(conn).get(job_id)
        if job is None:
            raise NotFoundError(f"Job not found: {job_id}")
        return JobItemRepository(conn).list_for_job(job_id)

    def _assert_fingerprints_fresh(self, plan: MetadataWritePlan) -> None:
        for item in plan.items:
            source = Path(item.source_path)
            if not source.is_file():
                raise ValidationError(
                    "source missing before execute",
                    detail=item.source_path,
                )
            current = path_fingerprint(source)
            if current != item.source_fingerprint:
                raise ValidationError(
                    "plan is stale; source fingerprint changed after review",
                    detail=item.source_path,
                )
