"""Copy/Move/Reference Job runners with per-item success/failure/skip reporting."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path

from koffer.domain.enums import ConflictAction, FileOperationKind, JobItemState, JobState, JobType
from koffer.domain.file_operations import FileOperationPlan, PlannedFileItem
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import path_fingerprint, verified_copy, verified_move
from koffer.jobs.cancel import is_cancel_requested, mark_cancelled, persist_progress
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.repositories.job_items import JobItem, JobItemRepository
from koffer.repositories.jobs import JobRepository


@dataclass(frozen=True, slots=True)
class _ItemOutcome:
    state: JobItemState
    destination_path: str | None
    error_code: str | None = None
    detail_json: str | None = None


def run_file_operation(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Execute a planned Reference/Copy/Move Job with per-item outcomes."""
    jobs = JobRepository(conn)
    items_repo = JobItemRepository(conn)
    plan = FileOperationPlan.from_scope(json.loads(job.scope_json))
    total = len(plan.items)

    now = utc_now_iso()
    running = replace(
        job,
        state=JobState.RUNNING,
        stage="items",
        started_at=now,
        progress_current=0,
        progress_total=total,
    )
    jobs.update(running)
    _seed_pending(items_repo, running, plan)
    _emit(progress, running, current=0, total=total, force=True)

    succeeded = 0
    failed = 0
    skipped = 0

    for index, planned in enumerate(plan.items):
        if is_cancel_requested(conn, job.id):
            summary = json.dumps(
                {
                    "succeeded": succeeded,
                    "failed": failed,
                    "skipped": skipped,
                    "total": total,
                    "cancelled_at_item": index,
                    "kind": str(plan.kind),
                }
            )
            cancelled = mark_cancelled(
                conn,
                replace(
                    running,
                    progress_current=succeeded + failed + skipped,
                    progress_total=total,
                    summary_json=summary,
                ),
                summary_json=summary,
            )
            _emit(
                progress,
                cancelled,
                current=succeeded + failed + skipped,
                total=total,
                succeeded=succeeded,
                failed=failed,
                skipped=skipped,
                force=True,
            )
            return cancelled

        item_key = f"{index:04d}:{planned.sample_id}"
        outcome = _process_item(plan.kind, planned, job_type=job.type)
        items_repo.upsert(
            JobItem(
                job_id=job.id,
                item_key=item_key,
                sample_id=planned.sample_id,
                source_path=planned.source_path,
                destination_path=outcome.destination_path,
                state=outcome.state,
                error_code=outcome.error_code,
                detail_json=outcome.detail_json,
            )
        )
        if outcome.state is JobItemState.SUCCEEDED:
            succeeded += 1
        elif outcome.state is JobItemState.SKIPPED:
            skipped += 1
        else:
            failed += 1

        current = succeeded + failed + skipped
        updated = persist_progress(
            conn,
            running,
            progress_current=current,
            progress_total=total,
            stage="items",
        )
        _emit(
            progress,
            updated,
            current=current,
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            active_item=item_key,
        )

    if failed > 0 and succeeded == 0 and skipped == 0:
        terminal_state = JobState.FAILED
        error_code = "all_items_failed"
    elif failed > 0:
        terminal_state = JobState.COMPLETED_WITH_ERRORS
        error_code = "partial_failure"
    else:
        terminal_state = JobState.COMPLETED
        error_code = None

    completed = replace(
        running,
        state=terminal_state,
        stage="commit",
        completed_at=utc_now_iso(),
        progress_current=total,
        progress_total=total,
        error_code=error_code,
        summary_json=json.dumps(
            {
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
                "total": total,
                "kind": str(plan.kind),
            }
        ),
    )
    jobs.update(completed)
    _emit(
        progress,
        completed,
        current=total,
        total=total,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        force=True,
    )
    return completed


def _seed_pending(
    items_repo: JobItemRepository,
    job: Job,
    plan: FileOperationPlan,
) -> None:
    for index, planned in enumerate(plan.items):
        items_repo.upsert(
            JobItem(
                job_id=job.id,
                item_key=f"{index:04d}:{planned.sample_id}",
                sample_id=planned.sample_id,
                source_path=planned.source_path,
                destination_path=planned.destination_path,
                state=JobItemState.PENDING,
                detail_json=json.dumps(
                    {
                        "conflict_action": str(planned.conflict_action),
                        "note": planned.note,
                    }
                ),
            )
        )


def _process_item(
    kind: FileOperationKind,
    planned: PlannedFileItem,
    *,
    job_type: JobType,
) -> _ItemOutcome:
    del job_type
    if planned.conflict_action is ConflictAction.SKIP:
        return _ItemOutcome(
            state=JobItemState.SKIPPED,
            destination_path=planned.destination_path,
            detail_json=json.dumps({"reason": "skipped_by_policy"}),
        )

    if kind is FileOperationKind.REFERENCE:
        source = Path(planned.source_path)
        if not source.is_file():
            return _ItemOutcome(
                state=JobItemState.FAILED,
                destination_path=None,
                error_code="source_missing",
                detail_json=json.dumps({"path": planned.source_path}),
            )
        # Reference must not copy or move.
        return _ItemOutcome(
            state=JobItemState.SUCCEEDED,
            destination_path=None,
            detail_json=json.dumps(
                {
                    "operation": "reference",
                    "source_hash": content_fingerprint(source),
                    "mutated": False,
                }
            ),
        )

    if planned.destination_path is None:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=None,
            error_code="missing_destination",
        )

    source = Path(planned.source_path)
    destination = Path(planned.destination_path)
    if not source.is_file():
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="source_missing",
        )
    try:
        current_fp = path_fingerprint(source)
    except OSError as exc:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="source_unreadable",
            detail_json=json.dumps({"error": str(exc)}),
        )
    if current_fp != planned.source_fingerprint:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="stale_fingerprint",
        )

    overwrite = planned.conflict_action is ConflictAction.REPLACE
    if destination.exists() and not overwrite:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="destination_exists",
            detail_json=json.dumps({"reason": "no_silent_overwrite"}),
        )

    try:
        source_hash = content_fingerprint(source)
        if kind is FileOperationKind.COPY:
            dest_hash = verified_copy(source, destination, overwrite=overwrite)
            if dest_hash != source_hash or not source.is_file():
                return _ItemOutcome(
                    state=JobItemState.FAILED,
                    destination_path=str(destination),
                    error_code="copy_verify_failed",
                )
            return _ItemOutcome(
                state=JobItemState.SUCCEEDED,
                destination_path=str(destination),
                detail_json=json.dumps(
                    {
                        "operation": "copy",
                        "source_hash": source_hash,
                        "destination_hash": dest_hash,
                        "source_preserved": True,
                    }
                ),
            )

        # MOVE
        dest_hash = verified_move(source, destination, overwrite=overwrite)
        source_gone = not source.exists()
        if dest_hash != source_hash:
            return _ItemOutcome(
                state=JobItemState.FAILED,
                destination_path=str(destination),
                error_code="move_verify_failed",
            )
        if not source_gone:
            return _ItemOutcome(
                state=JobItemState.FAILED,
                destination_path=str(destination),
                error_code="source_delete_failed",
                detail_json=json.dumps(
                    {
                        "operation": "move",
                        "destination_hash": dest_hash,
                        "source_retained": True,
                    }
                ),
            )
        return _ItemOutcome(
            state=JobItemState.SUCCEEDED,
            destination_path=str(destination),
            detail_json=json.dumps(
                {
                    "operation": "move",
                    "destination_hash": dest_hash,
                    "source_deleted": True,
                }
            ),
        )
    except FileExistsError:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="destination_exists",
            detail_json=json.dumps({"reason": "no_silent_overwrite"}),
        )
    except OSError as exc:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="filesystem_error",
            detail_json=json.dumps({"error": str(exc)}),
        )


def _emit(
    progress: ProgressThrottle | None,
    job: Job,
    *,
    current: int,
    total: int,
    succeeded: int = 0,
    failed: int = 0,
    skipped: int = 0,
    active_item: str | None = None,
    force: bool = False,
) -> None:
    if progress is None:
        return
    progress.publish(
        ProgressEvent(
            job_id=job.id,
            state=job.state,
            stage=job.stage,
            current=current,
            total=total,
            active_item=active_item,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
        ),
        force=force,
    )
