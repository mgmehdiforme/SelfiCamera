"""Design tokens and Qt stylesheets for SelfiCamera."""

from __future__ import annotations

BG = "#121318"
SURFACE = "#1A1C23"
SURFACE_2 = "#22252E"
SURFACE_3 = "#2B2F3A"
BORDER = "rgba(255, 255, 255, 18)"
BORDER_STRONG = "rgba(255, 255, 255, 34)"
TEXT = "#ECEDF1"
TEXT_MUTED = "#9AA0AE"
TEXT_FAINT = "#6B7180"
ACCENT = "#7C5CFF"
ACCENT_HOVER = "#9479FF"
ACCENT_SOFT = "rgba(124, 92, 255, 40)"
SUCCESS = "#22C55E"
WARNING = "#F5B83D"
DANGER = "#FF5C6C"

FONT_STACK = '"Inter", "Cantarell", "Ubuntu", "Noto Sans", "DejaVu Sans", sans-serif'

APP_STYLESHEET = f"""
QWidget#SettingsWindow {{
    background-color: {BG};
}}
QWidget {{
    color: {TEXT};
    font-family: {FONT_STACK};
    font-size: 13px;
}}
QLabel#PageTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#PageSubtitle {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#SectionTitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#Hint {{
    color: {TEXT_FAINT};
    font-size: 12px;
}}
QLabel#Value {{
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#Badge {{
    background: {ACCENT_SOFT};
    color: {ACCENT_HOVER};
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#BadgeWarn {{
    background: rgba(245, 184, 61, 30);
    color: {WARNING};
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}}
QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QListWidget#Nav {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px;
}}
QListWidget#Nav::item {{
    color: {TEXT_MUTED};
    padding: 9px 10px;
    border-radius: 8px;
    margin: 1px 0px;
}}
QListWidget#Nav::item:hover {{
    background-color: {SURFACE_2};
    color: {TEXT};
}}
QListWidget#Nav::item:selected {{
    background-color: {SURFACE_3};
    color: {TEXT};
}}
QWidget#Sidebar {{
    background-color: {SURFACE};
    border-right: 1px solid {BORDER};
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {SURFACE_3};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QPushButton {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {SURFACE_3};
    border-color: {BORDER_STRONG};
}}
QPushButton:pressed {{
    background-color: {ACCENT_SOFT};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
}}
QPushButton#Primary {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: white;
}}
QPushButton#Primary:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#Danger {{
    color: {DANGER};
}}
QPushButton#Segment {{
    background-color: transparent;
    border: none;
    border-radius: 7px;
    padding: 6px 8px;
    color: {TEXT_MUTED};
}}
QPushButton#Segment:hover {{
    color: {TEXT};
    background-color: {SURFACE_3};
}}
QPushButton#Segment:checked {{
    background-color: {ACCENT};
    color: white;
}}
QWidget#SegmentedTrack {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
}}
QComboBox, QLineEdit {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 18px;
}}
QComboBox:hover, QLineEdit:hover {{
    border-color: {BORDER_STRONG};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER_STRONG};
    selection-background-color: {SURFACE_3};
    outline: none;
    padding: 4px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {SURFACE_3};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: white;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #DCD3FF;
}}
QListWidget#SceneList {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}
QListWidget#SceneList::item {{
    padding: 8px;
    border-radius: 6px;
}}
QListWidget#SceneList::item:selected {{
    background-color: {SURFACE_3};
    color: {TEXT};
}}
QToolTip {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    padding: 4px 6px;
    border-radius: 6px;
}}
"""

MENU_STYLESHEET = f"""
QMenu {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
    padding: 6px;
    font-family: {FONT_STACK};
    font-size: 13px;
}}
QMenu::item {{
    padding: 7px 26px 7px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {SURFACE_3};
}}
QMenu::item:disabled {{
    color: {TEXT_FAINT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 5px 8px;
}}
QMenu::indicator {{
    width: 14px;
    height: 14px;
    left: 6px;
}}
"""

HUD_STYLESHEET = """
QWidget#Hud {
    background-color: rgba(18, 19, 24, 215);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 17px;
}
QToolButton {
    background: transparent;
    border: none;
    border-radius: 13px;
    padding: 3px;
}
QToolButton:hover {
    background-color: rgba(255, 255, 255, 36);
}
QToolButton:pressed, QToolButton:checked {
    background-color: rgba(124, 92, 255, 150);
}
"""
