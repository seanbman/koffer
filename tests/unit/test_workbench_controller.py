"""Unit tests for S08 workbench viewport/selection/undo model."""

from __future__ import annotations

from koffer.domain.preparation import PreparationRecipe, TrimSpec
from koffer.ui.models.workbench import WorkbenchController


def test_trim_constraints_and_numeric_sync() -> None:
    controller = WorkbenchController()
    controller.load(PreparationRecipe.default(), duration_ms=1000)
    controller.set_trim(200, 800)
    assert controller.selection.trim_start_ms == 200
    assert controller.selection.retained_end(1000) == 800
    controller.set_trim(900, 100)
    assert controller.selection.trim_start_ms == 900
    assert controller.selection.retained_end(1000) == 900


def test_undo_redo_and_dirty_state() -> None:
    controller = WorkbenchController()
    baseline = PreparationRecipe(trim=TrimSpec(start_ms=0, end_ms=None))
    controller.load(baseline, duration_ms=500)
    assert controller.dirty is False
    controller.set_fades(10, 80)
    controller.set_gain_db(-2.0)
    assert controller.dirty is True
    assert controller.can_undo is True
    controller.undo()
    assert controller.recipe.gain_db == 0.0
    assert controller.recipe.fade_in_ms == 10
    controller.redo()
    assert controller.recipe.gain_db == -2.0
    controller.mark_saved()
    assert controller.dirty is False


def test_zoom_pan_and_preview_loop_are_session_only() -> None:
    controller = WorkbenchController()
    controller.load(PreparationRecipe.default(), duration_ms=2000)
    controller.zoom_by(2.0, anchor_ms=1000)
    assert controller.viewport.span_ms() < 2000
    controller.pan_by_ms(100)
    controller.set_preview_loop(True, 100, 400)
    assert controller.selection.loop_enabled is True
    assert controller.dirty is False
    summary = controller.recipe.concise_edit_summary()
    assert summary is None


def test_concise_edit_summary_format() -> None:
    recipe = PreparationRecipe(
        trim=TrimSpec(start_ms=10, end_ms=500),
        transpose_semitones=-2.0,
    )
    assert recipe.concise_edit_summary() == "Edited · Trim + -2 st"
