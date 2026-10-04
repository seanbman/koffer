"""S00 Welcome / First Run."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.ui.tokens import CLAY, MUTED


class WelcomeScreen(QWidget):
    """Sparse first-run screen: safety promises + Add First Source."""

    add_source_requested = Signal()
    directory_dropped = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomeScreen")
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 48, 48, 48)
        root.setSpacing(20)

        brand = QLabel("Koffer")
        brand.setObjectName("pageTitle")
        brand.setStyleSheet(f"color: {CLAY}; font-size: 28px; font-weight: 700;")
        root.addWidget(brand)

        title = QLabel("Welcome — index your sample library in place")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        body = QLabel(
            "Koffer scans directories you authorize. Scanning never moves or renames "
            "your audio files. Core analysis stays local and works offline."
        )
        body.setObjectName("bodyText")
        body.setWordWrap(True)
        root.addWidget(body)

        promises = QHBoxLayout()
        promises.setSpacing(12)
        for heading, detail in (
            ("Files stay put", "Reference-first indexing. Adding a Source does not move audio."),
            ("Background scanning", "Discovery and analysis run as Jobs while you browse."),
            ("Works offline", "Your library remains usable when drives or networks drop."),
        ):
            card = QFrame()
            card.setObjectName("promiseCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            heading_label = QLabel(heading)
            heading_label.setObjectName("promiseTitle")
            detail_label = QLabel(detail)
            detail_label.setObjectName("bodyText")
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet(f"color: {MUTED};")
            card_layout.addWidget(heading_label)
            card_layout.addWidget(detail_label)
            promises.addWidget(card, stretch=1)
        root.addLayout(promises)

        actions = QHBoxLayout()
        self._add_button = QPushButton("Add First Source")
        self._add_button.setObjectName("addFirstSourceButton")
        self._add_button.setAccessibleName("Add First Source")
        self._add_button.setStyleSheet(
            "QPushButton#addFirstSourceButton {"
            " background-color: #CF8652; color: #0B0D0F; border: none;"
            " border-radius: 5px; padding: 8px 16px; min-height: 32px;"
            " font-weight: 600; }"
            "QPushButton#addFirstSourceButton:hover { background-color: #E7A36F; }"
        )
        self._add_button.clicked.connect(self.add_source_requested.emit)
        actions.addWidget(self._add_button)
        actions.addStretch(1)
        root.addLayout(actions)

        drop_hint = QLabel("Or drop a sample folder onto this window.")
        drop_hint.setObjectName("bodyText")
        root.addWidget(drop_hint)
        root.addStretch(1)

    @property
    def add_button(self) -> QPushButton:
        return self._add_button

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                local = url.toLocalFile()
                if local and Path(local).is_dir():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if not local:
                continue
            path = Path(local)
            if path.is_dir():
                self.directory_dropped.emit(path)
                event.acceptProposedAction()
                return
        event.ignore()
