"""S10 Suggestions Review foundations (docs/12, docs/15)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.services.analysis import AnalysisService, SuggestionReviewItem
from koffer.ui.tokens import CLAY, MUTED, RED, YELLOW


class SuggestionsReviewScreen(QWidget):
    """S10 inbox: pending Suggestions with accept/reject/edit and evidence."""

    back_requested = Signal()
    review_changed = Signal()

    def __init__(
        self,
        analysis_service: AnalysisService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = analysis_service
        self._items: list[SuggestionReviewItem] = []
        self._current: SuggestionReviewItem | None = None
        self.setObjectName("suggestionsReviewScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Suggestions Review")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self._badge = QLabel("0 pending")
        self._badge.setObjectName("suggestionsReviewBadge")
        self._badge.setStyleSheet(f"color: {CLAY}; font-weight: 600;")
        header.addWidget(self._badge)
        back = QPushButton("Back")
        back.setObjectName("suggestionsReviewBackButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        self._scope = QLabel("Batch scope: selected pending Suggestions only.")
        self._scope.setObjectName("suggestionsReviewScope")
        self._scope.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._scope)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Min confidence"))
        self._min_confidence = QLineEdit()
        self._min_confidence.setObjectName("suggestionsReviewMinConfidence")
        self._min_confidence.setPlaceholderText("0.0–1.0")
        self._min_confidence.setMaximumWidth(100)
        filters.addWidget(self._min_confidence)
        filters.addWidget(QLabel("Max confidence"))
        self._max_confidence = QLineEdit()
        self._max_confidence.setObjectName("suggestionsReviewMaxConfidence")
        self._max_confidence.setPlaceholderText("0.0–1.0")
        self._max_confidence.setMaximumWidth(100)
        filters.addWidget(self._max_confidence)

        filters.addWidget(QLabel("Dimension"))
        self._dimension = QLineEdit()
        self._dimension.setObjectName("suggestionsReviewDimensionFilter")
        self._dimension.setPlaceholderText("e.g. instrument_source")
        self._dimension.setMaximumWidth(200)
        filters.addWidget(self._dimension)
        apply_filters = QPushButton("Apply filters")
        apply_filters.setObjectName("suggestionsReviewApplyFilters")
        apply_filters.clicked.connect(self.refresh)
        filters.addWidget(apply_filters)
        filters.addStretch(1)
        root.addLayout(filters)

        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.setObjectName("suggestionsReviewList")
        self._list.currentRowChanged.connect(self._on_row_changed)
        body.addWidget(self._list, stretch=2)

        detail = QVBoxLayout()
        self._detail_title = QLabel("Select a Suggestion")
        self._detail_title.setObjectName("suggestionsReviewDetailTitle")
        self._detail_title.setWordWrap(True)
        detail.addWidget(self._detail_title)

        self._confidence = QLabel("")
        self._confidence.setObjectName("suggestionsReviewConfidence")
        detail.addWidget(self._confidence)

        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Value"))
        self._edit = QLineEdit()
        self._edit.setObjectName("suggestionsReviewEditValue")
        edit_row.addWidget(self._edit)
        detail.addLayout(edit_row)

        self._evidence = QLabel("")
        self._evidence.setObjectName("suggestionsReviewEvidence")
        self._evidence.setWordWrap(True)
        self._evidence.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._evidence.setStyleSheet(
            f"color: {MUTED}; font-family: monospace; background: rgba(0,0,0,0.25); padding: 8px;"
        )
        detail.addWidget(self._evidence, stretch=1)

        actions = QHBoxLayout()
        self._accept_btn = QPushButton("Accept (A)")
        self._accept_btn.setObjectName("suggestionsReviewAcceptButton")
        self._accept_btn.clicked.connect(self._accept_current)
        actions.addWidget(self._accept_btn)

        self._reject_btn = QPushButton("Reject (R)")
        self._reject_btn.setObjectName("suggestionsReviewRejectButton")
        self._reject_btn.setStyleSheet(f"color: {RED};")
        self._reject_btn.clicked.connect(self._reject_current)
        actions.addWidget(self._reject_btn)

        self._edit_accept_btn = QPushButton("Edit & Accept (E)")
        self._edit_accept_btn.setObjectName("suggestionsReviewEditAcceptButton")
        self._edit_accept_btn.setStyleSheet(f"color: {YELLOW};")
        self._edit_accept_btn.clicked.connect(self._edit_accept_current)
        actions.addWidget(self._edit_accept_btn)

        self._batch_accept_btn = QPushButton("Accept all visible")
        self._batch_accept_btn.setObjectName("suggestionsReviewBatchAcceptButton")
        self._batch_accept_btn.clicked.connect(self._batch_accept_visible)
        actions.addWidget(self._batch_accept_btn)
        actions.addStretch(1)
        detail.addLayout(actions)

        self._status = QLabel("")
        self._status.setObjectName("suggestionsReviewStatus")
        detail.addWidget(self._status)

        detail_wrap = QWidget()
        detail_wrap.setObjectName("suggestionsReviewDetail")
        detail_wrap.setLayout(detail)
        body.addWidget(detail_wrap, stretch=3)
        root.addLayout(body, stretch=1)

        self._accept_shortcut = QShortcut(QKeySequence("A"), self)
        self._accept_shortcut.setObjectName("suggestionsReviewAcceptShortcut")
        self._accept_shortcut.activated.connect(self._accept_current)
        self._reject_shortcut = QShortcut(QKeySequence("R"), self)
        self._reject_shortcut.setObjectName("suggestionsReviewRejectShortcut")
        self._reject_shortcut.activated.connect(self._reject_current)
        self._edit_shortcut = QShortcut(QKeySequence("E"), self)
        self._edit_shortcut.setObjectName("suggestionsReviewEditShortcut")
        self._edit_shortcut.activated.connect(self._edit_accept_current)

    def refresh(self) -> None:
        min_conf: float | None = None
        raw = self._min_confidence.text().strip()
        if raw:
            try:
                min_conf = float(raw)
            except ValueError:
                self._status.setText("Min confidence must be a number.")
                return
        max_conf: float | None = None
        raw_max = self._max_confidence.text().strip()
        if raw_max:
            try:
                max_conf = float(raw_max)
            except ValueError:
                self._status.setText("Max confidence must be a number.")
                return
        if min_conf is not None and not 0.0 <= min_conf <= 1.0:
            self._status.setText("Min confidence must be between 0.0 and 1.0.")
            return
        if max_conf is not None and not 0.0 <= max_conf <= 1.0:
            self._status.setText("Max confidence must be between 0.0 and 1.0.")
            return
        if min_conf is not None and max_conf is not None and min_conf > max_conf:
            self._status.setText("Min confidence cannot exceed max confidence.")
            return
        dimension = self._dimension.text().strip() or None
        self._items = self._service.list_pending_suggestions(
            min_confidence=min_conf,
            max_confidence=max_conf,
            dimension=dimension,
        )
        self._badge.setText(f"{len(self._items)} pending")
        self._scope.setText(f"Batch scope: {len(self._items)} visible pending Suggestion(s).")
        self._list.clear()
        for item in self._items:
            s = item.suggestion
            label = (
                f"{item.sample_filename} · {s.dimension} → {s.proposed_value} ({s.confidence:.0%})"
            )
            row = QListWidgetItem(label)
            row.setData(Qt.ItemDataRole.UserRole, str(s.id))
            self._list.addItem(row)
        if self._items:
            self._list.setCurrentRow(0)
        else:
            self._current = None
            self._detail_title.setText("No pending Suggestions")
            self._confidence.setText("")
            self._edit.clear()
            self._evidence.setText("")

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._items):
            self._current = None
            return
        self._current = self._items[row]
        s = self._current.suggestion
        self._detail_title.setText(
            f"{self._current.sample_relative_path}\n{s.dimension} → {s.proposed_value}"
        )
        self._confidence.setText(f"Confidence: {s.confidence:.0%} · provider {s.provider}")
        self._edit.setText(s.proposed_value)
        try:
            self._evidence.setText(self._service.evidence_summary(s.id))
        except ApplicationError as exc:
            self._evidence.setText(str(exc))
        self._status.setText("")

    def _current_id(self) -> EntityId | None:
        if self._current is None:
            return None
        return self._current.suggestion.id

    def _accept_current(self) -> None:
        sid = self._current_id()
        if sid is None:
            return
        try:
            self._service.accept_suggestion(sid)
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self._status.setText("Accepted (confirmed classification; no embedded write).")
        self.review_changed.emit()
        self.refresh()

    def _reject_current(self) -> None:
        sid = self._current_id()
        if sid is None:
            return
        try:
            self._service.reject_suggestion(sid)
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self._status.setText("Rejected (provenance retained).")
        self.review_changed.emit()
        self.refresh()

    def _edit_accept_current(self) -> None:
        sid = self._current_id()
        if sid is None:
            return
        edited = self._edit.text().strip()
        try:
            self._service.accept_suggestion(sid, edited_value=edited)
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self._status.setText("Edited & accepted (confirmed classification; no embedded write).")
        self.review_changed.emit()
        self.refresh()

    def _batch_accept_visible(self) -> None:
        if not self._items:
            self._status.setText("Nothing to accept.")
            return
        count = 0
        for item in list(self._items):
            try:
                self._service.accept_suggestion(item.suggestion.id)
                count += 1
            except ApplicationError:
                continue
        self._status.setText(f"Batch accepted {count} Suggestion(s).")
        self.review_changed.emit()
        self.refresh()
