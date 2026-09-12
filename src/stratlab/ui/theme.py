"""Dark technical palette and stylesheet for StratLab.

`PALETTE` is the single source of truth for colour.  The stylesheet below is
generated from it, and the hand-painted widgets (timeline, video player) read
the same tokens so nothing drifts.
"""

# --- Design tokens -----------------------------------------------------------
#
# Grounds are near-neutral and very close together: separation comes from
# spacing and small luminance steps rather than from borders.  Colour is
# reserved for meaning (current / fastest / slower / incomplete).

PALETTE = {
    # Grounds
    "bg_window": "#0f1013",
    "bg_panel": "#15171a",
    "bg_raised": "#1c1f23",
    "bg_sunken": "#101215",
    "bg_video": "#08090a",
    # Hairlines — used sparingly
    "line": "#212429",
    "line_strong": "#2b2f35",
    # Text
    "text_hi": "#e7e9ec",
    "text_mid": "#959ca6",
    "text_lo": "#636a74",
    "text_faint": "#4a5058",
    # Accent — interactive / current position
    "accent": "#5b9bd5",
    "accent_hi": "#8fbde8",
    "accent_dim": "#2c445c",
    "accent_bg": "#1b2733",
    # Semantic
    "good": "#5cc98d",
    "good_dim": "#1c3a2c",
    "warn": "#d59a5e",
    "warn_dim": "#3a2e1c",
    "bad": "#d4776b",
    "bad_dim": "#3a2320",
}

MONO_FAMILY = '"Cascadia Mono", "Consolas", "JetBrains Mono", monospace'
UI_FAMILY = '"Segoe UI", system-ui, -apple-system, sans-serif'

P = PALETTE

DARK_STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {P['bg_window']};
    color: {P['text_hi']};
}}

QWidget {{
    background-color: transparent;
    color: {P['text_hi']};
    font-family: {UI_FAMILY};
    font-size: 12px;
}}

/* ---- Menu bar ---------------------------------------------------------- */

QMenuBar {{
    background-color: {P['bg_window']};
    color: {P['text_mid']};
    padding: 3px 6px;
}}

QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {P['bg_raised']};
    color: {P['text_hi']};
}}

QMenu {{
    background-color: {P['bg_raised']};
    color: {P['text_hi']};
    border: 1px solid {P['line_strong']};
    padding: 5px 0px;
}}

QMenu::item {{
    padding: 6px 26px;
}}

QMenu::item:selected {{
    background-color: {P['accent_dim']};
    color: {P['text_hi']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {P['line']};
    margin: 5px 10px;
}}

/* ---- Status bar -------------------------------------------------------- */

QStatusBar {{
    background-color: {P['bg_window']};
    color: {P['text_lo']};
    font-size: 11px;
}}

QStatusBar::item {{
    border: none;
}}

QStatusBar QLabel {{
    color: {P['text_lo']};
    padding: 1px 2px;
}}

/* ---- Splitter ---------------------------------------------------------- */

QSplitter::handle:horizontal {{
    background-color: transparent;
    width: 10px;
}}

QSplitter::handle:vertical {{
    background-color: transparent;
    height: 10px;
}}

/* ---- Buttons ----------------------------------------------------------- */

QPushButton {{
    background-color: {P['bg_raised']};
    color: {P['text_mid']};
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: #23272d;
    color: {P['text_hi']};
}}

QPushButton:pressed {{
    background-color: #16181c;
}}

QPushButton:disabled {{
    background-color: #16181b;
    color: {P['text_faint']};
}}

/* Quiet buttons sit directly on the ground until hovered. */
QPushButton[flat="true"] {{
    background-color: transparent;
    color: {P['text_mid']};
}}

QPushButton[flat="true"]:hover {{
    background-color: {P['bg_raised']};
    color: {P['text_hi']};
}}

QPushButton[flat="true"]:disabled {{
    background-color: transparent;
    color: {P['text_faint']};
}}

/* Primary action — play / pause. */
QPushButton#btn-play {{
    background-color: {P['accent_dim']};
    color: #dbeaf8;
    font-weight: 600;
    min-width: 74px;
    padding: 6px 14px;
}}

QPushButton#btn-play:hover {{
    background-color: #36566f;
    color: #ffffff;
}}

QPushButton#btn-play:disabled {{
    background-color: #191c20;
    color: {P['text_faint']};
}}

/* Play while running reads as an active state, not a new colour. */
QPushButton#btn-play[playing="true"] {{
    background-color: {P['bg_raised']};
    color: {P['accent_hi']};
}}

QPushButton#btn-play[playing="true"]:hover {{
    background-color: #23272d;
    color: #ffffff;
}}

/* Marking group — neutral chrome, the glyph carries the colour. */
QPushButton#btn-in, QPushButton#btn-out {{
    background-color: {P['bg_raised']};
    font-weight: 600;
    padding: 6px 12px;
}}

QPushButton#btn-in {{
    color: {P['accent_hi']};
}}

QPushButton#btn-out {{
    color: {P['warn']};
}}

QPushButton#btn-in:hover {{
    background-color: {P['accent_bg']};
    color: {P['accent_hi']};
}}

QPushButton#btn-out:hover {{
    background-color: {P['warn_dim']};
    color: {P['warn']};
}}

/* Destructive — stays quiet until hovered. */
QPushButton#btn-delete {{
    background-color: transparent;
    color: {P['text_lo']};
    padding: 6px 8px;
}}

QPushButton#btn-delete:hover {{
    background-color: {P['bad_dim']};
    color: {P['bad']};
}}

/* ---- Text entry -------------------------------------------------------- */

QLineEdit {{
    background-color: {P['bg_sunken']};
    border: 1px solid {P['line_strong']};
    border-radius: 4px;
    color: {P['text_hi']};
    padding: 5px 8px;
    selection-background-color: {P['accent_dim']};
}}

QLineEdit:focus {{
    border-color: {P['accent']};
}}

/* ---- Combo box --------------------------------------------------------- */

QComboBox {{
    background-color: {P['bg_raised']};
    border: none;
    border-radius: 4px;
    color: {P['text_hi']};
    padding: 6px 10px;
    font-size: 13px;
    font-weight: 600;
}}

QComboBox:hover {{
    background-color: #23272d;
}}

QComboBox QAbstractItemView {{
    background-color: {P['bg_raised']};
    border: 1px solid {P['line_strong']};
    color: {P['text_hi']};
    selection-background-color: {P['accent_dim']};
    outline: none;
    padding: 3px;
}}

/* ---- Tables ------------------------------------------------------------ */

QTableWidget, QTreeWidget, QListWidget {{
    background-color: transparent;
    border: none;
    color: {P['text_hi']};
    outline: none;
    selection-background-color: {P['accent_bg']};
    selection-color: {P['text_hi']};
}}

QTableWidget::item {{
    border: none;
    padding: 0px 6px;
}}

QTableWidget::item:selected {{
    background-color: {P['accent_bg']};
    color: {P['text_hi']};
}}

QHeaderView::section {{
    background-color: transparent;
    color: {P['text_faint']};
    padding: 4px 6px;
    border: none;
    font-size: 10px;
    font-weight: 600;
}}

/* ---- Slider ------------------------------------------------------------ */

QSlider::groove:horizontal {{
    background: {P['bg_sunken']};
    height: 4px;
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {P['accent_dim']};
    height: 4px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {P['accent']};
    width: 3px;
    height: 14px;
    margin: -5px 0;
    border-radius: 1px;
}}

QSlider::handle:horizontal:hover {{
    background: {P['accent_hi']};
}}

/* ---- Scrollbars -------------------------------------------------------- */

QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: #2a2e34;
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #3a4049;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 9px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: #2a2e34;
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #3a4049;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* ---- Named presentation roles ------------------------------------------ */

/* Section caption above a panel. */
QLabel#panel-title {{
    color: {P['text_mid']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.1px;
}}

QLabel#panel-count {{
    color: {P['text_faint']};
    font-size: 11px;
    font-weight: 500;
}}

/* Primary numeric readout — the current frame. */
QLabel#readout-primary {{
    font-family: {MONO_FAMILY};
    font-size: 15px;
    font-weight: 600;
    color: {P['text_hi']};
    padding: 0px 1px;
}}

/* Supporting numerics — totals, timecode, fps. */
QLabel#readout-secondary {{
    font-family: {MONO_FAMILY};
    font-size: 12px;
    color: {P['text_lo']};
    padding: 0px 1px;
}}

QLabel#readout-unit {{
    color: {P['text_faint']};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
}}

/* Subordinate detail line under the attempts table. */
QLabel#detail-line {{
    color: {P['text_lo']};
    font-size: 11px;
    padding: 2px 2px;
}}

/* Compare header. */
QLabel#compare-summary {{
    color: {P['text_hi']};
    font-size: 15px;
    font-weight: 600;
    padding: 4px 0px 2px 0px;
}}

QLabel#compare-summary-sub {{
    font-family: {MONO_FAMILY};
    color: {P['text_mid']};
    font-size: 12px;
}}

QLabel#pane-status {{
    font-family: {MONO_FAMILY};
    color: {P['text_lo']};
    font-size: 11px;
    padding: 2px 2px;
}}

QLabel#pane-status[frozen="true"] {{
    color: {P['good']};
}}

/* Small state chips (FASTEST / +0.533s / TIED). */
QLabel#state-chip {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
    padding: 3px 9px;
    border-radius: 3px;
    background-color: {P['bg_raised']};
    color: {P['text_mid']};
}}

QLabel#state-chip[tone="good"] {{
    background-color: {P['good_dim']};
    color: {P['good']};
}}

QLabel#state-chip[tone="slow"] {{
    background-color: {P['bad_dim']};
    color: {P['bad']};
}}

QLabel#state-chip[tone="tied"] {{
    background-color: {P['accent_bg']};
    color: {P['accent_hi']};
}}
"""
