"""Offscreen pytest-qt coverage for S00/S05/S06 Source foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QPushButton

from koffer.app_context import AppContext
from koffer.domain.enums import SourceStatus
from koffer.ui.shell import MainWindow


def _write_audio(dir_path: Path, name: str = "kick.wav") -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    audio = dir_path / name
    audio.write_bytes(b"RIFF....WAVE")
    return audio


def test_s00_add_source_registers_and_enters_library(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "first-run")
    source_dir = tmp_path / "pack"
    audio = _write_audio(source_dir)
    before = audio.read_bytes()

    def picker(_parent: object) -> Path:
        return source_dir

    try:
        window = MainWindow(context, directory_picker=picker)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S00"

        add_btn = window.findChild(QPushButton, "addFirstSourceButton")
        assert add_btn is not None
        qtbot.mouseClick(add_btn, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

        sources = context.source_service.list()
        assert len(sources) == 1
        assert sources[0].root_path == str(source_dir.resolve())
        # Scan is queued immediately; status may already be scanning.
        assert sources[0].status in {SourceStatus.ONLINE, SourceStatus.SCANNING}
        assert window.current_screen_id() == "S01"
        # Discovery streams into the browser without requiring manual refresh/navigation.
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: window.library.model.rowCount() == 1,
            timeout=5000,
        )
        activity_status = window.findChild(QPushButton, "topBarActivityButton")
        assert activity_status is not None
        assert activity_status.text()
        # Adding a Source must not move/mutate audio bytes.
        assert audio.is_file()
        assert audio.read_bytes() == before
    finally:
        context.close()


def test_s05_shows_online_offline_enabled_from_repository(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "sources-status")
    online_dir = tmp_path / "online"
    offline_dir = tmp_path / "offline"
    _write_audio(online_dir)
    _write_audio(offline_dir)

    try:
        online = context.source_service.add_source(online_dir, display_name="Online Pack")
        offline = context.source_service.add_source(offline_dir, display_name="Offline Pack")
        context.source_service.set_enabled(online.id, True)
        # Force repository offline/disabled states for S05 rendering.
        from dataclasses import replace

        from koffer.domain.timestamps import utc_now_iso
        from koffer.repositories.sources import SourceRepository

        conn = context.connection_factory.get_connection()
        repo = SourceRepository(conn)
        repo.update(
            replace(
                context.source_service.get(offline.id),
                status=SourceStatus.OFFLINE,
                updated_at=utc_now_iso(),
            )
        )
        context.source_service.set_enabled(online.id, False)

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S05")

        source_list = window.findChild(QListWidget, "sourceList")
        assert source_list is not None
        texts = [source_list.item(i).text() for i in range(source_list.count())]
        joined = "\n".join(texts)
        assert "Online Pack" in joined
        assert "Offline Pack" in joined
        assert "Offline" in joined
        assert "Disabled" in joined or "disabled" in joined
        # Enabled=false Source reflects repository disabled state.
        refreshed_online = context.source_service.get(online.id)
        assert refreshed_online.enabled is False
        assert refreshed_online.status is SourceStatus.DISABLED
    finally:
        context.close()


def test_navigation_to_source_detail_shows_exclusions_and_jobs(
    qtbot: object, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QLabel, QListWidget, QWidget

    context = AppContext.open_temp(tmp_path / "detail")
    source_dir = tmp_path / "detail-pack"
    _write_audio(source_dir)

    try:
        source = context.source_service.add_source(source_dir, display_name="Detail Pack")
        job_id = context.source_service.scan(source.id)
        context.scheduler.wait(job_id, timeout=30.0)

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S05")

        source_list = window.findChild(QListWidget, "sourceList")
        assert source_list is not None
        assert source_list.count() >= 1
        item = source_list.item(0)
        assert item is not None
        source_list.setCurrentItem(item)
        source_list.itemActivated.emit(item)
        assert window.current_screen_id() == "S06"

        detail_widget = window.findChild(QWidget, "sourceDetailScreen")
        assert detail_widget is not None
        status = window.findChild(QLabel, "sourceDetailStatus")
        path_label = window.findChild(QLabel, "sourceDetailPath")
        exclusions = window.findChild(QLabel, "sourceDetailExclusions")
        jobs = window.findChild(QListWidget, "sourceDetailJobs")
        files = window.findChild(QListWidget, "sourceDetailFiles")
        assert status is not None
        assert path_label is not None
        assert exclusions is not None
        assert jobs is not None
        assert files is not None
        assert "Online" in status.text() or "Scanning" in status.text()
        assert str(source_dir.resolve()) in path_label.text()
        assert "hidden" in exclusions.text() or "Trash" in exclusions.text()
        assert any("source_scan" in jobs.item(i).text() for i in range(jobs.count()))
        assert any("kick.wav" in files.item(i).text() for i in range(files.count()))

        for object_name in (
            "sourceRescanButton",
            "sourcePauseButton",
            "sourceCancelScanButton",
            "sourceToggleEnabledButton",
            "sourceOpenInFilesButton",
            "sourceEditExclusionsButton",
            "sourceRemoveButton",
        ):
            assert window.findChild(QPushButton, object_name) is not None
    finally:
        context.close()


def test_nav_library_and_sources_buttons(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "nav")
    _write_audio(tmp_path / "nav-pack")
    context.source_service.add_source(tmp_path / "nav-pack")

    try:
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S01"

        sources_btn = None
        library_btn = None
        for btn in window.findChildren(QPushButton):
            if btn.text() == "Sources":
                sources_btn = btn
            if btn.text() == "Library":
                library_btn = btn
        assert sources_btn is not None
        assert library_btn is not None

        qtbot.mouseClick(sources_btn, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S05"
        qtbot.mouseClick(library_btn, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S01"
    finally:
        context.close()
