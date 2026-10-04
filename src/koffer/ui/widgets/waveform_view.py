"""Compact peak-envelope painter for Inspector waveform summary."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from koffer.audio.waveform import PeakEnvelope
from koffer.ui.tokens import BORDER, CANVAS, CLAY


class WaveformView(QWidget):
    """Draws a min/max peak envelope; empty when no envelope is set."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("waveformView")
        self.setMinimumHeight(96)
        self.setMaximumHeight(120)
        self._envelope: PeakEnvelope | None = None

    def set_envelope(self, envelope: PeakEnvelope | None) -> None:
        self._envelope = envelope
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(CANVAS))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        envelope = self._envelope
        if envelope is None or envelope.bucket_count < 1:
            painter.end()
            return

        width = max(1, self.width() - 2)
        height = max(1, self.height() - 2)
        mid_y = 1 + height / 2.0
        amp = (height / 2.0) - 4.0
        path = QPainterPath()
        for index, (lo, hi) in enumerate(zip(envelope.mins, envelope.maxs, strict=True)):
            x = 1.0 + (index / max(1, envelope.bucket_count - 1)) * width
            y_hi = mid_y - max(-1.0, min(1.0, hi)) * amp
            y_lo = mid_y - max(-1.0, min(1.0, lo)) * amp
            if index == 0:
                path.moveTo(QPointF(x, y_hi))
            else:
                path.lineTo(QPointF(x, y_hi))
            # Vertical tick for peak range keeps one-shot envelopes visible.
            painter.setPen(QPen(QColor(CLAY), 1))
            painter.drawLine(QPointF(x, y_lo), QPointF(x, y_hi))

        painter.setPen(QPen(QColor(CLAY), 1.5))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#252B30"), 1))
        painter.drawLine(
            QPointF(1, mid_y),
            QPointF(1 + width, mid_y),
        )
        painter.end()
