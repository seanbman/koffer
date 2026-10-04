"""Koffer application entrypoint and composition wiring."""

from __future__ import annotations

import argparse
import atexit
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from koffer.app_context import AppContext
from koffer.config import configure_logging, resolve_app_paths
from koffer.ui.shell import CANVAS_COLOR, WINDOW_TITLE, MainWindow, create_main_window

__all__ = [
    "CANVAS_COLOR",
    "WINDOW_TITLE",
    "AppContext",
    "MainWindow",
    "create_main_window",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    """Launch the Koffer Phase 2 shell with real SourceService wiring."""
    parser = argparse.ArgumentParser(prog="koffer")
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Reserved startup flag; composition is identical in V1 foundations.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Optional override for application data directory (tests/dev).",
    )
    args = parser.parse_args(argv)

    if args.data_dir is not None:
        root = args.data_dir.expanduser().resolve()
        context = AppContext.open_temp(root)
    else:
        paths = resolve_app_paths()
        context = AppContext.open(paths)

    logger = configure_logging(context.paths)
    logger.info("Starting Koffer Phase 2 sources UI foundations")
    atexit.register(context.close)

    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv if argv is None else argv)

    assert app is not None
    window = create_main_window(context)
    window.show()
    logger.info(
        "Main window shown title=%s screen=%s",
        window.windowTitle(),
        window.current_screen_id(),
    )

    if owns_app:
        return int(app.exec())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
