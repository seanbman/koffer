"""Unit tests for throttled Job progress emission."""

from __future__ import annotations

from koffer.domain.enums import JobState
from koffer.domain.ids import new_entity_id
from koffer.jobs.progress import ProgressEvent, ProgressThrottle


def test_progress_throttle_limits_rapid_running_updates() -> None:
    throttle = ProgressThrottle(min_interval_s=10.0)
    job_id = new_entity_id()
    emitted: list[ProgressEvent] = []
    throttle.add_listener(emitted.append)

    first = ProgressEvent(
        job_id=job_id,
        state=JobState.RUNNING,
        stage="items",
        current=1,
        total=100,
    )
    second = ProgressEvent(
        job_id=job_id,
        state=JobState.RUNNING,
        stage="items",
        current=2,
        total=100,
    )
    assert throttle.publish(first) is True
    assert throttle.publish(second) is False
    assert len(emitted) == 1

    # State change always emits.
    cancel = ProgressEvent(
        job_id=job_id,
        state=JobState.CANCEL_REQUESTED,
        stage="cancel_requested",
        current=2,
        total=100,
    )
    assert throttle.publish(cancel) is True
    assert len(emitted) == 2

    # Final progress always emits.
    final = ProgressEvent(
        job_id=job_id,
        state=JobState.RUNNING,
        stage="items",
        current=100,
        total=100,
    )
    assert throttle.publish(final) is True
    assert len(emitted) == 3
