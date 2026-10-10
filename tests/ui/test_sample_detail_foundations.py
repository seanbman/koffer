"""Offscreen pytest-qt coverage for the S07 Sample Detail contract."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QToolButton, QWidget

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_malformed_wav, write_tagged_wav
from koffer.domain import JobState
from koffer.domain.preparation import NormalizeSpec, PreparationRecipe, TrimSpec
from koffer.repositories import SampleRepository
from koffer.ui.shell import MainWindow
from koffer.ui.widgets.waveform_view import WaveformView


def test_s07_edit_sound_primary_and_human_readable_hierarchy(qtbot: object, tmp_path: Path) -> None:
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
        context.preparation_service.save_recipe(
            sample.id,
            PreparationRecipe(
                trim=TrimSpec(start_ms=12, end_ms=400),
                normalize=NormalizeSpec(enabled=True),
                transpose_semitones=-2.0,
            ),
        )

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

        identity = screen.findChild(QLabel, "sampleDetailIdentity")
        assert identity is not None
        assert "hat.wav" in identity.text().lower()

        waveform = screen.findChild(WaveformView, "sampleDetailWaveform")
        waveform_state = screen.findChild(QLabel, "sampleDetailWaveformState")
        assert waveform is not None
        assert waveform_state is not None
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: "loading" not in waveform_state.text().lower(),
            timeout=5_000,
        )
        assert "unavailable" not in waveform_state.text().lower()

        classification = screen.findChild(QWidget, "sampleDetailClassification")
        suggestions = screen.findChild(QWidget, "sampleDetailSuggestions")
        tags = screen.findChild(QWidget, "sampleDetailTagsCollections")
        edit_summary = screen.findChild(QWidget, "sampleDetailEditSummary")
        assert classification is not None
        assert suggestions is not None
        assert tags is not None
        assert edit_summary is not None
        summary_body = edit_summary.findChild(QLabel, "sampleDetailEditSummaryBody")
        assert summary_body is not None
        assert "Edited" in summary_body.text()
        assert "Trim" in summary_body.text()

        file_details = screen.findChild(QWidget, "sampleDetailFileDetails")
        analysis_details = screen.findChild(QWidget, "sampleDetailAnalysisDetails")
        assert file_details is not None
        assert analysis_details is not None
        file_body = file_details.findChild(QLabel, "sampleDetailFileDetailsBody")
        analysis_body = analysis_details.findChild(QLabel, "sampleDetailAnalysisDetailsBody")
        assert file_body is not None and file_body.isHidden()
        assert analysis_body is not None and analysis_body.isHidden()
        file_toggle = file_details.findChild(QToolButton, "sampleDetailFileDetailsToggle")
        assert file_toggle is not None
        file_toggle.setChecked(True)
        assert not file_body.isHidden()
        assert "Closed Hat" in file_body.text()

        # Default path must not dump raw JSON / hashes / UUIDs.
        default_text = " ".join(
            label.text()
            for label in screen.findChildren(QLabel)
            if label.isVisible() and label.objectName() != "sampleDetailFileDetailsBody"
        )
        assert "{" not in default_text
        assert "sha256" not in default_text.lower()
        assert str(sample.id) not in default_text

        edit = screen.findChild(QPushButton, "editMetadataButton")
        edit_sound = screen.findChild(QPushButton, "editSoundButton")
        add_collection = screen.findChild(QPushButton, "addToCollectionButton")
        assert edit is not None
        assert edit_sound is not None
        assert add_collection is not None
        assert edit_sound.text() == "Edit Sound"
        assert edit.text() == "Edit Info"
        assert edit is not edit_sound

        qtbot.mouseClick(edit_sound, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S08"
        assert window.transport.selected_sample_id == str(sample.id)
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
        file_toggle = window.findChild(QToolButton, "sampleDetailFileDetailsToggle")
        assert file_toggle is not None
        file_toggle.setChecked(True)
        file_body = window.findChild(QLabel, "sampleDetailFileDetailsBody")
        assert file_body is not None
        assert "unavailable" in file_body.text().lower() or "could not" in file_body.text().lower()

        back = window.findChild(QPushButton, "backToLibraryButton")
        assert back is not None
        qtbot.mouseClick(back, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S01"
    finally:
        context.close()
