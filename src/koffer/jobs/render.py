"""RENDER Job runner: FFmpeg temp render, verify, finalize; never mutates source."""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import uuid
from dataclasses import replace
from pathlib import Path

from koffer.audio.ffprobe import FfprobeError, probe_file
from koffer.audio.metadata import read_embedded, write_embedded
from koffer.audio.render import FfmpegError, FfmpegNotFoundError, run_ffmpeg_render
from koffer.domain.enums import ConflictAction, JobItemState, JobState
from koffer.domain.models import Job
from koffer.domain.preparation import RenderPlan
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import keep_both_destination, path_fingerprint
from koffer.jobs.cancel import is_cancel_requested, mark_cancelled, persist_progress
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.repositories.job_items import JobItem, JobItemRepository
from koffer.repositories.jobs import JobRepository


def run_render(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Execute a planned FFmpeg render; source path bytes must remain unchanged."""
    jobs = JobRepository(conn)
    items_repo = JobItemRepository(conn)
    plan = RenderPlan.from_scope(json.loads(job.scope_json))
    total = 1

    now = utc_now_iso()
    running = replace(
        job,
        state=JobState.RUNNING,
        stage="render",
        started_at=now,
        progress_current=0,
        progress_total=total,
    )
    jobs.update(running)
    items_repo.upsert(
        JobItem(
            job_id=job.id,
            item_key="0000:render",
            sample_id=plan.sample_id,
            source_path=plan.source_path,
            destination_path=plan.destination_path,
            state=JobItemState.PENDING,
            error_code=None,
            detail_json=None,
        )
    )
    _emit(progress, running, current=0, total=total, force=True)

    if is_cancel_requested(conn, job.id):
        cancelled = mark_cancelled(
            conn,
            replace(running, summary_json=json.dumps({"cancelled": True})),
            summary_json=json.dumps({"cancelled": True}),
        )
        _emit(progress, cancelled, current=0, total=total, force=True)
        return cancelled

    source = Path(plan.source_path)
    try:
        if not source.is_file():
            raise FileNotFoundError(f"source missing: {source}")
        if content_fingerprint(source) != plan.source_content_hash:
            raise OSError("source content hash changed before render")
        if path_fingerprint(source) != plan.source_fingerprint:
            raise OSError("source fingerprint changed before render")

        destination = Path(plan.destination_path)
        if destination.resolve() == source.resolve():
            raise OSError("refusing to render onto source path")

        if destination.exists():
            if plan.conflict_policy is ConflictAction.KEEP_BOTH:
                destination = keep_both_destination(destination)
            elif plan.conflict_policy is ConflictAction.SKIP:
                items_repo.upsert(
                    JobItem(
                        job_id=job.id,
                        item_key="0000:render",
                        sample_id=plan.sample_id,
                        source_path=plan.source_path,
                        destination_path=str(destination),
                        state=JobItemState.SKIPPED,
                        error_code="destination_exists",
                        detail_json=json.dumps({"policy": "skip"}),
                    )
                )
                completed = replace(
                    running,
                    state=JobState.COMPLETED,
                    stage="commit",
                    completed_at=utc_now_iso(),
                    progress_current=1,
                    progress_total=1,
                    summary_json=json.dumps(
                        {
                            "skipped": 1,
                            "destination_path": str(destination),
                            "source_content_hash": plan.source_content_hash,
                            "source_hash_unchanged": True,
                        }
                    ),
                )
                jobs.update(completed)
                _emit(progress, completed, current=1, total=1, force=True)
                return completed
            elif plan.conflict_policy is not ConflictAction.REPLACE:
                raise OSError(f"unsupported conflict policy: {plan.conflict_policy}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_name = f".{destination.name}.koffer-render-{uuid.uuid4().hex}"
        temp_path = destination.parent / temp_name

        run_ffmpeg_render(source, temp_path, plan.recipe)

        # Verify output basics via ffprobe when available.
        probe_ok = True
        probe_detail: dict[str, object] = {}
        try:
            probed = probe_file(temp_path)
            probe_detail = {
                "duration_ms": probed.duration_ms,
                "sample_rate_hz": probed.sample_rate_hz,
                "channels": probed.channels,
                "codec": probed.codec,
                "container_format": probed.container_format,
            }
        except FfprobeError as exc:
            probe_ok = False
            probe_detail = {"probe_error": exc.message}

        if plan.carry_metadata:
            _carry_metadata(source, temp_path, carry_artwork=plan.carry_artwork)

        # Atomic finalize: never write into source; replace destination only when explicit.
        if destination.exists() and plan.conflict_policy is ConflictAction.REPLACE:
            destination.unlink()
        os.rename(temp_path, destination)

        after_source_hash = content_fingerprint(source)
        source_unchanged = after_source_hash == plan.source_content_hash
        if not source_unchanged:
            raise OSError("source content hash changed during render")

        detail = {
            "destination_path": str(destination),
            "destination_hash": content_fingerprint(destination),
            "source_content_hash": plan.source_content_hash,
            "source_hash_unchanged": source_unchanged,
            "probe_ok": probe_ok,
            "probe": probe_detail,
            "recipe_version": plan.recipe.version,
        }
        items_repo.upsert(
            JobItem(
                job_id=job.id,
                item_key="0000:render",
                sample_id=plan.sample_id,
                source_path=plan.source_path,
                destination_path=str(destination),
                state=JobItemState.SUCCEEDED,
                error_code=None,
                detail_json=json.dumps(detail),
            )
        )
        completed = replace(
            running,
            state=JobState.COMPLETED,
            stage="commit",
            completed_at=utc_now_iso(),
            progress_current=1,
            progress_total=1,
            summary_json=json.dumps(
                {
                    "succeeded": 1,
                    "failed": 0,
                    "destination_path": str(destination),
                    "source_content_hash": plan.source_content_hash,
                    "source_hash_unchanged": True,
                    "probe_ok": probe_ok,
                }
            ),
        )
        persist_progress(
            conn,
            completed,
            progress_current=1,
            progress_total=1,
            stage="commit",
        )
        # persist_progress may not set terminal fields; rewrite terminal state.
        jobs.update(completed)
        _emit(progress, completed, current=1, total=1, succeeded=1, force=True)
        return completed
    except (OSError, FfmpegError, FfmpegNotFoundError, FileNotFoundError, ValueError) as exc:
        with contextlib.suppress(OSError):
            # Clean orphan temp if present.
            for orphan in Path(plan.destination_path).parent.glob(
                f".{Path(plan.destination_path).name}.koffer-render-*"
            ):
                orphan.unlink(missing_ok=True)
        error_code = type(exc).__name__
        items_repo.upsert(
            JobItem(
                job_id=job.id,
                item_key="0000:render",
                sample_id=plan.sample_id,
                source_path=plan.source_path,
                destination_path=plan.destination_path,
                state=JobItemState.FAILED,
                error_code=error_code,
                detail_json=json.dumps({"error": str(exc)}),
            )
        )
        # Source hash check even on failure path when file still exists.
        source_hash_unchanged = True
        if source.is_file():
            source_hash_unchanged = content_fingerprint(source) == plan.source_content_hash
        failed = replace(
            running,
            state=JobState.FAILED,
            stage="failed",
            completed_at=utc_now_iso(),
            progress_current=1,
            progress_total=1,
            error_code=error_code,
            summary_json=json.dumps(
                {
                    "failed": 1,
                    "error": str(exc),
                    "source_content_hash": plan.source_content_hash,
                    "source_hash_unchanged": source_hash_unchanged,
                }
            ),
        )
        jobs.update(failed)
        _emit(progress, failed, current=1, total=1, failed=1, force=True)
        return failed


def _carry_metadata(source: Path, destination: Path, *, carry_artwork: bool) -> None:
    """Best-effort metadata copy onto rendered output; never touches source."""
    snapshot = read_embedded(source)
    if not snapshot.ok:
        return
    fields: dict[str, str | None] = {key: value for key, value in snapshot.fields.items() if value}
    if not fields and not (carry_artwork and snapshot.has_artwork):
        return
    try:
        write_embedded(destination, fields)
    except Exception:
        # Metadata carry-over is best-effort for foundations; render still succeeds.
        return


def _emit(
    progress: ProgressThrottle | None,
    job: Job,
    *,
    current: int,
    total: int,
    succeeded: int = 0,
    failed: int = 0,
    skipped: int = 0,
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
            message=None,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
        ),
        force=force,
    )
