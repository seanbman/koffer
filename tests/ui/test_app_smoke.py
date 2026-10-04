"""Offscreen smoke: Phase 0 entrypoint creates an empty Koffer window."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from koffer.app import CANVAS_COLOR, WINDOW_TITLE, create_main_window


def test_create_main_window_empty_shell(qtbot: object) -> None:
    window = create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == WINDOW_TITLE
    canvas = window.centralWidget()
    assert canvas is not None
    assert canvas.objectName() == "kofferCanvas"
    assert CANVAS_COLOR in canvas.styleSheet()
