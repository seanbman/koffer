"""Native directory selection adapters for Source add flows."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

DirectoryPicker = Callable[[QWidget | None], Path | None]


def native_directory_picker(parent: QWidget | None = None) -> Path | None:
    """Open the platform directory dialog; returns None when cancelled."""
    selected = QFileDialog.getExistingDirectory(
        parent,
        "Add Source",
        str(Path.home()),
        QFileDialog.Option.ShowDirsOnly,
    )
    if not selected:
        return None
    return Path(selected)
