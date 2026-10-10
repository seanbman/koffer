"""S07 Sample: human-readable identity, waveform, classification, and Edit Sound."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.audio.metadata import EmbeddedMetadataSnapshot
from koffer.audio.waveform import PeakEnvelope, WaveformCache
from koffer.domain.errors import ApplicationError
from koffer.domain.ids import EntityId
from koffer.domain.models import Classification, Suggestion, TechnicalMetadata
from koffer.domain.preparation import PreparationRecipe
from koffer.ui.tokens import BLUE, CLAY, GREEN, MUTED, SURFACE_1, SURFACE_2, TEXT, YELLOW
from koffer.ui.widgets.waveform_view import WaveformView


def _format_identity(filename: str, extension: str, availability: object, favorite: bool) -> str:
    fav = " · Favorite" if favorite else ""
    return f"{filename}\n{str(availability).replace('_', ' ').title()} · {extension.upper()}{fav}"


def _format_classification_summary(classifications: tuple[Classification, ...]) -> str:
    if not classifications:
        return "No confirmed classifications yet. Use Edit Info to set Sample Type, Role, and more."
    by_dim: dict[str, list[str]] = {}
    for item in classifications:
        by_dim.setdefault(item.dimension, []).append(item.value)
    lines = [f"{dim}: {', '.join(values)}" for dim, values in by_dim.items()]
    return "\n".join(lines)


def _format_suggestion_summary(suggestions: tuple[Suggestion, ...]) -> str:
    open_items = [
        item
        for item in suggestions
        if str(item.status).lower() in {"pending", "open", "suggested", "new", "needs_review"}
    ]
    # Fall back to all suggestions when status vocabulary differs.
    items = open_items or list(suggestions)
    if not items:
        return "No Suggestions waiting for review."
    lines = []
    for item in items[:8]:
        conf = f"{item.confidence:.0%}"
        lines.append(f"Suggested {item.dimension}: {item.proposed_value} ({conf} confidence)")
    if len(items) > 8:
        lines.append(f"…and {len(items) - 8} more in Review")
    return "\n".join(lines)


def _format_tags_and_collections(tags: tuple[str, ...], collections: tuple[str, ...]) -> str:
    tag_text = ", ".join(tags) if tags else "No tags"
    collection_text = ", ".join(collections) if collections else "No Collections"
    return f"Tags: {tag_text}\nCollections: {collection_text}"


def _format_technical(tech: TechnicalMetadata | None) -> str:
    if tech is None:
        return "Technical probe not available yet."
    bit_depth = tech.bit_depth if tech.bit_depth is not None else "—"
    bitrate = tech.bitrate if tech.bitrate is not None else "—"
    return (
        f"Format: {tech.container_format} / {tech.codec}\n"
        f"Duration: {tech.duration_ms / 1000:.3f}s\n"
        f"Sample rate: {tech.sample_rate_hz} Hz · Channels: {tech.channels}\n"
        f"Bit depth: {bit_depth} · Bitrate: {bitrate}"
    )


def _format_embedded(embedded: EmbeddedMetadataSnapshot) -> str:
    if not embedded.ok:
        message = embedded.error_message or "Could not read embedded tags"
        return f"Embedded tags unavailable — {message}"
    interesting = []
    for key, value in embedded.fields.items():
        if value:
            interesting.append(f"{key}: {value}")
    if embedded.has_artwork:
        interesting.append("Artwork: embedded")
    return "\n".join(interesting) if interesting else "No embedded tags."


def _format_file_details(
    path: str | None,
    path_available: bool,
    tech: TechnicalMetadata | None,
    embedded: EmbeddedMetadataSnapshot,
    first_seen: str,
    last_seen: str,
    last_previewed: str | None,
) -> str:
    state = "Online" if path_available else "Unavailable"
    previewed = last_previewed or "Never"
    return (
        f"Path: {path or '—'}\n"
        f"Availability: {state}\n"
        f"{_format_technical(tech)}\n"
        f"{_format_embedded(embedded)}\n"
        f"Discovered: {first_seen}\n"
        f"Last seen: {last_seen}\n"
        f"Last previewed: {previewed}"
    )


def _format_analysis_details(suggestions: tuple[Suggestion, ...]) -> str:
    if not suggestions:
        return "No analysis details. Suggestions appear here after local analysis runs."
    lines = [
        "Advanced analysis disclosure — provider internals stay out of the default view.",
        f"Suggestion count: {len(suggestions)}",
    ]
    for item in suggestions[:12]:
        lines.append(
            f"{item.dimension} → {item.proposed_value} · "
            f"{item.confidence:.0%} · {str(item.status).replace('_', ' ').title()}"
        )
    return "\n".join(lines)


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


class _SummaryCard(QFrame):
    def __init__(
        self,
        title: str,
        object_name: str,
        accent: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        # Explicit child colors are required: a per-frame stylesheet breaks
        # palette inheritance and otherwise yields black text on dark surfaces.
        self.setStyleSheet(
            f"QFrame#{object_name} {{"
            f"background-color: {SURFACE_1}; color: {TEXT}; border: 1px solid {accent};"
            f"border-left: 3px solid {accent}; border-radius: 6px; }}"
            f"QFrame#{object_name} QLabel {{ color: {TEXT}; background: transparent; }}"
            f"QFrame#{object_name} QLabel#{object_name}Heading {{"
            f"color: {accent}; font-size: 11px; font-weight: 700; }}"
            f"QFrame#{object_name} QLabel#{object_name}Body {{"
            f"color: {TEXT}; font-size: 12px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName(f"{object_name}Heading")
        heading.setStyleSheet(f"color: {accent}; font-size: 11px; font-weight: 700;")
        layout.addWidget(heading)
        self._body = QLabel("")
        self._body.setObjectName(f"{object_name}Body")
        self._body.setWordWrap(True)
        self._body.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        layout.addWidget(self._body)

    def set_text(self, text: str) -> None:
        self._body.setText(text)


class _Disclosure(QFrame):
    def __init__(self, title: str, object_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setStyleSheet(
            f"QFrame#{object_name} {{"
            f"background-color: {SURFACE_2}; color: {TEXT};"
            f"border: 1px solid #30363D; border-radius: 6px; }}"
            f"QFrame#{object_name} QToolButton {{"
            f"color: {TEXT}; background: transparent; border: none;"
            f"font-size: 12px; font-weight: 700; text-align: left; padding: 2px 0; }}"
            f"QFrame#{object_name} QLabel {{ color: {MUTED}; background: transparent; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        self._toggle = QToolButton()
        self._toggle.setObjectName(f"{object_name}Toggle")
        self._toggle.setText(f"▸ {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._toggle.setStyleSheet(
            f"color: {TEXT}; background: transparent; border: none;"
            f"font-size: 12px; font-weight: 700; text-align: left;"
        )
        self._toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self._toggle)
        self._body = QLabel("")
        self._body.setObjectName(f"{object_name}Body")
        self._body.setWordWrap(True)
        self._body.setVisible(False)
        self._body.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        layout.addWidget(self._body)
        self._title = title

    def set_text(self, text: str) -> None:
        self._body.setText(text)

    def _on_toggled(self, checked: bool) -> None:
        self._body.setVisible(checked)
        prefix = "▾" if checked else "▸"
        self._toggle.setText(f"{prefix} {self._title}")


class SampleDetailScreen(QWidget):
    """Expanded Sample Detail (S07) with Edit Sound as the primary action."""

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
        root.addLayout(top)

        self._title = QLabel("Sample")
        self._title.setObjectName("pageTitle")
        root.addWidget(self._title)

        self._identity = QLabel("")
        self._identity.setObjectName("sampleDetailIdentity")
        self._identity.setWordWrap(True)
        self._identity.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        root.addWidget(self._identity)

        self._waveform = WaveformView()
        self._waveform.setObjectName("sampleDetailWaveform")
        self._waveform.setMinimumHeight(200)
        self._waveform.setMaximumHeight(260)
        root.addWidget(self._waveform)

        self._waveform_state = QLabel("Waveform: —")
        self._waveform_state.setObjectName("sampleDetailWaveformState")
        self._waveform_state.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._waveform_state)

        actions = QHBoxLayout()
        self._edit_sound_btn = QPushButton("Edit Sound")
        self._edit_sound_btn.setObjectName("editSoundButton")
        self._edit_sound_btn.setProperty("primary", True)
        self._edit_sound_btn.setStyleSheet(
            f"background-color: {CLAY}; color: #0B0D0F; border: none; font-weight: 700;"
        )
        self._edit_sound_btn.clicked.connect(self._emit_prepare)
        actions.addWidget(self._edit_sound_btn)

        self._edit_btn = QPushButton("Edit Info")
        self._edit_btn.setObjectName("editMetadataButton")
        self._edit_btn.clicked.connect(self._emit_edit_metadata)
        actions.addWidget(self._edit_btn)

        self._similar_btn = QPushButton("Find Similar")
        self._similar_btn.setObjectName("findSimilarButton")
        self._similar_btn.setStyleSheet(f"border-color: {BLUE};")
        self._similar_btn.clicked.connect(self._emit_find_similar)
        actions.addWidget(self._similar_btn)

        self._collection_btn = QPushButton("Add to Collection")
        self._collection_btn.setObjectName("addToCollectionButton")
        self._collection_btn.setStyleSheet(f"border-color: {GREEN};")
        self._collection_btn.clicked.connect(self._add_to_collection)
        actions.addWidget(self._collection_btn)

        self._more_btn = QToolButton()
        self._more_btn.setObjectName("sampleDetailMoreButton")
        self._more_btn.setText("More")
        self._more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(self._more_btn)
        self._more_btn.setMenu(more_menu)
        organize_action = more_menu.addAction("Organize…")
        organize_action.setObjectName("organizeSampleAction")
        organize_action.triggered.connect(self._emit_organize)
        reveal_action = more_menu.addAction("Reveal in Files")
        reveal_action.setObjectName("revealSampleAction")
        reveal_action.triggered.connect(self._emit_reveal)
        self._organize_action = organize_action
        self._reveal_action = reveal_action
        # Hidden compatibility buttons for older tests / automation.
        self._organize_btn = QPushButton("Organize")
        self._organize_btn.setObjectName("organizeSampleButton")
        self._organize_btn.setVisible(False)
        self._organize_btn.clicked.connect(self._emit_organize)
        self._reveal_btn = QPushButton("Reveal in Files")
        self._reveal_btn.setObjectName("revealSampleButton")
        self._reveal_btn.setVisible(False)
        self._reveal_btn.clicked.connect(self._emit_reveal)
        actions.addWidget(self._more_btn)
        actions.addWidget(self._organize_btn)
        actions.addWidget(self._reveal_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        scroll = QScrollArea()
        scroll.setObjectName("sampleDetailScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("sampleDetailBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        self._classification = _SummaryCard(
            "Classification",
            "sampleDetailClassification",
            CLAY,
        )
        self._suggestions = _SummaryCard(
            "Suggestions",
            "sampleDetailSuggestions",
            YELLOW,
        )
        self._tags = _SummaryCard(
            "Tags & Collections",
            "sampleDetailTagsCollections",
            GREEN,
        )
        self._edit_summary = _SummaryCard(
            "Edit summary",
            "sampleDetailEditSummary",
            CLAY,
        )
        for card in (
            self._classification,
            self._suggestions,
            self._tags,
            self._edit_summary,
        ):
            body_layout.addWidget(card)

        self._file_details = _Disclosure("File Details", "sampleDetailFileDetails")
        self._analysis_details = _Disclosure("Analysis Details", "sampleDetailAnalysisDetails")
        body_layout.addWidget(self._file_details)
        body_layout.addWidget(self._analysis_details)

        # Compatibility provenance object names remain available for advanced disclosure bodies.
        self._path = QLabel("")
        self._path.setObjectName("sampleDetailPath")
        self._path.setVisible(False)
        self._collections = QLabel("")
        self._collections.setObjectName("sampleDetailCollections")
        self._collections.setVisible(False)
        self._history = QLabel("")
        self._history.setObjectName("sampleDetailHistory")
        self._history.setVisible(False)
        self._recipe = QLabel("")
        self._recipe.setObjectName("sampleDetailRecipe")
        self._recipe.setVisible(False)
        body_layout.addWidget(self._path)
        body_layout.addWidget(self._collections)
        body_layout.addWidget(self._history)
        body_layout.addWidget(self._recipe)

        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

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
            _format_identity(
                sample.filename,
                sample.extension,
                sample.availability,
                sample.favorite,
            )
        )
        self._classification.set_text(_format_classification_summary(detail.classifications))
        self._suggestions.set_text(_format_suggestion_summary(detail.suggestions))
        self._tags.set_text(_format_tags_and_collections(detail.tags, detail.collection_names))

        recipe = PreparationRecipe.default()
        if detail.has_preparation_recipe:
            try:
                recipe = self._context.preparation_service.get_recipe(self._sample_id)
            except ApplicationError:
                recipe = PreparationRecipe.default()
        summary = recipe.concise_edit_summary()
        if summary is None:
            self._edit_summary.set_text(
                "No saved sound edits. Edit Sound to trim, fade, or reshape."
            )
        else:
            self._edit_summary.set_text(summary)
        self._recipe.setText(summary or "none")

        self._file_details.set_text(
            _format_file_details(
                detail.media_path,
                detail.path_available,
                detail.technical,
                detail.embedded,
                sample.first_seen_at,
                sample.last_seen_at,
                sample.last_previewed_at,
            )
        )
        self._analysis_details.set_text(_format_analysis_details(detail.suggestions))
        self._path.setText(detail.media_path or "—")
        names = ", ".join(detail.collection_names) if detail.collection_names else "No Collections."
        self._collections.setText(names)
        self._history.setText(
            f"Discovered: {sample.first_seen_at}\nLast seen: {sample.last_seen_at}"
        )

        enabled = detail.path_available and detail.media_path is not None
        self._reveal_btn.setEnabled(enabled)
        self._reveal_action.setEnabled(enabled)
        self._organize_btn.setEnabled(detail.path_available)
        self._organize_action.setEnabled(detail.path_available)
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
            f"Waveform: {resolved.duration_ms / 1000:.3f}s · "
            f"{resolved.sample_rate_hz} Hz · {resolved.channels} ch"
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
