"""PlaybackService: Qt Multimedia adapter (docs/07, docs/19, docs/27).

UI must not touch ``QMediaPlayer`` outside this adapter.
"""

from __future__ import annotations

import math
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from koffer.domain.errors import PathUnavailableError, ValidationError
from koffer.domain.ids import EntityId


class PlaybackState(StrEnum):
    """Normalized playback transport state exposed to UI/services."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


def gain_db_to_linear(gain_db: float) -> float:
    """Convert dB gain to linear amplitude; clamp to QAudioOutput range [0, 1]."""
    linear = math.pow(10.0, float(gain_db) / 20.0)
    if linear < 0.0:
        return 0.0
    if linear > 1.0:
        return 1.0
    return linear


class PlaybackService(QObject):
    """Event-driven Qt Multimedia playback adapter."""

    state_changed = Signal(str)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    loaded_sample_changed = Signal(object)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)

        self._sample_id: EntityId | None = None
        self._path: Path | None = None
        self._loop_start_ms: int | None = None
        self._loop_end_ms: int | None = None
        self._gain_db: float = 0.0
        self._state = PlaybackState.STOPPED
        self._suppress_loop = False

        self._audio.setVolume(gain_db_to_linear(self._gain_db))
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.errorOccurred.connect(self._on_error)

    @property
    def sample_id(self) -> EntityId | None:
        return self._sample_id

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def position_ms(self) -> int:
        return int(self._player.position())

    @property
    def duration_ms(self) -> int:
        return int(self._player.duration())

    @property
    def gain_db(self) -> float:
        return self._gain_db

    @property
    def loop_region(self) -> tuple[int | None, int | None]:
        return self._loop_start_ms, self._loop_end_ms

    @property
    def media_player(self) -> QMediaPlayer:
        """Internal adapter access for tests; UI must not use this."""
        return self._player

    def load(self, sample_id: EntityId, path: Path) -> None:
        """Load ``path`` for ``sample_id`` without mutating source bytes."""
        media = Path(path).expanduser()
        try:
            resolved = media.resolve(strict=False)
        except OSError as exc:
            raise PathUnavailableError(
                "Playback path could not be resolved",
                detail=str(exc),
                retryable=False,
            ) from exc
        if not resolved.is_file():
            raise PathUnavailableError(
                "Playback path is not a readable file",
                detail=str(resolved),
                retryable=False,
            )

        self._sample_id = sample_id
        self._path = resolved
        self._loop_start_ms = None
        self._loop_end_ms = None
        self._suppress_loop = True
        self._player.setSource(QUrl.fromLocalFile(str(resolved)))
        self._suppress_loop = False
        self._set_state(PlaybackState.STOPPED)
        self.loaded_sample_changed.emit(sample_id)

    def play(self) -> None:
        if self._path is None:
            raise ValidationError("No media loaded for playback")
        if self._loop_start_ms is not None and self._player.position() < self._loop_start_ms:
            self._player.setPosition(int(self._loop_start_ms))
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._suppress_loop = True
        self._player.stop()
        self._suppress_loop = False
        if self._loop_start_ms is not None:
            self._player.setPosition(int(self._loop_start_ms))

    def seek(self, position_ms: int) -> None:
        if position_ms < 0:
            raise ValidationError("seek position_ms must be >= 0", detail=str(position_ms))
        self._suppress_loop = True
        self._player.setPosition(int(position_ms))
        self._suppress_loop = False

    def set_loop(self, start_ms: int | None, end_ms: int | None) -> None:
        if start_ms is None and end_ms is None:
            self._loop_start_ms = None
            self._loop_end_ms = None
            return
        if start_ms is None or end_ms is None:
            raise ValidationError("Loop start_ms and end_ms must both be set or both cleared")
        if start_ms < 0 or end_ms < 0:
            raise ValidationError("Loop bounds must be >= 0")
        if end_ms <= start_ms:
            raise ValidationError(
                "Loop end_ms must be greater than start_ms",
                detail=f"start={start_ms} end={end_ms}",
            )
        self._loop_start_ms = int(start_ms)
        self._loop_end_ms = int(end_ms)

    def set_gain_db(self, gain_db: float) -> None:
        self._gain_db = float(gain_db)
        self._audio.setVolume(gain_db_to_linear(self._gain_db))

    @Slot(QMediaPlayer.PlaybackState)
    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._set_state(PlaybackState.PLAYING)
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._set_state(PlaybackState.PAUSED)
        else:
            self._set_state(PlaybackState.STOPPED)

    @Slot(int)
    def _on_position_changed(self, position: int) -> None:
        self.position_changed.emit(int(position))
        if self._suppress_loop:
            return
        if (
            self._state == PlaybackState.PLAYING
            and self._loop_start_ms is not None
            and self._loop_end_ms is not None
            and position >= self._loop_end_ms
        ):
            self._suppress_loop = True
            self._player.setPosition(int(self._loop_start_ms))
            self._suppress_loop = False

    @Slot(int)
    def _on_duration_changed(self, duration: int) -> None:
        self.duration_changed.emit(int(duration))

    @Slot(QMediaPlayer.Error, str)
    def _on_error(self, _error: QMediaPlayer.Error, error_string: str) -> None:
        message = error_string.strip() or "Playback error"
        self.error.emit(message)

    def _set_state(self, state: PlaybackState) -> None:
        if self._state == state:
            return
        self._state = state
        self.state_changed.emit(state.value)
