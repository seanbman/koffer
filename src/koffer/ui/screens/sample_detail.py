"""S07 Sample Detail: expanded Inspector with waveform, provenance, and actions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.audio.metadata import EmbeddedMetadataSnapshot
from koffer.audio.waveform import PeakEnvelope, WaveformCache
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.models import Classification, Suggestion, TechnicalMetadata
from koffer.services.samples import ProvenanceCategory
from koffer.ui.widgets.waveform_view import WaveformView


def _format_technical(tech: TechnicalMetadata | None) -> str:
    if tech is None:
        return "No technical probe yet."
    bit_depth = tech.bit_depth
    bitrate = tech.bitrate
    lines = [
        f"Container: {tech.container_format}",
        f"Codec: {tech.codec}",
        f"Duration: {tech.duration_ms} ms",
        f"Sample rate: {tech.sample_rate_hz} Hz",
        f"Channels: {tech.channels}",
        f"Bit depth: {bit_depth if bit_depth is not None else '—'}",
        f"Bitrate: {bitrate if bitrate is not None else '—'}",
    ]
    return "\n".join(lines)


def _format_embedded(embedded: EmbeddedMetadataSnapshot) -> str:
    if not embedded.ok:
        code = embedded.error_code or "error"
        message = embedded.error_message or "Unavailable"
        return f"Unavailable ({code}): {message}"
    lines = [f"{key}: {value if value else '—'}" for key, value in embedded.fields.items()]
    artwork = "yes" if embedded.has_artwork else "no"
    lines.append(f"artwork: {artwork}")
    return "\n".join(lines) if lines else "No embedded tags."


def _format_confirmed(classifications: tuple[Classification, ...]) -> str:
    if not classifications:
        return "No confirmed classifications."
    return "\n".join(f"{item.dimension}: {item.value}" for item in classifications)


def _format_suggested(suggestions: tuple[Suggestion, ...]) -> str:
    if not suggestions:
        return "No suggestions."
    lines = []
    for item in suggestions:
        conf = f"{item.confidence:.0%}"
        lines.append(f"{item.dimension}: {item.proposed_value} ({conf}, {item.status})")
    return "\n".join(lines)


def _format_tags(tags: tuple[str, ...]) -> str:
    if not tags:
        return "No user tags."
    return ", ".join(tags)


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


class _ProvenanceSection(QFrame):
    """One visually distinct provenance lane."""

    def __init__(
        self,
        category: ProvenanceCategory,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"provenance{category.value.title()}")
        self.setProperty("provenanceCategory", category.value)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("provenanceHeading")
        heading.setProperty("provenanceCategory", category.value)
        layout.addWidget(heading)
        self._body = QLabel("")
        self._body.setObjectName(f"provenanceBody{category.value.title()}")
        self._body.setProperty("provenanceCategory", category.value)
        self._body.setWordWrap(True)
        layout.addWidget(self._body)

    def set_text(self, text: str) -> None:
        self._body.setText(text)


class SampleDetailScreen(QWidget):
    """Expanded Sample Detail (S07) matching the documented desktop workspace."""

    back_requested = Signal()
    edit_metadata_requested = Signal(str)
    prepare_requested = Signal(str)
    find_similar_requested = Signal(str)
    organize_requested = Signal(str)
    reveal_requested = Signal(str)

    def __init__(
        self,
        context: AppContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._sample_service = context.sample_service
        self._sample_id: EntityId | None = None
        self._sample_name = ""
        self._media_path: str | None = None
        self._waveform_signals = _WaveformSignals(self)
        self._waveform_signals.completed.connect(self._on_waveform_ready)
        self.setObjectName("sampleDetailScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("Back to Library")
        back.setObjectName("backToLibraryButton")
        back.clicked.connect(self.back_requested.emit)
        top.addWidget(back)
        top.addStretch(1)
        self._edit_btn = QPushButton("Edit Metadata")
        self._edit_btn.setObjectName("editMetadataButton")
        self._edit_btn.clicked.connect(self._emit_edit_metadata)
        top.addWidget(self._edit_btn)
        self._prepare_btn = QPushButton("Prepare")
        self._prepare_btn.setObjectName("prepareButton")
        self._prepare_btn.setProperty("primary", True)
        self._prepare_btn.clicked.connect(self._emit_prepare)
        top.addWidget(self._prepare_btn)
        root.addLayout(top)

        self._title = QLabel("Sample Detail")
        self._title.setObjectName("pageTitle")
        root.addWidget(self._title)

        self._identity = QLabel("")
        self._identity.setObjectName("sampleDetailIdentity")
        self._identity.setWordWrap(True)
        root.addWidget(self._identity)

        self._waveform = WaveformView()
        self._waveform.setObjectName("sampleDetailWaveform")
        self._waveform.setMinimumHeight(180)
        self._waveform.setMaximumHeight(220)
        root.addWidget(self._waveform)

        self._waveform_state = QLabel("Waveform: —")
        self._waveform_state.setObjectName("sampleDetailWaveformState")
        root.addWidget(self._waveform_state)

        scroll = QScrollArea()
        scroll.setObjectName("sampleDetailScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("sampleDetailBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        self._technical = _ProvenanceSection(ProvenanceCategory.TECHNICAL, "TECHNICAL (factual)")
        self._embedded = _ProvenanceSection(ProvenanceCategory.EMBEDDED, "EMBEDDED (file tags)")
        self._confirmed = _ProvenanceSection(
            ProvenanceCategory.CONFIRMED, "CONFIRMED (classifications)"
        )
        self._suggested = _ProvenanceSection(ProvenanceCategory.SUGGESTED, "SUGGESTED (analysis)")
        self._tags = _ProvenanceSection(ProvenanceCategory.TAGS, "TAGS (user)")
        for section in (
            self._technical,
            self._embedded,
            self._confirmed,
            self._suggested,
            self._tags,
        ):
            body_layout.addWidget(section)

        self._collections = QLabel("")
        self._collections.setObjectName("sampleDetailCollections")
        self._collections.setWordWrap(True)
        body_layout.addWidget(self._collections)

        self._history = QLabel("")
        self._history.setObjectName("sampleDetailHistory")
        self._history.setWordWrap(True)
        body_layout.addWidget(self._history)

        self._recipe = QLabel("")
        self._recipe.setObjectName("sampleDetailRecipe")
        body_layout.addWidget(self._recipe)

        self._path = QLabel("")
        self._path.setObjectName("sampleDetailPath")
        self._path.setWordWrap(True)
        body_layout.addWidget(self._path)

        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        actions = QHBoxLayout()
        self._similar_btn = QPushButton("Find Similar")
        self._similar_btn.setObjectName("findSimilarButton")
        self._similar_btn.clicked.connect(self._emit_find_similar)
        actions.addWidget(self._similar_btn)

        self._collection_btn = QPushButton("Add to Collection")
        self._collection_btn.setObjectName("addToCollectionButton")
        self._collection_btn.clicked.connect(self._add_to_collection)
        actions.addWidget(self._collection_btn)

        self._organize_btn = QPushButton("Organize")
        self._organize_btn.setObjectName("organizeSampleButton")
        self._organize_btn.clicked.connect(self._emit_organize)
        actions.addWidget(self._organize_btn)

        self._reveal_btn = QPushButton("Reveal in Files")
        self._reveal_btn.setObjectName("revealSampleButton")
        self._reveal_btn.clicked.connect(self._emit_reveal)
        actions.addWidget(self._reveal_btn)
        actions.addStretch(1)
        root.addLayout(actions)

    @property
    def sample_id(self) -> EntityId | None:
        return self._sample_id

    @property
    def sample_name(self) -> str:
        return self._sample_name

    def show_sample(self, sample_id: EntityId) -> None:
        self._sample_id = sample_id
        self.refresh()

    def refresh(self) -> None:
        if self._sample_id is None:
            return
        detail = self._sample_service.get_detail(self._sample_id)
        sample = detail.sample
        self._sample_name = sample.filename
        self._media_path = detail.media_path
        self._title.setText(sample.filename)
        self._identity.setText(
            f"Availability: {sample.availability} · Format: {sample.extension} · "
            f"Favorite: {'yes' if sample.favorite else 'no'}"
        )
        path_state = "online" if detail.path_available else "unavailable"
        self._path.setText(f"PATH\n{detail.media_path or '—'} · {path_state}")
        recipe = "present" if detail.has_preparation_recipe else "none"
        self._recipe.setText(f"PREPARATION\nNon-destructive recipe: {recipe}")
        names = ", ".join(detail.collection_names) if detail.collection_names else "No Collections."
        self._collections.setText(f"COLLECTIONS\n{names}")
        previewed = sample.last_previewed_at or "Never"
        self._history.setText(
            "HISTORY\n"
            f"Discovered: {sample.first_seen_at}\n"
            f"Last seen: {sample.last_seen_at}\n"
            f"Last previewed: {previewed}"
        )

        provenance = detail.provenance()
        assert set(provenance) == {
            ProvenanceCategory.TECHNICAL.value,
            ProvenanceCategory.EMBEDDED.value,
            ProvenanceCategory.CONFIRMED.value,
            ProvenanceCategory.SUGGESTED.value,
            ProvenanceCategory.TAGS.value,
        }
        self._technical.set_text(_format_technical(detail.technical))
        self._embedded.set_text(_format_embedded(detail.embedded))
        self._confirmed.set_text(_format_confirmed(detail.classifications))
        self._suggested.set_text(_format_suggested(detail.suggestions))
        self._tags.set_text(_format_tags(detail.tags))

        self._reveal_btn.setEnabled(detail.path_available and detail.media_path is not None)
        self._organize_btn.setEnabled(detail.path_available)
        self._load_waveform(detail.media_path if detail.path_available else None)

    def _load_waveform(self, media_path: str | None) -> None:
        self._waveform.set_envelope(None)
        if self._sample_id is None or media_path is None:
            self._waveform_state.setText("Waveform: unavailable")
            return
        path = Path(media_path)
        if not path.is_file():
            self._waveform_state.setText("Waveform: unavailable")
            return
        self._waveform_state.setText("Waveform: loading…")
        task = _WaveformTask(
            self._context.waveform_cache,
            self._sample_id,
            path,
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

    def _add_to_collection(self) -> None:
        if self._sample_id is None:
            return
        collections = self._context.collection_service.list_with_counts()
        if not collections:
            name, accepted = QInputDialog.getText(
                self,
                "Add to Collection",
                "No Collections yet. Name a new Collection:",
            )
            if not accepted or not name.strip():
                return
            try:
                collection = self._context.collection_service.create(name.strip())
                self._context.collection_service.add_samples(collection.id, [self._sample_id])
            except ApplicationError as exc:
                QMessageBox.warning(self, "Could not add to Collection", str(exc))
                return
            self.refresh()
            return

        labels = [item.collection.name for item in collections]
        choice, accepted = QInputDialog.getItem(
            self,
            "Add to Collection",
            "Collection:",
            labels,
            0,
            False,
        )
        if not accepted or not choice:
            return
        selected = next(
            (item for item in collections if item.collection.name == choice),
            None,
        )
        if selected is None:
            return
        try:
            self._context.collection_service.add_samples(
                selected.collection.id,
                [self._sample_id],
            )
        except ApplicationError as exc:
            QMessageBox.warning(self, "Could not add to Collection", str(exc))
            return
        self.refresh()

    def _emit_edit_metadata(self) -> None:
        if self._sample_id is not None:
            self.edit_metadata_requested.emit(str(self._sample_id))

    def _emit_prepare(self) -> None:
        if self._sample_id is not None:
            self.prepare_requested.emit(str(self._sample_id))

    def _emit_find_similar(self) -> None:
        if self._sample_id is not None:
            self.find_similar_requested.emit(str(self._sample_id))

    def _emit_organize(self) -> None:
        if self._sample_id is not None:
            self.organize_requested.emit(str(self._sample_id))

    def _emit_reveal(self) -> None:
        if self._media_path is not None:
            self.reveal_requested.emit(self._media_path)
