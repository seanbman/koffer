"""Phase 0 application shell: empty dark window only."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from koffer.config import configure_logging, resolve_app_paths

CANVAS_COLOR = "#0B0D0F"
WINDOW_TITLE = "Koffer"


def create_main_window() -> QMainWindow:
    """Create the Phase 0 empty main window (no feature screens)."""
    window = QMainWindow()
    window.setWindowTitle(WINDOW_TITLE)
    window.resize(1440, 900)
    canvas = QWidget()
    canvas.setObjectName("kofferCanvas")
    canvas.setStyleSheet(f"#kofferCanvas {{ background-color: {CANVAS_COLOR}; }}")
    window.setCentralWidget(canvas)
    return window


def main(argv: list[str] | None = None) -> int:
    """Launch the Phase 0 Koffer shell."""
    parser = argparse.ArgumentParser(prog="koffer")
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Reserved startup flag; Phase 0 behaves identically.",
    )
    parser.parse_args(argv)

    paths = resolve_app_paths()
    logger = configure_logging(paths)
    logger.info("Starting Koffer Phase 0 shell")

    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv if argv is None else argv)

    assert app is not None
    window = create_main_window()
    window.show()
    logger.info("Main window shown title=%s", window.windowTitle())

    if owns_app:
        return int(app.exec())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
