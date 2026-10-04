"""S18 Settings: Library & Analysis foundations."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.ui.tokens import MUTED


class SettingsLibraryScreen(QWidget):
    """Scan, cache, inference, and similarity policy controls."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("settingsLibraryScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(12)

        title = QLabel("Settings — Library & Analysis")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "Controls scanning defaults, analysis concurrency, waveform cache, "
            "and local model/similarity policy."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)

        form = QFormLayout()
        self._recursive = QCheckBox("Recursive scanning")
        self._recursive.setObjectName("settingsRecursiveScanning")
        form.addRow(self._recursive)

        self._skip_hidden = QCheckBox("Skip hidden folders by default")
        self._skip_hidden.setObjectName("settingsSkipHidden")
        form.addRow(self._skip_hidden)

        self._auto_analysis = QCheckBox("Automatic analysis on discovery")
        self._auto_analysis.setObjectName("settingsAutomaticAnalysis")
        form.addRow(self._auto_analysis)

        self._concurrency = QSpinBox()
        self._concurrency.setObjectName("settingsAnalysisConcurrency")
        self._concurrency.setRange(1, 16)
        form.addRow("Analysis concurrency", self._concurrency)

        self._idle_deep = QCheckBox("Idle-only deep analysis")
        self._idle_deep.setObjectName("settingsIdleOnlyDeep")
        form.addRow(self._idle_deep)

        self._waveforms = QCheckBox("Waveform cache enabled")
        self._waveforms.setObjectName("settingsWaveformCache")
        form.addRow(self._waveforms)

        self._similarity = QCheckBox("Similarity indexing")
        self._similarity.setObjectName("settingsSimilarityIndexing")
        form.addRow(self._similarity)

        self._local_model = QCheckBox("Local model enabled")
        self._local_model.setObjectName("settingsLocalModelEnabled")
        form.addRow(self._local_model)

        self._cache_limit = QSpinBox()
        self._cache_limit.setObjectName("settingsCacheLimitMb")
        self._cache_limit.setRange(256, 1024 * 1024)
        self._cache_limit.setSuffix(" MB")
        form.addRow("Cache limit", self._cache_limit)

        root.addLayout(form)

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("settingsLibraryApplyButton")
        apply_btn.clicked.connect(self._apply)
        root.addWidget(apply_btn)
        root.addStretch(1)

    def refresh(self) -> None:
        lib = self._context.settings_service.load().library_analysis
        self._recursive.setChecked(lib.recursive_scanning)
        self._skip_hidden.setChecked(lib.skip_hidden_folders)
        self._auto_analysis.setChecked(lib.automatic_analysis)
        self._concurrency.setValue(lib.analysis_concurrency)
        self._idle_deep.setChecked(lib.idle_only_deep_analysis)
        self._waveforms.setChecked(lib.waveform_cache_enabled)
        self._similarity.setChecked(lib.similarity_indexing)
        self._local_model.setChecked(lib.local_model_enabled)
        self._cache_limit.setValue(lib.cache_limit_mb)

    def _apply(self) -> None:
        self._context.settings_service.update_library_analysis(
            recursive_scanning=self._recursive.isChecked(),
            skip_hidden_folders=self._skip_hidden.isChecked(),
            automatic_analysis=self._auto_analysis.isChecked(),
            analysis_concurrency=self._concurrency.value(),
            idle_only_deep_analysis=self._idle_deep.isChecked(),
            waveform_cache_enabled=self._waveforms.isChecked(),
            similarity_indexing=self._similarity.isChecked(),
            local_model_enabled=self._local_model.isChecked(),
            cache_limit_mb=self._cache_limit.value(),
        )
        self.refresh()
