"""S18 Settings: Library & Analysis — Local AI card (docs/32)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.domain.errors import ApplicationError
from koffer.services.local_ai import LocalAiStatus, LocalAiStatusKind
from koffer.ui.tokens import (
    BORDER,
    CANVAS,
    CLAY,
    GREEN,
    MUTED,
    RED,
    SURFACE_1,
    SURFACE_2,
    TEXT,
    YELLOW,
)


def _form_label(text: str, object_name: str) -> QLabel:
    """Explicit light-on-dark form caption (QFormLayout string rows default black)."""
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setStyleSheet(f"color: {TEXT};")
    return label


class SettingsLibraryScreen(QWidget):
    """Scan, cache, inference, and Local AI policy controls."""

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("settingsLibraryScreen")

        self.setStyleSheet(
            f"QWidget#settingsLibraryScreen {{ background-color: {CANVAS}; color: {TEXT}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("settingsLibraryScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea#settingsLibraryScroll {{ background-color: {CANVAS}; border: none; }}"
        )
        scroll.viewport().setAutoFillBackground(True)
        scroll.viewport().setStyleSheet(f"background-color: {CANVAS};")
        outer.addWidget(scroll)

        body = QWidget()
        body.setObjectName("settingsLibraryBody")
        body.setAutoFillBackground(True)
        body.setStyleSheet(
            f"QWidget#settingsLibraryBody {{ background-color: {CANVAS}; color: {TEXT}; }}"
            f"QWidget#settingsLibraryBody QLabel#settingsAnalysisConcurrencyLabel,"
            f"QWidget#settingsLibraryBody QLabel#settingsCacheLimitLabel {{ color: {TEXT}; }}"
            f"QWidget#settingsLibraryBody QCheckBox {{ color: {TEXT}; }}"
        )
        scroll.setWidget(body)

        root = QVBoxLayout(body)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        title = QLabel("Settings — Library & Analysis")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "Controls scanning defaults, analysis concurrency, waveform cache, "
            "and on-device Local AI."
        )
        hint.setObjectName("bodyText")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        root.addWidget(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
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
        form.addRow(
            _form_label("Analysis concurrency", "settingsAnalysisConcurrencyLabel"),
            self._concurrency,
        )

        self._idle_deep = QCheckBox("Idle-only deep analysis")
        self._idle_deep.setObjectName("settingsIdleOnlyDeep")
        form.addRow(self._idle_deep)

        self._waveforms = QCheckBox("Waveform cache enabled")
        self._waveforms.setObjectName("settingsWaveformCache")
        form.addRow(self._waveforms)

        self._similarity = QCheckBox("Similarity indexing")
        self._similarity.setObjectName("settingsSimilarityIndexing")
        form.addRow(self._similarity)

        self._cache_limit = QSpinBox()
        self._cache_limit.setObjectName("settingsCacheLimitMb")
        self._cache_limit.setRange(256, 1024 * 1024)
        self._cache_limit.setSuffix(" MB")
        form.addRow(
            _form_label("Cache limit", "settingsCacheLimitLabel"),
            self._cache_limit,
        )

        root.addLayout(form)

        root.addWidget(self._build_local_ai_card())

        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("settingsLibraryApplyButton")
        apply_btn.clicked.connect(self._apply)
        root.addWidget(apply_btn)
        root.addStretch(1)

    def _build_local_ai_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsLocalAiCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card.setStyleSheet(
            f"QFrame#settingsLocalAiCard {{"
            f"background-color: {SURFACE_2}; border: 1px solid {BORDER};"
            f"border-radius: 8px; }}"
            f"QFrame#settingsLocalAiCard QLabel {{ background: transparent; }}"
            f"QFrame#settingsLocalAiCard QPushButton:disabled {{"
            f"color: {MUTED}; background-color: {SURFACE_1}; border-color: {BORDER}; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QLabel("Local AI")
        heading.setObjectName("settingsLocalAiHeading")
        heading.setStyleSheet(f"color: {TEXT}; font-weight: 700; font-size: 14px;")
        layout.addWidget(heading)

        self._local_ai_state = QLabel("")
        self._local_ai_state.setObjectName("settingsLocalAiState")
        self._local_ai_state.setWordWrap(True)
        layout.addWidget(self._local_ai_state)

        self._local_ai_headline = QLabel("")
        self._local_ai_headline.setObjectName("settingsLocalAiHeadline")
        self._local_ai_headline.setWordWrap(True)
        self._local_ai_headline.setStyleSheet(f"color: {TEXT}; font-weight: 650;")
        layout.addWidget(self._local_ai_headline)

        self._local_ai_detail = QLabel("")
        self._local_ai_detail.setObjectName("settingsLocalAiDetail")
        self._local_ai_detail.setWordWrap(True)
        self._local_ai_detail.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(self._local_ai_detail)

        self._local_ai_meta = QLabel("")
        self._local_ai_meta.setObjectName("settingsLocalAiMeta")
        self._local_ai_meta.setWordWrap(True)
        self._local_ai_meta.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(self._local_ai_meta)

        self._local_ai_privacy = QLabel("")
        self._local_ai_privacy.setObjectName("settingsLocalAiPrivacy")
        self._local_ai_privacy.setWordWrap(True)
        self._local_ai_privacy.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(self._local_ai_privacy)

        primary = QWidget()
        primary.setObjectName("settingsLocalAiPrimaryActions")
        primary_layout = QVBoxLayout(primary)
        primary_layout.setContentsMargins(0, 4, 0, 0)
        primary_layout.setSpacing(8)

        self._install_btn = QPushButton("Install Model")
        self._install_btn.setObjectName("settingsLocalAiInstallButton")
        self._install_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._install_btn.clicked.connect(self._install_model)
        primary_layout.addWidget(self._install_btn)

        self._enable_btn = QPushButton("Enable Local AI")
        self._enable_btn.setObjectName("settingsLocalAiEnableButton")
        self._enable_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._enable_btn.clicked.connect(self._toggle_enabled)
        primary_layout.addWidget(self._enable_btn)

        self._backfill_btn = QPushButton("Analyze Existing Library")
        self._backfill_btn.setObjectName("settingsLocalAiBackfillButton")
        self._backfill_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._backfill_btn.clicked.connect(self._analyze_existing)
        primary_layout.addWidget(self._backfill_btn)
        layout.addWidget(primary)

        rebuild = QWidget()
        rebuild.setObjectName("settingsLocalAiRebuildActions")
        rebuild_layout = QVBoxLayout(rebuild)
        rebuild_layout.setContentsMargins(0, 4, 0, 0)
        rebuild_layout.setSpacing(8)

        self._rebuild_suggestions_btn = QPushButton("Rebuild Suggestions")
        self._rebuild_suggestions_btn.setObjectName("settingsLocalAiRebuildSuggestionsButton")
        self._rebuild_suggestions_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._rebuild_suggestions_btn.clicked.connect(self._rebuild_suggestions)
        rebuild_layout.addWidget(self._rebuild_suggestions_btn)

        self._rebuild_similarity_btn = QPushButton("Rebuild Similarity Index")
        self._rebuild_similarity_btn.setObjectName("settingsLocalAiRebuildSimilarityButton")
        self._rebuild_similarity_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._rebuild_similarity_btn.clicked.connect(self._rebuild_similarity)
        rebuild_layout.addWidget(self._rebuild_similarity_btn)
        layout.addWidget(rebuild)

        self._local_ai_action_note = QLabel("")
        self._local_ai_action_note.setObjectName("settingsLocalAiActionNote")
        self._local_ai_action_note.setWordWrap(True)
        self._local_ai_action_note.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(self._local_ai_action_note)

        return card

    def refresh(self) -> None:
        lib = self._context.settings_service.load().library_analysis
        self._recursive.setChecked(lib.recursive_scanning)
        self._skip_hidden.setChecked(lib.skip_hidden_folders)
        self._auto_analysis.setChecked(lib.automatic_analysis)
        self._concurrency.setValue(lib.analysis_concurrency)
        self._idle_deep.setChecked(lib.idle_only_deep_analysis)
        self._waveforms.setChecked(lib.waveform_cache_enabled)
        self._similarity.setChecked(lib.similarity_indexing)
        self._cache_limit.setValue(lib.cache_limit_mb)
        self._refresh_local_ai()

    def _refresh_local_ai(self) -> None:
        status = self._context.local_ai_service.status()
        self._apply_local_ai_status(status)

    def _apply_local_ai_status(self, status: LocalAiStatus) -> None:
        state_color = {
            LocalAiStatusKind.NOT_INSTALLED: YELLOW,
            LocalAiStatusKind.MANIFEST_BLOCKED: YELLOW,
            LocalAiStatusKind.INSTALLED_DISABLED: CLAY,
            LocalAiStatusKind.ENABLED: GREEN,
            LocalAiStatusKind.ERROR: RED,
            LocalAiStatusKind.DOWNLOADING: CLAY,
        }.get(status.kind, MUTED)
        self._local_ai_state.setText(status.kind.value.replace("_", " ").upper())
        self._local_ai_state.setStyleSheet(
            f"color: {state_color}; font-size: 11px; font-weight: 700;"
        )
        self._local_ai_headline.setText(status.headline)
        self._local_ai_detail.setText(status.detail)
        self._local_ai_meta.setText(
            f"{status.provider_label} · {status.model_version} · {status.size_label} · "
            f"{status.embedding_index_label}"
        )
        self._local_ai_privacy.setText(status.privacy_note)

        self._install_btn.setEnabled(status.install_ready)
        if status.kind is LocalAiStatusKind.MANIFEST_BLOCKED:
            self._install_btn.setToolTip(
                status.install_blocked_reason or "Model checksum is not recorded yet"
            )
            self._install_btn.setEnabled(False)
        elif status.kind is LocalAiStatusKind.ERROR and status.install_ready:
            self._install_btn.setText("Retry Install")
            self._install_btn.setToolTip("Reinstall and re-verify the model file")
        else:
            self._install_btn.setText("Install Model")
            self._install_btn.setToolTip("")

        if status.kind is LocalAiStatusKind.ENABLED:
            self._enable_btn.setText("Disable Local AI")
            self._enable_btn.setEnabled(True)
        elif status.can_enable:
            self._enable_btn.setText("Enable Local AI")
            self._enable_btn.setEnabled(True)
        else:
            self._enable_btn.setText("Enable Local AI")
            self._enable_btn.setEnabled(False)
            self._enable_btn.setToolTip("Install and verify the Local AI model before enabling")

        self._backfill_btn.setEnabled(status.can_analyze_existing)
        if not status.can_analyze_existing:
            self._backfill_btn.setToolTip(
                "Enable Local AI after installing the model to analyze existing Samples"
            )
        else:
            self._backfill_btn.setToolTip(
                "Queue Samples missing Local AI analysis for the active model version"
            )

        rebuild_ok = status.can_rebuild and status.enabled
        self._rebuild_suggestions_btn.setEnabled(rebuild_ok)
        self._rebuild_similarity_btn.setEnabled(status.can_rebuild)
        note = ""
        if status.kind is LocalAiStatusKind.MANIFEST_BLOCKED:
            note = status.install_blocked_reason or ""
        elif status.kind is LocalAiStatusKind.NOT_INSTALLED:
            note = "Library browsing and import work without Local AI."
        self._local_ai_action_note.setText(note)

    def _apply(self) -> None:
        self._context.settings_service.update_library_analysis(
            recursive_scanning=self._recursive.isChecked(),
            skip_hidden_folders=self._skip_hidden.isChecked(),
            automatic_analysis=self._auto_analysis.isChecked(),
            analysis_concurrency=self._concurrency.value(),
            idle_only_deep_analysis=self._idle_deep.isChecked(),
            waveform_cache_enabled=self._waveforms.isChecked(),
            similarity_indexing=self._similarity.isChecked(),
            cache_limit_mb=self._cache_limit.value(),
        )
        self.refresh()

    def _toggle_enabled(self) -> None:
        status = self._context.local_ai_service.status()
        try:
            if status.kind is LocalAiStatusKind.ENABLED:
                self._context.local_ai_service.set_enabled(False)
            else:
                self._context.local_ai_service.set_enabled(True)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Local AI", exc.summary)
        self._refresh_local_ai()

    def _install_model(self) -> None:
        status = self._context.local_ai_service.status()
        if not status.install_ready:
            QMessageBox.information(
                self,
                "Install Model",
                status.install_blocked_reason
                or "Model install is not available in the current state.",
            )
            self._refresh_local_ai()
            return
        reply = QMessageBox.question(
            self,
            "Install Local AI model",
            (
                f"Download {status.model_name} ({status.size_label}) to this computer?\n\n"
                f"{status.privacy_note}"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._context.local_ai_service.install_model()
        except ApplicationError as exc:
            QMessageBox.warning(
                self,
                "Install Model",
                f"{exc.summary}\n\nNo trusted model file was left behind. You can retry later.",
            )
        else:
            QMessageBox.information(
                self,
                "Install Model",
                "Local AI model installed and verified. Enable it to start analyzing Samples.",
            )
        self._refresh_local_ai()

    def _analyze_existing(self) -> None:
        try:
            plan = self._context.local_ai_service.plan_backfill()
        except ApplicationError as exc:
            QMessageBox.information(self, "Analyze Existing Library", exc.summary)
            self._refresh_local_ai()
            return
        if plan.sample_count == 0:
            QMessageBox.information(
                self,
                "Analyze Existing Library",
                (
                    f"Every eligible Sample already has Local AI output for "
                    f"{plan.model_name} ({plan.model_version})."
                ),
            )
            return
        reply = QMessageBox.question(
            self,
            "Analyze Existing Library",
            (
                f"Queue Local AI analysis for {plan.sample_count} Sample"
                f"{'s' if plan.sample_count != 1 else ''}?\n\n"
                f"Model: {plan.model_name} ({plan.model_version})\n"
                f"Workload: {plan.workload.value}\n\n"
                "Progress appears in Activity. You can pause or cancel from there. "
                "One bad file will not stop the rest. "
                "Suggestions stay pending until you accept them."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            job_id = self._context.local_ai_service.queue_backfill(plan)
        except ApplicationError as exc:
            QMessageBox.warning(self, "Analyze Existing Library", exc.summary)
            return
        self._local_ai_action_note.setText(
            f"Queued Analyze Existing Library ({plan.sample_count} Samples) — Job {job_id}"
        )

    def _rebuild_suggestions(self) -> None:
        try:
            job_id = self._context.local_ai_service.queue_rebuild_suggestions()
        except ApplicationError as exc:
            QMessageBox.information(self, "Rebuild Suggestions", exc.summary)
            return
        self._local_ai_action_note.setText(f"Queued Rebuild Suggestions — Job {job_id}")

    def _rebuild_similarity(self) -> None:
        try:
            job_id = self._context.local_ai_service.queue_rebuild_similarity_index()
        except ApplicationError as exc:
            QMessageBox.information(self, "Rebuild Similarity Index", exc.summary)
            return
        self._local_ai_action_note.setText(f"Queued Rebuild Similarity Index — Job {job_id}")
