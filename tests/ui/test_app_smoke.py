"""Offscreen smoke: Phase 2 shell creates a dark Koffer window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow

from koffer.app import CANVAS_COLOR, WINDOW_TITLE, create_main_window
from koffer.app_context import AppContext


def test_create_main_window_dark_shell(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "smoke-app")
    try:
        window = create_main_window(context)
        qtbot.addWidget(window)  # type: ignore[attr-defined]

        assert isinstance(window, QMainWindow)
        assert window.windowTitle() == WINDOW_TITLE
        shell = window.centralWidget()
        assert shell is not None
        assert shell.objectName() == "kofferShell"
        assert CANVAS_COLOR == "#0B0D0F"
        assert window.current_screen_id() == "S00"
    finally:
        context.close()
