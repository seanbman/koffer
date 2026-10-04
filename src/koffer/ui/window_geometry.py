"""Persist main-window and pane geometry under XDG config (docs/24, docs/28).

Uses durable JSON under the XDG config directory. Qt ``QSettings`` atomic
rewrites raise AccessError in some sandboxed CI/offscreen hosts, so the store
writes via pathlib for reliable restore across restarts.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QMainWindow, QSplitter

__all__ = ["WindowGeometryStore"]


class WindowGeometryStore:
    """XDG-config window/pane geometry store."""

    def __init__(self, config_dir: Path) -> None:
        config_dir.mkdir(parents=True, exist_ok=True)
        self._path = config_dir / "window-geometry.json"
        self._data: dict[str, object] = {}
        self._load()

    @property
    def settings_path(self) -> Path:
        return self._path

    def restore_window(self, window: QMainWindow) -> bool:
        """Restore geometry and Qt window state when previously saved."""
        restored = False
        geometry = self._decode(self._data.get("geometry"))
        if geometry is not None and not geometry.isEmpty():
            window.restoreGeometry(geometry)
            restored = True
        state = self._decode(self._data.get("windowState"))
        if state is not None and not state.isEmpty():
            window.restoreState(state)
            restored = True
        # Offscreen/small virtual screens can clamp restoreGeometry; re-apply explicit size.
        size = self._data.get("size")
        if isinstance(size, list) and len(size) == 2:
            try:
                width, height = int(size[0]), int(size[1])
            except (TypeError, ValueError):
                width, height = 0, 0
            if width > 0 and height > 0:
                window.resize(width, height)
                restored = True
        return restored

    def save_window(self, window: QMainWindow) -> None:
        self._data["geometry"] = self._encode(window.saveGeometry())
        self._data["windowState"] = self._encode(window.saveState())
        self._data["size"] = [int(window.width()), int(window.height())]
        self._flush()

    def restore_splitter(self, key: str, splitter: QSplitter) -> bool:
        splitters = self._data.get("splitters")
        if not isinstance(splitters, dict):
            return False
        raw = self._decode(splitters.get(key))
        if raw is None or raw.isEmpty():
            return False
        return bool(splitter.restoreState(raw))

    def save_splitter(self, key: str, splitter: QSplitter) -> None:
        splitters = self._data.get("splitters")
        if not isinstance(splitters, dict):
            splitters = {}
        splitters[key] = self._encode(splitter.saveState())
        self._data["splitters"] = splitters
        # Also keep explicit sizes for harness assertions when restoreState is lossy.
        sizes = self._data.get("splitter_sizes")
        if not isinstance(sizes, dict):
            sizes = {}
        sizes[key] = [int(v) for v in splitter.sizes()]
        self._data["splitter_sizes"] = sizes
        self._flush()

    def load_splitter_sizes(self, key: str) -> list[int] | None:
        sizes = self._data.get("splitter_sizes")
        if not isinstance(sizes, dict):
            return None
        raw = sizes.get(key)
        if not isinstance(raw, list):
            return None
        try:
            return [int(v) for v in raw]
        except (TypeError, ValueError):
            return None

    def _load(self) -> None:
        if not self._path.is_file():
            self._data = {}
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._data = {}
            return
        self._data = payload if isinstance(payload, dict) else {}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _encode(value: QByteArray) -> str:
        return base64.b64encode(value.data()).decode("ascii")

    @staticmethod
    def _decode(value: object) -> QByteArray | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return QByteArray(base64.b64decode(value.encode("ascii")))
        except (ValueError, TypeError):
            return None
