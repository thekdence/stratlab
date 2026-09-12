"""Dark technical stylesheet and palette for StratLab."""

DARK_STYLESHEET = """
QMainWindow {
    background-color: #141517;
    color: #e5e7eb;
}

QWidget {
    background-color: #141517;
    color: #e5e7eb;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    font-size: 12px;
}

QMenuBar {
    background-color: #1a1b1e;
    color: #d1d5db;
    border-bottom: 1px solid #2d3036;
    padding: 2px 4px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 3px;
}

QMenuBar::item:selected {
    background-color: #2b2e36;
    color: #ffffff;
}

QMenu {
    background-color: #1e2025;
    color: #e5e7eb;
    border: 1px solid #363a45;
    padding: 4px 0px;
}

QMenu::item {
    padding: 6px 24px;
}

QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #2d3036;
    margin: 4px 0px;
}

QStatusBar {
    background-color: #1a1b1e;
    color: #9ca3af;
    border-top: 1px solid #2d3036;
    font-size: 11px;
}

QSplitter::handle {
    background-color: #26282e;
}

QSplitter::handle:hover {
    background-color: #3b82f6;
}

QGroupBox {
    border: 1px solid #2d3036;
    border-radius: 4px;
    margin-top: 18px;
    font-weight: 600;
    color: #9ca3af;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    background-color: #141517;
}

QPushButton {
    background-color: #262930;
    color: #e5e7eb;
    border: 1px solid #373b45;
    border-radius: 4px;
    padding: 5px 12px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #323640;
    border-color: #4a505e;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1e2026;
    border-color: #2b2e36;
}

QPushButton:disabled {
    background-color: #1b1c20;
    color: #555860;
    border-color: #26282e;
}

QPushButton#btn-in {
    background-color: #1e3a8a;
    border-color: #2563eb;
    color: #93c5fd;
    font-weight: 600;
}

QPushButton#btn-in:hover {
    background-color: #2563eb;
    color: #ffffff;
}

QPushButton#btn-out {
    background-color: #701a75;
    border-color: #a21caf;
    color: #f0abfc;
    font-weight: 600;
}

QPushButton#btn-out:hover {
    background-color: #a21caf;
    color: #ffffff;
}

QPushButton#btn-play {
    background-color: #065f46;
    border-color: #059669;
    color: #a7f3d0;
    font-weight: 600;
    min-width: 60px;
}

QPushButton#btn-play:hover {
    background-color: #059669;
    color: #ffffff;
}

QPushButton#btn-delete {
    background-color: #3b181e;
    border-color: #7f1d1d;
    color: #fca5a5;
}

QPushButton#btn-delete:hover {
    background-color: #991b1b;
    color: #ffffff;
}

QLineEdit {
    background-color: #1e2026;
    border: 1px solid #363a45;
    border-radius: 4px;
    color: #ffffff;
    padding: 4px 8px;
}

QLineEdit:focus {
    border-color: #3b82f6;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #18191d;
    border: 1px solid #2d3036;
    border-radius: 4px;
    gridline-color: #26282e;
    color: #e5e7eb;
    selection-background-color: #26334d;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #1f2127;
    color: #9ca3af;
    padding: 5px;
    border: 1px solid #26282e;
    font-weight: 600;
}

QScrollBar:vertical {
    background: #141517;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #2b2e36;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #3b82f6;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #141517;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #2b2e36;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #3b82f6;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QLabel#timecode-label, QLabel#frame-label {
    font-family: "Consolas", "Cascadia Code", monospace;
    font-size: 13px;
    font-weight: bold;
    color: #60a5fa;
    background-color: #1a1c22;
    border: 1px solid #2d3036;
    border-radius: 3px;
    padding: 3px 6px;
}

QLabel#fps-badge {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #0369a1;
    border-radius: 3px;
    font-weight: 600;
    padding: 2px 6px;
    font-size: 11px;
}

QLabel#fastest-badge {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 3px;
    font-weight: bold;
    padding: 2px 8px;
}
"""
