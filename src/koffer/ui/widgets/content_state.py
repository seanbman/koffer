"""Shared empty / loading / error surfaces for owned screens (docs/13)."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from koffer.ui.tokens import CLAY, MUTED, RED, SURFACE_1, YELLOW

__all__ = ["ContentState", "ContentStatePanel"]


class ContentState(StrEnum):
    READY = "ready"
    EMPTY = "empty"
    LOADING = "loading"
    ERROR = "error"


class ContentStatePanel(QWidget):
    """Instructional empty/loading/error panel used across owned screens."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("contentStatePanel")
        self._state = ContentState.READY

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._title = QLabel("")
        self._title.setObjectName("contentStateTitle")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._body = QLabel("")
        self._body.setObjectName("contentStateBody")
        self._body.setWordWrap(True)
        layout.addWidget(self._body)

        self._safety = QLabel("")
        self._safety.setObjectName("contentStateSafety")
        self._safety.setWordWrap(True)
        layout.addWidget(self._safety)

        self.hide()

    @property
    def state(self) -> ContentState:
        return self._state

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def body_text(self) -> str:
        return self._body.text()

    def clear(self) -> None:
        """Hide the panel; content surface is ready."""
        self._state = ContentState.READY
        self._title.setText("")
        self._body.setText("")
        self._safety.setText("")
        self.hide()

    def show_empty(
        self,
        title: str,
        body: str,
        *,
        safety: str = "Existing audio files remain untouched.",
    ) -> None:
        self._state = ContentState.EMPTY
        self._title.setText(title)
        self._title.setStyleSheet(f"color: {CLAY}; font-size: 15px; font-weight: 700;")
        self._body.setText(body)
        self._body.setStyleSheet(f"color: {MUTED};")
        self._safety.setText(safety)
        self._safety.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self._apply_frame(SURFACE_1)
        self.show()

    def show_loading(self, message: str = "Loading…") -> None:
        self._state = ContentState.LOADING
        self._title.setText("Loading")
        self._title.setStyleSheet(f"color: {YELLOW}; font-size: 15px; font-weight: 700;")
        self._body.setText(message)
        self._body.setStyleSheet(f"color: {MUTED};")
        self._safety.setText("Background work continues; the UI stays interactive.")
        self._safety.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self._apply_frame(SURFACE_1)
        self.show()

    def show_error(self, title: str, body: str) -> None:
        self._state = ContentState.ERROR
        self._title.setText(title)
        self._title.setStyleSheet(f"color: {RED}; font-size: 15px; font-weight: 700;")
        self._body.setText(body)
        self._body.setStyleSheet(f"color: {MUTED};")
        self._safety.setText("No source audio was modified by this failure.")
        self._safety.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self._apply_frame("#241818")
        self.show()

    def _apply_frame(self, background: str) -> None:
        self.setStyleSheet(
            f"QWidget#contentStatePanel {{"
            f" background-color: {background};"
            f" border: 1px solid #30363D;"
            f" border-radius: 6px;"
            f"}}"
        )
