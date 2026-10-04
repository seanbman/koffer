"""S21 About & Diagnostics foundations."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from PySide6.QtCore import Qt, qVersion
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

from koffer import __version__ as KOFFER_VERSION
from koffer.app_context import AppContext
from koffer.diagnostics import build_diagnostics_bundle
from koffer.ui.tokens import MUTED


class AboutDiagnosticsScreen(QWidget):
    """Version/build, paths, licenses, diagnostics export excluding audio."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("aboutDiagnosticsScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        title = QLabel("About & Diagnostics")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self._version = QLabel("")
        self._version.setObjectName("aboutVersionLabel")
        self._version.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._version)

        self._paths = QTextEdit()
        self._paths.setObjectName("aboutPathsText")
        self._paths.setReadOnly(True)
        self._paths.setFixedHeight(140)
        root.addWidget(self._paths)

        self._bundle_contents = QTextEdit()
        self._bundle_contents.setObjectName("aboutDiagnosticsContents")
        self._bundle_contents.setReadOnly(True)
        self._bundle_contents.setFixedHeight(120)
        self._bundle_contents.setPlainText(
            "Diagnostics bundle includes version/build, OS, Qt/Python, XDG paths, "
            "schema version, Source status summary, and sanitized logs.\n"
            "Excluded by default: audio files, waveform cache, embeddings, cover art, "
            "and database content."
        )
        root.addWidget(self._bundle_contents)

        licenses = QLabel("Licenses: MIT (Koffer). Third-party notices ship with the package.")
        licenses.setObjectName("aboutLicensesLabel")
        licenses.setStyleSheet(f"color: {MUTED};")
        root.addWidget(licenses)

        actions = QHBoxLayout()
        copy_btn = QPushButton("Copy version info")
        copy_btn.setObjectName("aboutCopyVersionButton")
        copy_btn.setProperty("class", "secondaryButton")
        copy_btn.clicked.connect(self._copy_version)
        actions.addWidget(copy_btn)

        export_btn = QPushButton("Create Diagnostics Bundle")
        export_btn.setObjectName("aboutCreateDiagnosticsButton")
        export_btn.clicked.connect(self._export_diagnostics)
        actions.addWidget(export_btn)
        actions.addStretch(1)
        root.addLayout(actions)
        root.addStretch(1)

    def refresh(self) -> None:
        paths = self._context.paths
        self._version.setText(
            f"Koffer {KOFFER_VERSION} · Python {sys.version.split()[0]} · "
            f"Qt {qVersion()} · {platform.system()} {platform.release()}"
        )
        self._paths.setPlainText(
            "\n".join(
                [
                    f"config: {paths.config_dir}",
                    f"data: {paths.data_dir}",
                    f"cache: {paths.cache_dir}",
                    f"state: {paths.state_dir}",
                    f"logs: {paths.log_dir}",
                    f"database: {self._context.connection_factory.database_path}",
                ]
            )
        )

    def _copy_version(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._version.text())

    def _export_diagnostics(self) -> None:
        destination, _filter = QFileDialog.getSaveFileName(
            self,
            "Save diagnostics bundle",
            "koffer-diagnostics.zip",
            "Zip archive (*.zip)",
        )
        if not destination:
            return
        result = build_diagnostics_bundle(
            Path(destination),
            paths=self._context.paths,
            connection_factory=self._context.connection_factory,
            include_audio=False,
        )
        QMessageBox.information(
            self,
            "Diagnostics exported",
            (
                f"Wrote {result.path}.\n"
                f"Included {len(result.included_names)} entries.\n"
                "Audio/waveforms/embeddings excluded by default."
            ),
        )
