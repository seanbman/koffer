"""SourceService: add/remove/disable/exclusions/scan (docs/02, docs/27)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from koffer.domain.enums import ExclusionPatternType, JobType, ScanMode, SourceStatus
from koffer.domain.errors import NotFoundError, ValidationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import ExclusionPreview, ExclusionRule, Source
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.scanner import preview_exclusions
from koffer.jobs.scheduler import JobScheduler, JobSpec
from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.search_index import SearchIndexService
from koffer.repositories.exclusions import SourceExclusionRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository


def default_exclusion_rules(source_id: EntityId) -> list[ExclusionRule]:
    """Default exclusions: hidden dirs + common trash folder names."""
    return [
        ExclusionRule(
            id=new_entity_id(),
            source_id=source_id,
            pattern="hidden",
            pattern_type=ExclusionPatternType.HIDDEN_POLICY,
            enabled=True,
        ),
        ExclusionRule(
            id=new_entity_id(),
            source_id=source_id,
            pattern="**/.Trash/**",
            pattern_type=ExclusionPatternType.GLOB,
            enabled=True,
        ),
        ExclusionRule(
            id=new_entity_id(),
            source_id=source_id,
            pattern="**/$RECYCLE.BIN/**",
            pattern_type=ExclusionPatternType.GLOB,
            enabled=True,
        ),
    ]


class SourceService:
    """Authorize and manage scan roots; never mutates Source audio files."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        scheduler: JobScheduler,
    ) -> None:
        self._factory = connection_factory
        self._scheduler = scheduler

    def add_source(self, path: Path, display_name: str | None = None) -> Source:
        """Index ``path`` in place; does not move or rename filesystem contents."""
        root = path.expanduser()
        try:
            resolved = root.resolve(strict=False)
        except OSError as exc:
            raise ValidationError(
                "Source path could not be resolved",
                detail=str(exc),
            ) from exc
        if not resolved.exists() or not resolved.is_dir():
            raise ValidationError(
                "Source path must be an existing directory",
                detail=str(resolved),
            )

        now = utc_now_iso()
        source_id = new_entity_id()
        name = display_name.strip() if display_name and display_name.strip() else resolved.name
        source = Source(
            id=source_id,
            display_name=name,
            root_path=str(resolved),
            enabled=True,
            recursive=True,
            status=SourceStatus.ONLINE,
            created_at=now,
            updated_at=now,
        )
        conn = self._factory.get_connection()
        SourceRepository(conn).create(source)
        SourceExclusionRepository(conn).replace_for_source(
            source_id, default_exclusion_rules(source_id)
        )
        return source

    def remove_source(self, source_id: EntityId) -> None:
        """Remove Koffer indexing state for a Source; never deletes audio files."""
        conn = self._factory.get_connection()
        sources = SourceRepository(conn)
        source = sources.get(source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")

        samples = SampleRepository(conn)
        search = SearchIndexService(conn)
        existing = samples.list_by_source(source_id)
        for sample in existing:
            search.delete_sample(sample.id)
        samples.delete_by_source(source_id)
        SourceExclusionRepository(conn).delete_for_source(source_id)
        sources.delete(source_id)
        # Filesystem under source.root_path is intentionally untouched.

    def set_enabled(self, source_id: EntityId, enabled: bool) -> None:
        conn = self._factory.get_connection()
        sources = SourceRepository(conn)
        source = sources.get(source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")
        now = utc_now_iso()
        status: SourceStatus = source.status
        if not enabled:
            status = SourceStatus.DISABLED
        elif source.status is SourceStatus.DISABLED:
            status = SourceStatus.ONLINE
        sources.update(
            replace(
                source,
                enabled=enabled,
                status=status,
                updated_at=now,
            )
        )

    def update_exclusions(
        self, source_id: EntityId, rules: list[ExclusionRule]
    ) -> ExclusionPreview:
        conn = self._factory.get_connection()
        sources = SourceRepository(conn)
        source = sources.get(source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")

        normalized: list[ExclusionRule] = []
        for rule in rules:
            rule_id = rule.id if rule.id else new_entity_id()
            normalized.append(
                ExclusionRule(
                    id=rule_id,
                    source_id=source_id,
                    pattern=rule.pattern,
                    pattern_type=rule.pattern_type,
                    enabled=rule.enabled,
                )
            )
        stored = SourceExclusionRepository(conn).replace_for_source(source_id, normalized)
        matched, included = preview_exclusions(
            Path(source.root_path),
            stored,
            recursive=source.recursive,
        )
        return ExclusionPreview(
            rules=tuple(stored),
            matched_relative_paths=matched,
            excluded_count=len(matched),
            included_supported_count=included,
        )

    def scan(self, source_id: EntityId, mode: ScanMode = ScanMode.INCREMENTAL) -> EntityId:
        """Enqueue a source_scan Job; returns Job ID immediately."""
        conn = self._factory.get_connection()
        source = SourceRepository(conn).get(source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")
        if not source.enabled:
            raise ValidationError(
                "Cannot scan a disabled Source",
                detail=str(source_id),
            )
        return self._scheduler.submit(
            JobSpec(
                type=JobType.SOURCE_SCAN,
                scope={"source_id": str(source_id), "mode": str(mode)},
            )
        )

    def get(self, source_id: EntityId) -> Source:
        conn = self._factory.get_connection()
        source = SourceRepository(conn).get(source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")
        return source

    def list(self) -> list[Source]:
        conn = self._factory.get_connection()
        return SourceRepository(conn).list_all()
