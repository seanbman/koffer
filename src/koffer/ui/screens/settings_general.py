"""S17 Settings: General foundations."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.ui.tokens import MUTED


class SettingsGeneralScreen(QWidget):
    """Startup, paths, notifications; destructive confirms stay locked on."""

    open_library_settings_requested = Signal()
    open_audio_settings_requested = Signal()

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("settingsGeneralScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Settings — General")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        library_btn = QPushButton("Library & Analysis")
        library_btn.setObjectName("settingsOpenLibraryButton")
        library_btn.setProperty("class", "secondaryButton")
        library_btn.clicked.connect(self.open_library_settings_requested.emit)
        header.addWidget(library_btn)
        audio_btn = QPushButton("Audio & Interface")
        audio_btn.setObjectName("settingsOpenAudioButton")
        audio_btn.setProperty("class", "secondaryButton")
        audio_btn.clicked.connect(self.open_audio_settings_requested.emit)
        header.addWidget(audio_btn)
        root.addLayout(header)

        hint = QLabel(
            "Grouped by user concepts. Live-applicable toggles apply immediately. "
            "Destructive filesystem confirmations cannot be globally disabled."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)

        form = QFormLayout()
        self._restore_workspace = QCheckBox("Restore last workspace on launch")
        self._restore_workspace.setObjectName("settingsRestoreWorkspace")
        form.addRow(self._restore_workspace)

        self._notifications = QCheckBox("Show notifications")
        self._notifications.setObjectName("settingsNotifications")
        form.addRow(self._notifications)

        self._confirm_nondestructive = QCheckBox("Confirm non-destructive actions")
        self._confirm_nondestructive.setObjectName("settingsConfirmNonDestructive")
        form.addRow(self._confirm_nondestructive)

        self._confirm_destructive = QCheckBox("Confirm destructive filesystem actions")
        self._confirm_destructive.setObjectName("settingsConfirmDestructive")
        self._confirm_destructive.setEnabled(False)
        self._confirm_destructive.setChecked(True)
        form.addRow(self._confirm_destructive)

        self._db_path = QLineEdit()
        self._db_path.setObjectName("settingsDatabasePath")
        self._db_path.setReadOnly(True)
        form.addRow("Database path", self._db_path)

        self._managed_path = QLineEdit()
        self._managed_path.setObjectName("settingsManagedLibraryPath")
        form.addRow("Managed library path", self._managed_path)

        self._temp_path = QLineEdit()
        self._temp_path.setObjectName("settingsTempRenderPath")
        form.addRow("Temporary render path", self._temp_path)

        root.addLayout(form)

        save = QPushButton("Apply")
        save.setObjectName("settingsGeneralApplyButton")
        save.clicked.connect(self._apply)
        root.addWidget(save)
        root.addStretch(1)

    def refresh(self) -> None:
        settings = self._context.settings_service.load()
        general = settings.general
        self._restore_workspace.setChecked(general.restore_last_workspace)
        self._notifications.setChecked(general.show_notifications)
        self._confirm_nondestructive.setChecked(general.confirm_non_destructive)
        self._confirm_destructive.setChecked(True)
        db = str(self._context.connection_factory.database_path)
        self._db_path.setText(general.database_path or db)
        self._managed_path.setText(
            general.managed_library_path or str(self._context.paths.data_dir / "managed")
        )
        self._temp_path.setText(
            general.temp_render_path or str(self._context.paths.cache_dir / "renders")
        )

    def _apply(self) -> None:
        self._context.settings_service.update_general(
            restore_last_workspace=self._restore_workspace.isChecked(),
            show_notifications=self._notifications.isChecked(),
            confirm_non_destructive=self._confirm_nondestructive.isChecked(),
            confirm_destructive_filesystem=True,
            managed_library_path=self._managed_path.text().strip(),
            database_path=self._db_path.text().strip(),
            temp_render_path=self._temp_path.text().strip(),
        )
        self.refresh()
