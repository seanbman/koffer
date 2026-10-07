"""S09 Metadata Editor foundations (docs/12, docs/15)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.enums import ArtworkAction, MetadataWriteTarget
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.metadata_write import (
    ArtworkPayload,
    MetadataEditState,
    MetadataWritePlan,
    MetadataWriteRequest,
)
from koffer.services.metadata import MetadataService
from koffer.ui.tokens import CLAY, MUTED, RED, YELLOW


class MetadataEditorScreen(QWidget):
    """S09: edit embeddable metadata with explicit write target; Koffer tags stay library-only."""

    back_requested = Signal()
    execute_requested = Signal()
    plan_ready = Signal()

    def __init__(
        self,
        metadata_service: MetadataService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = metadata_service
        self._sample_ids: list[EntityId] = []
        self._state: MetadataEditState | None = None
        self._plan: MetadataWritePlan | None = None
        self._field_edits: dict[str, QLineEdit] = {}
        self._artwork_action = ArtworkAction.KEEP
        self._artwork_payload: ArtworkPayload | None = None
        self._artwork_path: Path | None = None
        self.setObjectName("metadataEditorScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Metadata Editor")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        back = QPushButton("Back")
        back.setObjectName("metadataEditorBackButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        self._summary = QLabel("Select samples to edit embedded metadata.")
        self._summary.setObjectName("metadataEditorSummary")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        scroll = QScrollArea()
        scroll.setObjectName("metadataEditorScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("metadataEditorBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

        # Descriptive (embeddable)
        desc_heading = QLabel("Descriptive (embeddable)")
        desc_heading.setObjectName("metadataEditorDescriptiveHeading")
        body_layout.addWidget(desc_heading)
        self._desc_form = QFormLayout()
        self._desc_form.setObjectName("metadataEditorDescriptiveForm")
        desc_wrap = QWidget()
        desc_wrap.setObjectName("metadataEditorDescriptiveSection")
        desc_wrap.setLayout(self._desc_form)
        body_layout.addWidget(desc_wrap)

        # Musical placeholder — BPM/key are not forced into embedded writes here.
        musical = QLabel(
            "Musical (Koffer-confirmed BPM/key stay library-only unless explicitly embedded later)."
        )
        musical.setObjectName("metadataEditorMusicalSection")
        musical.setWordWrap(True)
        musical.setStyleSheet(f"color: {MUTED};")
        body_layout.addWidget(musical)

        # Artwork
        artwork_heading = QLabel("Artwork")
        artwork_heading.setObjectName("metadataEditorArtworkHeading")
        body_layout.addWidget(artwork_heading)

        self._artwork = QLabel("Artwork: —")
        self._artwork.setObjectName("metadataEditorArtworkSection")
        self._artwork.setWordWrap(True)
        body_layout.addWidget(self._artwork)

        artwork_actions = QHBoxLayout()
        self._artwork_replace = QPushButton("Add / Replace")
        self._artwork_replace.setObjectName("metadataEditorArtworkReplaceButton")
        self._artwork_replace.setEnabled(False)
        self._artwork_replace.clicked.connect(self._choose_artwork)
        artwork_actions.addWidget(self._artwork_replace)

        self._artwork_remove = QPushButton("Remove")
        self._artwork_remove.setObjectName("metadataEditorArtworkRemoveButton")
        self._artwork_remove.setEnabled(False)
        self._artwork_remove.clicked.connect(self._mark_remove_artwork)
        artwork_actions.addWidget(self._artwork_remove)

        self._artwork_keep = QPushButton("Keep Current")
        self._artwork_keep.setObjectName("metadataEditorArtworkKeepButton")
        self._artwork_keep.setEnabled(False)
        self._artwork_keep.clicked.connect(self._keep_artwork)
        artwork_actions.addWidget(self._artwork_keep)
        artwork_actions.addStretch(1)
        body_layout.addLayout(artwork_actions)

        # Koffer tags — never forces embedded write
        tags_heading = QLabel("Koffer Tags (library-only — not written to the file)")
        tags_heading.setObjectName("metadataEditorKofferTagsHeading")
        body_layout.addWidget(tags_heading)
        self._tags = QLabel("—")
        self._tags.setObjectName("metadataEditorKofferTags")
        self._tags.setWordWrap(True)
        self._tags.setStyleSheet(f"color: {MUTED};")
        body_layout.addWidget(self._tags)

        # Write target
        target_heading = QLabel("Write Target")
        target_heading.setObjectName("metadataEditorWriteTargetHeading")
        body_layout.addWidget(target_heading)
        target_row = QHBoxLayout()
        self._target_group = QButtonGroup(self)
        self._update_original = QRadioButton("Update Original")
        self._update_original.setObjectName("metadataEditorUpdateOriginal")
        self._write_to_copy = QRadioButton("Write to Copy")
        self._write_to_copy.setObjectName("metadataEditorWriteToCopy")
        self._update_original.setChecked(True)
        self._target_group.addButton(self._update_original)
        self._target_group.addButton(self._write_to_copy)
        target_row.addWidget(self._update_original)
        target_row.addWidget(self._write_to_copy)
        target_row.addStretch(1)
        body_layout.addLayout(target_row)

        self._copy_dir_label = QLabel("Copy destination directory:")
        self._copy_dir_label.setObjectName("metadataEditorCopyDirLabel")
        body_layout.addWidget(self._copy_dir_label)
        self._copy_dir = QLineEdit()
        self._copy_dir.setObjectName("metadataEditorCopyDir")
        self._copy_dir.setPlaceholderText("/path/to/metadata-copies")
        body_layout.addWidget(self._copy_dir)
        self._write_to_copy.toggled.connect(self._sync_copy_dir_enabled)
        self._sync_copy_dir_enabled()

        self._limitations = QLabel("")
        self._limitations.setObjectName("metadataEditorLimitations")
        self._limitations.setWordWrap(True)
        self._limitations.setStyleSheet(f"color: {YELLOW};")
        body_layout.addWidget(self._limitations)

        exceptions_heading = QLabel("Exceptions (must be empty before execute)")
        exceptions_heading.setObjectName("metadataEditorExceptionsHeading")
        body_layout.addWidget(exceptions_heading)
        self._exceptions = QListWidget()
        self._exceptions.setObjectName("metadataEditorExceptionList")
        body_layout.addWidget(self._exceptions)

        self._plan_summary = QLabel("No plan yet.")
        self._plan_summary.setObjectName("metadataEditorPlanSummary")
        self._plan_summary.setWordWrap(True)
        body_layout.addWidget(self._plan_summary)

        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        actions = QHBoxLayout()
        self._plan_btn = QPushButton("Review Plan")
        self._plan_btn.setObjectName("metadataEditorPlanButton")
        self._plan_btn.clicked.connect(self._build_plan)
        actions.addWidget(self._plan_btn)
        actions.addStretch(1)
        self._execute_btn = QPushButton("Execute Write")
        self._execute_btn.setObjectName("metadataEditorExecuteButton")
        self._execute_btn.setStyleSheet(
            "QPushButton#metadataEditorExecuteButton {"
            f" background-color: {CLAY}; color: #0B0D0F; border: none;"
            " border-radius: 5px; padding: 8px 16px; min-height: 32px;"
            " font-weight: 600; }"
        )
        self._execute_btn.clicked.connect(self.execute_requested.emit)
        self._execute_btn.setEnabled(False)
        actions.addWidget(self._execute_btn)
        root.addLayout(actions)

        self._error = QLabel("")
        self._error.setObjectName("metadataEditorError")
        self._error.setStyleSheet(f"color: {RED};")
        self._error.setWordWrap(True)
        root.addWidget(self._error)

    @property
    def plan(self) -> MetadataWritePlan | None:
        return self._plan

    @property
    def sample_ids(self) -> list[EntityId]:
        return list(self._sample_ids)

    def show_samples(self, sample_ids: list[EntityId]) -> None:
        self._sample_ids = list(sample_ids)
        self._plan = None
        self._artwork_action = ArtworkAction.KEEP
        self._artwork_payload = None
        self._artwork_path = None
        self._error.setText("")
        self.refresh()

    def refresh(self) -> None:
        self._clear_fields()
        self._exceptions.clear()
        self._execute_btn.setEnabled(False)
        if not self._sample_ids:
            self._summary.setText("Select samples to edit embedded metadata.")
            self._artwork.setText("Artwork: —")
            self._tags.setText("—")
            self._limitations.setText("")
            self._plan_summary.setText("No plan yet.")
            return

        state = self._service.get_editor_state(self._sample_ids)
        self._state = state
        formats = ", ".join(state.format_ids) or "unknown"
        self._summary.setText(
            f"{len(state.sample_ids)} sample(s) · formats: {formats}. "
            "Unsupported embeddable fields are disabled with an explanation."
        )
        for field in state.embeddable_fields:
            edit = QLineEdit()
            edit.setObjectName(f"metadataField_{field.name}")
            if field.mixed:
                edit.setPlaceholderText("(mixed values)")
            elif field.value:
                edit.setText(field.value)
            edit.setEnabled(field.writable)
            if not field.writable:
                tip = field.explanation or "Not writable for selected format(s)."
                edit.setToolTip(tip)
                label_text = f"{field.name} (unsupported)"
            else:
                label_text = field.name
            self._desc_form.addRow(label_text, edit)
            self._field_edits[field.name] = edit

        if state.artwork_supported:
            self._artwork_replace.setEnabled(True)
            self._artwork_remove.setEnabled(
                state.artwork_present or self._artwork_payload is not None
            )
            self._artwork_keep.setEnabled(self._artwork_action is not ArtworkAction.KEEP)
            self._artwork_replace.setText(
                "Replace Artwork" if state.artwork_present else "Add Artwork"
            )
            self._artwork.setStyleSheet("")
            self._sync_artwork_status(state)
        else:
            self._artwork_action = ArtworkAction.KEEP
            self._artwork_payload = None
            self._artwork_path = None
            self._artwork_replace.setEnabled(False)
            self._artwork_remove.setEnabled(False)
            self._artwork_keep.setEnabled(False)
            self._artwork.setText(
                state.artwork_explanation or "Artwork: not supported for selected format(s)."
            )
            self._artwork.setStyleSheet(f"color: {YELLOW};")

        if state.koffer_tags:
            self._tags.setText(", ".join(state.koffer_tags))
        else:
            self._tags.setText("No Koffer tags on selected samples.")

        if state.limitations:
            self._limitations.setText("Format notes: " + " · ".join(state.limitations))
        else:
            self._limitations.setText("")

        if self._plan is not None:
            self._show_plan(self._plan)
        else:
            self._plan_summary.setText("No plan yet. Review Plan before execute.")

    def _clear_fields(self) -> None:
        while self._desc_form.rowCount():
            self._desc_form.removeRow(0)
        self._field_edits.clear()

    def _sync_copy_dir_enabled(self) -> None:
        enabled = self._write_to_copy.isChecked()
        self._copy_dir.setEnabled(enabled)
        self._copy_dir_label.setEnabled(enabled)

    def _sync_artwork_status(self, state: MetadataEditState | None = None) -> None:
        current = state or self._state
        if current is None:
            self._artwork.setText("Artwork: —")
            return
        existing = "present" if current.artwork_present else "none"
        if self._artwork_action is ArtworkAction.ADD_REPLACE and self._artwork_path is not None:
            self._artwork.setText(
                f"Artwork: {existing}. Pending add/replace: {self._artwork_path.name}"
            )
        elif self._artwork_action is ArtworkAction.REMOVE:
            self._artwork.setText(f"Artwork: {existing}. Pending removal.")
        else:
            self._artwork.setText(f"Artwork: supported ({existing}). No pending artwork write.")

    def _choose_artwork(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Choose Artwork",
            str(Path.home()),
            "Images (*.jpg *.jpeg *.png)",
        )
        if selected:
            self.set_artwork_file(Path(selected))

    def set_artwork_file(self, path: Path) -> bool:
        """Set pending JPEG/PNG artwork; helper is deterministic for UI tests."""
        target = Path(path)
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }.get(target.suffix.lower())
        if mime is None:
            self._error.setText("Artwork must be a JPEG or PNG image.")
            return False
        try:
            data = target.read_bytes()
        except OSError as exc:
            self._error.setText(f"Could not read artwork: {exc}")
            return False
        if not data:
            self._error.setText("Artwork image is empty.")
            return False
        if len(data) > 20 * 1024 * 1024:
            self._error.setText("Artwork image exceeds the 20 MB safety limit.")
            return False
        self._error.setText("")
        self._artwork_action = ArtworkAction.ADD_REPLACE
        self._artwork_payload = ArtworkPayload(data=data, mime=mime)
        self._artwork_path = target
        self._plan = None
        self._execute_btn.setEnabled(False)
        self._artwork_keep.setEnabled(True)
        self._artwork_remove.setEnabled(True)
        self._sync_artwork_status()
        return True

    def _mark_remove_artwork(self) -> None:
        if (
            self._state is not None
            and not self._state.artwork_present
            and self._artwork_payload is not None
        ):
            self._keep_artwork()
            return
        self._artwork_action = ArtworkAction.REMOVE
        self._artwork_payload = None
        self._artwork_path = None
        self._plan = None
        self._execute_btn.setEnabled(False)
        self._artwork_keep.setEnabled(True)
        self._sync_artwork_status()

    def _keep_artwork(self) -> None:
        self._artwork_action = ArtworkAction.KEEP
        self._artwork_payload = None
        self._artwork_path = None
        self._plan = None
        self._execute_btn.setEnabled(False)
        self._artwork_keep.setEnabled(False)
        if self._state is not None:
            self._artwork_remove.setEnabled(self._state.artwork_present)
        self._sync_artwork_status()

    def _selected_target(self) -> MetadataWriteTarget:
        if self._write_to_copy.isChecked():
            return MetadataWriteTarget.WRITE_TO_COPY
        return MetadataWriteTarget.UPDATE_ORIGINAL

    def _collect_fields(self) -> dict[str, str | None]:
        fields: dict[str, str | None] = {}
        for name, edit in self._field_edits.items():
            if not edit.isEnabled():
                continue
            text = edit.text().strip()
            # Only include fields the user actually touched or that have values to set.
            if text or edit.isModified():
                fields[name] = text or None
        return fields

    def _build_plan(self) -> None:
        self._error.setText("")
        self._plan = None
        self._execute_btn.setEnabled(False)
        if not self._sample_ids:
            self._error.setText("No samples selected.")
            return
        fields = self._collect_fields()
        if not fields and self._artwork_action is ArtworkAction.KEEP:
            self._error.setText(
                "Edit a supported field or choose an Artwork action before planning."
            )
            return
        target = self._selected_target()
        copy_dir = self._copy_dir.text().strip() or None
        request = MetadataWriteRequest(
            sample_ids=tuple(self._sample_ids),
            target=target,
            fields=fields,
            artwork_action=self._artwork_action,
            artwork=self._artwork_payload,
            copy_destination_dir=copy_dir,
        )
        try:
            plan = self._service.plan_write(request)
        except ApplicationError as exc:
            self._error.setText(str(exc))
            return
        self._show_plan(plan)
        self._plan = plan
        self.plan_ready.emit()

    def _show_plan(self, plan: MetadataWritePlan) -> None:
        self._exceptions.clear()
        for exc in plan.exceptions:
            text = f"{exc.field}: {exc.message} ({exc.code})"
            self._exceptions.addItem(QListWidgetItem(text))
        target_label = (
            "Update Original"
            if plan.target is MetadataWriteTarget.UPDATE_ORIGINAL
            else "Write to Copy"
        )
        paths = [item.destination_path for item in plan.items]
        preview = ", ".join(Path(p).name for p in paths[:5])
        more = "" if len(paths) <= 5 else f" (+{len(paths) - 5} more)"
        self._plan_summary.setText(
            f"Target: {target_label} · {len(plan.items)} file(s): {preview}{more}. "
            f"Artwork: {plan.artwork_action} · Exceptions: {len(plan.exceptions)}."
        )
        self._execute_btn.setEnabled(len(plan.exceptions) == 0 and len(plan.items) > 0)
