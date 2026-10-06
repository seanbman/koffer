"""Persistent bottom transport bound exclusively to PlaybackService."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from koffer.services.playback import PlaybackService, PlaybackState


def _format_time(milliseconds: int) -> str:
    """Format a non-negative media position as MM:SS.mmm."""
    value = max(0, int(milliseconds))
    minutes, remainder = divmod(value, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


class TransportBar(QWidget):
    """Global preview controls, playhead and gain status."""

    def __init__(
        self,
        playback: PlaybackService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("transportBar")
        self.setFixedHeight(72)
        self._playback = playback
        self._selected_sample_id: str | None = None
        self._selected_name = ""
        self._load_selection: Callable[[], None] | None = None
        self._duration_ms = 0
        self._seeking = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("transportPlayButton")
        self._play_btn.setAccessibleName("Play or pause preview")
        self._play_btn.setFixedWidth(40)
        self._play_btn.clicked.connect(self._on_play)
        layout.addWidget(self._play_btn)

        self._stop_btn = QPushButton("■")
        self._stop_btn.setObjectName("transportStopButton")
        self._stop_btn.setAccessibleName("Stop preview")
        self._stop_btn.setFixedWidth(36)
        self._stop_btn.clicked.connect(self._playback.stop)
        layout.addWidget(self._stop_btn)

        identity = QVBoxLayout()
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(2)
        self._title = QLabel("No sample playing")
        self._title.setObjectName("transportTitle")
        identity.addWidget(self._title)
        self._time = QLabel("00:00.000 / 00:00.000")
        self._time.setObjectName("transportTime")
        identity.addWidget(self._time)
        layout.addLayout(identity)

        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setObjectName("transportSeek")
        self._seek.setRange(0, 0)
        self._seek.setAccessibleName("Preview position")
        self._seek.sliderPressed.connect(self._on_seek_started)
        self._seek.sliderReleased.connect(self._on_seek_released)
        self._seek.sliderMoved.connect(self._on_seek_preview)
        layout.addWidget(self._seek, stretch=1)

        gain = QVBoxLayout()
        gain.setContentsMargins(0, 0, 0, 0)
        gain.setSpacing(2)
        preview = QLabel("PREVIEW")
        preview.setObjectName("sectionLabel")
        gain.addWidget(preview, alignment=Qt.AlignmentFlag.AlignRight)
        self._gain_label = QLabel(f"{self._playback.gain_db:g} dB")
        self._gain_label.setObjectName("transportGain")
        gain.addWidget(self._gain_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(gain)

        self._playback.state_changed.connect(self._on_state_changed)
        self._playback.loaded_sample_changed.connect(self._on_loaded)
        self._playback.position_changed.connect(self._on_position_changed)
        self._playback.duration_changed.connect(self._on_duration_changed)

    @property
    def selected_sample_id(self) -> str | None:
        return self._selected_sample_id

    @property
    def position_text(self) -> str:
        return self._time.text()

    def set_selection(self, sample_id: str | None, name: str = "") -> None:
        """Track browser selection for explicit Play; selection does not auto-play."""
        self._selected_sample_id = sample_id
        self._selected_name = name
        if sample_id is None:
            if self._playback.sample_id is None:
                self._title.setText("No sample playing")
            return
        self._title.setText(name or sample_id)

    def play_selection(self) -> None:
        """Load and play the current browser selection through PlaybackService."""
        self._on_play()

    def bind_selection_loader(self, loader: Callable[[], None]) -> None:
        """Register loader that resolves selected media into PlaybackService."""
        self._load_selection = loader

    def _on_play(self) -> None:
        if self._playback.state is PlaybackState.PLAYING:
            self._playback.pause()
            return
        if self._load_selection is not None:
            self._load_selection()
        if self._playback.path is None:
            return
        self._playback.play()

    @Slot(str)
    def _on_state_changed(self, state: str) -> None:
        self._play_btn.setText("❚❚" if state == PlaybackState.PLAYING.value else "▶")

    @Slot(object)
    def _on_loaded(self, sample_id: object) -> None:
        if sample_id is None:
            return
        if not self._selected_name:
            self._title.setText(str(sample_id))
        self._duration_ms = max(0, self._playback.duration_ms)
        self._seek.setRange(0, self._duration_ms)
        self._sync_time(self._playback.position_ms)

    @Slot(int)
    def _on_position_changed(self, position: int) -> None:
        if not self._seeking:
            self._seek.setValue(max(0, int(position)))
        self._sync_time(position)

    @Slot(int)
    def _on_duration_changed(self, duration: int) -> None:
        self._duration_ms = max(0, int(duration))
        self._seek.setRange(0, self._duration_ms)
        self._sync_time(self._playback.position_ms)

    def _on_seek_started(self) -> None:
        self._seeking = True

    def _on_seek_released(self) -> None:
        self._seeking = False
        self._playback.seek(self._seek.value())

    def _on_seek_preview(self, position: int) -> None:
        self._sync_time(position)

    def _sync_time(self, position: int) -> None:
        self._time.setText(f"{_format_time(position)} / {_format_time(self._duration_ms)}")
