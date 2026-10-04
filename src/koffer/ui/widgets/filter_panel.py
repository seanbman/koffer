"""S02 Search & Filters foundations: structured SampleFilters editing."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from koffer.domain.enums import SampleAvailability
from koffer.domain.query import NumericRange, SampleFilters


class FilterPanel(QWidget):
    """Foundational filter groups wired to SampleFilters (docs/12 S02)."""

    filters_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filterPanel")
        self._filters = SampleFilters()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("FILTERS")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        self._active_label = QLabel("Active: none")
        self._active_label.setObjectName("bodyText")
        self._active_label.setWordWrap(True)
        layout.addWidget(self._active_label)

        ext_row = QHBoxLayout()
        ext_row.addWidget(QLabel("Format"))
        self._extension_field = QLineEdit()
        self._extension_field.setObjectName("filterExtensionField")
        self._extension_field.setPlaceholderText("wav, flac, …")
        self._extension_field.editingFinished.connect(self._emit_filters)
        ext_row.addWidget(self._extension_field, stretch=1)
        layout.addLayout(ext_row)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Sample Type"))
        self._sample_type_field = QLineEdit()
        self._sample_type_field.setObjectName("filterSampleTypeField")
        self._sample_type_field.setPlaceholderText("One-shot, Loop, …")
        self._sample_type_field.editingFinished.connect(self._emit_filters)
        type_row.addWidget(self._sample_type_field, stretch=1)
        layout.addLayout(type_row)

        bpm_row = QHBoxLayout()
        bpm_row.addWidget(QLabel("BPM min"))
        self._bpm_min = QLineEdit()
        self._bpm_min.setObjectName("filterBpmMinField")
        self._bpm_min.setPlaceholderText("min")
        self._bpm_min.editingFinished.connect(self._emit_filters)
        bpm_row.addWidget(self._bpm_min)
        bpm_row.addWidget(QLabel("max"))
        self._bpm_max = QLineEdit()
        self._bpm_max.setObjectName("filterBpmMaxField")
        self._bpm_max.setPlaceholderText("max")
        self._bpm_max.editingFinished.connect(self._emit_filters)
        bpm_row.addWidget(self._bpm_max)
        layout.addLayout(bpm_row)

        avail_row = QHBoxLayout()
        avail_row.addWidget(QLabel("Availability"))
        self._availability = QComboBox()
        self._availability.setObjectName("filterAvailabilityCombo")
        self._availability.addItem("Any", None)
        self._availability.addItem("Online", SampleAvailability.ONLINE)
        self._availability.addItem("Source offline", SampleAvailability.SOURCE_OFFLINE)
        self._availability.addItem("Missing", SampleAvailability.MISSING)
        self._availability.currentIndexChanged.connect(self._emit_filters)
        avail_row.addWidget(self._availability, stretch=1)
        layout.addLayout(avail_row)

        self._favorite = QCheckBox("Favourites only")
        self._favorite.setObjectName("filterFavoriteCheck")
        self._favorite.stateChanged.connect(self._emit_filters)
        layout.addWidget(self._favorite)

        clear = QPushButton("Clear filters")
        clear.setObjectName("secondaryButton")
        clear.clicked.connect(self.clear_filters)
        layout.addWidget(clear)

        self._sync_active_label()

    @property
    def filters(self) -> SampleFilters:
        return self._filters

    @property
    def active_summary(self) -> str:
        return self._active_label.text()

    def set_filters(self, filters: SampleFilters) -> None:
        """Programmatically load filter controls without emitting."""
        self._filters = filters
        self._extension_field.setText(", ".join(filters.extensions))
        self._sample_type_field.setText(", ".join(filters.sample_type))
        self._bpm_min.setText("" if filters.bpm.min is None else str(filters.bpm.min))
        self._bpm_max.setText("" if filters.bpm.max is None else str(filters.bpm.max))
        self._favorite.setChecked(bool(filters.favorite))
        target = filters.availability[0] if len(filters.availability) == 1 else None
        index = 0
        for i in range(self._availability.count()):
            if self._availability.itemData(i) == target:
                index = i
                break
        self._availability.blockSignals(True)
        self._availability.setCurrentIndex(index)
        self._availability.blockSignals(False)
        self._sync_active_label()

    def apply_filters(self, filters: SampleFilters) -> None:
        """Load controls and emit ``filters_changed`` (browser query binding)."""
        self.set_filters(filters)
        self.filters_changed.emit(self._filters)

    def clear_filters(self) -> None:
        self.set_filters(SampleFilters())
        self.filters_changed.emit(self._filters)

    def _emit_filters(self) -> None:
        self._filters = self._read_filters()
        self._sync_active_label()
        self.filters_changed.emit(self._filters)

    def _read_filters(self) -> SampleFilters:
        extensions = _split_csv(self._extension_field.text())
        sample_types = _split_csv(self._sample_type_field.text())
        bpm = NumericRange(
            min=_parse_optional_float(self._bpm_min.text()),
            max=_parse_optional_float(self._bpm_max.text()),
        )
        availability_value = self._availability.currentData()
        availability: tuple[SampleAvailability, ...] = ()
        if isinstance(availability_value, SampleAvailability):
            availability = (availability_value,)
        favorite = True if self._favorite.isChecked() else None
        return SampleFilters(
            sample_type=sample_types,
            extensions=extensions,
            bpm=bpm,
            availability=availability,
            favorite=favorite,
        )

    def _sync_active_label(self) -> None:
        chips: list[str] = []
        if self._filters.extensions:
            chips.append("format=" + ",".join(self._filters.extensions))
        if self._filters.sample_type:
            chips.append("type=" + ",".join(self._filters.sample_type))
        if not self._filters.bpm.is_empty():
            chips.append(
                f"bpm={self._filters.bpm.min if self._filters.bpm.min is not None else ''}.."
                f"{self._filters.bpm.max if self._filters.bpm.max is not None else ''}"
            )
        if self._filters.availability:
            chips.append("availability=" + ",".join(str(a) for a in self._filters.availability))
        if self._filters.favorite:
            chips.append("favourites")
        self._active_label.setText("Active: " + (", ".join(chips) if chips else "none"))


def _split_csv(raw: str) -> tuple[str, ...]:
    parts = [part.strip() for part in raw.split(",")]
    return tuple(part for part in parts if part)


def _parse_optional_float(raw: str) -> float | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
