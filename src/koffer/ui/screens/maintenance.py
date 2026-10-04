"""S20 Maintenance & Backup foundations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.domain.enums import CacheCategory
from koffer.domain.errors import ApplicationError
from koffer.services.maintenance import PRESERVE_NOTES
from koffer.ui.tokens import MUTED


class MaintenanceScreen(QWidget):
    """Backup/restore/rebuild/cache controls with preserve notes."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("maintenanceScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        title = QLabel("Maintenance & Backup")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "Every action states what is preserved versus rebuilt. "
            "Long work runs as a Job; the UI stays interactive."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)

        self._usage = QLabel("")
        self._usage.setObjectName("maintenanceStorageUsage")
        root.addWidget(self._usage)

        self._note = QTextEdit()
        self._note.setObjectName("maintenancePreserveNote")
        self._note.setReadOnly(True)
        self._note.setFixedHeight(96)
        root.addWidget(self._note)

        grid = QVBoxLayout()
        grid.setSpacing(8)
        self._add_action(grid, "Back Up Library", "backup", self._backup)
        self._add_action(grid, "Restore Library", "restore", self._restore)
        self._add_action(grid, "Verify Database", "verify", self._verify)
        self._add_action(
            grid, "Rebuild Filesystem Index", "rebuild_filesystem_index", self._rebuild_fs
        )
        self._add_action(grid, "Rebuild Waveforms", "rebuild_waveforms", self._rebuild_waveforms)
        self._add_action(grid, "Rebuild Analysis", "rebuild_analysis", self._rebuild_analysis)
        self._add_action(
            grid, "Rebuild Similarity Index", "rebuild_similarity", self._rebuild_similarity
        )
        self._add_action(grid, "Clear Rebuildable Cache", "clear_cache", self._clear_cache)
        root.addLayout(grid)
        root.addStretch(1)
        self._show_note("backup")

    def refresh(self) -> None:
        usage = self._context.maintenance_service.storage_usage()
        self._usage.setText(
            "Storage — "
            f"database: {usage['database_bytes']} B · "
            f"data: {usage['data_dir_bytes']} B · "
            f"cache: {usage['cache_dir_bytes']} B"
        )

    def _add_action(
        self,
        layout: QVBoxLayout,
        label: str,
        note_key: str,
        handler: Callable[[], None],
    ) -> None:
        row = QHBoxLayout()
        button = QPushButton(label)
        object_name = {
            "backup": "maintenanceBackupButton",
            "restore": "maintenanceRestoreButton",
            "verify": "maintenanceVerifyButton",
            "rebuild_filesystem_index": "maintenanceRebuildFilesystemButton",
            "rebuild_waveforms": "maintenanceRebuildWaveformsButton",
            "rebuild_analysis": "maintenanceRebuildAnalysisButton",
            "rebuild_similarity": "maintenanceRebuildSimilarityButton",
            "clear_cache": "maintenanceClearCacheButton",
        }[note_key]
        button.setObjectName(object_name)
        button.clicked.connect(handler)
        button.pressed.connect(lambda key=note_key: self._show_note(key))
        row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)

    def _show_note(self, key: str) -> None:
        self._note.setPlainText(PRESERVE_NOTES.get(key, ""))

    def _backup(self) -> None:
        self._show_note("backup")
        destination = QFileDialog.getExistingDirectory(self, "Choose backup destination")
        if not destination:
            return
        try:
            job_id = self._context.maintenance_service.backup(Path(destination))
        except ApplicationError as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))
            return
        QMessageBox.information(self, "Backup started", f"Job {job_id} queued.")

    def _restore(self) -> None:
        self._show_note("restore")
        backup_dir = QFileDialog.getExistingDirectory(self, "Choose backup directory")
        if not backup_dir:
            return
        confirm = QMessageBox.question(
            self,
            "Restore library?",
            PRESERVE_NOTES["restore"] + "\n\nContinue?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            job_id = self._context.maintenance_service.restore(Path(backup_dir))
        except ApplicationError as exc:
            QMessageBox.warning(self, "Restore failed", str(exc))
            return
        QMessageBox.information(self, "Restore started", f"Job {job_id} queued.")

    def _verify(self) -> None:
        self._show_note("verify")
        job_id = self._context.maintenance_service.verify_database(deep=False)
        QMessageBox.information(self, "Verify started", f"Job {job_id} queued.")

    def _rebuild_fs(self) -> None:
        self._show_note("rebuild_filesystem_index")
        job_id = self._context.maintenance_service.rebuild_filesystem_index()
        QMessageBox.information(self, "Rebuild started", f"Job {job_id} queued.")

    def _rebuild_waveforms(self) -> None:
        self._show_note("rebuild_waveforms")
        job_id = self._context.maintenance_service.rebuild_waveforms()
        QMessageBox.information(self, "Rebuild started", f"Job {job_id} queued.")

    def _rebuild_analysis(self) -> None:
        self._show_note("rebuild_analysis")
        job_id = self._context.maintenance_service.rebuild_analysis()
        QMessageBox.information(self, "Rebuild started", f"Job {job_id} queued.")

    def _rebuild_similarity(self) -> None:
        self._show_note("rebuild_similarity")
        job_id = self._context.maintenance_service.rebuild_similarity()
        QMessageBox.information(self, "Rebuild started", f"Job {job_id} queued.")

    def _clear_cache(self) -> None:
        self._show_note("clear_cache")
        confirm = QMessageBox.question(
            self,
            "Clear rebuildable cache?",
            PRESERVE_NOTES["clear_cache"],
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        job_id = self._context.maintenance_service.clear_cache(
            {
                CacheCategory.WAVEFORMS,
                CacheCategory.EMBEDDINGS,
                CacheCategory.SIMILARITY_INDEX,
                CacheCategory.TEMP_RENDERS,
            }
        )
        QMessageBox.information(self, "Cache clear started", f"Job {job_id} queued.")
