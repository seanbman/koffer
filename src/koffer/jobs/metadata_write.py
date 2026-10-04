"""METADATA_WRITE Job runner with post-write reread verification (docs/18, docs/19)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path

from koffer.audio.metadata import write_embedded
from koffer.domain.enums import ArtworkAction, JobItemState, JobState, MetadataWriteTarget
from koffer.domain.metadata_write import MetadataWritePlan
from koffer.domain.models import Job
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import path_fingerprint, verified_copy
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


def run_metadata_write(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Execute a planned metadata write with per-item verify-after-reread outcomes."""
    jobs = JobRepository(conn)
    items_repo = JobItemRepository(conn)
    plan = MetadataWritePlan.from_scope(json.loads(job.scope_json))
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
                    "target": str(plan.target),
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
        outcome = _process_item(plan, planned)
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
                "target": str(plan.target),
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
    plan: MetadataWritePlan,
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
                        "format_id": planned.format_id,
                        "note": planned.note,
                        "source_content_hash": planned.source_content_hash,
                    }
                ),
            )
        )


def _process_item(plan: MetadataWritePlan, planned: object) -> _ItemOutcome:
    from koffer.domain.metadata_write import PlannedMetadataItem

    assert isinstance(planned, PlannedMetadataItem)
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

    original_hash = planned.source_content_hash
    try:
        live_hash = content_fingerprint(source)
    except OSError as exc:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="source_unreadable",
            detail_json=json.dumps({"error": str(exc)}),
        )
    if live_hash != original_hash:
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(destination),
            error_code="stale_content_hash",
        )

    write_target = destination
    if plan.target is MetadataWriteTarget.WRITE_TO_COPY:
        try:
            if destination.resolve() == source.resolve():
                return _ItemOutcome(
                    state=JobItemState.FAILED,
                    destination_path=str(destination),
                    error_code="copy_destination_is_source",
                )
            verified_copy(source, destination, overwrite=False)
            write_target = destination
        except FileExistsError:
            return _ItemOutcome(
                state=JobItemState.FAILED,
                destination_path=str(destination),
                error_code="destination_exists",
            )
        except OSError as exc:
            return _ItemOutcome(
                state=JobItemState.FAILED,
                destination_path=str(destination),
                error_code="copy_failed",
                detail_json=json.dumps({"error": str(exc)}),
            )

    remove_artwork = plan.artwork_action is ArtworkAction.REMOVE
    artwork = plan.artwork if plan.artwork_action is ArtworkAction.ADD_REPLACE else None
    try:
        result = write_embedded(
            write_target,
            plan.fields,
            artwork=artwork,
            remove_artwork=remove_artwork,
        )
    except Exception as exc:  # noqa: BLE001 — surface as item failure; do not swallow per-field
        source_changed = False
        if plan.target is MetadataWriteTarget.UPDATE_ORIGINAL and source.is_file():
            try:
                source_changed = content_fingerprint(source) != original_hash
            except OSError:
                source_changed = True
        return _ItemOutcome(
            state=JobItemState.FAILED,
            destination_path=str(write_target),
            error_code="write_failed",
            detail_json=json.dumps(
                {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "source_bytes_changed": source_changed,
                }
            ),
        )

    # WRITE_TO_COPY must leave the original content hash unchanged.
    if plan.target is MetadataWriteTarget.WRITE_TO_COPY:
        try:
            after_original = content_fingerprint(source)
        except OSError as exc:
            return _ItemOutcome(
                state=JobItemState.FAILED,
                destination_path=str(write_target),
                error_code="original_hash_check_failed",
                detail_json=json.dumps({"error": str(exc)}),
            )
        if after_original != original_hash:
            return _ItemOutcome(
                state=JobItemState.FAILED,
                destination_path=str(write_target),
                error_code="original_hash_changed",
                detail_json=json.dumps(
                    {
                        "expected": original_hash,
                        "actual": after_original,
                    }
                ),
            )

    return _ItemOutcome(
        state=JobItemState.SUCCEEDED,
        destination_path=str(write_target),
        detail_json=json.dumps(
            {
                "verified": result.verified,
                "format_id": result.format_id,
                "written_fields": result.written_fields,
                "verification_fields": result.verification_fields,
                "artwork_changed": result.artwork_changed,
                "has_artwork": result.has_artwork,
                "original_content_hash": original_hash,
                "target": str(plan.target),
            }
        ),
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
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            active_item=active_item,
        ),
        force=force,
    )
