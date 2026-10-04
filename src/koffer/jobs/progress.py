"""Throttled Job progress events so UI queues are not flooded (docs/18)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from koffer.domain.enums import JobState
from koffer.domain.ids import EntityId


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """UI-facing Job progress snapshot."""

    job_id: EntityId
    state: JobState
    stage: str | None
    current: int
    total: int | None
    message: str | None = None
    active_item: str | None = None
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


ProgressListener = Callable[[ProgressEvent], None]


class ProgressThrottle:
    """Emit progress at most once per interval unless state/stage/final force it."""

    def __init__(self, min_interval_s: float = 0.05) -> None:
        self._min_interval_s = max(0.0, float(min_interval_s))
        self._lock = threading.Lock()
        self._last_emit_mono: dict[str, float] = {}
        self._last_event: dict[str, ProgressEvent] = {}
        self._listeners: list[ProgressListener] = []

    def add_listener(self, listener: ProgressListener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(self, listener: ProgressListener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def should_emit(self, event: ProgressEvent, *, force: bool = False) -> bool:
        """Return True when ``event`` should be published."""
        key = str(event.job_id)
        now = time.monotonic()
        with self._lock:
            prev = self._last_event.get(key)
            if force or prev is None:
                self._accept(key, event, now)
                return True
            if prev.state is not event.state or prev.stage != event.stage:
                self._accept(key, event, now)
                return True
            if event.total is not None and event.current >= event.total:
                self._accept(key, event, now)
                return True
            if event.state not in {
                JobState.RUNNING,
                JobState.QUEUED,
                JobState.PAUSE_REQUESTED,
                JobState.PAUSED,
                JobState.CANCEL_REQUESTED,
            }:
                # Terminal / attention states always publish.
                self._accept(key, event, now)
                return True
            last = self._last_emit_mono.get(key, 0.0)
            if now - last >= self._min_interval_s:
                self._accept(key, event, now)
                return True
            return False

    def publish(self, event: ProgressEvent, *, force: bool = False) -> bool:
        """Publish ``event`` to listeners when not throttled; return whether emitted."""
        if not self.should_emit(event, force=force):
            return False
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            listener(event)
        return True

    def _accept(self, key: str, event: ProgressEvent, now: float) -> None:
        self._last_emit_mono[key] = now
        self._last_event[key] = event
