"""S08 Edit Sound: direct-manipulation waveform workbench over non-destructive recipes."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.audio.waveform import PeakEnvelope, WaveformCache
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.preparation import (
    ChannelMode,
    OutputFormat,
    PreparationRecipe,
    SourceOrInt,
)
from koffer.services.preparation import PreparationService
from koffer.ui.models.workbench import WorkbenchController
from koffer.ui.tokens import BORDER, CLAY, GREEN, MAGENTA, MUTED, SURFACE_1, TEXT, YELLOW
from koffer.ui.widgets.workbench_waveform import WorkbenchWaveformView


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
    """Edit Sound workbench: recipe edits never mutate source audio."""

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
        self._ab_mode = "B"
        self._suppress_control_events = False
        self._controller = WorkbenchController(self)
        self._waveform_signals = _WaveformSignals(self)
        self._waveform_signals.completed.connect(self._on_waveform_ready)
        self._preview_signals = _PreviewSignals(self)
        self._preview_signals.completed.connect(self._on_preview_ready)
        self._controller.changed.connect(self._on_controller_changed)
        self._controller.dirty_changed.connect(self._on_dirty_changed)
        self._controller.seek_requested.connect(self._on_seek_requested)
        self.setObjectName("samplePreparationScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(6)
        back = QPushButton("Back")
        back.setObjectName("samplePreparationBackButton")
        back.clicked.connect(self._request_back)
        header.addWidget(back)
        self._title = QLabel("Edit Sound")
        self._title.setObjectName("pageTitle")
        self._title.setStyleSheet(f"color: {TEXT}; font-size: 18px; font-weight: 600;")
        header.addWidget(self._title, stretch=1)

        self._dirty_badge = QLabel("Saved")
        self._dirty_badge.setObjectName("samplePreparationDirtyBadge")
        self._dirty_badge.setStyleSheet(f"color: {GREEN}; font-weight: 700;")
        header.addWidget(self._dirty_badge)

        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setObjectName("samplePreparationUndoButton")
        self._undo_btn.clicked.connect(self._controller.undo)
        header.addWidget(self._undo_btn)
        self._redo_btn = QPushButton("Redo")
        self._redo_btn.setObjectName("samplePreparationRedoButton")
        self._redo_btn.clicked.connect(self._controller.redo)
        header.addWidget(self._redo_btn)
        reset = QPushButton("Reset")
        reset.setObjectName("samplePreparationResetButton")
        reset.clicked.connect(self._reset_recipe)
        header.addWidget(reset)

        self._ab_a = QPushButton("A Original")
        self._ab_a.setObjectName("samplePreparationABOriginalButton")
        self._ab_a.setCheckable(True)
        self._ab_a.clicked.connect(lambda: self._set_ab_mode("A"))
        header.addWidget(self._ab_a)
        self._ab_b = QPushButton("B Edited")
        self._ab_b.setObjectName("samplePreparationABEditedButton")
        self._ab_b.setCheckable(True)
        self._ab_b.setChecked(True)
        self._ab_b.clicked.connect(lambda: self._set_ab_mode("B"))
        header.addWidget(self._ab_b)
        root.addLayout(header)

        meta = QHBoxLayout()
        meta.setSpacing(12)
        self._source_label = QLabel("Source: —")
        self._source_label.setObjectName("samplePreparationSourceLabel")
        self._source_label.setWordWrap(True)
        self._source_label.setStyleSheet(f"color: {TEXT};")
        meta.addWidget(self._source_label, stretch=1)

        self._nondestructive = QLabel("Non-destructive — source audio is never modified")
        self._nondestructive.setObjectName("samplePreparationNondestructiveBadge")
        self._nondestructive.setStyleSheet(f"color: {GREEN}; font-weight: 600;")
        meta.addWidget(self._nondestructive)
        root.addLayout(meta)

        workbench = QSplitter(Qt.Orientation.Horizontal)
        workbench.setObjectName("samplePreparationWorkbenchSplitter")
        workbench.setChildrenCollapsible(False)

        wave_panel = QWidget()
        wave_panel.setObjectName("samplePreparationWavePanel")
        wave_layout = QVBoxLayout(wave_panel)
        wave_layout.setContentsMargins(0, 0, 8, 0)
        wave_layout.setSpacing(6)

        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(6)
        zoom_out = QPushButton("Zoom −")
        zoom_out.setObjectName("samplePreparationZoomOutButton")
        zoom_out.clicked.connect(lambda: self._controller.zoom_by(0.8))
        zoom_row.addWidget(zoom_out)
        zoom_in = QPushButton("Zoom +")
        zoom_in.setObjectName("samplePreparationZoomInButton")
        zoom_in.clicked.connect(lambda: self._controller.zoom_by(1.25))
        zoom_row.addWidget(zoom_in)
        fit = QPushButton("Fit")
        fit.setObjectName("samplePreparationFitButton")
        fit.clicked.connect(self._controller.zoom_fit)
        zoom_row.addWidget(fit)
        self._selection_readout = QLabel("Trim: 0 ms → end")
        self._selection_readout.setObjectName("samplePreparationTrimState")
        self._selection_readout.setStyleSheet(f"color: {TEXT};")
        zoom_row.addWidget(self._selection_readout, stretch=1)
        self._playhead_readout = QLabel("Playhead: 00:00.000")
        self._playhead_readout.setObjectName("samplePreparationPlayheadReadout")
        self._playhead_readout.setStyleSheet(f"color: {MUTED};")
        zoom_row.addWidget(self._playhead_readout)
        wave_layout.addLayout(zoom_row)

        self._waveform = WorkbenchWaveformView(self._controller)
        self._waveform.setObjectName("samplePreparationWaveform")
        self._waveform.setMinimumHeight(180)
        self._waveform.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        wave_layout.addWidget(self._waveform, stretch=1)

        self._waveform_state = QLabel("Waveform: —")
        self._waveform_state.setObjectName("samplePreparationWaveformState")
        self._waveform_state.setStyleSheet(f"color: {MUTED};")
        wave_layout.addWidget(self._waveform_state)

        self._preview_note = QLabel(
            "A = original source · B = edited recipe preview. Source bytes stay untouched."
        )
        self._preview_note.setObjectName("samplePreparationPreviewNote")
        self._preview_note.setWordWrap(True)
        self._preview_note.setStyleSheet(f"color: {MUTED};")
        wave_layout.addWidget(self._preview_note)
        workbench.addWidget(wave_panel)

        dock = QWidget()
        dock.setObjectName("samplePreparationControlDock")
        dock.setMinimumWidth(300)
        dock.setMaximumWidth(420)
        dock_layout = QVBoxLayout(dock)
        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("samplePreparationScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("samplePreparationBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        group_style = (
            f"QGroupBox {{ color: {TEXT}; background-color: {SURFACE_1};"
            f" border: 1px solid {BORDER}; border-radius: 6px; margin-top: 10px;"
            f" padding-top: 8px; }}"
            f"QGroupBox::title {{ color: {TEXT}; subcontrol-origin: margin;"
            f" left: 10px; padding: 0 4px; font-weight: 700; }}"
            f"QGroupBox QLabel {{ color: {TEXT}; }}"
        )

        numeric = QGroupBox("Numeric alternatives")
        numeric.setObjectName("samplePreparationNumericGroup")
        numeric.setStyleSheet(group_style)
        form = QFormLayout(numeric)
        form.setObjectName("samplePreparationForm")
        form.setContentsMargins(10, 12, 10, 10)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._trim_start = QSpinBox()
        self._trim_start.setObjectName("samplePreparationTrimStart")
        self._trim_start.setRange(0, 10_000_000)
        self._trim_start.setSuffix(" ms")
        self._trim_start.valueChanged.connect(self._on_numeric_trim)
        form.addRow("Trim start", self._trim_start)

        self._trim_end = QSpinBox()
        self._trim_end.setObjectName("samplePreparationTrimEnd")
        self._trim_end.setRange(0, 10_000_000)
        self._trim_end.setSuffix(" ms")
        self._trim_end.setSpecialValueText("end")
        self._trim_end.valueChanged.connect(self._on_numeric_trim)
        form.addRow("Trim end", self._trim_end)

        self._fade_in = QSpinBox()
        self._fade_in.setObjectName("samplePreparationFadeIn")
        self._fade_in.setRange(0, 60_000)
        self._fade_in.setSuffix(" ms")
        self._fade_in.valueChanged.connect(self._on_numeric_fades)
        form.addRow("Fade in", self._fade_in)

        self._fade_out = QSpinBox()
        self._fade_out.setObjectName("samplePreparationFadeOut")
        self._fade_out.setRange(0, 60_000)
        self._fade_out.setSuffix(" ms")
        self._fade_out.valueChanged.connect(self._on_numeric_fades)
        form.addRow("Fade out", self._fade_out)

        self._loop_enabled = QCheckBox("Preview Loop")
        self._loop_enabled.setObjectName("samplePreparationPreviewLoop")
        self._loop_enabled.toggled.connect(self._on_loop_toggled)
        form.addRow("Preview Loop", self._loop_enabled)

        self._loop_start = QSpinBox()
        self._loop_start.setObjectName("samplePreparationLoopStart")
        self._loop_start.setRange(0, 10_000_000)
        self._loop_start.setSuffix(" ms")
        self._loop_start.valueChanged.connect(self._on_numeric_loop)
        form.addRow("Loop start", self._loop_start)

        self._loop_end = QSpinBox()
        self._loop_end.setObjectName("samplePreparationLoopEnd")
        self._loop_end.setRange(0, 10_000_000)
        self._loop_end.setSuffix(" ms")
        self._loop_end.setSpecialValueText("end")
        self._loop_end.valueChanged.connect(self._on_numeric_loop)
        form.addRow("Loop end", self._loop_end)

        self._gain = QDoubleSpinBox()
        self._gain.setObjectName("samplePreparationGain")
        self._gain.setRange(-60.0, 24.0)
        self._gain.setDecimals(1)
        self._gain.setSuffix(" dB")
        self._gain.valueChanged.connect(self._on_numeric_gain)
        form.addRow("Gain", self._gain)

        self._normalize = QCheckBox("Normalize")
        self._normalize.setObjectName("samplePreparationNormalize")
        self._normalize.toggled.connect(self._on_numeric_normalize)
        form.addRow("Normalize", self._normalize)

        self._normalize_peak = QDoubleSpinBox()
        self._normalize_peak.setObjectName("samplePreparationNormalizePeak")
        self._normalize_peak.setRange(-12.0, 0.0)
        self._normalize_peak.setDecimals(1)
        self._normalize_peak.setSingleStep(0.5)
        self._normalize_peak.setValue(-1.0)
        self._normalize_peak.setSuffix(" dBFS")
        self._normalize_peak.setEnabled(False)
        self._normalize_peak.valueChanged.connect(self._on_numeric_normalize)
        self._normalize.toggled.connect(self._normalize_peak.setEnabled)
        form.addRow("Norm peak", self._normalize_peak)

        self._transpose = QDoubleSpinBox()
        self._transpose.setObjectName("samplePreparationTranspose")
        self._transpose.setRange(-24.0, 24.0)
        self._transpose.setDecimals(1)
        self._transpose.setSuffix(" st")
        self._transpose.setStyleSheet(f"border-color: {MAGENTA};")
        self._transpose.valueChanged.connect(self._on_numeric_pitch)
        form.addRow("Pitch", self._transpose)

        self._fine_cents = QSpinBox()
        self._fine_cents.setObjectName("samplePreparationFineCents")
        self._fine_cents.setRange(-100, 100)
        self._fine_cents.setSuffix(" cents")
        self._fine_cents.valueChanged.connect(self._on_numeric_pitch)
        form.addRow("Fine pitch", self._fine_cents)

        self._stretch = QDoubleSpinBox()
        self._stretch.setObjectName("samplePreparationStretch")
        self._stretch.setRange(0.25, 4.0)
        self._stretch.setDecimals(3)
        self._stretch.setSingleStep(0.05)
        self._stretch.setValue(1.0)
        self._stretch.valueChanged.connect(self._on_numeric_stretch)
        form.addRow("Stretch", self._stretch)

        self._reverse = QCheckBox("Reverse")
        self._reverse.setObjectName("samplePreparationReverse")
        self._reverse.toggled.connect(self._on_numeric_reverse)
        form.addRow("Reverse", self._reverse)
        body_layout.addWidget(numeric)

        output = QGroupBox("Output preparation")
        output.setObjectName("samplePreparationOutputGroup")
        output.setStyleSheet(group_style)
        output_form = QFormLayout(output)
        output_form.setContentsMargins(10, 12, 10, 10)
        output_form.setHorizontalSpacing(8)
        output_form.setVerticalSpacing(6)

        self._channels = QComboBox()
        self._channels.setObjectName("samplePreparationChannels")
        for mode in ("source", "mono", "stereo"):
            self._channels.addItem(mode, mode)
        self._channels.currentIndexChanged.connect(self._on_numeric_output)
        output_form.addRow("Channels", self._channels)

        self._sample_rate = QComboBox()
        self._sample_rate.setObjectName("samplePreparationSampleRate")
        self._sample_rate.addItem("source", "source")
        for rate in (44_100, 48_000, 96_000):
            self._sample_rate.addItem(str(rate), rate)
        self._sample_rate.currentIndexChanged.connect(self._on_numeric_output)
        output_form.addRow("Sample rate", self._sample_rate)

        self._bit_depth = QComboBox()
        self._bit_depth.setObjectName("samplePreparationBitDepth")
        self._bit_depth.addItem("source", "source")
        for depth in (16, 24, 32):
            self._bit_depth.addItem(str(depth), depth)
        self._bit_depth.currentIndexChanged.connect(self._on_numeric_output)
        output_form.addRow("Bit depth", self._bit_depth)

        self._output_format = QComboBox()
        self._output_format.setObjectName("samplePreparationOutputFormat")
        for output_format in ("wav", "flac", "ogg", "mp3"):
            self._output_format.addItem(output_format, output_format)
        self._output_format.currentIndexChanged.connect(self._on_numeric_output)
        output_form.addRow("Format", self._output_format)
        body_layout.addWidget(output)
        body_layout.addStretch(1)

        scroll.setWidget(body)
        dock_layout.addWidget(scroll)
        workbench.addWidget(dock)
        workbench.setStretchFactor(0, 3)
        workbench.setStretchFactor(1, 1)
        workbench.setSizes([760, 340])
        root.addWidget(workbench, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        save = QPushButton("Save Recipe")
        save.setObjectName("samplePreparationSaveButton")
        save.clicked.connect(self._save_recipe)
        actions.addWidget(save)

        self._preview_btn = QPushButton("Preview Edited (B)")
        self._preview_btn.setObjectName("samplePreparationPreviewButton")
        self._preview_btn.clicked.connect(self._preview_recipe)
        actions.addWidget(self._preview_btn)

        export = QPushButton("Export Copy")
        export.setObjectName("samplePreparationExportButton")
        export.setProperty("primary", True)
        export.setStyleSheet(f"background-color: {CLAY}; color: #0B0D0F; font-weight: 700;")
        export.clicked.connect(self._request_export)
        actions.addWidget(export)
        root.addLayout(actions)

        self._status = QLabel("")
        self._status.setObjectName("samplePreparationStatus")
        self._status.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._status)

        # Compatibility alias used by older tests looking for WaveformView object name.
        self._trim_state = self._selection_readout
        self._workbench_splitter = workbench

    @property
    def sample_id(self) -> EntityId | None:
        return self._sample_id

    @property
    def preview_path(self) -> Path | None:
        return self._preview_path

    @property
    def controller(self) -> WorkbenchController:
        return self._controller

    def show_sample(self, sample_id: EntityId, *, source_path: str | None = None) -> None:
        self._sample_id = sample_id
        self._preview_path = None
        self._ab_mode = "B"
        self._ab_a.setChecked(False)
        self._ab_b.setChecked(True)
        media = self._service.resolve_media_path(sample_id)
        self._source_path = source_path or (str(media) if media is not None else "")
        detail = self._context.sample_service.get_detail(sample_id)
        self._title.setText(f"Edit Sound — {detail.sample.filename}")
        self._source_label.setText(f"Source: {self._source_path or '—'}")
        recipe = self._service.get_recipe(sample_id)
        duration = detail.technical.duration_ms if detail.technical is not None else 0
        self._controller.load(recipe, duration_ms=duration)
        self._sync_controls_from_controller()
        self._status.setText("Loaded non-destructive recipe. Adjustments do not write the source.")
        self._load_waveform(media)

    def refresh(self) -> None:
        if self._sample_id is not None and not self._controller.dirty:
            self.show_sample(self._sample_id, source_path=self._source_path or None)

    def current_recipe(self) -> PreparationRecipe:
        return self._controller.recipe

    def _request_back(self) -> None:
        if self._controller.dirty:
            choice = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save recipe before leaving Edit Sound?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Save and not self._save_recipe():
                return
        self.back_requested.emit()

    def _on_dirty_changed(self, dirty: bool) -> None:
        if dirty:
            self._dirty_badge.setText("Unsaved Changes")
            self._dirty_badge.setStyleSheet(f"color: {YELLOW}; font-weight: 700;")
        else:
            self._dirty_badge.setText("Saved")
            self._dirty_badge.setStyleSheet(f"color: {GREEN}; font-weight: 700;")
        self._undo_btn.setEnabled(self._controller.can_undo)
        self._redo_btn.setEnabled(self._controller.can_redo)

    def _on_controller_changed(self) -> None:
        self._sync_controls_from_controller()
        self._invalidate_preview()
        self._undo_btn.setEnabled(self._controller.can_undo)
        self._redo_btn.setEnabled(self._controller.can_redo)
        self._apply_loop_to_playback()

    def _sync_controls_from_controller(self) -> None:
        recipe = self._controller.recipe
        sel = self._controller.selection
        self._suppress_control_events = True
        try:
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
            self._loop_enabled.setChecked(sel.loop_enabled)
            self._loop_start.setValue(sel.loop_start_ms)
            self._loop_end.setValue(0 if sel.loop_end_ms is None else sel.loop_end_ms)
        finally:
            self._suppress_control_events = False
        end_label = "end" if recipe.trim.end_ms is None else f"{recipe.trim.end_ms} ms"
        self._selection_readout.setText(f"Trim: {recipe.trim.start_ms} ms → {end_label}")
        self._playhead_readout.setText(f"Playhead: {self._fmt_ms(sel.playhead_ms)}")

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _on_numeric_trim(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        end = self._trim_end.value()
        self._controller.set_trim(
            self._trim_start.value(),
            None if end == 0 else end,
        )

    def _on_numeric_fades(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        self._controller.set_fades(self._fade_in.value(), self._fade_out.value())

    def _on_numeric_gain(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        self._controller.set_gain_db(float(self._gain.value()))

    def _on_numeric_normalize(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        self._controller.set_normalize(
            self._normalize.isChecked(),
            float(self._normalize_peak.value()),
        )

    def _on_numeric_pitch(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        self._controller.set_pitch(float(self._transpose.value()), self._fine_cents.value())

    def _on_numeric_stretch(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        self._controller.set_time_stretch(float(self._stretch.value()))

    def _on_numeric_reverse(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        self._controller.set_reverse(self._reverse.isChecked())

    def _on_numeric_output(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        sample_rate_data = self._sample_rate.currentData()
        bit_depth_data = self._bit_depth.currentData()
        sample_rate: SourceOrInt = (
            "source" if sample_rate_data == "source" else int(sample_rate_data)
        )
        bit_depth: SourceOrInt = "source" if bit_depth_data == "source" else int(bit_depth_data)
        self._controller.set_output(
            channels=cast(ChannelMode, str(self._channels.currentData())),
            sample_rate_hz=sample_rate,
            bit_depth=bit_depth,
            output_format=cast(OutputFormat, self._output_format.currentText()),
        )

    def _on_loop_toggled(self, checked: bool) -> None:
        if self._suppress_control_events:
            return
        end = self._loop_end.value()
        self._controller.set_preview_loop(
            checked,
            self._loop_start.value(),
            None if end == 0 else end,
        )

    def _on_numeric_loop(self, *_args: object) -> None:
        if self._suppress_control_events:
            return
        end = self._loop_end.value()
        self._controller.set_preview_loop(
            self._loop_enabled.isChecked(),
            self._loop_start.value(),
            None if end == 0 else end,
        )

    def _invalidate_preview(self) -> None:
        self._preview_path = None

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
            f"Waveform: {resolved.duration_ms / 1000:.3f}s · "
            f"{resolved.sample_rate_hz} Hz · {resolved.channels} ch"
        )

    def _save_recipe(self) -> bool:
        if self._sample_id is None:
            return False
        recipe = self.current_recipe()
        try:
            self._service.save_recipe(self._sample_id, recipe)
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return False
        self._controller.mark_saved(recipe)
        self._status.setText("Recipe saved (source audio unchanged).")
        self.recipe_saved.emit()
        return True

    def _reset_recipe(self) -> None:
        if self._sample_id is None:
            return
        try:
            self._service.reset_recipe(self._sample_id)
        except ApplicationError as exc:
            self._status.setText(str(exc))
            return
        self._controller.load(PreparationRecipe.default(), duration_ms=self._controller.duration_ms)
        self._sync_controls_from_controller()
        self._status.setText("Recipe reset to defaults (source audio unchanged).")
        self.recipe_saved.emit()

    def _preview_recipe(self) -> None:
        if self._sample_id is None:
            return
        self._ab_mode = "B"
        self._ab_a.setChecked(False)
        self._ab_b.setChecked(True)
        recipe = self.current_recipe()
        try:
            self._service.create_preview(self._sample_id, recipe)
        except ApplicationError as exc:
            self._preview_note.setText(str(exc))
            return
        self._preview_btn.setEnabled(False)
        self._preview_note.setText("Rendering preview…")
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
        self._preview_note.setText("Edited preview ready (B). Source audio is unchanged.")
        if self._ab_mode == "B":
            self.preview_ready.emit(sample_id, str(path))

    def _set_ab_mode(self, mode: str) -> None:
        self._ab_mode = mode
        self._ab_a.setChecked(mode == "A")
        self._ab_b.setChecked(mode == "B")
        if self._sample_id is None:
            return
        if mode == "A":
            media = self._service.resolve_media_path(self._sample_id)
            if media is not None and media.is_file():
                try:
                    self._context.playback_service.load(self._sample_id, media)
                    self._apply_loop_to_playback()
                    self._context.playback_service.play()
                except ApplicationError as exc:
                    self._preview_note.setText(str(exc))
                    return
                self._preview_note.setText("A — playing original source.")
            return
        if self._preview_path is not None and self._preview_path.is_file():
            self.preview_ready.emit(str(self._sample_id), str(self._preview_path))
            self._preview_note.setText("B — playing edited preview.")
        else:
            self._preview_recipe()

    def _on_seek_requested(self, position_ms: int) -> None:
        try:
            self._context.playback_service.seek(int(position_ms))
        except ApplicationError:
            return

    def _apply_loop_to_playback(self) -> None:
        sel = self._controller.selection
        try:
            if sel.loop_enabled:
                end = sel.loop_end_ms
                if end is None:
                    end = self._controller.duration_ms
                if end > sel.loop_start_ms:
                    self._context.playback_service.set_loop(sel.loop_start_ms, end)
                    return
            self._context.playback_service.set_loop(None, None)
        except ApplicationError:
            return

    def _request_export(self) -> None:
        if self._sample_id is None:
            return
        if not self._save_recipe():
            return
        self.export_requested.emit(str(self._sample_id))

    @staticmethod
    def _fmt_ms(ms: int) -> str:
        value = max(0, int(ms))
        seconds, millis = divmod(value, 1000)
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}.{millis:03d}"
