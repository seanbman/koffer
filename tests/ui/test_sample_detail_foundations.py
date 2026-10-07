"""Offscreen pytest-qt coverage for the S07 Sample Detail contract."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QWidget

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_malformed_wav, write_tagged_wav
from koffer.domain import JobState
from koffer.repositories import SampleRepository
from koffer.ui.shell import MainWindow
from koffer.ui.widgets.waveform_view import WaveformView


def test_s07_renders_distinct_provenance_categories(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s07")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_tagged_wav(pack / "hat.wav", title="Closed Hat", artist="Kit")

    try:
        source = context.source_service.add_source(pack)
        job = context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0)
        assert job.state is JobState.COMPLETED
        sample = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )[0]

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")
        window.library.open_sample_detail_requested.emit(str(sample.id))
        assert window.current_screen_id() == "S07"

        screen = window.findChild(QWidget, "sampleDetailScreen")
        assert screen is not None
        title = screen.findChild(QLabel, "pageTitle")
        assert title is not None
        assert "hat.wav" in title.text().lower() or "hat" in title.text().lower()

        categories = {
            "provenanceTechnical",
            "provenanceEmbedded",
            "provenanceConfirmed",
            "provenanceSuggested",
            "provenanceTags",
        }
        for object_name in categories:
            frame = screen.findChild(QFrame, object_name)
            assert frame is not None, object_name
            assert frame.property("provenanceCategory") in {
                "technical",
                "embedded",
                "confirmed",
                "suggested",
                "tags",
            }

        embedded_body = screen.findChild(QLabel, "provenanceBodyEmbedded")
        assert embedded_body is not None
        assert "Closed Hat" in embedded_body.text()

        waveform = screen.findChild(WaveformView, "sampleDetailWaveform")
        waveform_state = screen.findChild(QLabel, "sampleDetailWaveformState")
        assert waveform is not None
        assert waveform_state is not None
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: "loading" not in waveform_state.text().lower(),
            timeout=5_000,
        )
        assert "unavailable" not in waveform_state.text().lower()

        edit = screen.findChild(QPushButton, "editMetadataButton")
        prepare = screen.findChild(QPushButton, "prepareButton")
        add_collection = screen.findChild(QPushButton, "addToCollectionButton")
        organize = screen.findChild(QPushButton, "organizeSampleButton")
        reveal = screen.findChild(QPushButton, "revealSampleButton")
        assert edit is not None
        assert prepare is not None
        assert add_collection is not None
        assert organize is not None
        assert reveal is not None
        assert edit is not prepare
        assert reveal.isEnabled()
        assert window.transport.selected_sample_id == str(sample.id)

        collections = screen.findChild(QLabel, "sampleDetailCollections")
        history = screen.findChild(QLabel, "sampleDetailHistory")
        path = screen.findChild(QLabel, "sampleDetailPath")
        assert collections is not None
        assert history is not None
        assert path is not None
        assert "HISTORY" in history.text()
        assert str(pack) in path.text()
    finally:
        context.close()


def test_s07_malformed_sample_does_not_crash_detail(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s07-bad")
    pack = tmp_path / "badpack"
    pack.mkdir()
    write_malformed_wav(pack / "broken.wav")

    try:
        source = context.source_service.add_source(pack)
        context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0)
        listed = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        if not listed:
            from koffer.domain import SampleAvailability, new_entity_id, utc_now_iso
            from koffer.domain.models import Sample

            now = utc_now_iso()
            sample = Sample(
                id=new_entity_id(),
                relative_path="broken.wav",
                normalized_path_cache="broken.wav",
                filename="broken.wav",
                extension="wav",
                size_bytes=20,
                mtime_ns=0,
                availability=SampleAvailability.ONLINE,
                favorite=False,
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
                source_id=source.id,
            )
            SampleRepository(context.connection_factory.get_connection()).create(sample)
        else:
            sample = listed[0]

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window._open_sample_detail(str(sample.id))  # noqa: SLF001 — direct foundation path
        assert window.current_screen_id() == "S07"
        embedded_body = window.findChild(QLabel, "provenanceBodyEmbedded")
        assert embedded_body is not None
        assert "Unavailable" in embedded_body.text() or "error" in embedded_body.text().lower()

        back = window.findChild(QPushButton, "backToLibraryButton")
        assert back is not None
        qtbot.mouseClick(back, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S01"
    finally:
        context.close()
