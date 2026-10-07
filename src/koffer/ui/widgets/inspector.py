"""Right-side Inspector: selected Sample facts + waveform summary (S01/S07 portion)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from koffer.audio.waveform import PeakEnvelope
from koffer.domain.query import SampleRow
from koffer.ui.widgets.waveform_view import WaveformView


class InspectorPanel(QWidget):
    """Shows facts for the current table selection; never steals selection focus."""

    collapse_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("inspectorPanel")
        self.setFixedWidth(336)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._collapsed = False
        self._sample_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        section = QLabel("INSPECTOR")
        section.setObjectName("sectionLabel")
        header.addWidget(section)
        header.addStretch(1)
        self._collapse_btn = QPushButton("Collapse")
        self._collapse_btn.setObjectName("secondaryButton")
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        header.addWidget(self._collapse_btn)
        layout.addLayout(header)

        self._body = QWidget()
        self._body.setObjectName("inspectorBody")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        self._title = QLabel("No selection")
        self._title.setObjectName("inspectorTitle")
        self._title.setWordWrap(True)
        body_layout.addWidget(self._title)

        self._waveform = WaveformView()
        body_layout.addWidget(self._waveform)

        self._waveform_summary = QLabel("Waveform: —")
        self._waveform_summary.setObjectName("waveformSummary")
        self._waveform_summary.setWordWrap(True)
        body_layout.addWidget(self._waveform_summary)

        self._facts = QLabel("Select a Sample to inspect.")
        self._facts.setObjectName("inspectorFacts")
        self._facts.setWordWrap(True)
        body_layout.addWidget(self._facts)
        body_layout.addStretch(1)

        layout.addWidget(self._body, stretch=1)

    @property
    def sample_id(self) -> str | None:
        return self._sample_id

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def waveform_summary_text(self) -> str:
        return self._waveform_summary.text()

    def clear(self) -> None:
        self._sample_id = None
        self._title.setText("No selection")
        self._facts.setText("Select a Sample to inspect.")
        self._waveform.set_envelope(None)
        self._waveform_summary.setText("Waveform: —")

    def show_sample(
        self,
        row: SampleRow,
        *,
        envelope: PeakEnvelope | None = None,
        media_path: str | None = None,
    ) -> None:
        """Update facts/waveform for ``row`` without changing table selection."""
        self._sample_id = str(row.id)
        self._title.setText(row.name)
        path_line = media_path or "—"
        duration = "—" if row.duration_ms is None else f"{row.duration_ms / 1000.0:.2f}s"
        bpm = "—" if row.bpm is None else f"{row.bpm:g}"
        key = row.key or "—"
        sample_type = row.sample_type or "—"
        instrument = row.instrument_source or "—"
        self._facts.setText(
            "\n".join(
                [
                    f"Type: {sample_type}",
                    f"Instrument: {instrument}",
                    f"BPM: {bpm}",
                    f"Key: {key}",
                    f"Duration: {duration}",
                    f"Format: {row.extension}",
                    f"Availability: {row.availability}",
                    f"Path: {path_line}",
                ]
            )
        )
        self.set_waveform(envelope)

    def set_waveform(
        self,
        envelope: PeakEnvelope | None,
        *,
        loading: bool = False,
    ) -> None:
        """Update only waveform state without disturbing selected Sample facts."""
        self._waveform.set_envelope(envelope)
        if loading:
            self._waveform_summary.setText("Waveform: loading…")
            return
        if envelope is None:
            self._waveform_summary.setText("Waveform: unavailable")
            return
        peak = max(abs(v) for v in (*envelope.mins, *envelope.maxs)) if envelope.mins else 0.0
        self._waveform_summary.setText(
            f"Waveform: {envelope.bucket_count} buckets · "
            f"{envelope.sample_rate_hz} Hz · "
            f"{envelope.channels} ch · "
            f"peak {peak:.2f} · "
            f"{envelope.duration_ms} ms"
        )

    def toggle_collapsed(self) -> None:
        """Toggle between the full and compact Inspector states."""
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        """Apply a deterministic Inspector collapsed state."""
        self._collapsed = bool(collapsed)
        self._body.setVisible(not self._collapsed)
        self._collapse_btn.setText("Expand" if self._collapsed else "Collapse")
        self.setFixedWidth(120 if self._collapsed else 336)
        self.collapse_toggled.emit(self._collapsed)

    def _toggle_collapse(self) -> None:
        self.toggle_collapsed()
