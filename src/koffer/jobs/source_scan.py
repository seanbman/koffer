"""Source scan Job runner: discover Samples without deleting audio files."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from koffer.domain.enums import JobState, SampleAvailability, ScanMode, SourceStatus
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import Job, Sample, Source
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.scanner import (
    DiscoveredFile,
    EnumerationFailed,
    enumerate_audio_files,
    normalize_relative_path,
)
from koffer.jobs.cancel import (
    is_cancel_requested,
    mark_cancelled,
    persist_progress,
    wait_if_paused,
)
from koffer.jobs.progress import ProgressEvent, ProgressThrottle
from koffer.persistence.search_index import SearchIndexService
from koffer.repositories.exclusions import SourceExclusionRepository
from koffer.repositories.jobs import JobRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository


def run_source_scan(
    conn: sqlite3.Connection,
    job: Job,
    *,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Execute a persisted ``source_scan`` Job on the calling thread's connection."""
    jobs = JobRepository(conn)
    sources = SourceRepository(conn)
    samples = SampleRepository(conn)
    exclusions = SourceExclusionRepository(conn)
    search = SearchIndexService(conn)

    scope = json.loads(job.scope_json)
    source_id = EntityId(str(scope["source_id"]))
    mode = ScanMode(str(scope.get("mode", ScanMode.INCREMENTAL)))

    control_state = wait_if_paused(conn, job.id)
    if control_state is JobState.CANCEL_REQUESTED:
        latest = jobs.get(job.id) or job
        return mark_cancelled(conn, latest)
    job = jobs.get(job.id) or job

    now = utc_now_iso()
    running = replace(
        job,
        state=JobState.RUNNING,
        stage="validate",
        started_at=now,
        progress_current=0,
        progress_total=None,
    )
    jobs.update(running)
    _emit_progress(progress, running, force=True)

    if is_cancel_requested(conn, job.id):
        return mark_cancelled(conn, running)

    source = sources.get(source_id)
    if source is None:
        failed = replace(
            running,
            state=JobState.FAILED,
            stage="validate",
            completed_at=utc_now_iso(),
            error_code="source_not_found",
            summary_json=json.dumps({"error": "source_not_found"}),
        )
        jobs.update(failed)
        _emit_progress(progress, failed, force=True)
        return failed

    scanning = replace(
        source,
        status=SourceStatus.SCANNING,
        last_scan_started_at=now,
        updated_at=now,
    )
    sources.update(scanning)

    rules = exclusions.list_for_source(source_id)
    root = Path(source.root_path)

    try:
        progressing = replace(running, stage="enumerate")
        jobs.update(progressing)
        _emit_progress(progress, progressing, force=True)
        discovered = enumerate_audio_files(
            root,
            recursive=source.recursive,
            rules=rules,
        )
    except EnumerationFailed as exc:
        return _fail_offline(
            conn,
            job=progressing,
            source=scanning,
            samples_repo=samples,
            sources_repo=sources,
            jobs_repo=jobs,
            error=exc,
            progress=progress,
        )

    return _apply_discovery(
        conn,
        job=progressing,
        source=scanning,
        discovered=discovered,
        mode=mode,
        samples_repo=samples,
        sources_repo=sources,
        jobs_repo=jobs,
        search=search,
        progress=progress,
    )


def _fail_offline(
    conn: sqlite3.Connection,
    *,
    job: Job,
    source: Source,
    samples_repo: SampleRepository,
    sources_repo: SourceRepository,
    jobs_repo: JobRepository,
    error: EnumerationFailed,
    progress: ProgressThrottle | None = None,
) -> Job:
    """Mark Source offline/unavailable without deleting or mass-missing Samples."""
    del conn  # connection owned by repositories
    now = utc_now_iso()
    if error.permission_denied:
        status = SourceStatus.PERMISSION_DENIED
        availability = SampleAvailability.PERMISSION_DENIED
        error_code = "permission_denied"
    else:
        status = SourceStatus.OFFLINE
        availability = SampleAvailability.SOURCE_OFFLINE
        error_code = "source_offline"

    # Preserve existing Sample rows; only update availability labels.
    existing = samples_repo.list_by_source(source.id)
    for sample in existing:
        if sample.availability is SampleAvailability.MISSING:
            continue
        samples_repo.update(
            replace(
                sample,
                availability=availability,
                updated_at=now,
            )
        )

    sources_repo.update(
        replace(
            source,
            status=status,
            last_scan_completed_at=now,
            updated_at=now,
        )
    )
    completed = replace(
        job,
        state=JobState.COMPLETED_WITH_ERRORS,
        stage="offline",
        completed_at=now,
        error_code=error_code,
        progress_current=0,
        progress_total=0,
        summary_json=json.dumps(
            {
                "error": error_code,
                "message": error.message,
                "samples_preserved": len(existing),
                "marked_missing": 0,
                "deleted": 0,
            }
        ),
    )
    jobs_repo.update(completed)
    _emit_progress(progress, completed, force=True)
    return completed


def _apply_discovery(
    conn: sqlite3.Connection,
    *,
    job: Job,
    source: Source,
    discovered: list[DiscoveredFile],
    mode: ScanMode,
    samples_repo: SampleRepository,
    sources_repo: SourceRepository,
    jobs_repo: JobRepository,
    search: SearchIndexService,
    progress: ProgressThrottle | None = None,
) -> Job:
    now = utc_now_iso()
    compare_job = replace(
        job,
        stage="compare",
        progress_current=0,
        progress_total=len(discovered),
    )
    jobs_repo.update(compare_job)
    _emit_progress(progress, compare_job, force=True)

    existing = {s.relative_path: s for s in samples_repo.list_by_source(source.id)}
    seen_paths: set[str] = set()
    inserted = 0
    updated = 0
    unchanged = 0
    fts_ids: list[EntityId] = []
    probe_sample_ids: list[EntityId] = []

    for index, item in enumerate(discovered, start=1):
        wait_if_paused(conn, job.id)
        if is_cancel_requested(conn, job.id):
            # Preserve rows already upserted; stop before missing-mark / FTS refresh.
            sources_repo.update(
                replace(
                    source,
                    status=SourceStatus.ONLINE if source.enabled else SourceStatus.DISABLED,
                    updated_at=utc_now_iso(),
                )
            )
            summary = json.dumps(
                {
                    "inserted": inserted,
                    "updated": updated,
                    "unchanged": unchanged,
                    "missing": 0,
                    "discovered": len(discovered),
                    "mode": str(mode),
                    "cancelled": True,
                    "probe_sample_ids": [str(sample_id) for sample_id in probe_sample_ids],
                }
            )
            cancelled = mark_cancelled(
                conn,
                replace(
                    compare_job,
                    progress_current=index - 1,
                    progress_total=len(discovered),
                    stage="cancelled",
                    summary_json=summary,
                ),
                summary_json=summary,
            )
            _emit_progress(progress, cancelled, force=True)
            return cancelled

        rel = normalize_relative_path(item.relative_path)
        seen_paths.add(rel)
        prior = existing.get(rel)
        if prior is None:
            sample = Sample(
                id=new_entity_id(),
                relative_path=rel,
                normalized_path_cache=rel.lower(),
                filename=item.filename,
                extension=item.extension,
                size_bytes=item.size_bytes,
                mtime_ns=item.mtime_ns,
                availability=SampleAvailability.ONLINE,
                favorite=False,
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
                source_id=source.id,
                device_id=item.device_id,
                inode=item.inode,
            )
            samples_repo.create(sample)
            fts_ids.append(sample.id)
            probe_sample_ids.append(sample.id)
            inserted += 1
        else:
            same_identity = prior.size_bytes == item.size_bytes and prior.mtime_ns == item.mtime_ns
            if mode is ScanMode.INCREMENTAL and same_identity:
                samples_repo.update(
                    replace(
                        prior,
                        availability=SampleAvailability.ONLINE,
                        last_seen_at=now,
                        updated_at=now,
                        device_id=item.device_id,
                        inode=item.inode,
                    )
                )
                unchanged += 1
            else:
                availability = (
                    SampleAvailability.ONLINE if same_identity else SampleAvailability.CHANGED
                )
                samples_repo.update(
                    replace(
                        prior,
                        filename=item.filename,
                        extension=item.extension,
                        size_bytes=item.size_bytes,
                        mtime_ns=item.mtime_ns,
                        availability=availability,
                        last_seen_at=now,
                        updated_at=now,
                        device_id=item.device_id,
                        inode=item.inode,
                        normalized_path_cache=rel.lower(),
                    )
                )
                fts_ids.append(prior.id)
                probe_sample_ids.append(prior.id)
                updated += 1

        if index % 50 == 0 or index == len(discovered):
            progress_job = persist_progress(
                conn,
                compare_job,
                stage="upsert",
                progress_current=index,
                progress_total=len(discovered),
            )
        else:
            progress_job = replace(
                compare_job,
                stage="upsert",
                progress_current=index,
                progress_total=len(discovered),
            )
        _emit_progress(progress, progress_job)

    # Mark unseen as missing only after successful enumeration.
    missing = 0
    for rel, prior in existing.items():
        if rel in seen_paths:
            continue
        samples_repo.update(
            replace(
                prior,
                availability=SampleAvailability.MISSING,
                updated_at=now,
            )
        )
        missing += 1

    for sample_id in fts_ids:
        search.refresh_sample(sample_id)

    sources_repo.update(
        replace(
            source,
            status=SourceStatus.ONLINE if source.enabled else SourceStatus.DISABLED,
            last_scan_completed_at=now,
            last_seen_at=now,
            updated_at=now,
        )
    )
    completed = replace(
        compare_job,
        state=JobState.COMPLETED,
        stage="commit",
        completed_at=now,
        error_code=None,
        progress_current=len(discovered),
        progress_total=len(discovered),
        summary_json=json.dumps(
            {
                "inserted": inserted,
                "updated": updated,
                "unchanged": unchanged,
                "missing": missing,
                "discovered": len(discovered),
                "mode": str(mode),
                "probe_sample_ids": [str(sample_id) for sample_id in probe_sample_ids],
            }
        ),
    )
    jobs_repo.update(completed)
    _emit_progress(progress, completed, force=True)
    return completed


def _emit_progress(
    progress: ProgressThrottle | None,
    job: Job,
    *,
    force: bool = False,
) -> None:
    if progress is None:
        return
    progress.publish(
        ProgressEvent(
            job_id=job.id,
            state=job.state,
            stage=job.stage,
            current=job.progress_current,
            total=job.progress_total,
        ),
        force=force,
    )
