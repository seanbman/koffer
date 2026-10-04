"""Offscreen pytest-qt coverage for S09 Metadata Editor foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QRadioButton, QWidget

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_tagged_wav
from koffer.domain.enums import JobState
from koffer.repositories.samples import SampleRepository
from koffer.ui.shell import MainWindow


def test_s09_disables_nothing_for_wav_and_requires_explicit_target(
    qtbot: object, tmp_path: Path
) -> None:
    context = AppContext.open_temp(tmp_path / "s09")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_tagged_wav(pack / "kick.wav", title="Kick", artist="Author")
    try:
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_metadata_editor([samples[0].id])

        assert window.current_screen_id() == "S09"
        screen = window.findChild(QWidget, "metadataEditorScreen")
        assert screen is not None

        update = window.findChild(QRadioButton, "metadataEditorUpdateOriginal")
        copy = window.findChild(QRadioButton, "metadataEditorWriteToCopy")
        assert update is not None and copy is not None
        assert update.isChecked()

        title = window.findChild(QLineEdit, "metadataField_title")
        assert title is not None
        assert title.isEnabled()
        assert title.text() == "Kick"

        tags = window.findChild(QLabel, "metadataEditorKofferTagsHeading")
        assert tags is not None
        assert "library-only" in tags.text().lower()

        # Change a supported field and review plan for Update Original.
        title.setText("Edited Kick")
        plan_btn = window.findChild(QPushButton, "metadataEditorPlanButton")
        assert plan_btn is not None
        plan_btn.click()
        execute = window.findChild(QPushButton, "metadataEditorExecuteButton")
        assert execute is not None
        assert execute.isEnabled()
        summary = window.findChild(QLabel, "metadataEditorPlanSummary")
        assert summary is not None
        assert "Update Original" in summary.text()
    finally:
        context.close()


def test_s09_write_to_copy_target_enables_destination(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s09copy")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_tagged_wav(pack / "clap.wav", title="Clap")
    try:
        source = context.source_service.add_source(pack)
        assert (
            context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0).state
            is JobState.COMPLETED
        )
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_metadata_editor([samples[0].id])

        copy = window.findChild(QRadioButton, "metadataEditorWriteToCopy")
        assert copy is not None
        copy.setChecked(True)
        dest = window.findChild(QLineEdit, "metadataEditorCopyDir")
        assert dest is not None
        assert dest.isEnabled()
        dest.setText(str(tmp_path / "meta-copies"))

        title = window.findChild(QLineEdit, "metadataField_title")
        assert title is not None
        title.setText("Copy Title")
        plan_btn = window.findChild(QPushButton, "metadataEditorPlanButton")
        assert plan_btn is not None
        plan_btn.click()
        summary = window.findChild(QLabel, "metadataEditorPlanSummary")
        assert summary is not None
        assert "Write to Copy" in summary.text()
        execute = window.findChild(QPushButton, "metadataEditorExecuteButton")
        assert execute is not None
        assert execute.isEnabled()
    finally:
        context.close()
