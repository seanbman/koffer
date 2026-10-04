"""S01 Library Browser with paged table, S02 filter foundations, Inspector binding."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.query import SampleFilters, SampleQuery
from koffer.ui.models.sample_table import SampleTableModel
from koffer.ui.widgets.filter_panel import FilterPanel
from koffer.ui.widgets.inspector import InspectorPanel


class LibraryBrowserScreen(QWidget):
    """S01: search/filter header + paged Sample table + Inspector (docs/12, docs/15)."""

    selection_changed = Signal(object, str)  # sample_id | None, name
    open_sample_detail_requested = Signal(str)  # sample_id

    def __init__(
        self,
        context: AppContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("libraryBrowser")
        self._context = context
        self._model = SampleTableModel(context.search_service, parent=self)
        self._auto_preview = False  # docs/28 default OFF

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Library")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self._count_label = QLabel("0 samples")
        self._count_label.setObjectName("bodyText")
        header.addWidget(self._count_label)
        root.addLayout(header)

        search_row = QHBoxLayout()
        self._search_field = QLineEdit()
        self._search_field.setObjectName("librarySearchField")
        self._search_field.setPlaceholderText("Search samples…")
        self._search_field.setClearButtonEnabled(True)
        self._search_field.returnPressed.connect(self._apply_text_query)
        self._search_field.textChanged.connect(self._on_text_changed)
        search_row.addWidget(self._search_field, stretch=1)

        self._filters_btn = QPushButton("Filters")
        self._filters_btn.setObjectName("secondaryButton")
        self._filters_btn.setCheckable(True)
        self._filters_btn.toggled.connect(self._toggle_filters)
        search_row.addWidget(self._filters_btn)
        root.addLayout(search_row)

        self._filter_panel = FilterPanel()
        self._filter_panel.setVisible(False)
        self._filter_panel.filters_changed.connect(self._on_filters_changed)
        root.addWidget(self._filter_panel)

        body = QHBoxLayout()
        body.setSpacing(0)

        self._table = QTableView()
        self._table.setObjectName("sampleTable")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(False)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_double_clicked)
        body.addWidget(self._table, stretch=1)

        self._inspector = InspectorPanel()
        open_detail = QPushButton("Open Sample")
        open_detail.setObjectName("openSampleDetailButton")
        open_detail.clicked.connect(self._emit_open_detail)
        inspector_column = QVBoxLayout()
        inspector_column.setContentsMargins(0, 0, 0, 0)
        inspector_column.setSpacing(8)
        inspector_column.addWidget(self._inspector, stretch=1)
        inspector_column.addWidget(open_detail)
        inspector_wrap = QWidget()
        inspector_wrap.setLayout(inspector_column)
        body.addWidget(inspector_wrap)
        root.addLayout(body, stretch=1)

        self.refresh()

    @property
    def model(self) -> SampleTableModel:
        return self._model

    @property
    def inspector(self) -> InspectorPanel:
        return self._inspector

    @property
    def filter_panel(self) -> FilterPanel:
        return self._filter_panel

    @property
    def table(self) -> QTableView:
        return self._table

    def focus_search(self) -> None:
        self._search_field.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search_field.selectAll()

    def refresh(self) -> None:
        """Reload counts/rows for the active query (e.g. after a scan)."""
        selected = self._selected_sample_id()
        self._model.refresh()
        self._sync_count()
        if selected is not None:
            self._restore_selection(selected)

    def selected_sample_id(self) -> str | None:
        return self._selected_sample_id()

    def show_filters(self, visible: bool = True) -> None:
        self._filters_btn.setChecked(visible)

    def load_selection_into_playback(self) -> None:
        """Resolve selected Sample media and load it into PlaybackService (no auto-play)."""
        sample_id = self._selected_sample_id()
        if sample_id is None:
            return
        path = self._context.resolve_sample_media_path(EntityId(sample_id))
        if path is None or not path.is_file():
            return
        try:
            self._context.playback_service.load(EntityId(sample_id), path)
        except ApplicationError:
            return

    def _toggle_filters(self, checked: bool) -> None:
        self._filter_panel.setVisible(checked)

    def _on_filters_changed(self, filters: object) -> None:
        if not isinstance(filters, SampleFilters):
            return
        current = self._model.query
        self._model.set_query(
            SampleQuery(
                version=current.version,
                text=current.text,
                filters=filters,
                sort=current.sort,
            )
        )
        self._sync_count()

    def _on_text_changed(self, _text: str) -> None:
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

    def _selected_sample_id(self) -> str | None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.sample_id_at(indexes[0].row())

    def _restore_selection(self, sample_id: str) -> None:
        for row in range(self._model.rowCount()):
            if self._model.sample_id_at(row) == sample_id:
                index = self._model.index(row, 0)
                self._table.selectRow(row)
                self._table.setCurrentIndex(index)
                return

    def _on_selection_changed(self, *_args: object) -> None:
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            self._inspector.clear()
            self.selection_changed.emit(None, "")
            return
        row_index = indexes[0].row()
        sample_row = self._model.sample_row_at(row_index)
        if sample_row is None:
            self._inspector.clear()
            self.selection_changed.emit(None, "")
            return

        media = self._context.resolve_sample_media_path(sample_row.id)
        envelope = None
        media_path: str | None = None
        if media is not None and media.is_file():
            media_path = str(media)
            try:
                envelope = self._context.waveform_cache.get_or_build(sample_row.id, Path(media))
            except ApplicationError:
                envelope = None

        # Inspector updates must not clear/replace table selection context.
        selected_before = self._selected_sample_id()
        self._inspector.show_sample(sample_row, envelope=envelope, media_path=media_path)
        if self._selected_sample_id() != selected_before:
            self._restore_selection(str(sample_row.id))

        self.selection_changed.emit(str(sample_row.id), sample_row.name)

        # Auto-preview default OFF (docs/28): selection never starts playback.
        if self._auto_preview:
            self.load_selection_into_playback()
            self._context.playback_service.play()

    def _on_double_clicked(self, *_args: object) -> None:
        self._emit_open_detail()

    def _emit_open_detail(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is not None:
            self.open_sample_detail_requested.emit(sample_id)


# Backward-compatible alias used by older Phase 2 shell imports.
LibraryPlaceholderScreen = LibraryBrowserScreen
