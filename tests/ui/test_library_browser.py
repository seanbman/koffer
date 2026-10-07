"""Offscreen coverage for S01/S02 foundations + Inspector/Playback bindings."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QTableView

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain import (
    EntityId,
    Sample,
    SampleAvailability,
    Source,
    SourceStatus,
    new_entity_id,
    utc_now_iso,
)
from koffer.domain.query import SampleFilters, SortDirection, SortField
from koffer.persistence import SearchIndexService
from koffer.repositories import SampleRepository, SourceRepository
from koffer.services.playback import PlaybackState
from koffer.ui.screens.library import LibraryBrowserScreen
from koffer.ui.shell import MainWindow
from koffer.ui.widgets.inspector import InspectorPanel
from koffer.ui.widgets.transport import TransportBar


def _seed_library(context: AppContext, tmp_path: Path, *, name: str = "deep-kick.wav") -> str:
    pack = tmp_path / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    wav = write_sine_wav(pack / name, duration_s=0.2)
    conn = context.connection_factory.get_connection()
    now = utc_now_iso()
    source = Source(
        id=new_entity_id(),
        display_name="UI Pack",
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


def test_s01_library_shows_paged_table_and_search(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "library-ui")
    try:
        _seed_library(context, tmp_path)

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")

        table = window.findChild(QTableView, "sampleTable")
        search = window.findChild(QLineEdit, "librarySearchField")
        assert table is not None
        assert search is not None
        assert table.model() is not None
        assert table.model().rowCount() == 1  # type: ignore[union-attr]

        library = window.findChild(LibraryBrowserScreen, "libraryBrowser")
        assert library is not None
        library.focus_search()
        search.setText("kick")
        qtbot.keyClick(search, Qt.Key.Key_Return)  # type: ignore[attr-defined]
        assert table.model().rowCount() == 1  # type: ignore[union-attr]
        assert table.model().data(table.model().index(0, 0)) == "deep-kick.wav"  # type: ignore[union-attr]
    finally:
        context.close()


def test_s01_selection_updates_inspector_keeps_table_selection(
    qtbot: object, tmp_path: Path
) -> None:
    context = AppContext.open_temp(tmp_path / "inspector-ui")
    try:
        sample_id = _seed_library(context, tmp_path, name="inspect-me.wav")
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")

        library = window.library
        table = library.table
        table.selectRow(0)
        qtbot.waitUntil(lambda: library.inspector.sample_id == sample_id, timeout=2000)  # type: ignore[attr-defined]

        inspector = window.findChild(InspectorPanel, "inspectorPanel")
        assert inspector is not None
        assert inspector.sample_id == sample_id
        assert inspector.title_text == "inspect-me.wav"
        assert "Waveform:" in inspector.waveform_summary_text
        assert "unavailable" not in inspector.waveform_summary_text

        selected = table.selectionModel().selectedRows()
        assert len(selected) == 1
        assert library.model.sample_id_at(selected[0].row()) == sample_id
        # Auto-preview OFF: selection alone must not start playback.
        assert context.playback_service.state == PlaybackState.STOPPED
        assert context.playback_service.sample_id is None
    finally:
        context.close()


def test_playback_invoked_from_browser_selection_path(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "transport-ui")
    try:
        sample_id = _seed_library(context, tmp_path, name="play-me.wav")
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")

        window.library.table.selectRow(0)
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: window.transport.selected_sample_id == sample_id,
            timeout=2000,
        )

        transport = window.findChild(TransportBar, "transportBar")
        assert transport is not None
        transport.play_selection()

        assert context.playback_service.sample_id is not None
        assert str(context.playback_service.sample_id) == sample_id
        assert context.playback_service.path is not None
        assert context.playback_service.path.name == "play-me.wav"
    finally:
        context.close()


def test_ctrl_f_focuses_search_and_filter_panel_applies(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "filters-ui")
    try:
        _seed_library(context, tmp_path, name="kick.wav")
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.show()
        qtbot.waitExposed(window)  # type: ignore[attr-defined]
        window.navigate("S01")

        window.focus_library_search()
        search = window.findChild(QLineEdit, "librarySearchField")
        assert search is not None
        qtbot.waitUntil(lambda: search.hasFocus(), timeout=2000)  # type: ignore[attr-defined]

        library = window.library
        library.show_filters(True)
        assert library.filter_panel.isVisible()
        library.filter_panel.apply_filters(SampleFilters(extensions=("wav",)))
        assert library.model.rowCount() == 1
        assert "format=wav" in library.filter_panel.active_summary
    finally:
        context.close()


def test_s01_table_sorting_updates_paged_query(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "sorting-ui")
    try:
        _seed_library(context, tmp_path, name="sort-me.wav")
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")

        table = window.library.table
        assert table.isSortingEnabled()
        table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        assert window.library.model.query.sort.field is SortField.NAME
        assert window.library.model.query.sort.direction is SortDirection.DESC

        table.sortByColumn(6, Qt.SortOrder.AscendingOrder)
        assert window.library.model.query.sort.field is SortField.EXTENSION
        assert window.library.model.query.sort.direction is SortDirection.ASC
    finally:
        context.close()


def test_s01_search_text_is_debounced(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "search-debounce-ui")
    try:
        _seed_library(context, tmp_path, name="debounced-kick.wav")
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")

        search = window.library.search_field
        assert window.library.model.query.text == ""
        search.setText("kick")
        assert window.library.model.query.text == ""

        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: window.library.model.query.text == "kick",
            timeout=1000,
        )
        assert window.library.model.rowCount() == 1
    finally:
        context.close()


def test_preview_history_drives_recents_view(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "recents-ui")
    try:
        sample_id = _seed_library(context, tmp_path, name="recent-hit.wav")
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")
        window.library.table.selectRow(0)
        window.library.load_selection_into_playback()

        # AppContext records history when playback enters PLAYING.
        context.playback_service.state_changed.emit("playing")

        sample = SampleRepository(context.connection_factory.get_connection()).get(
            EntityId(sample_id)
        )
        assert sample is not None
        assert sample.last_previewed_at is not None

        window.library.show_recents()
        assert window.library.view_title == "Recents"
        assert window.library.model.rowCount() == 1
        assert window.library.model.data(window.library.model.index(0, 0)) == "recent-hit.wav"
    finally:
        context.close()
