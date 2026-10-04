"""Offscreen pytest-qt coverage for S08/S14 preparation and render foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QSpinBox, QWidget

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import JobState
from koffer.filesystem.hashing import content_fingerprint
from koffer.repositories.samples import SampleRepository
from koffer.ui.shell import MainWindow


def test_s08_identifies_source_and_nondestructive_recipe(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s08")
    pack = tmp_path / "pack"
    pack.mkdir()
    media = write_sine_wav(pack / "tone.wav", duration_s=0.5)
    before = content_fingerprint(media)
    try:
        source = context.source_service.add_source(pack)
        scan_job = context.scheduler.wait(
            context.source_service.scan(source.id),
            timeout=30.0,
        )
        assert scan_job.state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_sample_preparation(samples[0].id)

        assert window.current_screen_id() == "S08"
        screen = window.findChild(QWidget, "samplePreparationScreen")
        assert screen is not None
        badge = window.findChild(QLabel, "samplePreparationNondestructiveBadge")
        assert badge is not None
        assert "Non-destructive" in badge.text()
        source_label = window.findChild(QLabel, "samplePreparationSourceLabel")
        assert source_label is not None
        assert "tone.wav" in source_label.text()

        trim_start = window.findChild(QSpinBox, "samplePreparationTrimStart")
        assert trim_start is not None
        trim_start.setValue(120)
        reverse = window.findChild(QCheckBox, "samplePreparationReverse")
        assert reverse is not None
        reverse.setChecked(True)

        save = window.findChild(QPushButton, "samplePreparationSaveButton")
        assert save is not None
        save.click()
        assert content_fingerprint(media) == before

        reset = window.findChild(QPushButton, "samplePreparationResetButton")
        assert reset is not None
        reset.click()
        assert trim_start.value() == 0
        assert reverse.isChecked() is False
        assert content_fingerprint(media) == before

        export = window.findChild(QPushButton, "samplePreparationExportButton")
        assert export is not None
        export.click()
        assert window.current_screen_id() == "S14"
        render_screen = window.findChild(QWidget, "renderExportScreen")
        assert render_screen is not None
        recipe_summary = window.findChild(QLabel, "renderExportRecipeSummary")
        assert recipe_summary is not None
        assert "Recipe summary" in recipe_summary.text()
        original = window.findChild(QLabel, "renderExportOriginalLabel")
        assert original is not None
        assert "Original:" in original.text()
        job_note = window.findChild(QLabel, "renderExportJobNote")
        assert job_note is not None
        assert "background Job" in job_note.text()
    finally:
        context.close()
