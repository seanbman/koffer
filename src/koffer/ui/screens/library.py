"""S01 Library Browser placeholder (Phase 2: empty browser acceptable)."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LibraryPlaceholderScreen(QWidget):
    """Workspace landing after first Source; full table arrives in Phase 3."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("libraryPlaceholder")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)

        title = QLabel("Library")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        body = QLabel(
            "Sample browser arrives in the next phase. Your Sources are indexing "
            "in the background — open Sources to watch status and scan Jobs."
        )
        body.setObjectName("bodyText")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch(1)
