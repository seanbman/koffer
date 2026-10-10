"""S14 Render / Export foundations (docs/12, docs/15). Explicit new output file only."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.enums import ConflictAction
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.preparation import PreparationRecipe, RenderOptions, RenderPlan
from koffer.services.preparation import PreparationService
from koffer.ui.tokens import CLAY, GREEN, MUTED, YELLOW


class RenderExportScreen(QWidget):
    """S14: summarize recipe, choose output, enqueue RENDER Job (never overwrites source)."""

    back_requested = Signal()
    execute_requested = Signal()
    plan_ready = Signal()

    def __init__(
        self,
        preparation_service: PreparationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = preparation_service
        self._sample_id: EntityId | None = None
        self._recipe: PreparationRecipe | None = None
        self._plan: RenderPlan | None = None
        self.setObjectName("renderExportScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Render / Export")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        back = QPushButton("Back")
        back.setObjectName("renderExportBackButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        self._original = QLabel("Original: —")
        self._original.setObjectName("renderExportOriginalLabel")
        self._original.setWordWrap(True)
        root.addWidget(self._original)

        self._output = QLabel("Output: —")
        self._output.setObjectName("renderExportOutputLabel")
        self._output.setWordWrap(True)
        self._output.setStyleSheet(f"color: {GREEN};")
        root.addWidget(self._output)

        self._recipe_summary = QLabel("Recipe summary: —")
        self._recipe_summary.setObjectName("renderExportRecipeSummary")
        self._recipe_summary.setWordWrap(True)
        self._recipe_summary.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._recipe_summary)

        form = QFormLayout()
        form.setObjectName("renderExportForm")

        self._destination = QLineEdit()
        self._destination.setObjectName("renderExportDestination")
        form.addRow("Destination directory", self._destination)

        self._filename = QLineEdit()
        self._filename.setObjectName("renderExportFilename")
        form.addRow("Filename", self._filename)

        self._format = QComboBox()
        self._format.setObjectName("renderExportFormat")
        for fmt in ("wav", "flac", "ogg", "mp3"):
            self._format.addItem(fmt)
        form.addRow("Output format", self._format)

        self._sample_rate = QComboBox()
        self._sample_rate.setObjectName("renderExportSampleRate")
        self._sample_rate.addItem("source", "source")
        for rate in (44100, 48000, 96000):
            self._sample_rate.addItem(str(rate), rate)
        form.addRow("Sample rate", self._sample_rate)

        self._channels = QComboBox()
        self._channels.setObjectName("renderExportChannels")
        for mode in ("source", "mono", "stereo"):
            self._channels.addItem(mode, mode)
        form.addRow("Channels", self._channels)

        self._bit_depth = QComboBox()
        self._bit_depth.setObjectName("renderExportBitDepth")
        self._bit_depth.addItem("source", "source")
        for depth in (16, 24, 32):
            self._bit_depth.addItem(str(depth), depth)
        form.addRow("Bit depth", self._bit_depth)

        self._carry_metadata = QCheckBox("Carry metadata to output")
        self._carry_metadata.setObjectName("renderExportCarryMetadata")
        self._carry_metadata.setChecked(True)
        form.addRow("Metadata", self._carry_metadata)

        self._conflict = QComboBox()
        self._conflict.setObjectName("renderExportConflictPolicy")
        self._conflict.addItem("Keep Both", ConflictAction.KEEP_BOTH.value)
        self._conflict.addItem("Skip", ConflictAction.SKIP.value)
        self._conflict.addItem("Replace (explicit)", ConflictAction.REPLACE.value)
        form.addRow("Filename conflict policy", self._conflict)

        root.addLayout(form)

        self._job_note = QLabel("Render runs as a background Job and always produces a new file.")
        self._job_note.setObjectName("renderExportJobNote")
        self._job_note.setStyleSheet(f"color: {YELLOW};")
        root.addWidget(self._job_note)

        actions = QHBoxLayout()
        plan_btn = QPushButton("Review Plan")
        plan_btn.setObjectName("renderExportPlanButton")
        plan_btn.clicked.connect(self._build_plan)
        actions.addWidget(plan_btn)

        self._execute = QPushButton("Export Copy")
        self._execute.setObjectName("renderExportExecuteButton")
        self._execute.setEnabled(False)
        self._execute.setProperty("primary", True)
        self._execute.setStyleSheet(f"background-color: {CLAY};")
        self._execute.clicked.connect(self.execute_requested.emit)
        actions.addWidget(self._execute)
        root.addLayout(actions)

        self._plan_summary = QLabel("")
        self._plan_summary.setObjectName("renderExportPlanSummary")
        self._plan_summary.setWordWrap(True)
        root.addWidget(self._plan_summary)
        root.addStretch(1)

    @property
    def plan(self) -> RenderPlan | None:
        return self._plan

    def show_sample(self, sample_id: EntityId, *, destination_dir: str | None = None) -> None:
        self._sample_id = sample_id
        self._plan = None
        self._execute.setEnabled(False)
        recipe = self._service.get_recipe(sample_id)
        self._recipe = recipe
        media = self._service.resolve_media_path(sample_id)
        original = str(media) if media is not None else "—"
        self._original.setText(f"Original: {original}")
        self._recipe_summary.setText("Recipe summary:\n" + "\n".join(recipe.summary_lines()))
        self._format.setCurrentText(recipe.output_format)
        if destination_dir:
            self._destination.setText(destination_dir)
        elif media is not None:
            self._destination.setText(str(media.parent / "renders"))
        else:
            self._destination.setText("")
        stem = media.stem + "_prepared" if media is not None else "prepared"
        self._filename.setText(stem)
        self._output.setText("Output: (review plan)")
        self._plan_summary.setText("")

    def refresh(self) -> None:
        if self._sample_id is not None:
            dest = self._destination.text().strip() or None
            self.show_sample(self._sample_id, destination_dir=dest)

    def _recipe_with_output_controls(self) -> PreparationRecipe:
        assert self._recipe is not None
        base = self._recipe
        sample_rate_data = self._sample_rate.currentData()
        bit_depth_data = self._bit_depth.currentData()
        return PreparationRecipe(
            version=base.version,
            trim=base.trim,
            fade_in_ms=base.fade_in_ms,
            fade_out_ms=base.fade_out_ms,
            gain_db=base.gain_db,
            normalize=base.normalize,
            transpose_semitones=base.transpose_semitones,
            fine_cents=base.fine_cents,
            time_stretch_ratio=base.time_stretch_ratio,
            reverse=base.reverse,
            channels=str(self._channels.currentData()),  # type: ignore[arg-type]
            sample_rate_hz=("source" if sample_rate_data == "source" else int(sample_rate_data)),
            bit_depth=("source" if bit_depth_data == "source" else int(bit_depth_data)),
            output_format=str(self._format.currentText()),  # type: ignore[arg-type]
        )

    def _build_plan(self) -> None:
        if self._sample_id is None:
            return
        try:
            recipe = self._recipe_with_output_controls()
            options = RenderOptions(
                destination_dir=self._destination.text().strip(),
                filename=self._filename.text().strip(),
                conflict_policy=ConflictAction(str(self._conflict.currentData())),
                carry_metadata=self._carry_metadata.isChecked(),
                carry_artwork=False,
            )
            plan = self._service.plan_render(self._sample_id, recipe, options)
        except ApplicationError as exc:
            self._plan = None
            self._execute.setEnabled(False)
            self._plan_summary.setText(str(exc))
            return
        self._plan = plan
        self._execute.setEnabled(True)
        self._output.setText(f"Output: {plan.destination_path}")
        self._plan_summary.setText(
            "Ready to export a new file. The original Sample remains unchanged.\n"
            f"Format: {recipe.output_format.upper()} · "
            f"Sample rate: {recipe.sample_rate_hz} · Channels: {recipe.channels} · "
            f"Bit depth: {recipe.bit_depth}\n"
            f"Conflict policy: {plan.conflict_policy.value.replace('_', ' ').title()}"
        )
        self.plan_ready.emit()

    def default_destination_hint(self) -> Path | None:
        text = self._destination.text().strip()
        return Path(text) if text else None
