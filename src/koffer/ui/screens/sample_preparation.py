"""S08 Sample Preparation foundations (docs/12, docs/15). Non-destructive recipes only."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.preparation import (
    NormalizeSpec,
    PreparationRecipe,
    TrimSpec,
)
from koffer.services.preparation import PreparationService
from koffer.ui.tokens import CLAY, GREEN, MUTED
from koffer.ui.widgets.waveform_view import WaveformView


class SamplePreparationScreen(QWidget):
    """S08: edit non-destructive recipe; never writes source audio on adjust/save/reset."""

    back_requested = Signal()
    export_requested = Signal(str)
    recipe_saved = Signal()

    def __init__(
        self,
        preparation_service: PreparationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = preparation_service
        self._sample_id: EntityId | None = None
        self._source_path: str = ""
        self.setObjectName("samplePreparationScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Sample Preparation")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        back = QPushButton("Back")
        back.setObjectName("samplePreparationBackButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        self._source_label = QLabel("Source: —")
        self._source_label.setObjectName("samplePreparationSourceLabel")
        self._source_label.setWordWrap(True)
        root.addWidget(self._source_label)

        self._nondestructive = QLabel("Recipe: Non-destructive (source audio is never modified)")
        self._nondestructive.setObjectName("samplePreparationNondestructiveBadge")
        self._nondestructive.setStyleSheet(f"color: {GREEN}; font-weight: 600;")
        root.addWidget(self._nondestructive)

        self._waveform = WaveformView()
        self._waveform.setObjectName("samplePreparationWaveform")
        self._waveform.setMinimumHeight(140)
        self._waveform.setMaximumHeight(180)
        root.addWidget(self._waveform)

        self._trim_state = QLabel("Trim: 0 ms → end")
        self._trim_state.setObjectName("samplePreparationTrimState")
        root.addWidget(self._trim_state)

        self._preview_note = QLabel("")
        self._preview_note.setObjectName("samplePreparationPreviewNote")
        self._preview_note.setWordWrap(True)
        self._preview_note.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._preview_note)

        scroll = QScrollArea()
        scroll.setObjectName("samplePreparationScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("samplePreparationBody")
        form = QFormLayout(body)
        form.setObjectName("samplePreparationForm")

        self._trim_start = QSpinBox()
        self._trim_start.setObjectName("samplePreparationTrimStart")
        self._trim_start.setRange(0, 10_000_000)
        self._trim_start.setSuffix(" ms")
        self._trim_start.valueChanged.connect(self._on_controls_changed)
        form.addRow("Trim start", self._trim_start)

        self._trim_end = QSpinBox()
        self._trim_end.setObjectName("samplePreparationTrimEnd")
        self._trim_end.setRange(0, 10_000_000)
        self._trim_end.setSuffix(" ms")
        self._trim_end.setSpecialValueText("end")
        self._trim_end.valueChanged.connect(self._on_controls_changed)
        form.addRow("Trim end (0 = file end)", self._trim_end)

        self._fade_in = QSpinBox()
        self._fade_in.setObjectName("samplePreparationFadeIn")
        self._fade_in.setRange(0, 60_000)
        self._fade_in.setSuffix(" ms")
        form.addRow("Fade in", self._fade_in)

        self._fade_out = QSpinBox()
        self._fade_out.setObjectName("samplePreparationFadeOut")
        self._fade_out.setRange(0, 60_000)
        self._fade_out.setSuffix(" ms")
        form.addRow("Fade out", self._fade_out)

        self._gain = QDoubleSpinBox()
        self._gain.setObjectName("samplePreparationGain")
        self._gain.setRange(-60.0, 24.0)
        self._gain.setDecimals(1)
        self._gain.setSuffix(" dB")
        form.addRow("Gain", self._gain)

        self._normalize = QCheckBox("Normalize")
        self._normalize.setObjectName("samplePreparationNormalize")
        form.addRow("Normalize", self._normalize)

        self._transpose = QDoubleSpinBox()
        self._transpose.setObjectName("samplePreparationTranspose")
        self._transpose.setRange(-24.0, 24.0)
        self._transpose.setDecimals(1)
        self._transpose.setSuffix(" st")
        form.addRow("Transpose", self._transpose)

        self._stretch = QDoubleSpinBox()
        self._stretch.setObjectName("samplePreparationStretch")
        self._stretch.setRange(0.25, 4.0)
        self._stretch.setDecimals(3)
        self._stretch.setSingleStep(0.05)
        self._stretch.setValue(1.0)
        form.addRow("Time stretch", self._stretch)

        self._reverse = QCheckBox("Reverse")
        self._reverse.setObjectName("samplePreparationReverse")
        form.addRow("Reverse", self._reverse)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        actions = QHBoxLayout()
        reset = QPushButton("Reset Recipe")
        reset.setObjectName("samplePreparationResetButton")
        reset.clicked.connect(self._reset_recipe)
        actions.addWidget(reset)

        save = QPushButton("Save Recipe")
        save.setObjectName("samplePreparationSaveButton")
        save.clicked.connect(self._save_recipe)
        actions.addWidget(save)

        preview = QPushButton("Preview")
        preview.setObjectName("samplePreparationPreviewButton")
        preview.clicked.connect(self._preview_recipe)
        actions.addWidget(preview)

        export = QPushButton("Export / Render…")
        export.setObjectName("samplePreparationExportButton")
        export.setProperty("primary", True)
        export.setStyleSheet(f"background-color: {CLAY};")
        export.clicked.connect(self._request_export)
        actions.addWidget(export)
        root.addLayout(actions)

        self._status = QLabel("")
        self._status.setObjectName("samplePreparationStatus")
        root.addWidget(self._status)

    def show_sample(self, sample_id: EntityId, *, source_path: str | None = None) -> None:
        self._sample_id = sample_id
        media = self._service.resolve_media_path(sample_id)
        self._source_path = source_path or (str(media) if media is not None else "")
        self._source_label.setText(f"Source: {self._source_path or '—'}")
        recipe = self._service.get_recipe(sample_id)
        self._apply_recipe_to_controls(recipe)
        self._status.setText("Loaded non-destructive recipe. Adjustments do not write the source.")
        self._preview_recipe()

    def refresh(self) -> None:
        if self._sample_id is not None:
            self.show_sample(self._sample_id, source_path=self._source_path or None)

    def current_recipe(self) -> PreparationRecipe:
        end_ms = self._trim_end.value()
        return PreparationRecipe(
            trim=TrimSpec(
                start_ms=self._trim_start.value(),
                end_ms=None if end_ms == 0 else end_ms,
            ),
            fade_in_ms=self._fade_in.value(),
            fade_out_ms=self._fade_out.value(),
            gain_db=float(self._gain.value()),
            normalize=NormalizeSpec(enabled=self._normalize.isChecked()),
            transpose_semitones=float(self._transpose.value()),
            time_stretch_ratio=float(self._stretch.value()),
            reverse=self._reverse.isChecked(),
        )

    def _apply_recipe_to_controls(self, recipe: PreparationRecipe) -> None:
        self._trim_start.setValue(recipe.trim.start_ms)
        self._trim_end.setValue(0 if recipe.trim.end_ms is None else recipe.trim.end_ms)
        self._fade_in.setValue(recipe.fade_in_ms)
        self._fade_out.setValue(recipe.fade_out_ms)
        self._gain.setValue(recipe.gain_db)
        self._normalize.setChecked(recipe.normalize.enabled)
        self._transpose.setValue(recipe.transpose_semitones)
        self._stretch.setValue(recipe.time_stretch_ratio)
        self._reverse.setChecked(recipe.reverse)
        self._on_controls_changed()

    def _on_controls_changed(self) -> None:
        end = self._trim_end.value()
        end_label = "end" if end == 0 else f"{end} ms"
        self._trim_state.setText(f"Trim: {self._trim_start.value()} ms → {end_label}")

    def _save_recipe(self) -> None:
        if self._sample_id is None:
            return
        try:
            self._service.save_recipe(self._sample_id, self.current_recipe())
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self._status.setText("Recipe saved (source audio unchanged).")
        self.recipe_saved.emit()

    def _reset_recipe(self) -> None:
        if self._sample_id is None:
            return
        try:
            self._service.reset_recipe(self._sample_id)
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self._apply_recipe_to_controls(PreparationRecipe.default())
        self._status.setText("Recipe reset to defaults (source audio unchanged).")
        self.recipe_saved.emit()

    def _preview_recipe(self) -> None:
        if self._sample_id is None:
            return
        try:
            handle = self._service.create_preview(self._sample_id, self.current_recipe())
        except ApplicationError as exc:
            self._preview_note.setText(str(exc))
            return
        self._preview_note.setText(f"Preview quality: {handle.quality}. {handle.note}")

    def _request_export(self) -> None:
        if self._sample_id is None:
            return
        # Persist current controls before opening S14 so render sees latest intent.
        try:
            self._service.save_recipe(self._sample_id, self.current_recipe())
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self.export_requested.emit(str(self._sample_id))
