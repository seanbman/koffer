"""S13 Conflicts & Duplicates foundation (docs/12, docs/15)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.enums import ConflictAction
from koffer.domain.file_operations import FileOperationPlan
from koffer.domain.ids import EntityId
from koffer.services.file_operations import FileOperationService
from koffer.ui.tokens import CLAY, MUTED, YELLOW


class ConflictsScreen(QWidget):
    """S13: resolve filename conflicts before execute; no silent overwrite."""

    apply_requested = Signal()
    back_requested = Signal()

    def __init__(
        self,
        file_operation_service: FileOperationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = file_operation_service
        self._plan: FileOperationPlan | None = None
        self._pending: dict[EntityId, ConflictAction] = {}
        self.setObjectName("conflictsScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Conflicts & Duplicates")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        back = QPushButton("Back to Review")
        back.setObjectName("conflictsBackButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        hint = QLabel(
            "Batch conflict rules stay Review until you choose Keep Both, Skip, or Replace."
        )
        hint.setObjectName("conflictsHint")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)

        self._policy = QLabel("Default: Review — never silent overwrite")
        self._policy.setObjectName("conflictsDefaultPolicy")
        self._policy.setStyleSheet(f"color: {YELLOW};")
        root.addWidget(self._policy)

        self._list = QListWidget()
        self._list.setObjectName("conflictsItemList")
        root.addWidget(self._list, stretch=1)

        self._empty = QLabel("No unresolved conflicts.")
        self._empty.setObjectName("bodyText")
        root.addWidget(self._empty)

        batch = QHBoxLayout()
        keep_both = QPushButton("Keep Both (all)")
        keep_both.setObjectName("conflictsKeepBothAllButton")
        keep_both.clicked.connect(lambda: self._set_all(ConflictAction.KEEP_BOTH))
        batch.addWidget(keep_both)
        skip_all = QPushButton("Skip (all)")
        skip_all.setObjectName("conflictsSkipAllButton")
        skip_all.clicked.connect(lambda: self._set_all(ConflictAction.SKIP))
        batch.addWidget(skip_all)
        batch.addStretch(1)
        apply_btn = QPushButton("Apply Resolutions")
        apply_btn.setObjectName("conflictsApplyButton")
        apply_btn.setStyleSheet(
            "QPushButton#conflictsApplyButton {"
            f" background-color: {CLAY}; color: #0B0D0F; border: none;"
            " border-radius: 5px; padding: 8px 16px; min-height: 32px;"
            " font-weight: 600; }"
        )
        apply_btn.clicked.connect(self._apply)
        batch.addWidget(apply_btn)
        root.addLayout(batch)

        item_actions = QHBoxLayout()
        for label, action, object_name in (
            ("Keep Both", ConflictAction.KEEP_BOTH, "conflictsKeepBothButton"),
            ("Skip", ConflictAction.SKIP, "conflictsSkipButton"),
            ("Replace", ConflictAction.REPLACE, "conflictsReplaceButton"),
        ):
            btn = QPushButton(label)
            btn.setObjectName(object_name)
            btn.clicked.connect(lambda _checked=False, a=action: self._set_selected(a))
            item_actions.addWidget(btn)
        item_actions.addStretch(1)
        root.addLayout(item_actions)

    @property
    def plan(self) -> FileOperationPlan | None:
        return self._plan

    def show_plan(self, plan: FileOperationPlan) -> None:
        self._plan = plan
        self._pending = {
            item.sample_id: item.conflict_action for item in plan.unresolved_conflicts()
        }
        self.refresh()

    def refresh(self) -> None:
        plan = self._plan
        self._list.clear()
        if plan is None:
            self._empty.setVisible(True)
            self._list.setVisible(False)
            return
        conflicts = plan.unresolved_conflicts()
        self._empty.setVisible(len(conflicts) == 0)
        self._list.setVisible(len(conflicts) > 0)
        self._policy.setText(
            f"Default: {plan.conflict_policy.default_action} — never silent overwrite"
        )
        for item in conflicts:
            pending = self._pending.get(item.sample_id, ConflictAction.REVIEW)
            text = (
                f"{Path(item.source_path).name}\n"
                f"{item.source_path}\n"
                f"→ {item.destination_path}\n"
                f"Action: {pending}"
            )
            row = QListWidgetItem(text)
            row.setData(int(Qt.ItemDataRole.UserRole), str(item.sample_id))
            self._list.addItem(row)

    def _set_selected(self, action: ConflictAction) -> None:
        row = self._list.currentItem()
        if row is None:
            return
        sample_id = EntityId(str(row.data(int(Qt.ItemDataRole.UserRole))))
        self._pending[sample_id] = action
        self.refresh()
        # Reselect matching row after rebuild.
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item is not None and str(item.data(int(Qt.ItemDataRole.UserRole))) == str(sample_id):
                self._list.setCurrentRow(index)
                break

    def _set_all(self, action: ConflictAction) -> None:
        if self._plan is None:
            return
        for item in self._plan.unresolved_conflicts():
            self._pending[item.sample_id] = action
        self.refresh()

    def _apply(self) -> None:
        if self._plan is None:
            return
        # Require every unresolved conflict to leave Review.
        for item in self._plan.unresolved_conflicts():
            action = self._pending.get(item.sample_id, ConflictAction.REVIEW)
            if action is ConflictAction.REVIEW:
                return
        self._plan = self._service.resolve_conflicts(self._plan, self._pending)
        self.apply_requested.emit()
