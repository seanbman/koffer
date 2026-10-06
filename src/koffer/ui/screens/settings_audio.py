"""S19 Settings: Audio & Interface foundations."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.ui.tokens import MUTED


class SettingsAudioScreen(QWidget):
    """Playback device, preview, UI density, and reduced-motion controls."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("settingsAudioScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        title = QLabel("Settings — Audio & Interface")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "Output device and preview defaults apply live where the backend allows. "
            "Invalid devices fall back to the system default without stranding the UI."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)

        form = QFormLayout()
        self._device = QComboBox()
        self._device.setObjectName("settingsOutputDevice")
        self._device.addItem("System default", "default")
        form.addRow("Output device", self._device)

        self._gain = QDoubleSpinBox()
        self._gain.setObjectName("settingsPreviewGain")
        self._gain.setRange(-60.0, 12.0)
        self._gain.setSingleStep(1.0)
        self._gain.setSuffix(" dB")
        form.addRow("Preview gain", self._gain)

        self._auto_preview = QCheckBox("Auto-preview on selection")
        self._auto_preview.setObjectName("settingsAutoPreview")
        form.addRow(self._auto_preview)

        self._loop = QCheckBox("Loop preview by default")
        self._loop.setObjectName("settingsLoopPreview")
        form.addRow(self._loop)

        self._density = QComboBox()
        self._density.setObjectName("settingsUiDensity")
        self._density.addItem("Comfortable", "comfortable")
        self._density.addItem("Compact", "compact")
        form.addRow("UI density", self._density)

        self._inspector = QCheckBox("Inspector open by default")
        self._inspector.setObjectName("settingsInspectorDefault")
        form.addRow(self._inspector)

        self._theme = QComboBox()
        self._theme.setObjectName("settingsTheme")
        self._theme.addItem("Dark", "dark")
        form.addRow("Theme", self._theme)

        self._reduced_motion = QCheckBox("Reduced motion")
        self._reduced_motion.setObjectName("settingsReducedMotion")
        form.addRow(self._reduced_motion)

        root.addLayout(form)

        shortcuts = QLabel(
            "Keyboard shortcuts follow the documented desktop defaults; "
            "editing is not yet exposed here."
        )
        shortcuts.setObjectName("settingsShortcutEditorPlaceholder")
        shortcuts.setStyleSheet(f"color: {MUTED};")
        root.addWidget(shortcuts)

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("settingsAudioApplyButton")
        apply_btn.clicked.connect(self._apply)
        root.addWidget(apply_btn)
        root.addStretch(1)

    def refresh(self) -> None:
        audio = self._context.settings_service.load().audio_interface
        index = self._device.findData(audio.output_device)
        self._device.setCurrentIndex(index if index >= 0 else 0)
        self._gain.setValue(float(audio.preview_gain))
        self._auto_preview.setChecked(audio.auto_preview)
        self._loop.setChecked(audio.loop_preview_default)
        density_index = self._density.findData(audio.ui_density)
        self._density.setCurrentIndex(density_index if density_index >= 0 else 0)
        self._inspector.setChecked(audio.inspector_default_open)
        theme_index = self._theme.findData(audio.theme)
        self._theme.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self._reduced_motion.setChecked(audio.reduced_motion)

    def _apply(self) -> None:
        self._context.settings_service.update_audio_interface(
            output_device=str(self._device.currentData() or "default"),
            preview_gain=float(self._gain.value()),
            auto_preview=self._auto_preview.isChecked(),
            loop_preview_default=self._loop.isChecked(),
            ui_density=str(self._density.currentData() or "compact"),
            inspector_default_open=self._inspector.isChecked(),
            theme=str(self._theme.currentData() or "dark"),
            reduced_motion=self._reduced_motion.isChecked(),
        )
        self._context.playback_service.set_gain_db(float(self._gain.value()))
        self.refresh()
