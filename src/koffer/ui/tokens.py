"""Design tokens from docs/13-ui-design-system.md."""

from __future__ import annotations

CANVAS = "#0B0D0F"
SURFACE_1 = "#121518"
SURFACE_2 = "#181C20"
SURFACE_3 = "#20252A"
BORDER = "#30363D"
TEXT = "#F1F4F6"
MUTED = "#98A2AD"
FAINT = "#66717C"
CLAY = "#CF8652"
CLAY_BRIGHT = "#E7A36F"
GREEN = "#67B983"
YELLOW = "#D7B65E"
RED = "#D36B6B"
BLUE = "#6FA3D8"

SHELL_STYLESHEET = f"""
QWidget#kofferShell {{
    background-color: {CANVAS};
    color: {TEXT};
}}
QWidget#kofferTopBar {{
    background-color: #0F1114;
    border-bottom: 1px solid {BORDER};
}}
QLabel#topBarBrand {{
    color: {CLAY_BRIGHT};
    font-size: 13px;
    font-weight: 800;
}}
QLabel#topBarWorkspace {{
    color: {FAINT};
    font-size: 11px;
}}
QLabel#topBarStatus {{
    color: {GREEN};
    font-size: 11px;
    font-weight: 700;
}}
QWidget#kofferNavRail {{
    background-color: {SURFACE_1};
    border-right: 1px solid {BORDER};
}}
QLabel#navSectionLabel {{
    color: {FAINT};
    font-size: 10px;
    font-weight: 700;
    padding: 12px 8px 2px 8px;
}}
QLabel#navEmptyText {{
    color: {FAINT};
    font-size: 11px;
    padding: 4px 12px 8px 12px;
}}
QPushButton {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 12px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {SURFACE_3};
    border-color: #3A4148;
}}
QPushButton:disabled {{
    color: {FAINT};
    background-color: {SURFACE_1};
}}
QPushButton:focus {{
    outline: none;
    border: 1px solid {CLAY_BRIGHT};
}}
QPushButton#navButton {{
    background-color: transparent;
    color: {MUTED};
    border: none;
    border-radius: 5px;
    text-align: left;
    padding: 8px 12px;
    min-height: 32px;
}}
QPushButton#navButton:checked {{
    background-color: {SURFACE_3};
    color: {TEXT};
    border-left: 2px solid {CLAY};
}}
QPushButton#navButton:hover {{
    background-color: {SURFACE_2};
    color: {TEXT};
}}
QPushButton#navButton:focus {{
    outline: none;
    border: 1px solid {CLAY_BRIGHT};
}}
QPushButton#savedSearchNavButton {{
    background-color: transparent;
    color: {MUTED};
    border: none;
    border-radius: 5px;
    text-align: left;
    padding: 6px 12px 6px 20px;
    min-height: 26px;
}}
QPushButton#savedSearchNavButton:hover,
QPushButton#savedSearchNavButton:checked {{
    background-color: {SURFACE_2};
    color: {TEXT};
}}
QPushButton#primaryButton,
QPushButton[class="primaryButton"] {{
    background-color: {CLAY};
    color: {CANVAS};
    border: none;
    border-radius: 5px;
    padding: 8px 16px;
    min-height: 32px;
    font-weight: 600;
}}
QPushButton#primaryButton:hover,
QPushButton[class="primaryButton"]:hover {{
    background-color: {CLAY_BRIGHT};
}}
QPushButton#secondaryButton,
QPushButton[class="secondaryButton"] {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 8px 16px;
    min-height: 32px;
}}
QLabel#pageTitle {{
    color: {TEXT};
    font-size: 22px;
    font-weight: 600;
}}
QLabel#bodyText {{
    color: {MUTED};
    font-size: 13px;
}}
QLabel#promiseTitle {{
    color: {TEXT};
    font-size: 14px;
    font-weight: 600;
}}
QLabel#statusOnline {{
    color: {GREEN};
    font-weight: 600;
}}
QLabel#statusOffline {{
    color: {YELLOW};
    font-weight: 600;
}}
QLabel#statusDisabled {{
    color: {FAINT};
    font-weight: 600;
}}
QLabel#statusError {{
    color: {RED};
    font-weight: 600;
}}
QListWidget#sourceList {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT};
    outline: none;
}}
QListWidget#sourceList::item {{
    padding: 10px 12px;
    border-bottom: 1px solid {BORDER};
}}
QListWidget#sourceList::item:selected {{
    background-color: {SURFACE_3};
    border-left: 2px solid {CLAY};
}}
QFrame#promiseCard {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QWidget#inspectorPanel {{
    background-color: {SURFACE_1};
    border-left: 1px solid {BORDER};
}}
QWidget#transportBar {{
    background-color: #101316;
    border-top: 1px solid {BORDER};
}}
QPushButton#transportPlayButton,
QPushButton#transportStopButton {{
    background-color: transparent;
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QPushButton#transportPlayButton:hover,
QPushButton#transportStopButton:hover {{
    border-color: {CLAY_BRIGHT};
    color: {CLAY_BRIGHT};
}}
QLabel#transportTitle {{
    color: {TEXT};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#transportTime,
QLabel#transportGain {{
    color: {MUTED};
    font-size: 11px;
}}
QSlider#transportSeek::groove:horizontal {{
    height: 3px;
    background: {BORDER};
    border-radius: 1px;
}}
QSlider#transportSeek::sub-page:horizontal {{
    background: {CLAY};
}}
QSlider#transportSeek::handle:horizontal {{
    width: 10px;
    margin: -4px 0;
    border-radius: 5px;
    background: {CLAY_BRIGHT};
}}
QWidget#filterPanel {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QLabel#sectionLabel {{
    color: {FAINT};
    font-size: 10px;
    font-weight: 700;
}}
QLabel#inspectorTitle {{
    color: {TEXT};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#waveformSummary {{
    color: {MUTED};
    font-size: 11px;
}}
QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {{
    background-color: {SURFACE_1};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    min-height: 26px;
    selection-background-color: {CLAY};
    selection-color: {CANVAS};
}}
QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {{
    border-color: {CLAY_BRIGHT};
}}
QLineEdit#librarySearchField {{
    padding: 6px 10px;
    min-height: 28px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_1};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {SURFACE_3};
}}
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {SURFACE_1};
}}
QCheckBox::indicator:checked {{
    background-color: {CLAY};
    border-color: {CLAY_BRIGHT};
}}
QTableView#sampleTable {{
    background-color: {SURFACE_1};
    alternate-background-color: #14181C;
    color: {TEXT};
    gridline-color: #252B30;
    border: 1px solid {BORDER};
    selection-background-color: {SURFACE_3};
    selection-color: {TEXT};
}}
QTableView#sampleTable:focus {{
    border: 1px solid {CLAY_BRIGHT};
}}
QListWidget:focus {{
    border: 1px solid {CLAY_BRIGHT};
}}
QHeaderView::section {{
    background-color: {SURFACE_1};
    color: {FAINT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
    font-size: 10px;
    font-weight: 700;
}}
QFrame#provenanceTechnical {{
    background-color: {SURFACE_1};
    border: 1px solid {BLUE};
    border-left: 3px solid {BLUE};
    border-radius: 6px;
}}
QFrame#provenanceEmbedded {{
    background-color: {SURFACE_1};
    border: 1px solid {GREEN};
    border-left: 3px solid {GREEN};
    border-radius: 6px;
}}
QFrame#provenanceConfirmed {{
    background-color: {SURFACE_1};
    border: 1px solid {CLAY};
    border-left: 3px solid {CLAY};
    border-radius: 6px;
}}
QFrame#provenanceSuggested {{
    background-color: {SURFACE_1};
    border: 1px solid {YELLOW};
    border-left: 3px solid {YELLOW};
    border-radius: 6px;
}}
QFrame#provenanceTags {{
    background-color: {SURFACE_1};
    border: 1px solid {CLAY_BRIGHT};
    border-left: 3px solid {CLAY_BRIGHT};
    border-radius: 6px;
}}
QLabel#provenanceHeading {{
    color: {TEXT};
    font-size: 11px;
    font-weight: 700;
}}
QWidget#contentStatePanel {{
    background-color: {SURFACE_1};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QMenuBar {{
    background-color: {CANVAS};
    color: {MUTED};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item {{
    padding: 4px 8px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background-color: {SURFACE_2};
    color: {TEXT};
}}
QMenu {{
    background-color: {SURFACE_1};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QMenu::item {{
    padding: 6px 28px 6px 10px;
}}
QMenu::item:selected {{
    background-color: {SURFACE_3};
}}
QScrollBar:vertical {{
    background: {CANVAS};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE_3};
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar:horizontal {{
    background: {CANVAS};
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {SURFACE_3};
    min-width: 24px;
    border-radius: 5px;
}}
"""
