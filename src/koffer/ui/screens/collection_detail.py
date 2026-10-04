"""S04 Collection Detail foundations: membership via CollectionService (no file I/O)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.models import Sample
from koffer.services.collections import CollectionService
from koffer.ui.tokens import MUTED

MIME_SAMPLE_IDS = "application/x-koffer-sample-ids"


class CollectionDetailScreen(QWidget):
    """Browser scoped to one Collection; membership never copies/moves files."""

    back_requested = Signal()
    membership_changed = Signal()

    def __init__(
        self,
        collection_service: CollectionService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._collection_service = collection_service
        self._collection_id: EntityId | None = None
        self.setObjectName("collectionDetailScreen")
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        back = QPushButton("Back to Collections")
        back.setObjectName("backToCollectionsButton")
        back.clicked.connect(self.back_requested.emit)
        root.addWidget(back)

        self._title = QLabel("Collection Detail")
        self._title.setObjectName("pageTitle")
        root.addWidget(self._title)

        self._description = QLabel("")
        self._description.setObjectName("collectionDetailDescription")
        self._description.setWordWrap(True)
        root.addWidget(self._description)

        self._safety = QLabel(
            "Membership is a logical link only. Adding or removing Samples never "
            "copies, moves, or deletes audio files. Deleting this Collection leaves audio intact."
        )
        self._safety.setObjectName("collectionDetailSafety")
        self._safety.setWordWrap(True)
        root.addWidget(self._safety)

        actions = QHBoxLayout()
        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.setObjectName("removeMembershipButton")
        self._remove_btn.clicked.connect(self._remove_selected)
        actions.addWidget(self._remove_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        self._list = QListWidget()
        self._list.setObjectName("collectionMemberList")
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.setAcceptDrops(True)
        root.addWidget(self._list, stretch=1)

        self._empty = QLabel(
            "This Collection is empty. Drag Samples here or add them from the Library "
            "to build membership without duplicating files."
        )
        self._empty.setObjectName("collectionDetailEmpty")
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._empty)

        self._count = QLabel("")
        self._count.setObjectName("collectionDetailCount")
        root.addWidget(self._count)

    def show_collection(self, collection_id: EntityId) -> None:
        self._collection_id = collection_id
        self.refresh()

    def refresh(self) -> None:
        if self._collection_id is None:
            return
        detail = self._collection_service.get_detail(self._collection_id)
        collection = detail.collection
        self._title.setText(collection.name)
        self._description.setText(collection.description or "No description")
        self._list.clear()
        for sample in detail.samples:
            self._list.addItem(self._make_row(sample))
        empty = len(detail.samples) == 0
        self._empty.setVisible(empty)
        self._list.setVisible(not empty)
        self._count.setText(f"{len(detail.samples)} samples · sort {collection.sort_mode}")

    def add_sample_ids(self, sample_ids: list[EntityId]) -> None:
        """Add membership for Sample IDs (drag/drop or programmatic). No file copy."""
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

    def selected_sample_ids(self) -> list[EntityId]:
        ids: list[EntityId] = []
        for item in self._list.selectedItems():
            value = item.data(int(Qt.ItemDataRole.UserRole))
            if isinstance(value, str) and value:
                ids.append(EntityId(value))
        return ids

    def _make_row(self, sample: Sample) -> QListWidgetItem:
        text = f"{sample.filename}\n{sample.relative_path}"
        row = QListWidgetItem(text)
        row.setData(int(Qt.ItemDataRole.UserRole), str(sample.id))
        return row

    def _remove_selected(self) -> None:
        self.remove_sample_ids(self.selected_sample_ids())

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
            # QByteArray.data() yields a buffer; cast keeps mypy happy under PySide stubs.
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
