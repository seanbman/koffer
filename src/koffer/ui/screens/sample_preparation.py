"""S08 Sample Preparation: non-destructive recipe editing and exact preview."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from koffer.app_context import AppContext
from koffer.audio.waveform import PeakEnvelope, WaveformCache
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.preparation import (
    ChannelMode,
    NormalizeSpec,
    OutputFormat,
    PreparationRecipe,
    SourceOrInt,
    TrimSpec,
)
from koffer.services.preparation import PreparationService
from koffer.ui.tokens import CLAY, GREEN, MUTED
from koffer.ui.widgets.waveform_view import WaveformView


class _WaveformSignals(QObject):
    completed = Signal(str, object)


class _WaveformTask(QRunnable):
    def __init__(
        self,
        cache: WaveformCache,
        sample_id: EntityId,
        media_path: Path,
        signals: _WaveformSignals,
    ) -> None:
        super().__init__()
        self._cache = cache
        self._sample_id = sample_id
        self._media_path = media_path
        self._signals = signals

    @Slot()
    def run(self) -> None:
        envelope: PeakEnvelope | None
        try:
            envelope = self._cache.get_or_build(self._sample_id, self._media_path)
        except Exception:
            envelope = None
        self._signals.completed.emit(str(self._sample_id), envelope)


class _PreviewSignals(QObject):
    completed = Signal(str, object, object)


class _PreviewTask(QRunnable):
    def __init__(
        self,
        service: PreparationService,
        sample_id: EntityId,
        recipe: PreparationRecipe,
        preview_dir: Path,
        signals: _PreviewSignals,
    ) -> None:
        super().__init__()
        self._service = service
        self._sample_id = sample_id
        self._recipe = recipe
        self._preview_dir = preview_dir
        self._signals = signals

    @Slot()
    def run(self) -> None:
        try:
            path = self._service.render_preview_file(
                self._sample_id,
                self._recipe,
                self._preview_dir,
            )
        except ApplicationError as exc:
            self._signals.completed.emit(str(self._sample_id), None, str(exc))
            return
        except Exception as exc:
            self._signals.completed.emit(str(self._sample_id), None, str(exc))
            return
        self._signals.completed.emit(str(self._sample_id), path, None)


class SamplePreparationScreen(QWidget):
    """Edit a recipe without changing source audio; preview is rendered off-thread."""

    back_requested = Signal()
    export_requested = Signal(str)
    preview_ready = Signal(str, str)
    recipe_saved = Signal()

    def __init__(
        self,
        context: AppContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._service = context.preparation_service
        self._sample_id: EntityId | None = None
        self._source_path: str = ""
        self._preview_path: Path | None = None
        self._waveform_signals = _WaveformSignals(self)
        self._waveform_signals.completed.connect(self._on_waveform_ready)
        self._preview_signals = _PreviewSignals(self)
        self._preview_signals.completed.connect(self._on_preview_ready)
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
        self._waveform.setMinimumHeight(180)
        self._waveform.setMaximumHeight(250)
        root.addWidget(self._waveform)

        self._waveform_state = QLabel("Waveform: —")
        self._waveform_state.setObjectName("samplePreparationWaveformState")
        self._waveform_state.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._waveform_state)

        self._trim_state = QLabel("Trim: 0 ms → end")
        self._trim_state.setObjectName("samplePreparationTrimState")
        root.addWidget(self._trim_state)

        self._preview_note = QLabel(
            "Preview renders the current recipe to a temporary file; the original remains untouched."
        )
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
        self._fade_in.valueChanged.connect(self._invalidate_preview)
        form.addRow("Fade in", self._fade_in)

        self._fade_out = QSpinBox()
        self._fade_out.setObjectName("samplePreparationFadeOut")
        self._fade_out.setRange(0, 60_000)
        self._fade_out.setSuffix(" ms")
        self._fade_out.valueChanged.connect(self._invalidate_preview)
        form.addRow("Fade out", self._fade_out)

        self._gain = QDoubleSpinBox()
        self._gain.setObjectName("samplePreparationGain")
        self._gain.setRange(-60.0, 24.0)
        self._gain.setDecimals(1)
        self._gain.setSuffix(" dB")
        self._gain.valueChanged.connect(self._invalidate_preview)
        form.addRow("Gain", self._gain)

        self._normalize = QCheckBox("Normalize")
        self._normalize.setObjectName("samplePreparationNormalize")
        self._normalize.toggled.connect(self._invalidate_preview)
        form.addRow("Normalize", self._normalize)

        self._normalize_peak = QDoubleSpinBox()
        self._normalize_peak.setObjectName("samplePreparationNormalizePeak")
        self._normalize_peak.setRange(-12.0, 0.0)
        self._normalize_peak.setDecimals(1)
        self._normalize_peak.setSingleStep(0.5)
        self._normalize_peak.setValue(-1.0)
        self._normalize_peak.setSuffix(" dBFS")
        self._normalize_peak.setEnabled(False)
        self._normalize_peak.valueChanged.connect(self._invalidate_preview)
        self._normalize.toggled.connect(self._normalize_peak.setEnabled)
        form.addRow("Normalize peak", self._normalize_peak)

        self._transpose = QDoubleSpinBox()
        self._transpose.setObjectName("samplePreparationTranspose")
        self._transpose.setRange(-24.0, 24.0)
        self._transpose.setDecimals(1)
        self._transpose.setSuffix(" st")
        self._transpose.valueChanged.connect(self._invalidate_preview)
        form.addRow("Transpose", self._transpose)

        self._fine_cents = QSpinBox()
        self._fine_cents.setObjectName("samplePreparationFineCents")
        self._fine_cents.setRange(-100, 100)
        self._fine_cents.setSuffix(" cents")
        self._fine_cents.valueChanged.connect(self._invalidate_preview)
        form.addRow("Fine pitch", self._fine_cents)

        self._stretch = QDoubleSpinBox()
        self._stretch.setObjectName("samplePreparationStretch")
        self._stretch.setRange(0.25, 4.0)
        self._stretch.setDecimals(3)
        self._stretch.setSingleStep(0.05)
        self._stretch.setValue(1.0)
        self._stretch.valueChanged.connect(self._invalidate_preview)
        form.addRow("Time stretch", self._stretch)

        self._reverse = QCheckBox("Reverse")
        self._reverse.setObjectName("samplePreparationReverse")
        self._reverse.toggled.connect(self._invalidate_preview)
        form.addRow("Reverse", self._reverse)

        self._channels = QComboBox()
        self._channels.setObjectName("samplePreparationChannels")
        for mode in ("source", "mono", "stereo"):
            self._channels.addItem(mode, mode)
        self._channels.currentIndexChanged.connect(self._invalidate_preview)
        form.addRow("Channels", self._channels)

        self._sample_rate = QComboBox()
        self._sample_rate.setObjectName("samplePreparationSampleRate")
        self._sample_rate.addItem("source", "source")
        for rate in (44_100, 48_000, 96_000):
            self._sample_rate.addItem(str(rate), rate)
        self._sample_rate.currentIndexChanged.connect(self._invalidate_preview)
        form.addRow("Sample rate", self._sample_rate)

        self._bit_depth = QComboBox()
        self._bit_depth.setObjectName("samplePreparationBitDepth")
        self._bit_depth.addItem("source", "source")
        for depth in (16, 24, 32):
            self._bit_depth.addItem(str(depth), depth)
        self._bit_depth.currentIndexChanged.connect(self._invalidate_preview)
        form.addRow("Bit depth", self._bit_depth)

        self._output_format = QComboBox()
        self._output_format.setObjectName("samplePreparationOutputFormat")
        for output_format in ("wav", "flac", "ogg", "mp3"):
            self._output_format.addItem(output_format, output_format)
        self._output_format.currentIndexChanged.connect(self._invalidate_preview)
        form.addRow("Output format", self._output_format)

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

        self._preview_btn = QPushButton("Preview Recipe")
        self._preview_btn.setObjectName("samplePreparationPreviewButton")
        self._preview_btn.clicked.connect(self._preview_recipe)
        actions.addWidget(self._preview_btn)

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

    @property
    def sample_id(self) -> EntityId | None:
        return self._sample_id

    @property
    def preview_path(self) -> Path | None:
        return self._preview_path

    def show_sample(self, sample_id: EntityId, *, source_path: str | None = None) -> None:
        self._sample_id = sample_id
        self._preview_path = None
        media = self._service.resolve_media_path(sample_id)
        self._source_path = source_path or (str(media) if media is not None else "")
        self._source_label.setText(f"Source: {self._source_path or '—'}")
        recipe = self._service.get_recipe(sample_id)
        self._apply_recipe_to_controls(recipe)
        self._status.setText("Loaded non-destructive recipe. Adjustments do not write the source.")
        self._load_waveform(media)

    def refresh(self) -> None:
        if self._sample_id is not None:
            self.show_sample(self._sample_id, source_path=self._source_path or None)

    def current_recipe(self) -> PreparationRecipe:
        end_ms = self._trim_end.value()
        sample_rate_data = self._sample_rate.currentData()
        bit_depth_data = self._bit_depth.currentData()
        sample_rate: SourceOrInt = (
            "source" if sample_rate_data == "source" else int(sample_rate_data)
        )
        bit_depth: SourceOrInt = "source" if bit_depth_data == "source" else int(bit_depth_data)
        return PreparationRecipe(
            trim=TrimSpec(
                start_ms=self._trim_start.value(),
                end_ms=None if end_ms == 0 else end_ms,
            ),
            fade_in_ms=self._fade_in.value(),
            fade_out_ms=self._fade_out.value(),
            gain_db=float(self._gain.value()),
            normalize=NormalizeSpec(
                enabled=self._normalize.isChecked(),
                target_peak_dbfs=float(self._normalize_peak.value()),
            ),
            transpose_semitones=float(self._transpose.value()),
            fine_cents=self._fine_cents.value(),
            time_stretch_ratio=float(self._stretch.value()),
            reverse=self._reverse.isChecked(),
            channels=cast(ChannelMode, str(self._channels.currentData())),
            sample_rate_hz=sample_rate,
            bit_depth=bit_depth,
            output_format=cast(OutputFormat, self._output_format.currentText()),
        )

    def _apply_recipe_to_controls(self, recipe: PreparationRecipe) -> None:
        self._trim_start.setValue(recipe.trim.start_ms)
        self._trim_end.setValue(0 if recipe.trim.end_ms is None else recipe.trim.end_ms)
        self._fade_in.setValue(recipe.fade_in_ms)
        self._fade_out.setValue(recipe.fade_out_ms)
        self._gain.setValue(recipe.gain_db)
        self._normalize.setChecked(recipe.normalize.enabled)
        self._normalize_peak.setValue(recipe.normalize.target_peak_dbfs)
        self._transpose.setValue(recipe.transpose_semitones)
        self._fine_cents.setValue(recipe.fine_cents)
        self._stretch.setValue(recipe.time_stretch_ratio)
        self._reverse.setChecked(recipe.reverse)
        self._set_combo_data(self._channels, recipe.channels)
        self._set_combo_data(self._sample_rate, recipe.sample_rate_hz)
        self._set_combo_data(self._bit_depth, recipe.bit_depth)
        self._set_combo_data(self._output_format, recipe.output_format)
        self._on_controls_changed()

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _invalidate_preview(self, *_args: object) -> None:
        self._preview_path = None

    def _on_controls_changed(self) -> None:
        self._invalidate_preview()
        end = self._trim_end.value()
        end_label = "end" if end == 0 else f"{end} ms"
        self._trim_state.setText(f"Trim: {self._trim_start.value()} ms → {end_label}")

    def _load_waveform(self, media: Path | None) -> None:
        self._waveform.set_envelope(None)
        if self._sample_id is None or media is None or not media.is_file():
            self._waveform_state.setText("Waveform: unavailable")
            return
        self._waveform_state.setText("Waveform: loading…")
        task = _WaveformTask(
            self._context.waveform_cache,
            self._sample_id,
            media,
            self._waveform_signals,
        )
        QThreadPool.globalInstance().start(task)

    @Slot(str, object)
    def _on_waveform_ready(self, sample_id: str, envelope: object) -> None:
        if self._sample_id is None or sample_id != str(self._sample_id):
            return
        resolved = envelope if isinstance(envelope, PeakEnvelope) else None
        self._waveform.set_envelope(resolved)
        if resolved is None:
            self._waveform_state.setText("Waveform: unavailable")
            return
        self._waveform_state.setText(
            f"Waveform: {resolved.duration_ms} ms · {resolved.sample_rate_hz} Hz · "
            f"{resolved.channels} ch"
        )

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
        recipe = self.current_recipe()
        try:
            self._service.create_preview(self._sample_id, recipe)
        except ApplicationError as exc:
            self._preview_note.setText(str(exc))
            return
        self._preview_btn.setEnabled(False)
        self._preview_note.setText("Rendering recipe preview off-thread…")
        preview_dir = self._context.paths.cache_dir / "previews"
        task = _PreviewTask(
            self._service,
            self._sample_id,
            recipe,
            preview_dir,
            self._preview_signals,
        )
        QThreadPool.globalInstance().start(task)

    @Slot(str, object, object)
    def _on_preview_ready(self, sample_id: str, path: object, error: object) -> None:
        self._preview_btn.setEnabled(True)
        if self._sample_id is None or sample_id != str(self._sample_id):
            return
        if error is not None:
            self._preview_note.setText(str(error))
            return
        if not isinstance(path, Path):
            self._preview_note.setText("Preview render produced no playable file.")
            return
        self._preview_path = path
        self._preview_note.setText(
            "Recipe preview ready. Playing the temporary render; source audio is unchanged."
        )
        self.preview_ready.emit(sample_id, str(path))

    def _request_export(self) -> None:
        if self._sample_id is None:
            return
        try:
            self._service.save_recipe(self._sample_id, self.current_recipe())
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self.export_requested.emit(str(self._sample_id))
