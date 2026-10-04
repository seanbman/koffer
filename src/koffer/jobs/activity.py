"""Activity Center grouping helpers over durable Job rows (S16)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from koffer.domain.enums import ActivityGroup, JobState
from koffer.domain.models import Job


@dataclass(frozen=True, slots=True)
class JobSummary:
    """UI read model for one Activity Center row."""

    job: Job
    group: ActivityGroup
    title: str
    detail: str
    succeeded: int
    failed: int
    skipped: int


_RUNNING = frozenset(
    {
        JobState.RUNNING,
        JobState.PAUSE_REQUESTED,
        JobState.PAUSED,
        JobState.CANCEL_REQUESTED,
    }
)
_QUEUED = frozenset({JobState.QUEUED})
_COMPLETED = frozenset({JobState.COMPLETED, JobState.CANCELLED})
_ATTENTION = frozenset(
    {
        JobState.FAILED,
        JobState.COMPLETED_WITH_ERRORS,
        JobState.INTERRUPTED,
    }
)


def activity_group_for_state(state: JobState) -> ActivityGroup:
    if state in _RUNNING:
        return ActivityGroup.RUNNING
    if state in _QUEUED:
        return ActivityGroup.QUEUED
    if state in _ATTENTION:
        return ActivityGroup.NEEDS_ATTENTION
    return ActivityGroup.COMPLETED


def summarize_job(job: Job) -> JobSummary:
    succeeded, failed, skipped = _counts(job)
    scope_hint = _scope_hint(job)
    type_label = str(job.type).replace("_", " ")
    title = f"{type_label} · {scope_hint}" if scope_hint else type_label
    if job.progress_total is not None:
        detail = f"{job.progress_current} / {job.progress_total}"
        if job.stage:
            detail = f"{job.stage} · {detail}"
    elif job.stage:
        detail = job.stage
    else:
        detail = str(job.state)
    if job.error_code:
        detail = f"{detail} · {job.error_code}"
    return JobSummary(
        job=job,
        group=activity_group_for_state(job.state),
        title=title,
        detail=detail,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
    )


def group_summaries(jobs: list[Job]) -> dict[ActivityGroup, list[JobSummary]]:
    grouped: dict[ActivityGroup, list[JobSummary]] = {
        ActivityGroup.RUNNING: [],
        ActivityGroup.QUEUED: [],
        ActivityGroup.NEEDS_ATTENTION: [],
        ActivityGroup.COMPLETED: [],
    }
    for job in jobs:
        summary = summarize_job(job)
        grouped[summary.group].append(summary)
    for group in grouped:
        grouped[group].sort(key=lambda item: (item.job.created_at, str(item.job.id)), reverse=True)
    return grouped


def _counts(job: Job) -> tuple[int, int, int]:
    if not job.summary_json:
        return 0, 0, 0
    try:
        payload = json.loads(job.summary_json)
    except json.JSONDecodeError:
        return 0, 0, 0
    if not isinstance(payload, dict):
        return 0, 0, 0
    return (
        int(payload.get("succeeded") or payload.get("inserted") or 0),
        int(payload.get("failed") or 0),
        int(payload.get("skipped") or 0),
    )


def _scope_hint(job: Job) -> str:
    try:
        scope = json.loads(job.scope_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(scope, dict):
        return ""
    for key in ("source_id", "sample_id", "label", "path"):
        value = scope.get(key)
        if isinstance(value, str) and value:
            return value if len(value) <= 48 else f"{value[:45]}..."
    sample_ids = scope.get("sample_ids")
    if isinstance(sample_ids, list) and sample_ids:
        return f"{len(sample_ids)} samples"
    item_count = scope.get("item_count")
    if isinstance(item_count, int):
        return f"{item_count} items"
    return ""
