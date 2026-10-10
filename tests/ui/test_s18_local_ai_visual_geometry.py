"""Focused offscreen contrast and geometry assertions for S18 Local AI card."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea, QWidget

from koffer.app_context import AppContext
from koffer.ui.shell import MainWindow
from koffer.ui.tokens import CANVAS, MUTED, SURFACE_2, TEXT


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
    assert color.name().lower() != "#000000"
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


def test_s18_local_ai_contrast_and_min_geometry(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s18-visual")
    try:
        window = MainWindow(context, directory_picker=lambda _p: None, restore_geometry=False)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S18")
        assert window.current_screen_id() == "S18"

        action_names = (
            "settingsLocalAiInstallButton",
            "settingsLocalAiEnableButton",
            "settingsLocalAiBackfillButton",
            "settingsLocalAiRebuildSuggestionsButton",
            "settingsLocalAiRebuildSimilarityButton",
        )

        for width, height in ((1440, 900), (1180, 720)):
            _settle(window, qtbot, width, height)
            screen = window.findChild(QWidget, "settingsLibraryScreen")
            body = window.findChild(QWidget, "settingsLibraryBody")
            scroll = window.findChild(QScrollArea, "settingsLibraryScroll")
            card = window.findChild(QWidget, "settingsLocalAiCard")
            assert screen is not None and body is not None and card is not None
            assert scroll is not None

            concurrency_label = window.findChild(QLabel, "settingsAnalysisConcurrencyLabel")
            cache_label = window.findChild(QLabel, "settingsCacheLimitLabel")
            assert concurrency_label is not None and cache_label is not None
            _assert_readable(concurrency_label, against=QColor(CANVAS), minimum=4.5)
            _assert_readable(cache_label, against=QColor(CANVAS), minimum=4.5)
            assert (
                concurrency_label.palette().color(concurrency_label.foregroundRole()).name().lower()
                != "#000000"
            )

            heading = window.findChild(QLabel, "settingsLocalAiHeading")
            headline = window.findChild(QLabel, "settingsLocalAiHeadline")
            detail = window.findChild(QLabel, "settingsLocalAiDetail")
            privacy = window.findChild(QLabel, "settingsLocalAiPrivacy")
            assert heading is not None and headline is not None
            assert detail is not None and privacy is not None
            _assert_readable(heading, against=QColor(SURFACE_2), minimum=4.5)
            _assert_readable(headline, against=QColor(SURFACE_2), minimum=4.5)
            _assert_readable(detail, against=QColor(SURFACE_2), minimum=3.0)
            _assert_readable(privacy, against=QColor(SURFACE_2), minimum=3.0)
            assert MUTED.lower() in (detail.styleSheet() or "").lower()
            assert TEXT.lower() in (heading.styleSheet() or "").lower()

            primary = window.findChild(QWidget, "settingsLocalAiPrimaryActions")
            rebuild = window.findChild(QWidget, "settingsLocalAiRebuildActions")
            assert primary is not None and rebuild is not None
            _assert_fully_inside(primary, card)
            _assert_fully_inside(rebuild, card)
            _assert_fully_inside(card, body)
            _assert_no_overlap(primary, rebuild)

            actions = []
            for name in action_names:
                button = window.findChild(QPushButton, name)
                assert button is not None, name
                assert button.isVisible()
                assert button.height() >= 28
                assert button.width() >= 120
                # Contained by the card/body; scroll viewport may crop until scrolled.
                _assert_fully_inside(button, card)
                _assert_fully_inside(button, body)
                scroll.ensureWidgetVisible(button)
                QApplication.processEvents()
                assert button.visibleRegion().boundingRect().height() >= 20
                actions.append(button)

            for index, left in enumerate(actions):
                for right in actions[index + 1 :]:
                    _assert_no_overlap(left, right)

            assert len(actions) == len(action_names)
            # Vertical stack: each action sits strictly below the previous.
            for upper, lower in zip(actions[:-1], actions[1:], strict=True):
                assert _widget_global_rect(upper).bottom() <= _widget_global_rect(lower).top()
    finally:
        context.close()
