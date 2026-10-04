"""S05 Sources list bound to SourceService status."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.enums import SourceStatus
from koffer.domain.ids import EntityId
from koffer.domain.models import Source
from koffer.services.sources import SourceListItem, SourceService
from koffer.ui.tokens import FAINT, GREEN, MUTED, RED, YELLOW


def _status_label(source: Source) -> tuple[str, str]:
    """Return (human label, objectName) for online/offline/enabled state."""
    if not source.enabled or source.status is SourceStatus.DISABLED:
        return "Disabled", "statusDisabled"
    if source.status is SourceStatus.OFFLINE:
        return "Offline", "statusOffline"
    if source.status is SourceStatus.ONLINE:
        return "Online", "statusOnline"
    if source.status is SourceStatus.SCANNING:
        return "Scanning", "statusOnline"
    if source.status is SourceStatus.PERMISSION_DENIED:
        return "Permission denied", "statusError"
    if source.status is SourceStatus.ERROR:
        return "Error", "statusError"
    return str(source.status), "statusOffline"


def _status_color(object_name: str) -> str:
    return {
        "statusOnline": GREEN,
        "statusOffline": YELLOW,
        "statusDisabled": FAINT,
        "statusError": RED,
    }.get(object_name, MUTED)


class SourcesScreen(QWidget):
    """Sources health dashboard foundation."""

    add_source_requested = Signal()
    source_selected = Signal(object)

    def __init__(
        self,
        source_service: SourceService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_service = source_service
        self.setObjectName("sourcesScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Sources")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        add_btn = QPushButton("Add Source")
        add_btn.setObjectName("addSourceButton")
        add_btn.setStyleSheet(
            "QPushButton#addSourceButton {"
            " background-color: #CF8652; color: #0B0D0F; border: none;"
            " border-radius: 5px; padding: 8px 16px; min-height: 32px;"
            " font-weight: 600; }"
        )
        add_btn.clicked.connect(self.add_source_requested.emit)
        header.addWidget(add_btn)
        root.addLayout(header)

        hint = QLabel("Online / offline / enabled state comes from the Source repository.")
        hint.setObjectName("bodyText")
        root.addWidget(hint)

        self._list = QListWidget()
        self._list.setObjectName("sourceList")
        self._list.itemActivated.connect(self._on_item_activated)
        self._list.itemDoubleClicked.connect(self._on_item_activated)
        root.addWidget(self._list, stretch=1)

        self._empty = QLabel("No Sources yet. Add a directory to begin indexing.")
        self._empty.setObjectName("bodyText")
        root.addWidget(self._empty)

    def refresh(self) -> None:
        self._list.clear()
        items = self._source_service.list_with_status()
        self._empty.setVisible(len(items) == 0)
        self._list.setVisible(len(items) > 0)
        for item in items:
            self._list.addItem(self._make_row(item))

    def _make_row(self, item: SourceListItem) -> QListWidgetItem:
        source = item.source
        status_text, status_name = _status_label(source)
        enabled_text = "enabled" if source.enabled else "disabled"
        job_text = ""
        if item.current_job is not None:
            job_text = f" · job {item.current_job.state}"
        last_scan = source.last_scan_completed_at or "never"
        text = (
            f"{source.display_name}\n"
            f"{source.root_path}\n"
            f"{status_text} · {enabled_text} · {item.sample_count} files · "
            f"last scan {last_scan}{job_text}"
        )
        row = QListWidgetItem(text)
        row.setData(int(Qt.ItemDataRole.UserRole), str(source.id))
        row.setToolTip(f"status={source.status} enabled={source.enabled}")
        # Color is not the only carrier — text includes Online/Offline/Disabled.
        row.setForeground(QColor(_status_color(status_name)))
        return row

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        source_id = item.data(int(Qt.ItemDataRole.UserRole))
        if isinstance(source_id, str) and source_id:
            self.source_selected.emit(EntityId(source_id))

    def selected_source_id(self) -> EntityId | None:
        item = self._list.currentItem()
        if item is None:
            return None
        value = item.data(int(Qt.ItemDataRole.UserRole))
        if isinstance(value, str) and value:
            return EntityId(value)
        return None
