"""Colour tokens and the global stylesheet (iOS / macOS inspired)."""

from __future__ import annotations

BG        = "#F2F2F7"
CARD      = "#FFFFFF"
TEXT      = "#1C1C1E"
TEXT2     = "#3C3C43"
MUTED     = "#8E8E93"
SEP       = "#E5E5EA"
SEP_SOFT  = "rgba(60,60,67,0.08)"
FILL      = "#F2F2F7"
FILL2     = "#E9E9EE"

BLUE      = "#007AFF"
BLUE_DARK = "#0A66D0"
GREEN     = "#34C759"
RED       = "#FF3B30"
ORANGE    = "#FF9500"
PURPLE    = "#AF52DE"
PINK      = "#FF2D55"
TEAL      = "#30B0C7"
INDIGO    = "#5856D6"

RADIUS = 14

FONT = ('"SF Pro Text", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", '
        '"Microsoft YaHei", "Helvetica Neue", Arial, sans-serif')


def qss() -> str:
    r = RADIUS
    return f"""
* {{
    font-family: {FONT};
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}

/* window surface -------------------------------------------------------- */
QWidget#Root {{
    background: {BG};
    border-radius: {r}px;
}}
QFrame#TitleBar {{
    background: {CARD};
    border: none;
    border-bottom: 1px solid {SEP};
    border-top-left-radius: {r}px;
    border-top-right-radius: {r}px;
}}
QFrame#BottomBar {{
    background: {CARD};
    border: none;
    border-top: 1px solid {SEP};
    border-bottom-left-radius: {r}px;
    border-bottom-right-radius: {r}px;
}}

/* cards ----------------------------------------------------------------- */
QFrame#Card {{
    background: {CARD};
    border: 1px solid {SEP_SOFT};
    border-radius: 12px;
}}

/* text ------------------------------------------------------------------ */
QLabel#H1 {{ font-size: 15px; font-weight: 700; }}
QLabel#H2 {{ font-size: 13px; font-weight: 600; }}
QLabel#Section {{ font-size: 11px; font-weight: 700; color: {MUTED}; letter-spacing: 0.6px; }}
QLabel#Field {{ font-size: 12px; color: {TEXT2}; }}
QLabel#Muted {{ font-size: 11px; color: {MUTED}; }}
QLabel#Badge {{
    background: {FILL}; border: 1px solid {SEP}; border-radius: 8px;
    padding: 3px 9px; color: {TEXT2}; font-size: 11px;
}}
QLabel#Chip {{
    background: rgba(0,122,255,0.10); border: 1px solid rgba(0,122,255,0.16);
    border-radius: 8px; padding: 4px 9px; color: {BLUE_DARK};
    font-size: 11px; font-weight: 600;
}}
QLabel#ItemTitle {{ font-size: 13px; font-weight: 500; }}
QLabel#ItemSub {{ font-size: 10px; color: {MUTED}; }}

/* buttons --------------------------------------------------------------- */
QPushButton {{
    background: {FILL}; border: 1px solid transparent; border-radius: 9px;
    padding: 7px 14px; font-size: 13px; font-weight: 500;
}}
QPushButton:hover {{ background: {FILL2}; }}
QPushButton:pressed {{ background: #DEDEE3; }}
QPushButton:disabled {{ color: {MUTED}; background: {FILL}; }}

QPushButton#Primary {{
    background: {BLUE}; color: #FFFFFF; font-weight: 600;
    padding: 10px 18px; border-radius: 11px;
}}
QPushButton#Primary:hover {{ background: {BLUE_DARK}; }}
QPushButton#Primary:disabled {{ background: #B9D6F5; color: #FFFFFF; }}

QPushButton#Tint {{
    background: rgba(0,122,255,0.11); color: {BLUE_DARK}; font-weight: 600;
}}
QPushButton#Tint:hover {{ background: rgba(0,122,255,0.19); }}
QPushButton#Tint:disabled {{ background: {FILL}; color: {MUTED}; }}

QPushButton#Ghost {{ background: transparent; color: {BLUE}; font-weight: 600; padding: 6px 10px; }}
QPushButton#Ghost:hover {{ background: rgba(0,122,255,0.10); }}

QPushButton#Danger {{ background: rgba(255,59,48,0.10); color: {RED}; font-weight: 600; }}
QPushButton#Danger:hover {{ background: rgba(255,59,48,0.18); }}

QToolButton {{
    background: transparent; border: 1px solid transparent; border-radius: 8px;
    padding: 6px 10px; color: {TEXT2}; font-weight: 500;
}}
QToolButton:hover {{ background: {FILL}; }}

/* segmented control ----------------------------------------------------- */
QFrame#Segmented {{ background: {FILL2}; border: none; border-radius: 10px; }}
QFrame#Segmented QToolButton {{
    background: transparent; border: none; border-radius: 8px;
    padding: 5px 10px; color: {TEXT2}; font-weight: 500;
}}
QFrame#Segmented QToolButton:hover:!checked {{ color: {TEXT}; }}
QFrame#Segmented QToolButton:checked {{ background: {CARD}; color: {TEXT}; font-weight: 600; }}
QFrame#Segmented QToolButton:disabled {{ color: #C7C7CC; }}

/* inputs ---------------------------------------------------------------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {CARD}; border: 1px solid {SEP}; border-radius: 9px;
    padding: 7px 9px; min-height: 18px;
    selection-background-color: rgba(0,122,255,0.25);
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {BLUE}; }}
QLineEdit:read-only {{ background: {FILL}; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 18px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{ width: 15px; border: none; background: transparent; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid {MUTED};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none; width: 0; height: 0;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {MUTED};
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{
    image: none; width: 0; height: 0; margin-right: 6px;
    border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {MUTED};
}}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {SEP}; border-radius: 9px; padding: 4px;
    selection-background-color: rgba(0,122,255,0.14); selection-color: {TEXT}; outline: none;
}}

QCheckBox {{ spacing: 8px; color: {TEXT2}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid #C7C7CC; background: {CARD};
}}
QCheckBox::indicator:checked {{ background: {BLUE}; border: 1px solid {BLUE}; }}

/* scrolling ------------------------------------------------------------- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QStackedWidget {{ background: transparent; }}
QTextBrowser#Result {{ background: transparent; border: none; padding: 0px; }}

QPlainTextEdit#Log {{
    background: #FFFFFF; border: 1px solid {SEP_SOFT}; border-radius: 10px;
    padding: 8px 9px; color: {TEXT2};
    font-family: "Cascadia Mono", "Consolas", "SFMono-Regular", monospace;
    font-size: 11px;
}}

QTabWidget#PanelTabs::pane {{
    border: 1px solid {SEP_SOFT}; border-radius: 12px; background: {CARD};
    top: -1px;
}}
QTabWidget#PanelTabs QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 6px 14px;
    margin-right: 4px; border: none; border-bottom: 2px solid transparent;
    font-size: 12px; font-weight: 600;
}}
QTabWidget#PanelTabs QTabBar::tab:selected {{ color: {BLUE_DARK}; border-bottom: 2px solid {BLUE}; }}
QTabWidget#PanelTabs QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: rgba(60,60,67,0.20); border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(60,60,67,0.32); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: rgba(60,60,67,0.20); border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

/* list ------------------------------------------------------------------ */
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ background: transparent; border-radius: 10px; margin: 2px 0px; }}
QListWidget::item:hover {{ background: rgba(0,0,0,0.035); }}
QListWidget::item:selected {{ background: rgba(0,122,255,0.13); }}

/* progress -------------------------------------------------------------- */
QProgressBar {{ background: {SEP}; border: none; border-radius: 3px; height: 5px; color: transparent; }}
QProgressBar::chunk {{ background: {BLUE}; border-radius: 3px; }}

QToolTip {{
    background: rgba(28,28,30,0.92); color: #FFFFFF;
    border: none; border-radius: 8px; padding: 6px 10px;
}}
"""


__all__ = ["qss", "BG", "CARD", "TEXT", "TEXT2", "MUTED", "SEP", "FILL", "FILL2",
           "BLUE", "BLUE_DARK", "GREEN", "RED", "ORANGE", "PURPLE", "PINK",
           "TEAL", "INDIGO", "RADIUS", "FONT"]
