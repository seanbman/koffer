"""S15 Offline / Missing Recovery foundations."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.enums import RecoveryCondition
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.services.recovery import RecoveryIssue, RecoveryService
from koffer.ui.tokens import MUTED, YELLOW


class OfflineRecoveryScreen(QWidget):
    """Lists distinct offline/missing/changed conditions with safe actions."""

    def __init__(
        self,
        recovery_service: RecoveryService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._recovery = recovery_service
        self._issues: list[RecoveryIssue] = []
        self.setObjectName("offlineRecoveryScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        title = QLabel("Offline / Missing Recovery")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "Offline is not deleted. Moved, changed, and permission-denied states "
            "stay distinct. Repair actions never guess destructively."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)

        self._list = QListWidget()
        self._list.setObjectName("offlineRecoveryList")
        root.addWidget(self._list, stretch=1)

        actions = QHBoxLayout()
        self._recheck_btn = QPushButton("Recheck Source")
        self._recheck_btn.setObjectName("recoveryRecheckButton")
        self._recheck_btn.setProperty("class", "secondaryButton")
        self._recheck_btn.clicked.connect(self._recheck_selected)
        actions.addWidget(self._recheck_btn)

        self._accept_btn = QPushButton("Accept changed file")
        self._accept_btn.setObjectName("recoveryAcceptChangedButton")
        self._accept_btn.setProperty("class", "secondaryButton")
        self._accept_btn.clicked.connect(self._accept_changed)
        actions.addWidget(self._accept_btn)

        self._leave_btn = QPushButton("Leave unresolved")
        self._leave_btn.setObjectName("recoveryLeaveButton")
        self._leave_btn.setProperty("class", "secondaryButton")
        self._leave_btn.clicked.connect(self._leave_unresolved)
        actions.addWidget(self._leave_btn)

        self._remove_btn = QPushButton("Remove stale entry")
        self._remove_btn.setObjectName("recoveryRemoveStaleButton")
        self._remove_btn.setProperty("class", "secondaryButton")
        self._remove_btn.clicked.connect(self._remove_stale)
        actions.addWidget(self._remove_btn)

        actions.addStretch(1)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("recoveryRefreshButton")
        refresh.setProperty("class", "secondaryButton")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        root.addLayout(actions)

    def refresh(self) -> None:
        self._issues = self._recovery.list_issues()
        self._list.clear()
        if not self._issues:
            item = QListWidgetItem("No offline or missing issues.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
            return
        for issue in self._issues:
            text = f"[{issue.condition.value}] {issue.label}\n{issue.detail}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, issue)
            if issue.condition in {
                RecoveryCondition.SOURCE_OFFLINE,
                RecoveryCondition.FILE_MISSING,
                RecoveryCondition.FILE_CHANGED,
            }:
                item.setForeground(QColor(YELLOW))
            self._list.addItem(item)

    def _selected_issue(self) -> RecoveryIssue | None:
        item = self._list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, RecoveryIssue) else None

    def _recheck_selected(self) -> None:
        issue = self._selected_issue()
        if issue is None or issue.source_id is None:
            return
        try:
            self._recovery.recheck_source(EntityId(str(issue.source_id)))
        except ApplicationError as exc:
            QMessageBox.warning(self, "Recheck failed", str(exc))
            return
        self.refresh()

    def _accept_changed(self) -> None:
        issue = self._selected_issue()
        if issue is None or issue.sample_id is None:
            return
        if issue.condition is not RecoveryCondition.FILE_CHANGED:
            QMessageBox.information(
                self,
                "Not applicable",
                "Accept changed file only applies to changed Samples.",
            )
            return
        try:
            self._recovery.accept_changed_file(EntityId(str(issue.sample_id)))
        except ApplicationError as exc:
            QMessageBox.warning(self, "Accept failed", str(exc))
            return
        self.refresh()

    def _leave_unresolved(self) -> None:
        issue = self._selected_issue()
        if issue is None or issue.sample_id is None:
            return
        try:
            self._recovery.leave_unresolved(EntityId(str(issue.sample_id)))
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not leave unresolved", str(exc))
            return
        QMessageBox.information(self, "Left unresolved", "No destructive change was made.")

    def _remove_stale(self) -> None:
        issue = self._selected_issue()
        if issue is None or issue.sample_id is None:
            return
        confirm = QMessageBox.question(
            self,
            "Remove stale library entry?",
            "Removes the Sample from Koffer's index only. Audio files are never deleted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._recovery.remove_stale_entry(EntityId(str(issue.sample_id)))
        except ApplicationError as exc:
            QMessageBox.warning(self, "Remove failed", str(exc))
            return
        self.refresh()
