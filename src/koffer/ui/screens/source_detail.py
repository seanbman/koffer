"""S06 Source Detail foundations: status, exclusions, jobs summary."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from koffer.domain.enums import SourceStatus
from koffer.domain.ids import EntityId
from koffer.services.sources import SourceService
from koffer.ui.screens.sources import _status_label


class SourceDetailScreen(QWidget):
    """Basic Source Detail view wired to SourceService.get_detail."""

    back_requested = Signal()

    def __init__(
        self,
        source_service: SourceService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_service = source_service
        self._source_id: EntityId | None = None
        self.setObjectName("sourceDetailScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        back = QPushButton("Back to Sources")
        back.setObjectName("backToSourcesButton")
        back.clicked.connect(self.back_requested.emit)
        root.addWidget(back)

        self._title = QLabel("Source Detail")
        self._title.setObjectName("pageTitle")
        root.addWidget(self._title)

        self._status = QLabel("")
        self._status.setObjectName("sourceDetailStatus")
        root.addWidget(self._status)

        self._path = QLabel("")
        self._path.setObjectName("sourceDetailPath")
        self._path.setWordWrap(True)
        root.addWidget(self._path)

        self._counts = QLabel("")
        self._counts.setObjectName("sourceDetailCounts")
        root.addWidget(self._counts)

        exclusions_heading = QLabel("Exclusions")
        exclusions_heading.setObjectName("promiseTitle")
        root.addWidget(exclusions_heading)
        self._exclusions = QLabel("")
        self._exclusions.setObjectName("sourceDetailExclusions")
        self._exclusions.setWordWrap(True)
        root.addWidget(self._exclusions)

        jobs_heading = QLabel("Jobs")
        jobs_heading.setObjectName("promiseTitle")
        root.addWidget(jobs_heading)
        self._jobs = QLabel("")
        self._jobs.setObjectName("sourceDetailJobs")
        self._jobs.setWordWrap(True)
        root.addWidget(self._jobs)

        root.addStretch(1)

    def show_source(self, source_id: EntityId) -> None:
        self._source_id = source_id
        self.refresh()

    def refresh(self) -> None:
        if self._source_id is None:
            return
        detail = self._source_service.get_detail(self._source_id)
        source = detail.source
        status_text, status_name = _status_label(source)
        self._title.setText(source.display_name)
        enabled = "enabled" if source.enabled else "disabled"
        self._status.setText(f"Status: {status_text} ({enabled})")
        self._status.setProperty("sourceStatus", str(source.status))
        self._status.setProperty("statusKind", status_name)
        self._path.setText(f"Path: {source.root_path}")
        self._counts.setText(
            f"Indexed files: {detail.sample_count} · "
            f"Last successful scan: {source.last_scan_completed_at or 'never'} · "
            f"Last scan started: {source.last_scan_started_at or 'never'}"
        )
        if detail.exclusions:
            lines = [
                f"- {rule.pattern} ({rule.pattern_type}{'' if rule.enabled else ', disabled'})"
                for rule in detail.exclusions
            ]
            self._exclusions.setText("\n".join(lines))
        else:
            self._exclusions.setText("No exclusion rules.")

        if detail.current_job is not None:
            current = (
                f"Current: {detail.current_job.type} · {detail.current_job.state}"
                f" · stage={detail.current_job.stage or '-'}"
            )
        else:
            current = "Current: none"
        if detail.recent_jobs:
            recent = "\n".join(
                f"- {job.type} · {job.state} · created {job.created_at}"
                for job in detail.recent_jobs
            )
        else:
            recent = "No jobs yet."
        self._jobs.setText(f"{current}\n{recent}")

        # Keep offline/online distinction readable even if stylesheet misses objectName.
        if source.status is SourceStatus.OFFLINE:
            self._status.setStyleSheet("color: #D7B65E; font-weight: 600;")
        elif not source.enabled or source.status is SourceStatus.DISABLED:
            self._status.setStyleSheet("color: #66717C; font-weight: 600;")
        else:
            self._status.setStyleSheet("color: #67B983; font-weight: 600;")
