"""S01 Library Browser with paged Sample table bound to SearchService."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.query import SampleQuery
from koffer.services.search import SearchService
from koffer.ui.models.sample_table import SampleTableModel


class LibraryBrowserScreen(QWidget):
    """S01: search header + sortable paged Sample table (docs/12, docs/15)."""

    def __init__(
        self,
        search_service: SearchService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("libraryBrowser")
        self._search = search_service
        self._model = SampleTableModel(search_service, parent=self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Library")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self._count_label = QLabel("0 samples")
        self._count_label.setObjectName("bodyText")
        header.addWidget(self._count_label)
        layout.addLayout(header)

        self._search_field = QLineEdit()
        self._search_field.setObjectName("librarySearchField")
        self._search_field.setPlaceholderText("Search samples…")
        self._search_field.setClearButtonEnabled(True)
        self._search_field.returnPressed.connect(self._apply_text_query)
        self._search_field.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._search_field)

        self._table = QTableView()
        self._table.setObjectName("sampleTable")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(False)  # sort goes through SampleQuery
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

        self.refresh()

    @property
    def model(self) -> SampleTableModel:
        return self._model

    def focus_search(self) -> None:
        self._search_field.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def refresh(self) -> None:
        """Reload counts/rows for the active query (e.g. after a scan)."""
        self._model.refresh()
        self._sync_count()

    def _on_text_changed(self, _text: str) -> None:
        # Live filter as the user types; cheap COUNT + page fetch.
        self._apply_text_query()

    def _apply_text_query(self) -> None:
        text = self._search_field.text().strip()
        current = self._model.query
        self._model.set_query(
            SampleQuery(
                version=current.version,
                text=text,
                filters=current.filters,
                sort=current.sort,
            )
        )
        self._sync_count()

    def _sync_count(self) -> None:
        total = self._model.rowCount()
        label = "sample" if total == 1 else "samples"
        self._count_label.setText(f"{total} {label}")


# Backward-compatible alias used by older Phase 2 shell imports.
LibraryPlaceholderScreen = LibraryBrowserScreen
