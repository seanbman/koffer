"""Offscreen coverage for S01 paged library browser."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QTableView

from koffer.app_context import AppContext
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
from koffer.ui.screens.library import LibraryBrowserScreen
from koffer.ui.shell import MainWindow


def test_s01_library_shows_paged_table_and_search(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "library-ui")
    try:
        conn = context.connection_factory.get_connection()
        now = utc_now_iso()
        source = Source(
            id=new_entity_id(),
            display_name="UI Pack",
            root_path=str(tmp_path / "pack"),
            enabled=True,
            recursive=True,
            status=SourceStatus.ONLINE,
            created_at=now,
            updated_at=now,
        )
        SourceRepository(conn).create(source)
        sample = Sample(
            id=new_entity_id(),
            relative_path="kick.wav",
            normalized_path_cache="kick.wav",
            filename="deep-kick.wav",
            extension="wav",
            size_bytes=1024,
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
