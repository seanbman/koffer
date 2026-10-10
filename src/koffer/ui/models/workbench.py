"""Testable Sample Workbench edit model (docs/31).

UI gestures and numeric controls mutate this controller; paint code only reads state.
Preview Loop is session-only and never implies export looping.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Signal

from koffer.domain.preparation import (
    ChannelMode,
    NormalizeSpec,
    OutputFormat,
    PreparationRecipe,
    SourceOrInt,
    TrimSpec,
)

__all__ = [
    "EditSelection",
    "EnvelopeOverlay",
    "WaveformViewport",
    "WorkbenchController",
]


@dataclass(frozen=True, slots=True)
class WaveformViewport:
    """Visible time window over the source duration."""

    duration_ms: int = 0
    visible_start_ms: int = 0
    visible_end_ms: int = 0

    def span_ms(self) -> int:
        end = self.visible_end_ms if self.visible_end_ms > 0 else self.duration_ms
        return max(1, end - self.visible_start_ms)

    def clamped(self) -> WaveformViewport:
        duration = max(0, self.duration_ms)
        start = max(0, min(self.visible_start_ms, duration))
        end = self.visible_end_ms if self.visible_end_ms > 0 else duration
        end = max(start + 1 if duration > 0 else 0, min(end, duration if duration > 0 else end))
        if duration > 0 and end <= start:
            end = duration
            start = 0
        return WaveformViewport(duration_ms=duration, visible_start_ms=start, visible_end_ms=end)


@dataclass(frozen=True, slots=True)
class EditSelection:
    """Trim + Preview Loop region in milliseconds."""

    trim_start_ms: int = 0
    trim_end_ms: int | None = None
    loop_enabled: bool = False
    loop_start_ms: int = 0
    loop_end_ms: int | None = None
    playhead_ms: int = 0

    def retained_end(self, duration_ms: int) -> int:
        if self.trim_end_ms is None:
            return max(0, duration_ms)
        return max(self.trim_start_ms, min(self.trim_end_ms, duration_ms))


@dataclass(frozen=True, slots=True)
class EnvelopeOverlay:
    """Fade envelope durations drawn over the retained region."""

    fade_in_ms: int = 0
    fade_out_ms: int = 0


@dataclass(frozen=True, slots=True)
class _WorkbenchSnapshot:
    recipe: PreparationRecipe
    loop_enabled: bool
    loop_start_ms: int
    loop_end_ms: int | None


class WorkbenchController(QObject):
    """Session editor state with undo/redo for recipe + preview loop."""

    changed = Signal()
    dirty_changed = Signal(bool)
    seek_requested = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._recipe = PreparationRecipe.default()
        self._baseline = PreparationRecipe.default()
        self._duration_ms = 0
        self._viewport = WaveformViewport()
        self._loop_enabled = False
        self._loop_start_ms = 0
        self._loop_end_ms: int | None = None
        self._playhead_ms = 0
        self._undo: list[_WorkbenchSnapshot] = []
        self._redo: list[_WorkbenchSnapshot] = []
        self._dirty = False

    @property
    def recipe(self) -> PreparationRecipe:
        return self._recipe

    @property
    def baseline(self) -> PreparationRecipe:
        return self._baseline

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def viewport(self) -> WaveformViewport:
        return self._viewport

    @property
    def selection(self) -> EditSelection:
        return EditSelection(
            trim_start_ms=self._recipe.trim.start_ms,
            trim_end_ms=self._recipe.trim.end_ms,
            loop_enabled=self._loop_enabled,
            loop_start_ms=self._loop_start_ms,
            loop_end_ms=self._loop_end_ms,
            playhead_ms=self._playhead_ms,
        )

    @property
    def envelope(self) -> EnvelopeOverlay:
        return EnvelopeOverlay(
            fade_in_ms=self._recipe.fade_in_ms,
            fade_out_ms=self._recipe.fade_out_ms,
        )

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def load(self, recipe: PreparationRecipe, *, duration_ms: int = 0) -> None:
        """Replace session state from a persisted recipe (clears history)."""
        recipe.validate()
        self._recipe = recipe
        self._baseline = recipe
        self._duration_ms = max(0, duration_ms)
        self._viewport = WaveformViewport(
            duration_ms=self._duration_ms,
            visible_start_ms=0,
            visible_end_ms=self._duration_ms,
        ).clamped()
        self._loop_enabled = False
        self._loop_start_ms = recipe.trim.start_ms
        self._loop_end_ms = recipe.trim.end_ms
        self._playhead_ms = recipe.trim.start_ms
        self._undo.clear()
        self._redo.clear()
        self._set_dirty(False)
        self.changed.emit()

    def set_duration_ms(self, duration_ms: int) -> None:
        self._duration_ms = max(0, duration_ms)
        self._viewport = replace(self._viewport, duration_ms=self._duration_ms).clamped()
        self.changed.emit()

    def mark_saved(self, recipe: PreparationRecipe | None = None) -> None:
        saved = recipe if recipe is not None else self._recipe
        saved.validate()
        self._baseline = saved
        self._recipe = saved
        self._set_dirty(False)
        self.changed.emit()

    def begin_gesture(self) -> None:
        """Capture one undo frame before a continuous pointer drag."""
        self._push_undo()
        self._redo.clear()

    def apply_recipe(self, recipe: PreparationRecipe, *, record_history: bool = True) -> None:
        recipe.validate()
        if record_history:
            self._push_undo()
        self._recipe = recipe
        self._redo.clear()
        self._sync_dirty()
        self.changed.emit()

    def set_trim(self, start_ms: int, end_ms: int | None, *, record_history: bool = True) -> None:
        start = max(0, int(start_ms))
        end = None if end_ms is None else max(0, int(end_ms))
        if self._duration_ms > 0:
            start = min(start, self._duration_ms)
            if end is not None:
                end = min(end, self._duration_ms)
        if end is not None and end < start:
            end = start
        trim = TrimSpec(start_ms=start, end_ms=end)
        trim.validate()
        self.apply_recipe(replace(self._recipe, trim=trim), record_history=record_history)

    def set_fades(
        self,
        fade_in_ms: int,
        fade_out_ms: int,
        *,
        record_history: bool = True,
    ) -> None:
        fade_in = max(0, int(fade_in_ms))
        fade_out = max(0, int(fade_out_ms))
        self.apply_recipe(
            replace(self._recipe, fade_in_ms=fade_in, fade_out_ms=fade_out),
            record_history=record_history,
        )

    def set_gain_db(self, gain_db: float, *, record_history: bool = True) -> None:
        self.apply_recipe(
            replace(self._recipe, gain_db=float(gain_db)),
            record_history=record_history,
        )

    def set_normalize(
        self,
        enabled: bool,
        target_peak_dbfs: float = -1.0,
        *,
        record_history: bool = True,
    ) -> None:
        normalize = NormalizeSpec(
            enabled=bool(enabled),
            target_peak_dbfs=float(target_peak_dbfs),
        )
        self.apply_recipe(
            replace(self._recipe, normalize=normalize),
            record_history=record_history,
        )

    def set_pitch(
        self,
        transpose_semitones: float,
        fine_cents: int,
        *,
        record_history: bool = True,
    ) -> None:
        self.apply_recipe(
            replace(
                self._recipe,
                transpose_semitones=float(transpose_semitones),
                fine_cents=int(fine_cents),
            ),
            record_history=record_history,
        )

    def set_time_stretch(self, ratio: float, *, record_history: bool = True) -> None:
        self.apply_recipe(
            replace(self._recipe, time_stretch_ratio=float(ratio)),
            record_history=record_history,
        )

    def set_reverse(self, reverse: bool, *, record_history: bool = True) -> None:
        self.apply_recipe(
            replace(self._recipe, reverse=bool(reverse)),
            record_history=record_history,
        )

    def set_output(
        self,
        *,
        channels: ChannelMode | None = None,
        sample_rate_hz: SourceOrInt | None = None,
        bit_depth: SourceOrInt | None = None,
        output_format: OutputFormat | None = None,
        record_history: bool = True,
    ) -> None:
        recipe = self._recipe
        if channels is not None:
            recipe = replace(recipe, channels=channels)
        if sample_rate_hz is not None:
            recipe = replace(recipe, sample_rate_hz=sample_rate_hz)
        if bit_depth is not None:
            recipe = replace(recipe, bit_depth=bit_depth)
        if output_format is not None:
            recipe = replace(recipe, output_format=output_format)
        self.apply_recipe(recipe, record_history=record_history)

    def set_preview_loop(
        self,
        enabled: bool,
        start_ms: int | None = None,
        end_ms: int | None = None,
        *,
        record_history: bool = True,
    ) -> None:
        if record_history:
            self._push_undo()
        self._loop_enabled = bool(enabled)
        if start_ms is not None:
            self._loop_start_ms = max(0, int(start_ms))
        if end_ms is not None:
            self._loop_end_ms = max(0, int(end_ms))
        if self._loop_enabled:
            if self._loop_end_ms is None and self._duration_ms > 0:
                self._loop_end_ms = self._duration_ms
            if self._loop_end_ms is not None and self._loop_end_ms <= self._loop_start_ms:
                self._loop_end_ms = self._loop_start_ms + 1
        self._redo.clear()
        # Preview Loop is session-only; dirty tracks recipe persistence only.
        self.changed.emit()

    def reset_trim(self, *, record_history: bool = True) -> None:
        self.set_trim(0, None, record_history=record_history)

    def set_playhead_ms(self, position_ms: int, *, emit_seek: bool = True) -> None:
        position = max(0, int(position_ms))
        if self._duration_ms > 0:
            position = min(position, self._duration_ms)
        self._playhead_ms = position
        self.changed.emit()
        if emit_seek:
            self.seek_requested.emit(position)

    def zoom_by(self, factor: float, *, anchor_ms: int | None = None) -> None:
        view = self._viewport.clamped()
        if view.duration_ms <= 0:
            return
        span = view.span_ms()
        new_span = int(max(20, min(view.duration_ms, span / max(0.05, factor))))
        anchor = view.visible_start_ms + span // 2 if anchor_ms is None else max(0, anchor_ms)
        start = max(0, anchor - new_span // 2)
        end = min(view.duration_ms, start + new_span)
        start = max(0, end - new_span)
        self._viewport = WaveformViewport(
            duration_ms=view.duration_ms,
            visible_start_ms=start,
            visible_end_ms=end,
        ).clamped()
        self.changed.emit()

    def zoom_fit(self) -> None:
        self._viewport = WaveformViewport(
            duration_ms=self._duration_ms,
            visible_start_ms=0,
            visible_end_ms=self._duration_ms,
        ).clamped()
        self.changed.emit()

    def pan_by_ms(self, delta_ms: int) -> None:
        view = self._viewport.clamped()
        span = view.span_ms()
        start = max(0, min(view.visible_start_ms + int(delta_ms), max(0, view.duration_ms - span)))
        self._viewport = WaveformViewport(
            duration_ms=view.duration_ms,
            visible_start_ms=start,
            visible_end_ms=start + span,
        ).clamped()
        self.changed.emit()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        snap = self._undo.pop()
        self._restore(snap)
        self._sync_dirty()
        self.changed.emit()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        snap = self._redo.pop()
        self._restore(snap)
        self._sync_dirty()
        self.changed.emit()
        return True

    def reset_to_defaults(self, *, record_history: bool = True) -> None:
        self.apply_recipe(PreparationRecipe.default(), record_history=record_history)
        self._loop_enabled = False
        self._loop_start_ms = 0
        self._loop_end_ms = None

    def _snapshot(self) -> _WorkbenchSnapshot:
        return _WorkbenchSnapshot(
            recipe=self._recipe,
            loop_enabled=self._loop_enabled,
            loop_start_ms=self._loop_start_ms,
            loop_end_ms=self._loop_end_ms,
        )

    def _restore(self, snap: _WorkbenchSnapshot) -> None:
        self._recipe = snap.recipe
        self._loop_enabled = snap.loop_enabled
        self._loop_start_ms = snap.loop_start_ms
        self._loop_end_ms = snap.loop_end_ms

    def _push_undo(self) -> None:
        self._undo.append(self._snapshot())
        if len(self._undo) > 64:
            self._undo.pop(0)

    def _sync_dirty(self) -> None:
        dirty = self._recipe != self._baseline
        self._set_dirty(dirty)

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)
