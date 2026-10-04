"""Phase 13 UX hardening: shortcuts, geometry persistence, Sample context menu."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QLineEdit

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain import (
    Sample,
    SampleAvailability,
    Source,
    SourceStatus,
    new_entity_id,
    utc_now_iso,
)
from koffer.persistence import SearchIndexService
from koffer.repositories import SampleRepository, SourceRepository
from koffer.ui.shell import MainWindow
from koffer.ui.tokens import CLAY_BRIGHT, SHELL_STYLESHEET
from koffer.ui.widgets.content_state import ContentState, ContentStatePanel


def _seed_library(context: AppContext, tmp_path: Path, *, name: str = "ux-kick.wav") -> str:
    pack = tmp_path / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    wav = write_sine_wav(pack / name, duration_s=0.15)
    conn = context.connection_factory.get_connection()
    now = utc_now_iso()
    source = Source(
        id=new_entity_id(),
        display_name="UX Pack",
        root_path=str(pack),
        enabled=True,
        recursive=True,
        status=SourceStatus.ONLINE,
        created_at=now,
        updated_at=now,
    )
    SourceRepository(conn).create(source)
    sample = Sample(
        id=new_entity_id(),
        relative_path=name,
        normalized_path_cache=name,
        filename=name,
        extension="wav",
        size_bytes=wav.stat().st_size,
        mtime_ns=1,
        availability=SampleAvailability.ONLINE,
        favorite=False,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        source_id=source.id,
    )
    SampleRepository(conn).create(sample)
    SearchIndexService(conn).refresh_sample(sample.id)
    return str(sample.id)


def test_global_ctrl_f_focuses_search_offscreen(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "ctrl-f")
    try:
        _seed_library(context, tmp_path)
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.show()
        qtbot.waitExposed(window)  # type: ignore[attr-defined]
        window.navigate("S01")
        window.library.table.setFocus()

        shortcut = window.findChild(QShortcut, "focusSearchShortcut")
        assert shortcut is not None
        assert shortcut.key() == QKeySequence("Ctrl+F")

        # Offscreen hosts often drop real keyClick → ApplicationShortcut delivery;
        # activate the bound Ctrl+F shortcut directly for a deterministic verifier.
        window.trigger_focus_search_shortcut()
        search = window.findChild(QLineEdit, "librarySearchField")
        assert search is not None
        qtbot.waitUntil(lambda: search.hasFocus(), timeout=2000)  # type: ignore[attr-defined]
    finally:
        context.close()


def test_window_and_pane_geometry_persists_across_restart(qtbot: object, tmp_path: Path) -> None:
    root = tmp_path / "geometry-app"
    context = AppContext.open_temp(root)
    try:
        _seed_library(context, tmp_path)
        window = MainWindow(context, directory_picker=lambda _p: None, restore_geometry=False)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.show()
        qtbot.waitExposed(window)  # type: ignore[attr-defined]
        window.navigate("S01")
        window.resize(1333, 877)
        window.library.splitter.setSizes([700, 400])
        saved_sizes = window.library.splitter.sizes()
        assert saved_sizes[0] > 0 and saved_sizes[1] > 0
        window.persist_geometry()
        assert window.geometry_store.settings_path.is_file()
        window.close()
    finally:
        context.close()

    context2 = AppContext.open_temp(root)
    try:
        restored = MainWindow(context2, directory_picker=lambda _p: None, restore_geometry=True)
        qtbot.addWidget(restored)  # type: ignore[attr-defined]
        restored.show()
        qtbot.waitExposed(restored)  # type: ignore[attr-defined]
        # Prefer persisted explicit size (restoreGeometry can clamp on offscreen screens).
        assert restored.geometry_store.settings_path.is_file()
        payload_size = restored.width(), restored.height()
        assert payload_size == (1333, 877)
        pane_sizes = restored.library.splitter.sizes()
        stored_sizes = restored.geometry_store.load_splitter_sizes("library")
        assert stored_sizes == saved_sizes
        assert pane_sizes == saved_sizes
    finally:
        context2.close()


def test_sample_context_menu_exposes_required_actions(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "context-menu")
    try:
        sample_id = _seed_library(context, tmp_path)
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")
        window.library.table.selectRow(0)
        assert window.library.selected_sample_id() == sample_id

        menu = window.library.build_sample_context_menu()
        actions = {
            action.objectName(): action for action in menu.actions() if isinstance(action, QAction)
        }
        assert "sampleContextPlay" in actions
        assert actions["sampleContextPlay"].text() == "Play / Pause"
        assert "sampleContextFavourite" in actions
        assert actions["sampleContextFavourite"].text() == "Favourite"
        assert "sampleContextAddToCollection" in actions
        assert "Add to Collection" in actions["sampleContextAddToCollection"].text()
        assert "sampleContextPrepare" in actions
        assert "Prepare" in actions["sampleContextPrepare"].text()
        assert "sampleContextEditMetadata" in actions
        assert "Edit Metadata" in actions["sampleContextEditMetadata"].text()
        for name in (
            "sampleContextPlay",
            "sampleContextFavourite",
            "sampleContextAddToCollection",
            "sampleContextPrepare",
            "sampleContextEditMetadata",
        ):
            assert actions[name].isEnabled()
    finally:
        context.close()


def test_owned_screens_share_content_state_and_visible_focus_tokens(
    qtbot: object, tmp_path: Path
) -> None:
    context = AppContext.open_temp(tmp_path / "content-state")
    try:
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]

        window.navigate("S03")
        assert any(
            panel.state is ContentState.EMPTY for panel in window.findChildren(ContentStatePanel)
        )

        window.navigate("S05")
        window.navigate("S16")
        assert any(
            panel.state is ContentState.EMPTY for panel in window.findChildren(ContentStatePanel)
        )

        assert CLAY_BRIGHT in SHELL_STYLESHEET
        assert "QLineEdit#librarySearchField:focus" in SHELL_STYLESHEET
        assert "QTableView#sampleTable:focus" in SHELL_STYLESHEET
    finally:
        context.close()
