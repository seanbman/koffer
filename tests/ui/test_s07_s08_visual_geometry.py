"""Focused offscreen contrast and geometry assertions for S07/S08 visual acceptance."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QToolButton, QWidget

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav, write_tagged_wav
from koffer.domain import JobState
from koffer.repositories import SampleRepository
from koffer.ui.shell import MainWindow
from koffer.ui.tokens import MUTED, SURFACE_1, SURFACE_2, TEXT
from koffer.ui.widgets.workbench_waveform import WorkbenchWaveformView


def _srgb_channel(value: float) -> float:
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: QColor) -> float:
    r = _srgb_channel(color.redF())
    g = _srgb_channel(color.greenF())
    b = _srgb_channel(color.blueF())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: QColor, bg: QColor) -> float:
    lighter = max(_relative_luminance(fg), _relative_luminance(bg))
    darker = min(_relative_luminance(fg), _relative_luminance(bg))
    return (lighter + 0.05) / (darker + 0.05)


def _stylesheet_color(widget: QWidget, *, property_name: str = "color") -> QColor | None:
    sheet = widget.styleSheet() or ""
    match = re.search(rf"{property_name}\s*:\s*(#[0-9A-Fa-f]{{6}})", sheet)
    if match is None:
        parent = widget.parentWidget()
        while parent is not None:
            parent_sheet = parent.styleSheet() or ""
            object_name = widget.objectName()
            if object_name:
                scoped = re.search(
                    rf"QLabel#{re.escape(object_name)}\s*\{{[^}}]*{property_name}\s*:\s*"
                    rf"(#[0-9A-Fa-f]{{6}})",
                    parent_sheet,
                )
                if scoped is not None:
                    return QColor(scoped.group(1))
            match = re.search(rf"{property_name}\s*:\s*(#[0-9A-Fa-f]{{6}})", parent_sheet)
            if match is not None:
                return QColor(match.group(1))
            parent = parent.parentWidget()
        return None
    return QColor(match.group(1))


def _assert_readable(widget: QWidget, *, against: QColor, minimum: float = 4.5) -> None:
    color = _stylesheet_color(widget)
    assert color is not None, f"{widget.objectName() or widget} missing explicit color"
    ratio = _contrast_ratio(color, against)
    assert ratio >= minimum, (
        f"{widget.objectName() or type(widget).__name__} contrast {ratio:.2f} < {minimum} "
        f"({color.name()} on {against.name()})"
    )


def _widget_global_rect(widget: QWidget) -> QRect:
    top_left = widget.mapToGlobal(widget.rect().topLeft())
    return QRect(top_left, widget.rect().size())


def _assert_fully_inside(child: QWidget, parent: QWidget) -> None:
    parent_rect = _widget_global_rect(parent)
    child_rect = _widget_global_rect(child)
    assert child_rect.width() > 0 and child_rect.height() > 0, child.objectName()
    assert parent_rect.contains(child_rect), (
        f"{child.objectName()} {child_rect.getRect()} not inside "
        f"{parent.objectName()} {parent_rect.getRect()}"
    )


def _assert_no_overlap(left: QWidget, right: QWidget) -> None:
    assert not _widget_global_rect(left).intersects(_widget_global_rect(right)), (
        f"{left.objectName()} overlaps {right.objectName()}"
    )


def _settle(window: MainWindow, qtbot: object, width: int, height: int) -> None:
    window.resize(width, height)
    window.show()
    qtbot.waitExposed(window)  # type: ignore[attr-defined]
    QApplication.processEvents()
    qtbot.wait(50)  # type: ignore[attr-defined]
    QApplication.processEvents()


def test_s07_dark_theme_card_contrast_and_min_geometry(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s07-visual")
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

        window = MainWindow(context, directory_picker=lambda _p: None, restore_geometry=False)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window._open_sample_detail(str(sample.id))  # noqa: SLF001
        assert window.current_screen_id() == "S07"

        for width, height in ((1440, 900), (1180, 720)):
            _settle(window, qtbot, width, height)
            screen = window.findChild(QWidget, "sampleDetailScreen")
            assert screen is not None

            cards = (
                "sampleDetailClassification",
                "sampleDetailSuggestions",
                "sampleDetailTagsCollections",
                "sampleDetailEditSummary",
            )
            for card_name in cards:
                card = screen.findChild(QWidget, card_name)
                assert card is not None, card_name
                heading = card.findChild(QLabel, f"{card_name}Heading")
                body = card.findChild(QLabel, f"{card_name}Body")
                assert heading is not None and body is not None
                _assert_readable(heading, against=QColor(SURFACE_1), minimum=3.0)
                _assert_readable(body, against=QColor(SURFACE_1), minimum=4.5)
                body_color = _stylesheet_color(body)
                assert body_color is not None
                assert body_color.name().lower() != "#000000"
                assert card.width() >= 240
                assert card.height() >= 40

            for disclosure_name in ("sampleDetailFileDetails", "sampleDetailAnalysisDetails"):
                disclosure = screen.findChild(QWidget, disclosure_name)
                assert disclosure is not None
                toggle = disclosure.findChild(QToolButton, f"{disclosure_name}Toggle")
                body = disclosure.findChild(QLabel, f"{disclosure_name}Body")
                assert toggle is not None and body is not None
                _assert_readable(toggle, against=QColor(SURFACE_2), minimum=4.5)
                toggle.setChecked(True)
                QApplication.processEvents()
                _assert_readable(body, against=QColor(SURFACE_2), minimum=3.0)
                assert MUTED.lower() in (body.styleSheet() or "").lower()
                assert disclosure.width() >= 240

            identity = screen.findChild(QLabel, "sampleDetailIdentity")
            assert identity is not None
            _assert_readable(identity, against=QColor(SURFACE_1), minimum=4.5)

            for action_name in (
                "editSoundButton",
                "editMetadataButton",
                "findSimilarButton",
                "addToCollectionButton",
            ):
                button = screen.findChild(QPushButton, action_name)
                assert button is not None
                assert button.isVisible()
                _assert_fully_inside(button, screen)
                assert button.height() >= 28
                assert button.width() >= 64
    finally:
        context.close()


def test_s08_workbench_geometry_at_reference_and_minimum(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s08-visual")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "tone.wav", duration_s=0.5)
    try:
        source = context.source_service.add_source(pack)
        job = context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0)
        assert job.state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )

        window = MainWindow(context, directory_picker=lambda _p: None, restore_geometry=False)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_sample_preparation(samples[0].id)
        assert window.current_screen_id() == "S08"

        for width, height, min_wave_h in ((1440, 900, 220), (1180, 720, 160)):
            _settle(window, qtbot, width, height)
            screen = window.findChild(QWidget, "samplePreparationScreen")
            assert screen is not None

            waveform = screen.findChild(WorkbenchWaveformView, "samplePreparationWaveform")
            dock = screen.findChild(QWidget, "samplePreparationControlDock")
            numeric = screen.findChild(QWidget, "samplePreparationNumericGroup")
            assert waveform is not None
            assert dock is not None
            assert numeric is not None
            assert waveform.height() >= min_wave_h
            assert dock.width() >= 280
            _assert_fully_inside(waveform, screen)
            _assert_fully_inside(dock, screen)
            _assert_no_overlap(waveform, dock)

            for control_name in (
                "samplePreparationTrimStart",
                "samplePreparationFadeIn",
                "samplePreparationGain",
                "samplePreparationPreviewLoop",
                "samplePreparationZoomInButton",
                "samplePreparationZoomOutButton",
                "samplePreparationFitButton",
            ):
                control = screen.findChild(QWidget, control_name)
                assert control is not None, control_name
                assert control.width() > 0 and control.height() > 0
                # Numeric dock may scroll; require a usable laid-out or hinted size.
                assert max(control.height(), control.sizeHint().height()) >= 16

            for action_name in (
                "samplePreparationSaveButton",
                "samplePreparationPreviewButton",
                "samplePreparationExportButton",
            ):
                action = screen.findChild(QPushButton, action_name)
                assert action is not None, action_name
                assert action.isVisible()
                _assert_fully_inside(action, screen)
                assert action.height() >= 28
                # Footer actions must not collide with the waveform plane.
                _assert_no_overlap(action, waveform)

            # Labels in the dock remain explicitly light on dark.
            title = screen.findChild(QLabel, "pageTitle")
            assert title is not None
            assert (
                TEXT.lower() in (title.styleSheet() or "").lower()
                or title.palette().color(title.foregroundRole()).name().lower() != "#000000"
            )
            trim_state = screen.findChild(QLabel, "samplePreparationTrimState")
            assert trim_state is not None
            _assert_readable(trim_state, against=QColor(SURFACE_1), minimum=4.5)
    finally:
        context.close()
