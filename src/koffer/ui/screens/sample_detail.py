"""S07 Sample Detail foundations: provenance-grouped expanded Inspector."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from koffer.audio.metadata import EmbeddedMetadataSnapshot
from koffer.domain.ids import EntityId
from koffer.domain.models import Classification, Suggestion, TechnicalMetadata
from koffer.services.samples import ProvenanceCategory, SampleService


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
    """Expanded Sample Detail (S07) with distinct provenance categories."""

    back_requested = Signal()
    edit_metadata_requested = Signal(str)
    prepare_requested = Signal(str)

    def __init__(
        self,
        sample_service: SampleService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sample_service = sample_service
        self._sample_id: EntityId | None = None
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

        self._path = QLabel("")
        self._path.setObjectName("sampleDetailPath")
        self._path.setWordWrap(True)
        root.addWidget(self._path)

        self._recipe = QLabel("")
        self._recipe.setObjectName("sampleDetailRecipe")
        root.addWidget(self._recipe)

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
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        actions_note = QLabel("Edit Metadata and Prepare are separate actions.")
        actions_note.setObjectName("bodyText")
        root.addWidget(actions_note)

    def show_sample(self, sample_id: EntityId) -> None:
        self._sample_id = sample_id
        self.refresh()

    def refresh(self) -> None:
        if self._sample_id is None:
            return
        detail = self._sample_service.get_detail(self._sample_id)
        sample = detail.sample
        self._title.setText(sample.filename)
        availability = sample.availability
        self._identity.setText(
            f"Availability: {availability} · Format: {sample.extension} · "
            f"Favorite: {'yes' if sample.favorite else 'no'}"
        )
        path_state = "online" if detail.path_available else "unavailable"
        self._path.setText(f"Path ({path_state}): {detail.media_path or '—'}")
        recipe = "present" if detail.has_preparation_recipe else "none"
        self._recipe.setText(f"Preparation recipe: {recipe}")

        # Distinct provenance categories — never collapse into one bag of tags.
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

    def _emit_edit_metadata(self) -> None:
        if self._sample_id is not None:
            self.edit_metadata_requested.emit(str(self._sample_id))

    def _emit_prepare(self) -> None:
        if self._sample_id is not None:
            self.prepare_requested.emit(str(self._sample_id))
