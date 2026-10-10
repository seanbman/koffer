"""Direct-manipulation waveform for S08 Edit Sound (docs/31)."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from koffer.audio.waveform import PeakEnvelope
from koffer.ui.models.workbench import WorkbenchController
from koffer.ui.tokens import BORDER, CANVAS, CLAY, CLAY_BRIGHT, FAINT, GREEN, MUTED, VIOLET

_HANDLE_HIT_PX = 10


class _DragKind(StrEnum):
    NONE = "none"
    SEEK = "seek"
    TRIM_START = "trim_start"
    TRIM_END = "trim_end"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"
    PAN = "pan"


class WorkbenchWaveformView(QWidget):
    """Interactive peak envelope with trim/fade/loop handles and seek/zoom."""

    interaction_finished = Signal()

    def __init__(
        self,
        controller: WorkbenchController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("workbenchWaveformView")
        self.setMinimumHeight(220)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._controller = controller
        self._envelope: PeakEnvelope | None = None
        self._drag = _DragKind.NONE
        self._drag_origin_x = 0.0
        self._controller.changed.connect(self.update)
        self.setAccessibleName("Sample waveform editor")

    def set_envelope(self, envelope: PeakEnvelope | None) -> None:
        self._envelope = envelope
        if envelope is not None:
            self._controller.set_duration_ms(envelope.duration_ms)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(CANVAS))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        view = self._controller.viewport.clamped()
        duration = view.duration_ms
        if duration <= 0:
            painter.setPen(QColor(MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Waveform unavailable")
            painter.end()
            return

        width = max(1, self.width() - 2)
        height = max(1, self.height() - 2)
        mid_y = 1 + height / 2.0
        amp = (height / 2.0) - 8.0
        visible_start = view.visible_start_ms
        span = view.span_ms()

        selection = self._controller.selection
        trim_start = selection.trim_start_ms
        trim_end = selection.retained_end(duration)
        left_x = self._ms_to_x(trim_start)
        right_x = self._ms_to_x(trim_end)

        # Dim excluded regions.
        painter.fillRect(1, 1, max(0, int(left_x) - 1), height, QColor(20, 22, 26, 180))
        if right_x < width + 1:
            painter.fillRect(
                int(right_x),
                1,
                max(0, width - int(right_x) + 1),
                height,
                QColor(20, 22, 26, 180),
            )
        # Retained region tint.
        retained_w = max(1, int(right_x - left_x))
        painter.fillRect(int(left_x), 1, retained_w, height, QColor(VIOLET + "33"))

        envelope = self._envelope
        if envelope is not None and envelope.bucket_count > 0:
            path = QPainterPath()
            for index, (lo, hi) in enumerate(zip(envelope.mins, envelope.maxs, strict=True)):
                t = index / max(1, envelope.bucket_count - 1)
                ms = int(t * duration)
                if ms < visible_start or ms > visible_start + span:
                    continue
                x = self._ms_to_x(ms)
                y_hi = mid_y - max(-1.0, min(1.0, hi)) * amp
                y_lo = mid_y - max(-1.0, min(1.0, lo)) * amp
                vivid = trim_start <= ms <= trim_end
                color = QColor(CLAY_BRIGHT if vivid else FAINT)
                painter.setPen(QPen(color, 1))
                painter.drawLine(QPointF(x, y_lo), QPointF(x, y_hi))
                if path.elementCount() == 0:
                    path.moveTo(QPointF(x, y_hi))
                else:
                    path.lineTo(QPointF(x, y_hi))
            painter.setPen(QPen(QColor(CLAY), 1.5))
            painter.drawPath(path)

        # Fade overlays.
        env = self._controller.envelope
        if env.fade_in_ms > 0:
            fade_end = min(trim_end, trim_start + env.fade_in_ms)
            self._draw_fade(painter, trim_start, fade_end, mid_y, amp, inbound=True)
        if env.fade_out_ms > 0:
            fade_start = max(trim_start, trim_end - env.fade_out_ms)
            self._draw_fade(painter, fade_start, trim_end, mid_y, amp, inbound=False)

        # Preview Loop region.
        if selection.loop_enabled:
            loop_end = selection.loop_end_ms if selection.loop_end_ms is not None else duration
            lx0 = self._ms_to_x(selection.loop_start_ms)
            lx1 = self._ms_to_x(loop_end)
            painter.setPen(QPen(QColor(GREEN), 1, Qt.PenStyle.DashLine))
            painter.drawRect(int(lx0), 4, max(2, int(lx1 - lx0)), height - 8)
            self._draw_handle(painter, lx0, QColor(GREEN), "L")
            self._draw_handle(painter, lx1, QColor(GREEN), "L")

        # Trim handles.
        self._draw_handle(painter, left_x, QColor(VIOLET), "T")
        self._draw_handle(painter, right_x, QColor(VIOLET), "T")

        # Fade handles (always visible so durations can be dragged from zero).
        self._draw_handle(
            painter,
            self._ms_to_x(trim_start + env.fade_in_ms),
            QColor(CLAY_BRIGHT),
            "F",
        )
        self._draw_handle(
            painter,
            self._ms_to_x(max(trim_start, trim_end - env.fade_out_ms)),
            QColor(CLAY_BRIGHT),
            "F",
        )

        # Playhead.
        play_x = self._ms_to_x(selection.playhead_ms)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
        painter.drawLine(QPointF(play_x, 1), QPointF(play_x, 1 + height))

        # Time ruler.
        painter.setPen(QColor(MUTED))
        painter.drawText(8, 16, self._fmt(visible_start))
        painter.drawText(self.width() - 72, 16, self._fmt(visible_start + span))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x = event.position().x()
        kind = self._hit_test(x)
        self._drag = kind
        self._drag_origin_x = x
        if kind in {
            _DragKind.TRIM_START,
            _DragKind.TRIM_END,
            _DragKind.FADE_IN,
            _DragKind.FADE_OUT,
            _DragKind.LOOP_START,
            _DragKind.LOOP_END,
        }:
            self._controller.begin_gesture()
        if kind is _DragKind.SEEK:
            self._controller.set_playhead_ms(self._x_to_ms(x))
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        x = event.position().x()
        if self._drag is _DragKind.NONE:
            self.setCursor(self._cursor_for(self._hit_test(x)))
            return
        ms = self._x_to_ms(x)
        sel = self._controller.selection
        recipe = self._controller.recipe
        duration = self._controller.duration_ms
        if self._drag is _DragKind.SEEK:
            self._controller.set_playhead_ms(ms)
        elif self._drag is _DragKind.TRIM_START:
            end = sel.retained_end(duration)
            self._controller.set_trim(min(ms, end), recipe.trim.end_ms, record_history=False)
        elif self._drag is _DragKind.TRIM_END:
            start = recipe.trim.start_ms
            end_ms = None if ms >= duration else max(start, ms)
            self._controller.set_trim(start, end_ms, record_history=False)
        elif self._drag is _DragKind.FADE_IN:
            fade = max(0, ms - recipe.trim.start_ms)
            self._controller.set_fades(fade, recipe.fade_out_ms, record_history=False)
        elif self._drag is _DragKind.FADE_OUT:
            end = sel.retained_end(duration)
            fade = max(0, end - ms)
            self._controller.set_fades(recipe.fade_in_ms, fade, record_history=False)
        elif self._drag is _DragKind.LOOP_START:
            end = sel.loop_end_ms if sel.loop_end_ms is not None else duration
            self._controller.set_preview_loop(
                True,
                min(ms, end - 1),
                end,
                record_history=False,
            )
        elif self._drag is _DragKind.LOOP_END:
            start = sel.loop_start_ms
            self._controller.set_preview_loop(
                True,
                start,
                max(start + 1, ms),
                record_history=False,
            )
        elif self._drag is _DragKind.PAN:
            delta_px = x - self._drag_origin_x
            view = self._controller.viewport.clamped()
            ms_per_px = view.span_ms() / max(1, self.width() - 2)
            self._controller.pan_by_ms(int(-delta_px * ms_per_px))
            # Reset origin so pan is incremental.
            self._drag_origin_x = x

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        del event
        self._drag = _DragKind.NONE
        self.interaction_finished.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.25 if delta > 0 else 0.8
        self._controller.zoom_by(factor, anchor_ms=self._x_to_ms(event.position().x()))
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        del event
        self._controller.reset_trim(record_history=True)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        step = 10 if mods & Qt.KeyboardModifier.ControlModifier else 50
        fine = 1 if mods & Qt.KeyboardModifier.AltModifier else step
        sel = self._controller.selection
        recipe = self._controller.recipe
        if key == Qt.Key.Key_Left and mods & Qt.KeyboardModifier.ShiftModifier:
            self._controller.set_trim(
                max(0, recipe.trim.start_ms - fine),
                recipe.trim.end_ms,
            )
        elif key == Qt.Key.Key_Right and mods & Qt.KeyboardModifier.ShiftModifier:
            self._controller.set_trim(
                recipe.trim.start_ms + fine,
                recipe.trim.end_ms,
            )
        elif key == Qt.Key.Key_Left:
            self._controller.set_playhead_ms(sel.playhead_ms - fine)
        elif key == Qt.Key.Key_Right:
            self._controller.set_playhead_ms(sel.playhead_ms + fine)
        elif key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            self._controller.zoom_by(1.25, anchor_ms=sel.playhead_ms)
        elif key == Qt.Key.Key_Minus:
            self._controller.zoom_by(0.8, anchor_ms=sel.playhead_ms)
        elif key == Qt.Key.Key_0:
            self._controller.zoom_fit()
        else:
            super().keyPressEvent(event)

    def _hit_test(self, x: float) -> _DragKind:
        sel = self._controller.selection
        recipe = self._controller.recipe
        duration = self._controller.duration_ms
        trim_end = sel.retained_end(duration)
        targets: list[tuple[_DragKind, float]] = [
            (_DragKind.TRIM_START, self._ms_to_x(recipe.trim.start_ms)),
            (_DragKind.TRIM_END, self._ms_to_x(trim_end)),
            (_DragKind.FADE_IN, self._ms_to_x(recipe.trim.start_ms + recipe.fade_in_ms)),
            (
                _DragKind.FADE_OUT,
                self._ms_to_x(max(recipe.trim.start_ms, trim_end - recipe.fade_out_ms)),
            ),
        ]
        if sel.loop_enabled:
            loop_end = sel.loop_end_ms if sel.loop_end_ms is not None else duration
            targets.extend(
                [
                    (_DragKind.LOOP_START, self._ms_to_x(sel.loop_start_ms)),
                    (_DragKind.LOOP_END, self._ms_to_x(loop_end)),
                ]
            )
        for kind, hx in targets:
            if abs(x - hx) <= _HANDLE_HIT_PX:
                return kind
        if self._controller.viewport.span_ms() < max(1, duration):
            # Allow pan when zoomed via middle-ish empty drag; default seek.
            return _DragKind.SEEK
        return _DragKind.SEEK

    def _cursor_for(self, kind: _DragKind) -> Qt.CursorShape:
        if kind in {
            _DragKind.TRIM_START,
            _DragKind.TRIM_END,
            _DragKind.FADE_IN,
            _DragKind.FADE_OUT,
            _DragKind.LOOP_START,
            _DragKind.LOOP_END,
        }:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.ArrowCursor

    def _ms_to_x(self, ms: int) -> float:
        view = self._controller.viewport.clamped()
        span = view.span_ms()
        width = max(1, self.width() - 2)
        rel = (ms - view.visible_start_ms) / span
        return 1.0 + max(0.0, min(1.0, rel)) * width

    def _x_to_ms(self, x: float) -> int:
        view = self._controller.viewport.clamped()
        span = view.span_ms()
        width = max(1, self.width() - 2)
        rel = (x - 1.0) / width
        return int(view.visible_start_ms + max(0.0, min(1.0, rel)) * span)

    def _draw_handle(self, painter: QPainter, x: float, color: QColor, label: str) -> None:
        painter.setPen(QPen(color, 2))
        painter.drawLine(QPointF(x, 1), QPointF(x, self.height() - 1))
        painter.setBrush(color)
        painter.drawRect(int(x) - 4, 8, 8, 18)
        painter.setPen(QColor(CANVAS))
        painter.drawText(int(x) - 3, 21, label)

    def _draw_fade(
        self,
        painter: QPainter,
        start_ms: int,
        end_ms: int,
        mid_y: float,
        amp: float,
        *,
        inbound: bool,
    ) -> None:
        if end_ms <= start_ms:
            return
        path = QPainterPath()
        x0 = self._ms_to_x(start_ms)
        x1 = self._ms_to_x(end_ms)
        if inbound:
            path.moveTo(QPointF(x0, mid_y))
            path.lineTo(QPointF(x1, mid_y - amp * 0.85))
            path.lineTo(QPointF(x1, mid_y + amp * 0.85))
            path.closeSubpath()
        else:
            path.moveTo(QPointF(x0, mid_y - amp * 0.85))
            path.lineTo(QPointF(x1, mid_y))
            path.lineTo(QPointF(x0, mid_y + amp * 0.85))
            path.closeSubpath()
        color = QColor(CLAY_BRIGHT)
        color.setAlpha(60)
        painter.fillPath(path, color)

    @staticmethod
    def _fmt(ms: int) -> str:
        value = max(0, int(ms))
        seconds, millis = divmod(value, 1000)
        minutes, secs = divmod(seconds, 60)
        return f"{minutes:02d}:{secs:02d}.{millis:03d}"
