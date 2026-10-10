"""S01 Library Browser with paged table, S02 filter foundations, Inspector binding."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.audio.waveform import PeakEnvelope, WaveformCache
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.query import (
    SampleFilters,
    SampleQuery,
    SavedSearch,
    SortDirection,
    SortField,
    SortSpec,
)
from koffer.services.playback import PlaybackState
from koffer.ui.models.sample_table import SampleTableModel
from koffer.ui.widgets.content_state import ContentState, ContentStatePanel
from koffer.ui.widgets.filter_panel import FilterPanel
from koffer.ui.widgets.inspector import InspectorPanel


class _WaveformSignals(QObject):
    completed = Signal(str, object)


class _WaveformTask(QRunnable):
    def __init__(
        self,
        cache: WaveformCache,
        sample_id: EntityId,
        media_path: Path,
        signals: _WaveformSignals,
    ) -> None:
        super().__init__()
        self._cache = cache
        self._sample_id = sample_id
        self._media_path = media_path
        self._signals = signals

    @Slot()
    def run(self) -> None:
        envelope: PeakEnvelope | None
        try:
            envelope = self._cache.get_or_build(self._sample_id, self._media_path)
        except Exception:
            envelope = None
        self._signals.completed.emit(str(self._sample_id), envelope)


class LibraryBrowserScreen(QWidget):
    """S01: search/filter header + paged Sample table + Inspector (docs/12, docs/15)."""

    selection_changed = Signal(object, str)  # sample_id | None, name
    open_sample_detail_requested = Signal(str)  # sample_id
    play_requested = Signal(str)
    prepare_requested = Signal(str)
    edit_metadata_requested = Signal(str)
    find_similar_requested = Signal(str)
    add_to_collection_requested = Signal(str)
    favourite_changed = Signal(str, bool)
    saved_searches_changed = Signal()

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
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(150)
        self._search_debounce.timeout.connect(self._apply_text_query)
        self._waveform_signals = _WaveformSignals(self)
        self._waveform_signals.completed.connect(self._on_waveform_ready)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        self._title = QLabel("All Samples")
        self._title.setObjectName("pageTitle")
        header.addWidget(self._title)
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
        self._filter_panel.save_requested.connect(self._save_current_search)
        root.addWidget(self._filter_panel)

        self._state_panel = ContentStatePanel()
        root.addWidget(self._state_panel)

        body = QHBoxLayout()
        body.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("libraryPaneSplitter")
        self._splitter.setChildrenCollapsible(False)

        self._table = QTableView()
        self._table.setObjectName("sampleTable")
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_double_clicked)
        self._splitter.addWidget(self._table)

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
        inspector_wrap.setObjectName("libraryInspectorColumn")
        inspector_wrap.setLayout(inspector_column)
        self._splitter.addWidget(inspector_wrap)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([900, 340])

        body.addWidget(self._splitter, stretch=1)
        root.addLayout(body, stretch=1)

        self._install_sample_shortcuts()
        self.refresh()

    def _install_sample_shortcuts(self) -> None:
        """Docs/28 Sample browser shortcuts (active while this screen is focused)."""
        bindings: list[tuple[str, str, object]] = [
            ("Space", "libraryPlayShortcut", self._action_play),
            ("Return", "libraryOpenDetailShortcut", self._emit_open_detail),
            ("Ctrl+D", "libraryFavouriteShortcut", self._action_favourite),
            ("Ctrl+Shift+C", "libraryAddCollectionShortcut", self._action_add_to_collection),
            ("Ctrl+Shift+S", "libraryFindSimilarShortcut", self._action_find_similar),
            ("Ctrl+M", "libraryEditMetadataShortcut", self._action_edit_metadata),
            ("Ctrl+P", "libraryPrepareShortcut", self._action_prepare),
        ]
        for sequence, object_name, slot in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setObjectName(object_name)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

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

    @property
    def splitter(self) -> QSplitter:
        return self._splitter

    @property
    def state_panel(self) -> ContentStatePanel:
        return self._state_panel

    @property
    def search_field(self) -> QLineEdit:
        return self._search_field

    @property
    def view_title(self) -> str:
        return self._title.text()

    def show_all_samples(self) -> None:
        """Open the canonical unscoped library view."""
        self._apply_named_view(
            "All Samples",
            SampleQuery(sort=SortSpec(field=SortField.NAME, direction=SortDirection.ASC)),
        )

    def show_favourites(self) -> None:
        """Open the dynamic Favourites library view."""
        self._apply_named_view(
            "Favourites",
            SampleQuery(
                filters=SampleFilters(favorite=True),
                sort=SortSpec(field=SortField.NAME, direction=SortDirection.ASC),
            ),
        )

    def show_recents(self) -> None:
        """Open Samples that have actually been previewed, newest first."""
        self._apply_named_view(
            "Recents",
            SampleQuery(
                filters=SampleFilters(previewed_only=True),
                sort=SortSpec(field=SortField.LAST_USED, direction=SortDirection.DESC),
            ),
        )

    def show_saved_search(self, saved: SavedSearch) -> None:
        """Open a persisted dynamic SampleQuery without converting it to a static list."""
        self._apply_named_view(saved.name, saved.query)

    def focus_search(self) -> None:
        self._search_field.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search_field.selectAll()

    def _apply_named_view(self, title: str, query: SampleQuery) -> None:
        self._title.setText(title)
        self._search_field.blockSignals(True)
        self._search_field.setText(query.text)
        self._search_field.blockSignals(False)
        self._filter_panel.set_filters(query.filters)
        self._model.set_query(query)
        self._sync_count()
        self._sync_content_state()

    def _save_current_search(self) -> None:
        name, accepted = QInputDialog.getText(self, "Save Search", "Saved search name")
        if not accepted or not name.strip():
            return
        try:
            self._context.search_service.save_search(name, self._model.query)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not save search", str(exc))
            return
        self.saved_searches_changed.emit()

    def clear_search_or_defocus(self) -> bool:
        """Escape while search focused: clear text once, then return focus to table."""
        if not self._search_field.hasFocus():
            return False
        if self._search_field.text():
            self._search_field.clear()
            return True
        self._table.setFocus(Qt.FocusReason.ShortcutFocusReason)
        return True

    def refresh(self) -> None:
        """Reload counts/rows for the active query (e.g. after a scan)."""
        selected = self._selected_sample_id()
        self._state_panel.show_loading("Refreshing library…")
        try:
            self._model.refresh()
            self._sync_count()
            if selected is not None:
                self._restore_selection(selected)
            self._sync_content_state()
        except ApplicationError as exc:
            self._state_panel.show_error("Library refresh failed", str(exc))
            self._table.setVisible(False)

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

    def build_sample_context_menu(self) -> QMenu:
        """Sample actions from docs/28 — used by context menu and tests."""
        menu = QMenu(self)
        menu.setObjectName("sampleContextMenu")
        sample_id = self._selected_sample_id()
        enabled = sample_id is not None

        play = QAction("Play / Pause", menu)
        play.setObjectName("sampleContextPlay")
        play.setEnabled(enabled)
        play.triggered.connect(self._action_play)
        menu.addAction(play)

        favourite = QAction("Favourite", menu)
        favourite.setObjectName("sampleContextFavourite")
        favourite.setEnabled(enabled)
        favourite.triggered.connect(self._action_favourite)
        menu.addAction(favourite)

        add_collection = QAction("Add to Collection…", menu)
        add_collection.setObjectName("sampleContextAddToCollection")
        add_collection.setEnabled(enabled)
        add_collection.triggered.connect(self._action_add_to_collection)
        menu.addAction(add_collection)

        prepare = QAction("Edit Sound…", menu)
        prepare.setObjectName("sampleContextPrepare")
        prepare.setEnabled(enabled)
        prepare.triggered.connect(self._action_prepare)
        menu.addAction(prepare)

        edit_metadata = QAction("Edit Metadata…", menu)
        edit_metadata.setObjectName("sampleContextEditMetadata")
        edit_metadata.setEnabled(enabled)
        edit_metadata.triggered.connect(self._action_edit_metadata)
        menu.addAction(edit_metadata)

        return menu

    def _on_context_menu(self, pos: object) -> None:
        from PySide6.QtCore import QPoint

        point = pos if isinstance(pos, QPoint) else self._table.viewport().rect().center()
        index = self._table.indexAt(point)
        if index.isValid():
            self._table.selectRow(index.row())
        menu = self.build_sample_context_menu()
        menu.exec(self._table.viewport().mapToGlobal(point))

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
        self._sync_content_state()

    def _on_text_changed(self, _text: str) -> None:
        self._search_debounce.start()

    def _apply_text_query(self) -> None:
        self._search_debounce.stop()
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
        self._sync_content_state()

    def _sync_count(self) -> None:
        total = self._model.rowCount()
        label = "sample" if total == 1 else "samples"
        self._count_label.setText(f"{total} {label}")

    def _sync_content_state(self) -> None:
        total = self._model.rowCount()
        if total == 0:
            query_text = self._model.query.text.strip()
            if query_text or not self._model.query.filters.is_empty():
                self._state_panel.show_empty(
                    "No matching Samples",
                    "Try clearing search or filters. Indexed audio stays safe.",
                )
            else:
                self._state_panel.show_empty(
                    "Library is empty",
                    "Add a Source to index Samples. Nothing is copied until you choose Copy/Move.",
                )
            self._table.setVisible(False)
            return
        if self._state_panel.state is not ContentState.READY:
            self._state_panel.clear()
        self._table.setVisible(True)

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
        media_path: str | None = None
        if media is not None and media.is_file():
            media_path = str(media)

        # Inspector updates must not clear/replace table selection context.
        selected_before = self._selected_sample_id()
        self._inspector.show_sample(sample_row, envelope=None, media_path=media_path)
        if media is not None and media.is_file():
            self._inspector.set_waveform(None, loading=True)
            task = _WaveformTask(
                self._context.waveform_cache,
                sample_row.id,
                Path(media),
                self._waveform_signals,
            )
            QThreadPool.globalInstance().start(task)
        if self._selected_sample_id() != selected_before:
            self._restore_selection(str(sample_row.id))

        self.selection_changed.emit(str(sample_row.id), sample_row.name)

        # Auto-preview default OFF (docs/28): selection never starts playback.
        if self._auto_preview:
            self.load_selection_into_playback()
            self._context.playback_service.play()

    @Slot(str, object)
    def _on_waveform_ready(self, sample_id: str, envelope: object) -> None:
        """Apply a background waveform only if its Sample remains selected."""
        if self._selected_sample_id() != sample_id:
            return
        resolved = envelope if isinstance(envelope, PeakEnvelope) else None
        self._inspector.set_waveform(resolved)

    def _on_double_clicked(self, *_args: object) -> None:
        self._emit_open_detail()

    def _emit_open_detail(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is not None:
            self.open_sample_detail_requested.emit(sample_id)

    def _action_play(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is None:
            return
        self.load_selection_into_playback()
        playback = self._context.playback_service
        if playback.state is PlaybackState.PLAYING:
            playback.pause()
        else:
            playback.play()
        self.play_requested.emit(sample_id)

    def _action_favourite(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is None:
            return
        try:
            updated = self._context.sample_service.toggle_favorite(EntityId(sample_id))
        except ApplicationError as exc:
            self._state_panel.show_error("Could not update Favourite", str(exc))
            return
        self.favourite_changed.emit(sample_id, updated.favorite)
        self.refresh()

    def _action_add_to_collection(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is None:
            return
        collections = self._context.collection_service.list_with_counts()
        if not collections:
            name, accepted = QInputDialog.getText(
                self,
                "Add to Collection",
                "No Collections yet. Name a new Collection:",
            )
            if not accepted or not name.strip():
                return
            try:
                collection = self._context.collection_service.create(name.strip())
                self._context.collection_service.add_samples(collection.id, [EntityId(sample_id)])
            except ApplicationError as exc:
                QMessageBox.warning(self, "Could not add to Collection", str(exc))
                return
            self.add_to_collection_requested.emit(sample_id)
            return

        labels = [item.collection.name for item in collections]
        choice, accepted = QInputDialog.getItem(
            self,
            "Add to Collection",
            "Collection:",
            labels,
            0,
            False,
        )
        if not accepted or not choice:
            return
        selected = next(
            (item for item in collections if item.collection.name == choice),
            None,
        )
        if selected is None:
            return
        try:
            self._context.collection_service.add_samples(
                selected.collection.id, [EntityId(sample_id)]
            )
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not add to Collection", str(exc))
            return
        self.add_to_collection_requested.emit(sample_id)

    def _action_prepare(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is not None:
            self.prepare_requested.emit(sample_id)

    def _action_edit_metadata(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is not None:
            self.edit_metadata_requested.emit(sample_id)

    def _action_find_similar(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is not None:
            self.find_similar_requested.emit(sample_id)


# Backward-compatible alias used by older Phase 2 shell imports.
LibraryPlaceholderScreen = LibraryBrowserScreen
