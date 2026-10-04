"""Bottom transport bar bound exclusively to PlaybackService."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from koffer.services.playback import PlaybackService, PlaybackState


class TransportBar(QWidget):
    """Play/pause/stop + now-playing label; UI never touches QMediaPlayer."""

    def __init__(
        self,
        playback: PlaybackService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("transportBar")
        self.setFixedHeight(64)
        self._playback = playback
        self._selected_sample_id: str | None = None
        self._selected_name: str = ""
        self._load_selection: Callable[[], None] | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        self._play_btn = QPushButton("Play")
        self._play_btn.setObjectName("primaryButton")
        self._play_btn.clicked.connect(self._on_play)
        layout.addWidget(self._play_btn)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setObjectName("secondaryButton")
        self._pause_btn.clicked.connect(self._playback.pause)
        layout.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("secondaryButton")
        self._stop_btn.clicked.connect(self._playback.stop)
        layout.addWidget(self._stop_btn)

        self._title = QLabel("No selection")
        self._title.setObjectName("bodyText")
        layout.addWidget(self._title, stretch=1)

        self._state_label = QLabel(PlaybackState.STOPPED.value)
        self._state_label.setObjectName("sectionLabel")
        layout.addWidget(self._state_label)

        self._playback.state_changed.connect(self._on_state_changed)
        self._playback.loaded_sample_changed.connect(self._on_loaded)

    @property
    def selected_sample_id(self) -> str | None:
        return self._selected_sample_id

    def set_selection(self, sample_id: str | None, name: str = "") -> None:
        """Track browser selection for explicit Play (auto-preview remains OFF)."""
        self._selected_sample_id = sample_id
        self._selected_name = name
        if sample_id is None:
            self._title.setText("No selection")
        else:
            self._title.setText(name or sample_id)

    def play_selection(self) -> None:
        """Load+play the current browser selection via PlaybackService."""
        self._on_play()

    def bind_selection_loader(self, loader: Callable[[], None]) -> None:
        """Register loader that resolves selected media into PlaybackService."""
        self._load_selection = loader

    def _on_play(self) -> None:
        if self._load_selection is not None:
            self._load_selection()
        if self._playback.path is None:
            return
        self._playback.play()

    @Slot(str)
    def _on_state_changed(self, state: str) -> None:
        self._state_label.setText(state)
        if state == PlaybackState.PLAYING.value:
            self._play_btn.setText("Playing")
        else:
            self._play_btn.setText("Play")

    @Slot(object)
    def _on_loaded(self, sample_id: object) -> None:
        if sample_id is not None and not self._selected_name:
            self._title.setText(str(sample_id))
