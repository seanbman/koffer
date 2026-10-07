"""S04 Collection Detail: scoped Sample browser and logical membership management."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
    PageRequest,
    SampleFilters,
    SampleQuery,
    SortDirection,
    SortField,
    SortSpec,
)
from koffer.services.search import SearchService
from koffer.ui.models.sample_table import SampleTableModel
from koffer.ui.tokens import MUTED
from koffer.ui.widgets.inspector import InspectorPanel

MIME_SAMPLE_IDS = "application/x-koffer-sample-ids"


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


class _SampleChooser(QDialog):
    """Small paged search chooser for adding multiple Samples to a Collection."""

    def __init__(
        self,
        search_service: SearchService,
        excluded_ids: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._search = search_service
        self._excluded_ids = excluded_ids
        self.setWindowTitle("Add Samples to Collection")
        self.resize(620, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        prompt = QLabel("Search the Library, then select one or more Samples.")
        prompt.setObjectName("bodyText")
        root.addWidget(prompt)

        self._query = QLineEdit()
        self._query.setObjectName("collectionAddSampleSearch")
        self._query.setPlaceholderText("Search samples…")
        self._query.textChanged.connect(self._refresh)
        root.addWidget(self._query)

        self._list = QListWidget()
        self._list.setObjectName("collectionAddSampleList")
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        root.addWidget(self._list, stretch=1)

        self._summary = QLabel("")
        self._summary.setObjectName("bodyText")
        root.addWidget(self._summary)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh()

    def selected_ids(self) -> list[EntityId]:
        ids: list[EntityId] = []
        for item in self._list.selectedItems():
            value = item.data(int(Qt.ItemDataRole.UserRole))
            if isinstance(value, str) and value:
                ids.append(EntityId(value))
        return ids

    def _refresh(self) -> None:
        query = SampleQuery(
            text=self._query.text().strip(),
            sort=SortSpec(field=SortField.NAME, direction=SortDirection.ASC),
        )
        page = self._search.search(query, PageRequest(offset=0, limit=200))
        self._list.clear()
        visible = 0
        for row in page.items:
            if str(row.id) in self._excluded_ids:
                continue
            item = QListWidgetItem(
                f"{row.name}\n{row.sample_type or 'Unclassified'} · "
                f"{row.extension.upper()} · {row.availability}"
            )
            item.setData(int(Qt.ItemDataRole.UserRole), str(row.id))
            self._list.addItem(item)
            visible += 1
        hidden = max(0, page.total - len(page.items))
        suffix = f" · {hidden} more match(es); refine search" if hidden else ""
        self._summary.setText(f"{visible} selectable Sample(s){suffix}")


class CollectionDetailScreen(QWidget):
    """Browser scoped to one Collection; membership never copies, moves, or deletes audio."""

    back_requested = Signal()
    membership_changed = Signal()
    selection_changed = Signal(object, str)
    open_sample_detail_requested = Signal(str)
    prepare_requested = Signal(str)

    def __init__(
        self,
        context: AppContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._collection_service = context.collection_service
        self._collection_id: EntityId | None = None
        self._collection_name = ""
        self._model = SampleTableModel(context.search_service, parent=self)
        self._waveform_signals = _WaveformSignals(self)
        self._waveform_signals.completed.connect(self._on_waveform_ready)
        self.setObjectName("collectionDetailScreen")
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        back = QPushButton("Back to Collections")
        back.setObjectName("backToCollectionsButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)

        self._title = QLabel("Collection Detail")
        self._title.setObjectName("pageTitle")
        header.addWidget(self._title)
        header.addStretch(1)

        edit = QPushButton("Edit Collection")
        edit.setObjectName("editCollectionButton")
        edit.clicked.connect(self._edit_collection)
        header.addWidget(edit)

        add = QPushButton("Add Samples")
        add.setObjectName("addCollectionSamplesButton")
        add.setProperty("class", "primaryButton")
        add.clicked.connect(self._choose_samples_to_add)
        header.addWidget(add)
        root.addLayout(header)

        self._description = QLabel("")
        self._description.setObjectName("collectionDetailDescription")
        self._description.setWordWrap(True)
        root.addWidget(self._description)

        meta_row = QHBoxLayout()
        self._count = QLabel("")
        self._count.setObjectName("collectionDetailCount")
        meta_row.addWidget(self._count)
        meta_row.addStretch(1)
        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.setObjectName("removeMembershipButton")
        self._remove_btn.clicked.connect(self._remove_selected)
        meta_row.addWidget(self._remove_btn)
        root.addLayout(meta_row)

        self._safety = QLabel(
            "Collection membership is logical only. Removing Samples here never copies, "
            "moves, or deletes audio files."
        )
        self._safety.setObjectName("collectionDetailSafety")
        self._safety.setWordWrap(True)
        self._safety.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._safety)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("collectionDetailSplitter")

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        self._table = QTableView()
        self._table.setObjectName("collectionSampleTable")
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._open_selected)
        center_layout.addWidget(self._table, stretch=1)

        self._empty = QLabel(
            "This Collection is empty. Use Add Samples or drag Samples here. "
            "No audio is duplicated."
        )
        self._empty.setObjectName("collectionDetailEmpty")
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet(f"color: {MUTED};")
        center_layout.addWidget(self._empty)

        self._splitter.addWidget(center)

        inspector_column = QVBoxLayout()
        inspector_column.setContentsMargins(0, 0, 0, 0)
        inspector_column.setSpacing(8)
        self._inspector = InspectorPanel()
        self._inspector.setObjectName("collectionInspectorPanel")
        inspector_column.addWidget(self._inspector, stretch=1)

        inspector_actions = QHBoxLayout()
        open_detail = QPushButton("Open Detail")
        open_detail.setObjectName("collectionOpenSampleDetailButton")
        open_detail.clicked.connect(self._open_selected)
        inspector_actions.addWidget(open_detail)

        prepare = QPushButton("Prepare")
        prepare.setObjectName("collectionPrepareSampleButton")
        prepare.setProperty("class", "primaryButton")
        prepare.clicked.connect(self._prepare_selected)
        inspector_actions.addWidget(prepare)
        inspector_column.addLayout(inspector_actions)

        inspector_wrap = QWidget()
        inspector_wrap.setObjectName("collectionInspectorColumn")
        inspector_wrap.setLayout(inspector_column)
        self._splitter.addWidget(inspector_wrap)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([900, 336])
        root.addWidget(self._splitter, stretch=1)

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def table(self) -> QTableView:
        return self._table

    @property
    def model(self) -> SampleTableModel:
        return self._model

    def show_collection(self, collection_id: EntityId) -> None:
        self._collection_id = collection_id
        self.refresh()

    def refresh(self) -> None:
        if self._collection_id is None:
            return
        detail = self._collection_service.get_detail(self._collection_id)
        collection = detail.collection
        self._collection_name = collection.name
        self._title.setText(collection.name)
        self._description.setText(collection.description or "No description")
        self._model.set_query(
            SampleQuery(
                filters=SampleFilters(collection_ids=(collection.id,)),
                sort=SortSpec(field=SortField.NAME, direction=SortDirection.ASC),
            )
        )
        count = self._model.rowCount()
        suffix = "s" if count != 1 else ""
        self._count.setText(f"{count} sample{suffix} · sort {collection.sort_mode}")
        empty = count == 0
        self._empty.setVisible(empty)
        self._table.setVisible(not empty)
        self._remove_btn.setEnabled(not empty)
        if empty:
            self._inspector.clear()
            self.selection_changed.emit(None, "")

    def add_sample_ids(self, sample_ids: list[EntityId]) -> None:
        """Add membership for Sample IDs. This never performs file I/O."""
        if self._collection_id is None or not sample_ids:
            return
        try:
            self._collection_service.add_samples(self._collection_id, sample_ids)
        except ApplicationError:
            return
        self.refresh()
        self.membership_changed.emit()

    def remove_sample_ids(self, sample_ids: list[EntityId]) -> None:
        if self._collection_id is None or not sample_ids:
            return
        try:
            self._collection_service.remove_samples(self._collection_id, sample_ids)
        except ApplicationError:
            return
        self.refresh()
        self.membership_changed.emit()

    def load_selection_into_playback(self) -> None:
        """Load the selected Collection Sample into the shared preview transport."""
        sample_id = self._selected_sample_id()
        if sample_id is None:
            return
        sid = EntityId(sample_id)
        path = self._context.resolve_sample_media_path(sid)
        if path is None or not path.is_file():
            return
        try:
            self._context.playback_service.load(sid, path)
        except ApplicationError:
            return

    def selected_sample_ids(self) -> list[EntityId]:
        ids: list[EntityId] = []
        for index in self._table.selectionModel().selectedRows():
            sample_id = self._model.sample_id_at(index.row())
            if sample_id is not None:
                ids.append(EntityId(sample_id))
        return ids

    def _edit_collection(self) -> None:
        if self._collection_id is None:
            return
        collection = self._collection_service.get(self._collection_id)
        name, accepted = QInputDialog.getText(
            self,
            "Edit Collection",
            "Name:",
            text=collection.name,
        )
        if not accepted or not name.strip():
            return
        description, accepted = QInputDialog.getMultiLineText(
            self,
            "Edit Collection",
            "Description:",
            collection.description or "",
        )
        if not accepted:
            return
        try:
            self._collection_service.update(
                self._collection_id,
                name=name.strip(),
                description=description,
                clear_description=not description.strip(),
            )
        except ApplicationError:
            return
        self.refresh()
        self.membership_changed.emit()

    def _choose_samples_to_add(self) -> None:
        if self._collection_id is None:
            return
        excluded = {
            str(sample_id)
            for sample_id in self._collection_service.list_sample_ids(self._collection_id)
        }
        chooser = _SampleChooser(self._context.search_service, excluded, self)
        if chooser.exec() != QDialog.DialogCode.Accepted:
            return
        self.add_sample_ids(chooser.selected_ids())

    def _remove_selected(self) -> None:
        self.remove_sample_ids(self.selected_sample_ids())

    def _selected_sample_id(self) -> str | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._model.sample_id_at(rows[0].row())

    def _on_selection_changed(self, *_args: object) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._inspector.clear()
            self.selection_changed.emit(None, "")
            return
        row = self._model.sample_row_at(rows[0].row())
        if row is None:
            self._inspector.clear()
            self.selection_changed.emit(None, "")
            return
        media = self._context.resolve_sample_media_path(row.id)
        media_path = str(media) if media is not None and media.is_file() else None
        self._inspector.show_sample(row, envelope=None, media_path=media_path)
        self.selection_changed.emit(str(row.id), row.name)
        if media is not None and media.is_file():
            self._inspector.set_waveform(None, loading=True)
            task = _WaveformTask(
                self._context.waveform_cache,
                row.id,
                media,
                self._waveform_signals,
            )
            QThreadPool.globalInstance().start(task)

    @Slot(str, object)
    def _on_waveform_ready(self, sample_id: str, envelope: object) -> None:
        if sample_id != self._selected_sample_id():
            return
        resolved = envelope if isinstance(envelope, PeakEnvelope) else None
        self._inspector.set_waveform(resolved)

    def _open_selected(self, *_args: object) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is not None:
            self.open_sample_detail_requested.emit(sample_id)

    def _prepare_selected(self) -> None:
        sample_id = self._selected_sample_id()
        if sample_id is not None:
            self.prepare_requested.emit(sample_id)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime is not None and (mime.hasFormat(MIME_SAMPLE_IDS) or mime.hasText()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        if mime is None:
            event.ignore()
            return
        payload = ""
        if mime.hasFormat(MIME_SAMPLE_IDS):
            raw = mime.data(MIME_SAMPLE_IDS)
            payload = memoryview(raw.data()).tobytes().decode("utf-8")
        elif mime.hasText():
            payload = mime.text()
        sample_ids = [
            EntityId(part.strip())
            for part in payload.replace(",", "\n").splitlines()
            if part.strip()
        ]
        if not sample_ids:
            event.ignore()
            return
        self.add_sample_ids(sample_ids)
        event.acceptProposedAction()
