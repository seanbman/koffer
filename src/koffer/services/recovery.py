"""Offline / missing recovery actions for S15 (docs/24, docs/12)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from koffer.domain.enums import RecoveryCondition, SampleAvailability, SourceStatus
from koffer.domain.errors import NotFoundError, ValidationError
from koffer.domain.ids import EntityId
from koffer.domain.models import Sample, Source
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.hashing import content_fingerprint
from koffer.persistence.connection import ConnectionFactory
from koffer.persistence.search_index import SearchIndexService
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository

__all__ = ["RecoveryIssue", "RecoveryService"]

_PROBLEM_AVAILABILITIES = (
    SampleAvailability.SOURCE_OFFLINE,
    SampleAvailability.MISSING,
    SampleAvailability.CHANGED,
    SampleAvailability.PERMISSION_DENIED,
)


@dataclass(frozen=True, slots=True)
class RecoveryIssue:
    """One distinct recovery condition for S15 listing."""

    condition: RecoveryCondition
    label: str
    detail: str
    sample_id: EntityId | None = None
    source_id: EntityId | None = None
    filename: str = ""


class RecoveryService:
    """Repair unavailable paths without guessing destructively."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._factory = connection_factory

    def list_issues(self) -> list[RecoveryIssue]:
        conn = self._factory.get_connection()
        sources = SourceRepository(conn)
        samples = SampleRepository(conn)
        issues: list[RecoveryIssue] = []

        for source in sources.list_all():
            if source.status is SourceStatus.OFFLINE:
                issues.append(
                    RecoveryIssue(
                        condition=RecoveryCondition.SOURCE_OFFLINE,
                        label=source.display_name,
                        detail=(
                            f"Source offline at {source.root_path}. "
                            "Samples and metadata are kept; playback is disabled."
                        ),
                        source_id=source.id,
                    )
                )
            elif source.status is SourceStatus.PERMISSION_DENIED:
                issues.append(
                    RecoveryIssue(
                        condition=RecoveryCondition.PERMISSION_DENIED,
                        label=source.display_name,
                        detail=f"Permission denied for Source root {source.root_path}.",
                        source_id=source.id,
                    )
                )
            elif source.status is SourceStatus.ERROR:
                issues.append(
                    RecoveryIssue(
                        condition=RecoveryCondition.MOUNT_IDENTITY_CHANGED,
                        label=source.display_name,
                        detail=(
                            f"Source reported an error at {source.root_path}. "
                            "Organization is preserved until you reconnect or rescan."
                        ),
                        source_id=source.id,
                    )
                )

        for sample in samples.list_by_availability(_PROBLEM_AVAILABILITIES):
            condition = _condition_for_sample(sample)
            sample_source = sources.get(sample.source_id) if sample.source_id is not None else None
            source_name = (
                sample_source.display_name if sample_source is not None else "unknown Source"
            )
            issues.append(
                RecoveryIssue(
                    condition=condition,
                    label=sample.filename,
                    detail=_detail_for_sample(sample, condition, source_name),
                    sample_id=sample.id,
                    source_id=sample.source_id,
                    filename=sample.filename,
                )
            )
        return issues

    def recheck_source(self, source_id: EntityId) -> Source:
        """Refresh Source online/offline/permission status without deleting Samples."""
        conn = self._factory.get_connection()
        sources = SourceRepository(conn)
        source = sources.get(source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")
        root = Path(source.root_path)
        now = utc_now_iso()
        if not root.exists():
            status = SourceStatus.OFFLINE
        elif not root.is_dir():
            status = SourceStatus.ERROR
        else:
            try:
                next(root.iterdir(), None)
                status = SourceStatus.ONLINE
            except PermissionError:
                status = SourceStatus.PERMISSION_DENIED
            except OSError:
                status = SourceStatus.ERROR
        updated = replace(source, status=status, last_seen_at=now, updated_at=now)
        sources.update(updated)

        # Propagate offline/online to Samples without treating offline as deleted.
        samples = SampleRepository(conn)
        for sample in samples.list_by_source(source_id):
            if status is SourceStatus.ONLINE:
                if sample.availability is SampleAvailability.SOURCE_OFFLINE:
                    samples.update(
                        replace(
                            sample,
                            availability=SampleAvailability.ONLINE,
                            updated_at=now,
                        )
                    )
            elif status is SourceStatus.OFFLINE:
                if sample.availability is SampleAvailability.ONLINE:
                    samples.update(
                        replace(
                            sample,
                            availability=SampleAvailability.SOURCE_OFFLINE,
                            updated_at=now,
                        )
                    )
            elif status is SourceStatus.PERMISSION_DENIED:
                samples.update(
                    replace(
                        sample,
                        availability=SampleAvailability.PERMISSION_DENIED,
                        updated_at=now,
                    )
                )
        return updated

    def leave_unresolved(self, sample_id: EntityId) -> None:
        """Explicit no-op acknowledgment — never guesses a destructive fix."""
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")

    def remove_stale_entry(self, sample_id: EntityId) -> None:
        """Remove library index row only; never deletes audio files."""
        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        sample = samples.get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        SearchIndexService(conn).delete_sample(sample_id)
        samples.delete(sample_id)

    def accept_changed_file(self, sample_id: EntityId) -> None:
        """Accept on-disk change: keep organization, mark online, refresh fingerprints."""
        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        sources = SourceRepository(conn)
        sample = samples.get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        if sample.availability is not SampleAvailability.CHANGED:
            raise ValidationError(
                "Accept changed file only applies to changed Samples",
                detail=str(sample_id),
            )
        if sample.source_id is None:
            raise ValidationError("Sample has no Source", detail=str(sample_id))
        source = sources.get(sample.source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {sample.source_id}")
        path = Path(source.root_path) / sample.relative_path
        if not path.is_file():
            raise ValidationError("Changed file is not readable at expected path", detail=str(path))
        samples.update(_sample_from_path(sample, path))

    def locate_file(self, sample_id: EntityId, new_path: Path) -> Sample:
        """Reconnect Sample identity to a user-chosen path when the file exists."""
        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        sources = SourceRepository(conn)
        sample = samples.get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        if sample.source_id is None:
            raise ValidationError("Sample has no Source", detail=str(sample_id))
        source = sources.get(sample.source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {sample.source_id}")
        path = Path(new_path).expanduser().resolve(strict=False)
        if not path.is_file():
            raise ValidationError("Located path must be an existing file", detail=str(path))
        root = Path(source.root_path).resolve(strict=False)
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValidationError(
                "Located file must remain under the Source root",
                detail=str(path),
            ) from exc
        updated = _sample_from_path(
            sample,
            path,
            relative_path=relative.as_posix(),
        )
        samples.update(updated)
        SearchIndexService(conn).refresh_sample(sample_id)
        return updated


def _sample_from_path(
    sample: Sample,
    path: Path,
    *,
    relative_path: str | None = None,
) -> Sample:
    stat = path.stat()
    now = utc_now_iso()
    rel = relative_path if relative_path is not None else sample.relative_path
    return replace(
        sample,
        relative_path=rel,
        normalized_path_cache=rel.lower(),
        filename=path.name,
        extension=path.suffix.lstrip(".").lower(),
        size_bytes=int(stat.st_size),
        mtime_ns=int(stat.st_mtime_ns),
        device_id=int(stat.st_dev),
        inode=int(stat.st_ino),
        quick_hash=f"{stat.st_size}:{stat.st_mtime_ns}",
        content_hash=content_fingerprint(path),
        availability=SampleAvailability.ONLINE,
        last_seen_at=now,
        updated_at=now,
    )


def _condition_for_sample(sample: Sample) -> RecoveryCondition:
    if sample.availability is SampleAvailability.SOURCE_OFFLINE:
        return RecoveryCondition.SOURCE_OFFLINE
    if sample.availability is SampleAvailability.MISSING:
        return RecoveryCondition.FILE_MISSING
    if sample.availability is SampleAvailability.CHANGED:
        return RecoveryCondition.FILE_CHANGED
    if sample.availability is SampleAvailability.PERMISSION_DENIED:
        return RecoveryCondition.PERMISSION_DENIED
    return RecoveryCondition.FILE_MOVED


def _detail_for_sample(sample: Sample, condition: RecoveryCondition, source_name: str) -> str:
    if condition is RecoveryCondition.SOURCE_OFFLINE:
        return (
            f"{sample.filename} is offline because Source '{source_name}' is unavailable. "
            "Not treated as deleted."
        )
    if condition is RecoveryCondition.FILE_MISSING:
        return (
            f"{sample.filename} is missing under '{source_name}'. "
            "Locate the file, leave unresolved, or remove the stale library entry."
        )
    if condition is RecoveryCondition.FILE_CHANGED:
        return (
            f"{sample.filename} changed outside Koffer. "
            "User organization remains; accept the change to refresh analysis."
        )
    if condition is RecoveryCondition.PERMISSION_DENIED:
        return f"Permission denied reading {sample.filename} under '{source_name}'."
    return f"{sample.filename} may have moved under '{source_name}'."
