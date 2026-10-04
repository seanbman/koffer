"""FileOperationService: plan/execute Reference, Copy, Move (docs/03, docs/27)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from koffer.domain.enums import ConflictAction, FileOperationKind, JobType
from koffer.domain.errors import NotFoundError, ValidationError
from koffer.domain.file_operations import (
    ConflictPolicy,
    FileOperationPlan,
    PlannedFileItem,
)
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.operations import keep_both_destination, path_fingerprint
from koffer.jobs.scheduler import JobScheduler, JobSpec
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.job_items import JobItem, JobItemRepository
from koffer.repositories.jobs import JobRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository

__all__ = [
    "ConflictPolicy",
    "FileOperationPlan",
    "FileOperationService",
    "PlannedFileItem",
]


class FileOperationService:
    """Two-step plan/execute API; Reference never copies or moves."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        scheduler: JobScheduler,
    ) -> None:
        self._factory = connection_factory
        self._scheduler = scheduler

    def plan_reference(
        self,
        sample_ids: Iterable[EntityId],
        *,
        conflict_policy: ConflictPolicy | None = None,
    ) -> FileOperationPlan:
        """Plan Reference: keep files at existing paths (no destination mutation)."""
        del conflict_policy  # Reference has no destination conflicts.
        items = []
        for sample_id, source_path, fingerprint in self._resolve_samples(sample_ids):
            items.append(
                PlannedFileItem(
                    sample_id=sample_id,
                    source_path=str(source_path),
                    source_fingerprint=fingerprint,
                    destination_path=None,
                    conflict=False,
                    conflict_action=ConflictAction.REVIEW,
                    destination_exists=False,
                    note="reference_in_place",
                )
            )
        return FileOperationPlan(
            id=str(new_entity_id()),
            kind=FileOperationKind.REFERENCE,
            items=tuple(items),
            destination_root=None,
            conflict_policy=ConflictPolicy(),
            created_at=utc_now_iso(),
        )

    def plan_copy(
        self,
        sample_ids: Iterable[EntityId],
        destination: Path,
        conflict_policy: ConflictPolicy | None = None,
    ) -> FileOperationPlan:
        return self._plan_mutation(
            sample_ids,
            destination,
            kind=FileOperationKind.COPY,
            conflict_policy=conflict_policy,
        )

    def plan_move(
        self,
        sample_ids: Iterable[EntityId],
        destination: Path,
        conflict_policy: ConflictPolicy | None = None,
    ) -> FileOperationPlan:
        return self._plan_mutation(
            sample_ids,
            destination,
            kind=FileOperationKind.MOVE,
            conflict_policy=conflict_policy,
        )

    def resolve_conflicts(
        self,
        plan: FileOperationPlan,
        resolutions: dict[EntityId, ConflictAction],
        *,
        alternate_destinations: dict[EntityId, Path] | None = None,
    ) -> FileOperationPlan:
        """Apply S13 per-item resolutions; Keep Both allocates a free name."""
        alternates = alternate_destinations or {}
        updated: list[PlannedFileItem] = []
        for item in plan.items:
            action = resolutions.get(item.sample_id, item.conflict_action)
            dest = item.destination_path
            note = item.note
            conflict = item.conflict
            destination_exists = item.destination_exists
            if action is ConflictAction.KEEP_BOTH and dest is not None:
                dest = str(keep_both_destination(Path(dest)))
                conflict = False
                destination_exists = Path(dest).exists()
                note = "keep_both"
            elif action is ConflictAction.SKIP:
                note = "skip"
                conflict = False
            elif action is ConflictAction.REPLACE:
                if not item.destination_exists:
                    msg = "replace requires an existing destination conflict"
                    raise ValidationError(msg)
                note = "replace_explicit"
                conflict = False
            elif action is ConflictAction.CHOOSE_DESTINATION:
                alt = alternates.get(item.sample_id)
                if alt is None:
                    msg = f"choose_destination missing path for {item.sample_id}"
                    raise ValidationError(msg)
                dest = str(alt.resolve())
                destination_exists = Path(dest).exists()
                conflict = destination_exists
                note = "choose_destination"
                if destination_exists:
                    action = ConflictAction.REVIEW
            elif action is ConflictAction.REVIEW and item.conflict:
                conflict = True
            updated.append(
                replace(
                    item,
                    destination_path=dest,
                    conflict_action=action,
                    conflict=conflict,
                    destination_exists=destination_exists,
                    note=note,
                )
            )
        return replace(plan, items=tuple(updated))

    def execute(self, plan: FileOperationPlan) -> EntityId:
        """Execute a reviewed plan; refuses unresolved Review conflicts and stale sources."""
        if not plan.items:
            raise ValidationError("plan has no items")
        unresolved = plan.unresolved_conflicts()
        if unresolved:
            raise ValidationError(
                "plan has unresolved conflicts; resolve on S13 before execute",
                detail=f"unresolved={len(unresolved)}",
            )
        self._assert_fingerprints_fresh(plan)

        if plan.kind is FileOperationKind.REFERENCE:
            job_type = JobType.REFERENCE_SAMPLES
        elif plan.kind is FileOperationKind.COPY:
            job_type = JobType.COPY_FILES
        elif plan.kind is FileOperationKind.MOVE:
            job_type = JobType.MOVE_FILES
        else:
            raise ValidationError(f"unsupported plan kind: {plan.kind}")

        return self._scheduler.submit(JobSpec(type=job_type, scope=plan.to_scope()))

    def list_item_results(self, job_id: EntityId) -> list[JobItem]:
        conn = self._factory.get_connection()
        job = JobRepository(conn).get(job_id)
        if job is None:
            raise NotFoundError(f"Job not found: {job_id}")
        return JobItemRepository(conn).list_for_job(job_id)

    def _plan_mutation(
        self,
        sample_ids: Iterable[EntityId],
        destination: Path,
        *,
        kind: FileOperationKind,
        conflict_policy: ConflictPolicy | None,
    ) -> FileOperationPlan:
        policy = conflict_policy or ConflictPolicy()
        dest_root = Path(destination).expanduser().resolve()
        if dest_root.exists() and not dest_root.is_dir():
            raise ValidationError("destination must be a directory", detail=str(dest_root))
        items: list[PlannedFileItem] = []
        for sample_id, source_path, fingerprint in self._resolve_samples(sample_ids):
            proposed = dest_root / source_path.name
            exists = proposed.exists()
            action = policy.default_action
            conflict = False
            note: str | None = None
            final_dest: str | None = str(proposed)
            destination_exists = exists
            if exists and action is ConflictAction.KEEP_BOTH:
                final_dest = str(keep_both_destination(proposed))
                destination_exists = False
                note = "keep_both"
            elif exists and action is ConflictAction.SKIP:
                note = "skip"
            elif exists and action is ConflictAction.REPLACE:
                note = "replace_explicit"
            elif exists:
                # Default Review (and choose_destination) leave conflict unresolved.
                action = ConflictAction.REVIEW
                conflict = True
                note = "needs_review"
            items.append(
                PlannedFileItem(
                    sample_id=sample_id,
                    source_path=str(source_path),
                    source_fingerprint=fingerprint,
                    destination_path=final_dest,
                    conflict=conflict,
                    conflict_action=action,
                    destination_exists=destination_exists,
                    note=note,
                )
            )
        return FileOperationPlan(
            id=str(new_entity_id()),
            kind=kind,
            items=tuple(items),
            destination_root=str(dest_root),
            conflict_policy=policy,
            created_at=utc_now_iso(),
        )

    def _resolve_samples(
        self,
        sample_ids: Iterable[EntityId],
    ) -> list[tuple[EntityId, Path, str]]:
        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        sources = SourceRepository(conn)
        resolved: list[tuple[EntityId, Path, str]] = []
        seen: set[str] = set()
        for raw_id in sample_ids:
            sample_id = EntityId(str(raw_id))
            key = str(sample_id)
            if key in seen:
                continue
            seen.add(key)
            sample = samples.get(sample_id)
            if sample is None:
                raise NotFoundError(f"Sample not found: {sample_id}")
            if sample.source_id is None:
                raise ValidationError(f"Sample has no Source: {sample_id}")
            source = sources.get(sample.source_id)
            if source is None:
                raise NotFoundError(f"Source not found: {sample.source_id}")
            path = Path(source.root_path) / sample.relative_path
            if not path.is_file():
                raise ValidationError(
                    "Sample path unavailable for file operation",
                    detail=str(path),
                )
            resolved.append((sample_id, path.resolve(), path_fingerprint(path)))
        if not resolved:
            raise ValidationError("no samples selected")
        return resolved

    def _assert_fingerprints_fresh(self, plan: FileOperationPlan) -> None:
        for item in plan.items:
            if item.conflict_action is ConflictAction.SKIP:
                continue
            source = Path(item.source_path)
            if not source.is_file():
                raise ValidationError(
                    "plan outdated: source missing",
                    detail=item.source_path,
                )
            current = path_fingerprint(source)
            if current != item.source_fingerprint:
                raise ValidationError(
                    "plan outdated: source fingerprint changed",
                    detail=item.source_path,
                )
