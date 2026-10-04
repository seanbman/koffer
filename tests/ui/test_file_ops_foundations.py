"""Offscreen pytest-qt coverage for S12/S13 file-operation foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QWidget

from koffer.app_context import AppContext
from koffer.domain.enums import ConflictAction, JobState
from koffer.repositories.samples import SampleRepository
from koffer.ui.shell import MainWindow


def _write_audio(dir_path: Path, name: str, payload: bytes = b"RIFF....WAVE") -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    audio = dir_path / name
    audio.write_bytes(payload)
    return audio


def test_s12_shows_operation_destination_and_conflicts(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s12")
    pack = tmp_path / "pack"
    _write_audio(pack, "kick.wav", b"RIFF-KICK")
    try:
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        dest = tmp_path / "managed"
        dest.mkdir()
        (dest / "kick.wav").write_bytes(b"EXISTING")
        plan = context.file_operation_service.plan_copy([samples[0].id], dest)

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_file_operation_plan(plan)

        assert window.current_screen_id() == "S12"
        screen = window.findChild(QWidget, "importReviewScreen")
        assert screen is not None
        operation = window.findChild(QLabel, "importReviewOperation")
        assert operation is not None
        assert "Copy" in operation.text()
        destination = window.findChild(QLabel, "importReviewDestination")
        assert destination is not None
        assert str(dest.resolve()) in destination.text()
        policy = window.findChild(QLabel, "importReviewConflictPolicy")
        assert policy is not None
        assert "review" in policy.text().lower()
        assert "never silent overwrite" in policy.text().lower()
        item_list = window.findChild(QListWidget, "importReviewItemList")
        assert item_list is not None
        assert item_list.count() == 1
        assert "CONFLICT" in item_list.item(0).text()
        execute = window.findChild(QPushButton, "importReviewExecuteButton")
        assert execute is not None
        assert not execute.isEnabled()
    finally:
        context.close()


def test_s13_resolves_keep_both_and_returns_to_executable_s12(
    qtbot: object, tmp_path: Path
) -> None:
    context = AppContext.open_temp(tmp_path / "s13")
    pack = tmp_path / "pack"
    _write_audio(pack, "kick.wav", b"RIFF-NEW")
    try:
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        dest = tmp_path / "managed"
        dest.mkdir()
        (dest / "kick.wav").write_bytes(b"RIFF-OLD")
        plan = context.file_operation_service.plan_copy([samples[0].id], dest)

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_file_operation_plan(plan)

        resolve = window.findChild(QPushButton, "importReviewResolveButton")
        assert resolve is not None
        qtbot.mouseClick(resolve, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S13"

        conflicts = window.findChild(QWidget, "conflictsScreen")
        assert conflicts is not None
        default_policy = window.findChild(QLabel, "conflictsDefaultPolicy")
        assert default_policy is not None
        assert "never silent overwrite" in default_policy.text().lower()

        keep_both_all = window.findChild(QPushButton, "conflictsKeepBothAllButton")
        assert keep_both_all is not None
        qtbot.mouseClick(keep_both_all, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        apply = window.findChild(QPushButton, "conflictsApplyButton")
        assert apply is not None
        qtbot.mouseClick(apply, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

        assert window.current_screen_id() == "S12"
        execute = window.findChild(QPushButton, "importReviewExecuteButton")
        assert execute is not None
        assert execute.isEnabled()
        item_list = window.findChild(QListWidget, "importReviewItemList")
        assert item_list is not None
        assert "keep both" in item_list.item(0).text().lower()
        assert window.import_review.plan is not None
        assert not window.import_review.plan.unresolved_conflicts()
        assert window.import_review.plan.items[0].conflict_action is ConflictAction.KEEP_BOTH
    finally:
        context.close()


def test_reference_plan_states_plain_language_without_destination(
    qtbot: object, tmp_path: Path
) -> None:
    context = AppContext.open_temp(tmp_path / "s12-ref")
    pack = tmp_path / "pack"
    audio = _write_audio(pack, "rim.wav", b"RIFF-RIM")
    before = audio.read_bytes()
    try:
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        plan = context.file_operation_service.plan_reference([samples[0].id])

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_file_operation_plan(plan)
        operation = window.findChild(QLabel, "importReviewOperation")
        assert operation is not None
        assert "Reference" in operation.text()
        destination = window.findChild(QLabel, "importReviewDestination")
        assert destination is not None
        assert "none" in destination.text().lower() or "Reference" in destination.text()
        execute = window.findChild(QPushButton, "importReviewExecuteButton")
        assert execute is not None
        assert execute.isEnabled()
        qtbot.mouseClick(execute, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
        assert window.current_screen_id() == "S16"
        assert audio.read_bytes() == before
    finally:
        context.close()
