"""S03 Collections browser bound to CollectionService."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.services.collections import CollectionListItem, CollectionService
from koffer.ui.widgets.content_state import ContentStatePanel


class CollectionsScreen(QWidget):
    """Collections list foundation: create/delete/open without filesystem side effects."""

    collection_selected = Signal(object)
    collection_changed = Signal()

    def __init__(
        self,
        collection_service: CollectionService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._collection_service = collection_service
        self.setObjectName("collectionsScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Collections")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)

        new_btn = QPushButton("New Collection")
        new_btn.setObjectName("newCollectionButton")
        new_btn.setStyleSheet(
            "QPushButton#newCollectionButton {"
            " background-color: #CF8652; color: #0B0D0F; border: none;"
            " border-radius: 5px; padding: 8px 16px; min-height: 32px;"
            " font-weight: 600; }"
        )
        new_btn.clicked.connect(self._create_collection)
        header.addWidget(new_btn)

        rename_btn = QPushButton("Rename")
        rename_btn.setObjectName("renameCollectionButton")
        rename_btn.clicked.connect(self._rename_selected)
        header.addWidget(rename_btn)

        duplicate_btn = QPushButton("Duplicate")
        duplicate_btn.setObjectName("duplicateCollectionButton")
        duplicate_btn.clicked.connect(self._duplicate_selected)
        header.addWidget(duplicate_btn)

        delete_btn = QPushButton("Delete Collection")
        delete_btn.setObjectName("deleteCollectionButton")
        delete_btn.clicked.connect(self._delete_selected)
        header.addWidget(delete_btn)
        root.addLayout(header)

        hint = QLabel(
            "Collections group Samples without copying or moving audio files. "
            "Deleting a Collection leaves audio files intact."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._list = QListWidget()
        self._list.setObjectName("collectionList")
        self._list.itemActivated.connect(self._on_item_activated)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        root.addWidget(self._list, stretch=1)

        self._state_panel = ContentStatePanel()
        root.addWidget(self._state_panel)

    def refresh(self) -> None:
        self._list.clear()
        self._state_panel.show_loading("Loading Collections…")
        try:
            items = self._collection_service.list_with_counts()
        except ApplicationError as exc:
            self._list.setVisible(False)
            self._state_panel.show_error("Collections unavailable", str(exc))
            return
        if len(items) == 0:
            self._list.setVisible(False)
            self._state_panel.show_empty(
                "No Collections yet",
                "Create one to organize Samples without copying or moving audio files.",
            )
        else:
            self._state_panel.clear()
            self._list.setVisible(True)
            for item in items:
                self._list.addItem(self._make_row(item))

    def selected_collection_id(self) -> EntityId | None:
        item = self._list.currentItem()
        if item is None:
            return None
        value = item.data(int(Qt.ItemDataRole.UserRole))
        if isinstance(value, str) and value:
            return EntityId(value)
        return None

    def _make_row(self, item: CollectionListItem) -> QListWidgetItem:
        collection = item.collection
        description = collection.description or "No description"
        text = (
            f"{collection.name}\n"
            f"{item.sample_count} samples · updated {collection.updated_at}\n"
            f"{description}"
        )
        row = QListWidgetItem(text)
        row.setData(int(Qt.ItemDataRole.UserRole), str(collection.id))
        return row

    def _create_collection(self) -> None:
        name, accepted = QInputDialog.getText(self, "New Collection", "Name:")
        if not accepted:
            return
        try:
            self._collection_service.create(name)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not create Collection", str(exc))
            return
        self.refresh()
        self.collection_changed.emit()

    def create_collection_named(self, name: str, description: str | None = None) -> EntityId:
        """Test/helper path that skips the modal dialog."""
        collection = self._collection_service.create(name, description=description)
        self.refresh()
        self.collection_changed.emit()
        return collection.id

    def _rename_selected(self) -> None:
        collection_id = self.selected_collection_id()
        if collection_id is None:
            return
        collection = self._collection_service.get(collection_id)
        name, accepted = QInputDialog.getText(
            self,
            "Rename Collection",
            "Name:",
            text=collection.name,
        )
        if not accepted or not name.strip() or name.strip() == collection.name:
            return
        try:
            self._collection_service.update(collection_id, name=name.strip())
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not rename Collection", str(exc))
            return
        self.refresh()
        self.collection_changed.emit()

    def _duplicate_selected(self) -> None:
        collection_id = self.selected_collection_id()
        if collection_id is None:
            return
        source = self._collection_service.get(collection_id)
        name, accepted = QInputDialog.getText(
            self,
            "Duplicate Collection",
            "New name:",
            text=f"{source.name} Copy",
        )
        if not accepted or not name.strip():
            return
        try:
            self._collection_service.duplicate(
                collection_id,
                name=name.strip(),
            )
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not duplicate Collection", str(exc))
            return
        self.refresh()
        self.collection_changed.emit()

    def _delete_selected(self) -> None:
        collection_id = self.selected_collection_id()
        if collection_id is None:
            return
        collection = self._collection_service.get(collection_id)
        answer = QMessageBox.question(
            self,
            "Delete Collection",
            (
                f'Delete Collection "{collection.name}"?\n\n'
                "Audio files and Sample records remain intact. "
                "Only this Collection and its membership links are removed."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._collection_service.delete(collection_id)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not delete Collection", str(exc))
            return
        self.refresh()
        self.collection_changed.emit()

    def delete_collection(self, collection_id: EntityId, *, confirm: bool = True) -> None:
        """Delete helper for tests; confirmation dialog optional."""
        if confirm:
            self._list.clearSelection()
            for index in range(self._list.count()):
                item = self._list.item(index)
                if item is not None and item.data(int(Qt.ItemDataRole.UserRole)) == str(
                    collection_id
                ):
                    self._list.setCurrentItem(item)
                    break
            self._delete_selected()
            return
        self._collection_service.delete(collection_id)
        self.refresh()
        self.collection_changed.emit()

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        collection_id = item.data(int(Qt.ItemDataRole.UserRole))
        if isinstance(collection_id, str) and collection_id:
            self.collection_selected.emit(EntityId(collection_id))
