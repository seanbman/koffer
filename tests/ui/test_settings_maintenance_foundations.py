"""Offscreen pytest-qt coverage for S15/S17–S21 foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QListWidget,
    QPushButton,
    QWidget,
)

from koffer.app_context import AppContext
from koffer.domain.enums import SampleAvailability, SourceStatus
from koffer.domain.ids import new_entity_id
from koffer.domain.models import Sample, Source
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.ui.shell import MainWindow

def test_s15_s17_s21_reachable_from_shell_navigation(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "phase12-ui")
    try:
        now = utc_now_iso()
        source = Source(
            id=new_entity_id(),
            display_name="Offline Drive",
            root_path=str((tmp_path / "missing-root").resolve()),
            enabled=True,
            recursive=True,
            status=SourceStatus.OFFLINE,
            created_at=now,
            updated_at=now,
        )
        conn = context.connection_factory.get_connection()
        SourceRepository(conn).create(source)
        SampleRepository(conn).create(
            Sample(
                id=new_entity_id(),
                source_id=source.id,
                relative_path="gone.wav",
                normalized_path_cache="gone.wav",
                filename="gone.wav",
                extension="wav",
                size_bytes=1,
                mtime_ns=1,
                availability=SampleAvailability.MISSING,
                favorite=False,
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
        )

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]

        screens = {
            "S15": "offlineRecoveryScreen",
            "S17": "settingsGeneralScreen",
            "S18": "settingsLibraryScreen",
            "S19": "settingsAudioScreen",
            "S20": "maintenanceScreen",
            "S21": "aboutDiagnosticsScreen",
        }
        for screen_id, object_name in screens.items():
            window.navigate(screen_id)
            assert window.current_screen_id() == screen_id
            widget = window.findChild(QWidget, object_name)
            assert widget is not None

        # S15 lists distinct offline/missing issues.
        window.navigate("S15")
        issue_list = window.findChild(QListWidget, "offlineRecoveryList")
        assert issue_list is not None
        texts = "\n".join(issue_list.item(i).text() for i in range(issue_list.count()))
        assert "source_offline" in texts
        assert "file_missing" in texts
        assert "samples and metadata are kept" in texts.lower()
        assert "missing under" in texts.lower()

        # S17 keeps destructive confirmation locked.
        window.navigate("S17")
        destructive = window.findChild(QWidget, "settingsConfirmDestructive")
        assert destructive is not None
        assert not destructive.isEnabled()  # type: ignore[attr-defined]

        # S20 exposes backup/restore/rebuild controls and preserve note.
        window.navigate("S20")
        assert window.findChild(QPushButton, "maintenanceBackupButton") is not None
        assert window.findChild(QPushButton, "maintenanceRestoreButton") is not None
        assert window.findChild(QPushButton, "maintenanceRebuildFilesystemButton") is not None
        note = window.findChild(QWidget, "maintenancePreserveNote")
        assert note is not None

        # S21 shows version + diagnostics export control.
        window.navigate("S21")
        version = window.findChild(QLabel, "aboutVersionLabel")
        assert version is not None
        assert "Koffer" in version.text()
        assert window.findChild(QPushButton, "aboutCreateDiagnosticsButton") is not None
    finally:
        context.close()


def test_s15_locate_file_repairs_missing_sample_without_moving_audio(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    context = AppContext.open_temp(tmp_path / "recovery-locate")
    root = tmp_path / "source"
    root.mkdir()
    replacement = root / "recovered.wav"
    replacement.write_bytes(b"RIFF-RECOVERED")
    now = utc_now_iso()
    source = Source(
        id=new_entity_id(),
        display_name="Recovery Source",
        root_path=str(root.resolve()),
        enabled=True,
        recursive=True,
        status=SourceStatus.ONLINE,
        created_at=now,
        updated_at=now,
    )
    sample = Sample(
        id=new_entity_id(),
        source_id=source.id,
        relative_path="missing.wav",
        normalized_path_cache="missing.wav",
        filename="missing.wav",
        extension="wav",
        size_bytes=1,
        mtime_ns=1,
        availability=SampleAvailability.MISSING,
        favorite=False,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    conn = context.connection_factory.get_connection()
    SourceRepository(conn).create(source)
    SampleRepository(conn).create(sample)

    try:
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S15")

        issues = window.findChild(QListWidget, "offlineRecoveryList")
        locate = window.findChild(QPushButton, "recoveryLocateFileButton")
        assert issues is not None
        assert locate is not None
        target_row = next(
            index
            for index in range(issues.count())
            if "file_missing" in issues.item(index).text()
        )
        issues.setCurrentRow(target_row)
        before = replacement.read_bytes()

        monkeypatch.setattr(  # type: ignore[attr-defined]
            QFileDialog,
            "getOpenFileName",
            lambda *_args, **_kwargs: (str(replacement), ""),
        )
        locate.click()

        repaired = SampleRepository(conn).get(sample.id)
        assert repaired is not None
        assert repaired.relative_path == "recovered.wav"
        assert repaired.filename == "recovered.wav"
        assert repaired.availability is SampleAvailability.ONLINE
        assert replacement.read_bytes() == before

        issue_text = "\n".join(
            issues.item(index).text() for index in range(issues.count())
        )
        assert "file_missing" not in issue_text
    finally:
        context.close()
