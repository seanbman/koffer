"""S12 Import / Organize Review foundation (docs/12, docs/15)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.enums import ConflictAction, FileOperationKind
from koffer.domain.file_operations import FileOperationPlan
from koffer.services.file_operations import FileOperationService
from koffer.ui.tokens import CLAY, MUTED, YELLOW


def _operation_plain_language(kind: FileOperationKind) -> str:
    if kind is FileOperationKind.REFERENCE:
        return "Reference — keep files at their current locations (no copy or move)."
    if kind is FileOperationKind.COPY:
        return "Copy — create new files at the destination; originals stay untouched."
    return "Move — relocate files into the destination."


def _operation_action_label(kind: FileOperationKind) -> str:
    return {
        FileOperationKind.REFERENCE: "Reference",
        FileOperationKind.COPY: "Copy",
        FileOperationKind.MOVE: "Move",
    }[kind]


def _conflict_action_label(action: ConflictAction) -> str:
    return {
        ConflictAction.REVIEW: "Review required",
        ConflictAction.KEEP_BOTH: "Keep both",
        ConflictAction.SKIP: "Skip",
        ConflictAction.REPLACE: "Replace (explicit)",
        ConflictAction.CHOOSE_DESTINATION: "Choose destination",
    }[action]


class ImportReviewScreen(QWidget):
    """S12: review Reference/Copy/Move plan before filesystem mutation."""

    execute_requested = Signal()
    resolve_conflicts_requested = Signal()
    back_requested = Signal()

    def __init__(
        self,
        file_operation_service: FileOperationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = file_operation_service
        self._plan: FileOperationPlan | None = None
        self.setObjectName("importReviewScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Import / Organize Review")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        back = QPushButton("Back")
        back.setObjectName("importReviewBackButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        self._operation = QLabel("No operation selected.")
        self._operation.setObjectName("importReviewOperation")
        self._operation.setWordWrap(True)
        root.addWidget(self._operation)

        self._destination = QLabel("Destination: —")
        self._destination.setObjectName("importReviewDestination")
        self._destination.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._destination)

        self._policy = QLabel("Conflict default: Review (never silent overwrite)")
        self._policy.setObjectName("importReviewConflictPolicy")
        self._policy.setStyleSheet(f"color: {YELLOW};")
        root.addWidget(self._policy)

        self._items = QListWidget()
        self._items.setObjectName("importReviewItemList")
        root.addWidget(self._items, stretch=1)

        self._empty = QLabel("Load an operation to review items before continuing.")
        self._empty.setObjectName("bodyText")
        root.addWidget(self._empty)

        actions = QHBoxLayout()
        self._resolve_btn = QPushButton("Resolve Conflicts")
        self._resolve_btn.setObjectName("importReviewResolveButton")
        self._resolve_btn.clicked.connect(self.resolve_conflicts_requested.emit)
        actions.addWidget(self._resolve_btn)
        actions.addStretch(1)
        self._execute_btn = QPushButton("Apply")
        self._execute_btn.setObjectName("importReviewExecuteButton")
        self._execute_btn.setStyleSheet(
            "QPushButton#importReviewExecuteButton {"
            f" background-color: {CLAY}; color: #0B0D0F; border: none;"
            " border-radius: 5px; padding: 8px 16px; min-height: 32px;"
            " font-weight: 600; }"
        )
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        actions.addWidget(self._execute_btn)
        root.addLayout(actions)

    @property
    def plan(self) -> FileOperationPlan | None:
        return self._plan

    def show_plan(self, plan: FileOperationPlan) -> None:
        self._plan = plan
        self.refresh()

    def refresh(self) -> None:
        plan = self._plan
        self._items.clear()
        if plan is None:
            self._operation.setText("No operation selected.")
            self._destination.setText("Destination: —")
            self._empty.setVisible(True)
            self._items.setVisible(False)
            self._resolve_btn.setEnabled(False)
            self._execute_btn.setEnabled(False)
            return

        self._operation.setText(_operation_plain_language(plan.kind))
        self._execute_btn.setText(_operation_action_label(plan.kind))
        if plan.destination_root:
            self._destination.setText(f"Destination: {plan.destination_root}")
        else:
            self._destination.setText("Destination: (none — Reference keeps paths)")
        self._policy.setText(
            "Conflict default: "
            f"{_conflict_action_label(plan.conflict_policy.default_action)} "
            "(never silent overwrite)"
        )
        unresolved = plan.unresolved_conflicts()
        self._empty.setVisible(False)
        self._items.setVisible(True)
        for item in plan.items:
            conflict_bit = ""
            if item.conflict and item.conflict_action is ConflictAction.REVIEW:
                conflict_bit = " · CONFLICT: needs review"
            elif item.conflict_action is ConflictAction.SKIP:
                conflict_bit = " · Skip"
            elif item.conflict_action is ConflictAction.KEEP_BOTH:
                conflict_bit = " · Keep both"
            elif item.conflict_action is ConflictAction.REPLACE:
                conflict_bit = " · Replace (explicit)"
            dest = item.destination_path or "(in place)"
            text = f"{Path(item.source_path).name}\n{item.source_path}\n→ {dest}{conflict_bit}"
            self._items.addItem(QListWidgetItem(text))
        self._resolve_btn.setEnabled(len(unresolved) > 0)
        self._execute_btn.setEnabled(len(unresolved) == 0 and len(plan.items) > 0)
