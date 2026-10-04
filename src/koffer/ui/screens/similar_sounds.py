"""S11 Similar Sounds foundations (docs/12, docs/15)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.errors import ModelUnavailableError
from koffer.domain.ids import EntityId
from koffer.domain.query import SampleFilters, SampleQuery
from koffer.services.similarity import (
    SimilarityResult,
    SimilarityService,
    SimilarityStatusKind,
)
from koffer.ui.tokens import CLAY, MUTED, RED, YELLOW


class SimilarSoundsScreen(QWidget):
    """S11: seed pinned, similarity-ranked results, model-absent messaging."""

    back_requested = Signal()
    preview_requested = Signal(str)

    def __init__(
        self,
        similarity_service: SimilarityService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = similarity_service
        self._seed_id: EntityId | None = None
        self._seed_name: str = ""
        self._results: list[SimilarityResult] = []
        self.setObjectName("similarSoundsScreen")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Similar Sounds")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        back = QPushButton("Back")
        back.setObjectName("similarSoundsBackButton")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        root.addLayout(header)

        self._seed = QLabel("Seed: —")
        self._seed.setObjectName("similarSoundsSeed")
        self._seed.setStyleSheet(f"color: {CLAY}; font-weight: 600;")
        root.addWidget(self._seed)

        self._status = QLabel("")
        self._status.setObjectName("similarSoundsStatus")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"color: {MUTED};")
        root.addWidget(self._status)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Extension filter"))
        self._extension = QLineEdit()
        self._extension.setObjectName("similarSoundsExtensionFilter")
        self._extension.setPlaceholderText("e.g. wav")
        self._extension.setMaximumWidth(120)
        filters.addWidget(self._extension)
        apply_btn = QPushButton("Apply metadata filters")
        apply_btn.setObjectName("similarSoundsApplyFilters")
        apply_btn.clicked.connect(self.refresh)
        filters.addWidget(apply_btn)
        filters.addStretch(1)
        note = QLabel("Filters narrow results; they do not replace similarity ranking.")
        note.setObjectName("similarSoundsFilterNote")
        note.setStyleSheet(f"color: {MUTED};")
        filters.addWidget(note)
        root.addLayout(filters)

        self._list = QListWidget()
        self._list.setObjectName("similarSoundsList")
        self._list.itemSelectionChanged.connect(self._on_selection)
        root.addWidget(self._list, stretch=1)

        actions = QHBoxLayout()
        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setObjectName("similarSoundsPreviewButton")
        self._preview_btn.clicked.connect(self._emit_preview)
        actions.addWidget(self._preview_btn)
        actions.addStretch(1)
        root.addLayout(actions)

    def show_seed(self, sample_id: EntityId, *, filename: str = "") -> None:
        self._seed_id = sample_id
        self._seed_name = filename or str(sample_id)
        self.refresh()

    def refresh(self) -> None:
        status = self._service.status()
        if self._seed_id is None:
            self._seed.setText("Seed: —")
            self._status.setText("Select Find Similar from a Sample.")
            self._list.clear()
            return

        self._seed.setText(f"Seed (pinned): {self._seed_name}")
        if status.kind is SimilarityStatusKind.MODEL_UNAVAILABLE:
            self._status.setText(
                "Semantic embeddings are unavailable. "
                "Library browse/search/collections remain usable. "
                f"{status.detail} Model setup is available in Settings."
            )
            self._status.setStyleSheet(f"color: {YELLOW};")
            self._list.clear()
            unavailable = QListWidgetItem("Model unavailable — no similarity results")
            unavailable.setData(256, None)
            self._list.addItem(unavailable)
            self._results = []
            return

        query = self._build_query()
        try:
            results = self._service.find_similar(self._seed_id, limit=50, filters=query)
        except ModelUnavailableError as exc:
            self._status.setText(str(exc))
            self._status.setStyleSheet(f"color: {RED};")
            self._list.clear()
            self._results = []
            return

        self._results = results
        backend = status.backend
        self._status.setText(
            f"Ranked by audio similarity · provider={status.provider} "
            f"· model={status.model_version} · index={status.index_size} ({backend})"
        )
        self._status.setStyleSheet(f"color: {MUTED};")
        self._list.clear()
        # Seed remains visible at the top (acceptance: seed Sample always visible).
        seed_item = QListWidgetItem(f"SEED  {self._seed_name}  (pinned)")
        seed_item.setData(256, str(self._seed_id))
        self._list.addItem(seed_item)
        for row in results:
            offline = row.availability.value != "online"
            marker = " [offline]" if offline else ""
            text = f"{row.score:0.3f}  {row.filename}{marker}"
            item = QListWidgetItem(text)
            item.setData(256, str(row.sample_id))
            self._list.addItem(item)

    def _build_query(self) -> SampleQuery | None:
        ext = self._extension.text().strip().lower().lstrip(".")
        if not ext:
            return None
        return SampleQuery(filters=SampleFilters(extensions=(ext,)))

    def _on_selection(self) -> None:
        return

    def _emit_preview(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        sample_id = item.data(256)
        if sample_id:
            self.preview_requested.emit(str(sample_id))
