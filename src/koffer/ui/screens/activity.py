"""S16 Activity Center — Jobs grouped by Running / Queued / Completed / Needs Attention."""

from __future__ import annotations

from PySide6.QtCore import Qt
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

from koffer.domain.enums import ActivityGroup, JobState
from koffer.domain.ids import EntityId
from koffer.jobs.activity import JobSummary, group_summaries
from koffer.jobs.scheduler import JobScheduler
from koffer.ui.tokens import BLUE, BORDER, CLAY, FAINT, GREEN, MUTED, RED, YELLOW
from koffer.ui.widgets.content_state import ContentStatePanel

_GROUP_ORDER = (
    ActivityGroup.RUNNING,
    ActivityGroup.QUEUED,
    ActivityGroup.NEEDS_ATTENTION,
    ActivityGroup.COMPLETED,
)

_GROUP_LABELS = {
    ActivityGroup.RUNNING: "RUNNING",
    ActivityGroup.QUEUED: "QUEUED",
    ActivityGroup.NEEDS_ATTENTION: "NEEDS ATTENTION",
    ActivityGroup.COMPLETED: "COMPLETED",
}


class ActivityCenterScreen(QWidget):
    """Lists durable Jobs from the scheduler; closing does not cancel work."""

    def __init__(
        self,
        scheduler: JobScheduler,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scheduler = scheduler
        self.setObjectName("activityCenterScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Activity Center")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)

        self._badge_running = QLabel("0 RUNNING")
        self._badge_running.setObjectName("activityBadgeRunning")
        self._badge_running.setStyleSheet(
            f"color: {BLUE}; background: #1B2B39; border: 1px solid {BORDER};"
            " border-radius: 12px; padding: 4px 10px; font-weight: 600;"
        )
        header.addWidget(self._badge_running)

        self._badge_attention = QLabel("0 NEEDS ATTENTION")
        self._badge_attention.setObjectName("activityBadgeAttention")
        self._badge_attention.setStyleSheet(
            f"color: {YELLOW}; background: #332D1B; border: 1px solid {BORDER};"
            " border-radius: 12px; padding: 4px 10px; font-weight: 600;"
        )
        header.addWidget(self._badge_attention)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("activityRefreshButton")
        refresh_btn.setProperty("class", "secondaryButton")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        hint = QLabel(
            "Background Jobs keep running when this screen is closed. "
            "Cancel is cooperative between items."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._list = QListWidget()
        self._list.setObjectName("activityJobList")
        root.addWidget(self._list, stretch=1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._cancel_btn = QPushButton("Cancel selected")
        self._cancel_btn.setObjectName("activityCancelButton")
        self._cancel_btn.setProperty("class", "secondaryButton")
        self._cancel_btn.clicked.connect(self._cancel_selected)
        actions.addWidget(self._cancel_btn)
        root.addLayout(actions)

        self._state_panel = ContentStatePanel()
        root.addWidget(self._state_panel)

    def refresh(self) -> None:
        self._state_panel.show_loading("Loading Jobs…")
        jobs = self._scheduler.list()
        grouped = group_summaries(jobs)
        self._badge_running.setText(f"{len(grouped[ActivityGroup.RUNNING])} RUNNING")
        self._badge_attention.setText(
            f"{len(grouped[ActivityGroup.NEEDS_ATTENTION])} NEEDS ATTENTION"
        )

        self._list.clear()
        total_rows = 0
        for group in _GROUP_ORDER:
            summaries = grouped[group]
            if not summaries:
                continue
            header = QListWidgetItem(_GROUP_LABELS[group])
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setForeground(QColor(FAINT))
            self._list.addItem(header)
            for summary in summaries:
                self._list.addItem(self._make_row(summary))
                total_rows += 1

        if total_rows == 0:
            self._list.setVisible(False)
            self._state_panel.show_empty(
                "No Jobs yet",
                (
                    "Scans and analysis appear here while they run. "
                    "Closing this screen does not cancel work."
                ),
            )
        else:
            self._state_panel.clear()
            self._list.setVisible(True)

    def _make_row(self, summary: JobSummary) -> QListWidgetItem:
        job = summary.job
        state_text = str(job.state)
        counts = f"ok {summary.succeeded} · failed {summary.failed} · skipped {summary.skipped}"
        text = f"{summary.title}\n{summary.detail}\n{state_text} · {counts}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, str(job.id))
        item.setData(Qt.ItemDataRole.UserRole + 1, str(job.state))
        color = {
            JobState.RUNNING: BLUE,
            JobState.QUEUED: MUTED,
            JobState.COMPLETED: GREEN,
            JobState.CANCELLED: MUTED,
            JobState.FAILED: RED,
            JobState.COMPLETED_WITH_ERRORS: YELLOW,
            JobState.INTERRUPTED: YELLOW,
            JobState.CANCEL_REQUESTED: CLAY,
        }.get(job.state, MUTED)
        item.setForeground(QColor(color))
        return item

    def _cancel_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        job_id = item.data(Qt.ItemDataRole.UserRole)
        if not job_id:
            return
        self._scheduler.cancel(EntityId(str(job_id)))
        self.refresh()
