"""S06 Source Detail: health, controls, exclusions, jobs, and indexed files."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.domain.enums import ExclusionPatternType, JobState, SourceStatus
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import ExclusionRule
from koffer.ui.screens.sources import _status_label


class _ExclusionEditor(QDialog):
    """Edit Source exclusion patterns as one rule per line."""

    def __init__(
        self,
        rules: tuple[ExclusionRule, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._existing = {rule.pattern: rule for rule in rules}
        self.setWindowTitle("Edit Source Exclusions")
        self.resize(560, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        note = QLabel(
            "One exclusion pattern per line. Koffer will preview the effect before "
            "changing the stored rules."
        )
        note.setWordWrap(True)
        note.setObjectName("bodyText")
        root.addWidget(note)

        self._editor = QPlainTextEdit()
        self._editor.setObjectName("sourceExclusionEditor")
        self._editor.setPlainText("\n".join(rule.pattern for rule in rules if rule.enabled))
        root.addWidget(self._editor, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def proposed_rules(self, source_id: EntityId) -> list[ExclusionRule]:
        patterns: list[str] = []
        for raw in self._editor.toPlainText().splitlines():
            pattern = raw.strip()
            if pattern and pattern not in patterns:
                patterns.append(pattern)

        rules: list[ExclusionRule] = []
        for pattern in patterns:
            existing = self._existing.get(pattern)
            if existing is not None:
                rules.append(
                    ExclusionRule(
                        id=existing.id,
                        source_id=source_id,
                        pattern=existing.pattern,
                        pattern_type=existing.pattern_type,
                        enabled=True,
                    )
                )
                continue
            pattern_type = (
                ExclusionPatternType.HIDDEN_POLICY
                if pattern == "hidden"
                else ExclusionPatternType.GLOB
            )
            rules.append(
                ExclusionRule(
                    id=new_entity_id(),
                    source_id=source_id,
                    pattern=pattern,
                    pattern_type=pattern_type,
                    enabled=True,
                )
            )
        return rules


class SourceDetailScreen(QWidget):
    """Operational Source Detail workspace bound to SourceService and JobScheduler."""

    back_requested = Signal()

    def __init__(
        self,
        context: AppContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._source_service = context.source_service
        self._source_id: EntityId | None = None
        self._source_name = ""
        self.setObjectName("sourceDetailScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        back = QPushButton("Back to Sources")
        back.setObjectName("backToSourcesButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)

        self._title = QLabel("Source Detail")
        self._title.setObjectName("pageTitle")
        header.addWidget(self._title)
        header.addStretch(1)

        self._rescan = QPushButton("Rescan")
        self._rescan.setObjectName("sourceRescanButton")
        self._rescan.setProperty("class", "primaryButton")
        self._rescan.clicked.connect(self._rescan_source)
        header.addWidget(self._rescan)

        self._pause = QPushButton("Pause")
        self._pause.setObjectName("sourcePauseButton")
        self._pause.clicked.connect(self._toggle_pause)
        header.addWidget(self._pause)

        self._cancel = QPushButton("Cancel Scan")
        self._cancel.setObjectName("sourceCancelScanButton")
        self._cancel.clicked.connect(self._cancel_scan)
        header.addWidget(self._cancel)

        self._toggle_enabled_btn = QPushButton("Disable")
        self._toggle_enabled_btn.setObjectName("sourceToggleEnabledButton")
        self._toggle_enabled_btn.clicked.connect(self._toggle_enabled)
        header.addWidget(self._toggle_enabled_btn)
        root.addLayout(header)

        path_row = QHBoxLayout()
        self._status = QLabel("")
        self._status.setObjectName("sourceDetailStatus")
        path_row.addWidget(self._status)

        self._path = QLabel("")
        self._path.setObjectName("sourceDetailPath")
        self._path.setWordWrap(True)
        path_row.addWidget(self._path, stretch=1)

        open_files = QPushButton("Open in Files")
        open_files.setObjectName("sourceOpenInFilesButton")
        open_files.clicked.connect(self._open_in_files)
        path_row.addWidget(open_files)
        root.addLayout(path_row)

        self._counts = QLabel("")
        self._counts.setObjectName("sourceDetailCounts")
        self._counts.setWordWrap(True)
        root.addWidget(self._counts)

        exclusion_header = QHBoxLayout()
        exclusions_heading = QLabel("EXCLUSIONS")
        exclusions_heading.setObjectName("sectionLabel")
        exclusion_header.addWidget(exclusions_heading)
        exclusion_header.addStretch(1)
        edit_rules = QPushButton("Edit Rules")
        edit_rules.setObjectName("sourceEditExclusionsButton")
        edit_rules.clicked.connect(self._edit_exclusions)
        exclusion_header.addWidget(edit_rules)
        root.addLayout(exclusion_header)

        self._exclusions = QLabel("")
        self._exclusions.setObjectName("sourceDetailExclusions")
        self._exclusions.setWordWrap(True)
        root.addWidget(self._exclusions)

        jobs_heading = QLabel("RECENT JOBS")
        jobs_heading.setObjectName("sectionLabel")
        root.addWidget(jobs_heading)

        self._jobs = QListWidget()
        self._jobs.setObjectName("sourceDetailJobs")
        root.addWidget(self._jobs, stretch=1)

        files_heading = QLabel("INDEXED FILES")
        files_heading.setObjectName("sectionLabel")
        root.addWidget(files_heading)

        self._files = QListWidget()
        self._files.setObjectName("sourceDetailFiles")
        root.addWidget(self._files, stretch=2)

        footer = QHBoxLayout()
        footer.addStretch(1)
        remove = QPushButton("Remove from Koffer")
        remove.setObjectName("sourceRemoveButton")
        remove.clicked.connect(self._remove_source)
        footer.addWidget(remove)
        root.addLayout(footer)

    @property
    def source_name(self) -> str:
        return self._source_name

    def show_source(self, source_id: EntityId) -> None:
        self._source_id = source_id
        self.refresh()

    def refresh(self) -> None:
        if self._source_id is None:
            return
        detail = self._source_service.get_detail(self._source_id)
        source = detail.source
        self._source_name = source.display_name
        status_text, status_name = _status_label(source)
        self._title.setText(source.display_name)
        enabled = "enabled" if source.enabled else "disabled"
        self._status.setText(f"{status_text} · {enabled}")
        self._status.setProperty("sourceStatus", str(source.status))
        self._status.setProperty("statusKind", status_name)
        self._path.setText(source.root_path)
        self._counts.setText(
            f"{detail.sample_count} indexed · {detail.issue_count} issue(s) · "
            f"{detail.pending_analysis_count} pending analysis · "
            f"last successful scan {source.last_scan_completed_at or 'never'} · "
            f"last scan started {source.last_scan_started_at or 'never'}"
        )

        if detail.exclusions:
            self._exclusions.setText(
                " · ".join(
                    rule.pattern + ("" if rule.enabled else " (disabled)")
                    for rule in detail.exclusions
                )
            )
        else:
            self._exclusions.setText("No exclusion rules.")

        self._jobs.clear()
        if detail.recent_jobs:
            for job in detail.recent_jobs:
                progress = ""
                if job.progress_total:
                    progress = f" · {job.progress_current}/{job.progress_total}"
                self._jobs.addItem(
                    QListWidgetItem(
                        f"{job.type} · {job.state}{progress}\n"
                        f"{job.stage or '—'} · created {job.created_at}"
                    )
                )
        else:
            self._jobs.addItem(QListWidgetItem("No jobs yet."))

        self._files.clear()
        if detail.samples:
            for sample in detail.samples:
                self._files.addItem(
                    QListWidgetItem(
                        f"{sample.filename}\n"
                        f"{sample.relative_path} · {sample.availability}"
                    )
                )
        else:
            self._files.addItem(QListWidgetItem("No indexed Samples yet."))

        current = detail.current_job
        pausable = current is not None and current.state in {
            JobState.QUEUED,
            JobState.RUNNING,
            JobState.PAUSE_REQUESTED,
            JobState.PAUSED,
        }
        self._pause.setEnabled(pausable)
        self._cancel.setEnabled(current is not None)
        if current is not None and current.state in {
            JobState.PAUSE_REQUESTED,
            JobState.PAUSED,
        }:
            self._pause.setText("Resume")
        else:
            self._pause.setText("Pause")

        self._rescan.setEnabled(source.enabled and current is None)
        self._toggle_enabled_btn.setText("Disable" if source.enabled else "Enable")

        if source.status is SourceStatus.OFFLINE:
            self._status.setStyleSheet("color: #D7B65E; font-weight: 600;")
        elif not source.enabled or source.status is SourceStatus.DISABLED:
            self._status.setStyleSheet("color: #66717C; font-weight: 600;")
        else:
            self._status.setStyleSheet("color: #67B983; font-weight: 600;")

    def _rescan_source(self) -> None:
        if self._source_id is None:
            return
        try:
            self._source_service.scan(self._source_id)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not rescan Source", str(exc))
            return
        self.refresh()

    def _toggle_pause(self) -> None:
        if self._source_id is None:
            return
        detail = self._source_service.get_detail(self._source_id)
        job = detail.current_job
        if job is None:
            return
        try:
            if job.state in {JobState.PAUSE_REQUESTED, JobState.PAUSED}:
                self._context.scheduler.resume(job.id)
            else:
                self._context.scheduler.pause(job.id)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not change scan state", str(exc))
            return
        self.refresh()

    def _cancel_scan(self) -> None:
        if self._source_id is None:
            return
        job = self._source_service.get_detail(self._source_id).current_job
        if job is None:
            return
        self._context.scheduler.cancel(job.id)
        self.refresh()

    def _toggle_enabled(self) -> None:
        if self._source_id is None:
            return
        source = self._source_service.get(self._source_id)
        try:
            self._source_service.set_enabled(self._source_id, not source.enabled)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not update Source", str(exc))
            return
        self.refresh()

    def _open_in_files(self) -> None:
        if self._source_id is None:
            return
        source = self._source_service.get(self._source_id)
        QDesktopServices.openUrl(QUrl.fromLocalFile(source.root_path))

    def _edit_exclusions(self) -> None:
        if self._source_id is None:
            return
        detail = self._source_service.get_detail(self._source_id)
        editor = _ExclusionEditor(detail.exclusions, self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        proposed = editor.proposed_rules(self._source_id)
        try:
            preview = self._source_service.preview_exclusion_rules(
                self._source_id,
                proposed,
            )
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not preview exclusions", str(exc))
            return

        examples = "\n".join(preview.matched_relative_paths[:8])
        if examples:
            examples = f"\n\nExamples:\n{examples}"
        answer = QMessageBox.question(
            self,
            "Apply Source Exclusions?",
            (
                f"These rules would exclude {preview.excluded_count} supported path(s) "
                f"and leave {preview.included_supported_count} included."
                f"{examples}\n\n"
                "Applying rules changes Koffer indexing only; audio files are not deleted."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._source_service.update_exclusions(self._source_id, proposed)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not apply exclusions", str(exc))
            return
        self.refresh()

    def _remove_source(self) -> None:
        if self._source_id is None:
            return
        source = self._source_service.get(self._source_id)
        answer = QMessageBox.question(
            self,
            "Remove Source from Koffer?",
            (
                f'Remove "{source.display_name}" from Koffer?\n\n'
                "Indexed Sample records for this Source will be removed from Koffer. "
                "Audio files on disk will not be deleted or moved."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._source_service.remove_source(self._source_id)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not remove Source", str(exc))
            return
        self._source_id = None
        self._source_name = ""
        self.back_requested.emit()
