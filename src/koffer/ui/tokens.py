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
QWidget#kofferNavRail {{
    background-color: {SURFACE_1};
    border-right: 1px solid {BORDER};
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
QPushButton#primaryButton {{
    background-color: {CLAY};
    color: {CANVAS};
    border: none;
    border-radius: 5px;
    padding: 8px 16px;
    min-height: 32px;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background-color: {CLAY_BRIGHT};
}}
QPushButton#secondaryButton {{
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
"""
