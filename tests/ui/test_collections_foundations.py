"""Offscreen pytest-qt coverage for S03/S04 Collections foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QTableView, QWidget

from koffer.app_context import AppContext
from koffer.domain import JobState
from koffer.repositories import SampleRepository
from koffer.ui.shell import MainWindow


def _write_audio(dir_path: Path, name: str, payload: bytes = b"RIFF....WAVE") -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    audio = dir_path / name
    audio.write_bytes(payload)
    return audio


def test_s03_renders_real_collection_data(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s03")
    try:
        collection = context.collection_service.create(
            "Vinyl Chops",
            description="Short chops",
        )
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S03")

        screen = window.findChild(QWidget, "collectionsScreen")
        assert screen is not None
        collection_list = window.findChild(QListWidget, "collectionList")
        assert collection_list is not None
        assert collection_list.count() == 1
        text = collection_list.item(0).text()
        assert "Vinyl Chops" in text
        assert "Short chops" in text
        assert "0 samples" in text
        assert str(collection.id) == collection_list.item(0).data(int(Qt.ItemDataRole.UserRole))
    finally:
        context.close()


def test_s04_renders_membership_and_empty_state(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s04")
    pack = tmp_path / "pack"
    kick = _write_audio(pack, "kick.wav", b"RIFF-KICK")
    before = kick.read_bytes()

    try:
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        assert len(samples) == 1

        collection = context.collection_service.create("MPC Export")
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S03")
        window.collections.collection_selected.emit(collection.id)
        assert window.current_screen_id() == "S04"

        empty = window.findChild(QLabel, "collectionDetailEmpty")
        safety = window.findChild(QLabel, "collectionDetailSafety")
        assert empty is not None
        # Offscreen ancestors may not be shown; use isHidden for setVisible state.
        assert not empty.isHidden()
        assert "Drag Samples" in empty.text() or "add" in empty.text().lower()
        assert safety is not None
        assert "never" in safety.text().lower()
        assert "copies" in safety.text().lower() or "moves" in safety.text().lower()

        # Add membership through UI helper (same path as drag/drop).
        window.collection_detail.add_sample_ids([samples[0].id])
        member_table = window.findChild(QTableView, "collectionSampleTable")
        assert member_table is not None
        assert window.collection_detail.model.rowCount() == 1
        assert (
            window.collection_detail.model.data(window.collection_detail.model.index(0, 0))
            == "kick.wav"
        )
        assert empty.isHidden()

        member_table.selectRow(0)
        assert window.transport.selected_sample_id == str(samples[0].id)
        assert window.collection_detail.selected_sample_ids() == [samples[0].id]

        # Removing membership leaves the audio file bytes intact.
        window.collection_detail.remove_sample_ids([samples[0].id])
        assert window.collection_detail.model.rowCount() == 0
        assert not empty.isHidden()
        assert kick.is_file()
        assert kick.read_bytes() == before
        still = SampleRepository(context.connection_factory.get_connection()).get(samples[0].id)
        assert still is not None
    finally:
        context.close()


def test_nav_collections_button_and_detail_roundtrip(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "nav-collections")
    _write_audio(tmp_path / "nav-pack", "hat.wav")
    context.source_service.add_source(tmp_path / "nav-pack")
    collection = context.collection_service.create("Nav Collection")

    try:
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]

        collections_btn = None
        for btn in window.findChildren(QPushButton):
            if btn.text() == "Collections":
                collections_btn = btn
                break
        assert collections_btn is not None
        qtbot.mouseClick(collections_btn, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S03"

        collection_list = window.findChild(QListWidget, "collectionList")
        assert collection_list is not None
        assert collection_list.count() >= 1
        item = collection_list.item(0)
        assert item is not None
        collection_list.itemActivated.emit(item)
        assert window.current_screen_id() == "S04"
        assert window.findChild(QWidget, "collectionDetailScreen") is not None

        back = window.findChild(QPushButton, "backToCollectionsButton")
        assert back is not None
        qtbot.mouseClick(back, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S03"
        assert context.collection_service.get(collection.id).name == "Nav Collection"
    finally:
        context.close()


def test_collection_duplicate_copies_membership_not_audio(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "duplicate-collection")
    pack = tmp_path / "duplicate-pack"
    audio = _write_audio(pack, "snare.wav", b"RIFF-SNARE")
    before = audio.read_bytes()

    try:
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )[0]
        original = context.collection_service.create(
            "Original",
            description="Membership should be cloned without copying audio.",
        )
        context.collection_service.add_samples(original.id, [sample.id])

        duplicate = context.collection_service.duplicate(original.id, name="Original Copy")
        assert duplicate.name == "Original Copy"
        assert duplicate.description == original.description
        assert context.collection_service.list_sample_ids(duplicate.id) == [sample.id]
        assert audio.read_bytes() == before
    finally:
        context.close()
