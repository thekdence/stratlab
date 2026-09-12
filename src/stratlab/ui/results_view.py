"""Comparison results view displaying attempt rankings, deltas, and speedrun metrics."""

from __future__ import annotations
from fractions import Fraction
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QPushButton,
    QApplication,
    QAbstractItemView,
)
from PySide6.QtGui import QColor, QFont

from stratlab.core.segment import Segment
from stratlab.core.results import AttemptResult, calculate_results
from stratlab.core.timing import format_duration


class ResultsViewWidget(QWidget):
    """Displays ranked speedrun comparison results and deltas."""

    seek_requested = Signal(int)  # frame to seek

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._results: list[AttemptResult] = []
        self._fps: Fraction = Fraction(60, 1)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header toolbar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 4, 4, 2)
        header_layout.setSpacing(6)

        self.title_label = QLabel("COMPARISON RESULTS")
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #9ca3af; letter-spacing: 0.5px;")
        header_layout.addWidget(self.title_label)

        self.summary_badge = QLabel("")
        self.summary_badge.setObjectName("fastest-badge")
        self.summary_badge.setVisible(False)
        header_layout.addWidget(self.summary_badge)

        header_layout.addStretch()

        self.btn_copy = QPushButton("Copy Summary")
        self.btn_copy.setToolTip("Copy formatted comparison summary to clipboard")
        self.btn_copy.clicked.connect(self._copy_summary_to_clipboard)
        header_layout.addWidget(self.btn_copy)

        layout.addLayout(header_layout)

        # Placeholder label when < 2 valid attempts
        self.placeholder_label = QLabel(
            "Mark at least 2 valid attempts with IN and OUT points to compute comparison results."
        )
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #6b7280; padding: 24px; font-style: italic;")
        layout.addWidget(self.placeholder_label)

        # Results table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Rank",
            "Strategy / Attempt",
            "Duration",
            "Frames",
            "Delta Time",
            "Frames Lost",
            "% Slower",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setVisible(False)
        layout.addWidget(self.table)

    def update_results(self, segments: list[Segment], fps: Fraction) -> None:
        self._fps = fps
        self._results = calculate_results(segments, fps)

        if not self._results:
            self.placeholder_label.setVisible(True)
            self.table.setVisible(False)
            self.summary_badge.setVisible(False)
            self.btn_copy.setEnabled(False)
            return

        self.placeholder_label.setVisible(False)
        self.table.setVisible(True)
        self.btn_copy.setEnabled(True)

        # Update fastest summary badge
        fastest = self._results[0]
        self.summary_badge.setText(f"FASTEST: {fastest.name} ({format_duration(fastest.duration_seconds)})")
        self.summary_badge.setVisible(True)

        self.table.setRowCount(len(self._results))
        for row, res in enumerate(self._results):
            # Rank
            item_rank = QTableWidgetItem(f"#{res.rank}")
            item_rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if res.is_fastest:
                item_rank.setForeground(QColor("#34d399"))
            self.table.setItem(row, 0, item_rank)

            # Strategy / Attempt Name
            item_name = QTableWidgetItem(res.name)
            font = item_name.font()
            if res.is_fastest:
                font.setBold(True)
                item_name.setFont(font)
                item_name.setForeground(QColor("#34d399"))
            self.table.setItem(row, 1, item_name)

            # Duration
            dur_str = f"{format_duration(res.duration_seconds)} ({res.duration_ms:.0f}ms)"
            item_dur = QTableWidgetItem(dur_str)
            item_dur.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, item_dur)

            # Frames
            item_frames = QTableWidgetItem(f"{res.duration_frames} fr")
            item_frames.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, item_frames)

            # Delta Time
            if res.is_fastest:
                item_delta = QTableWidgetItem("FASTEST")
                item_delta.setForeground(QColor("#34d399"))
                font_d = item_delta.font()
                font_d.setBold(True)
                item_delta.setFont(font_d)
                item_delta.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item_delta = QTableWidgetItem(f"+{res.delta_seconds:.3f}s")
                item_delta.setForeground(QColor("#f87171"))
                item_delta.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, item_delta)

            # Frames Lost
            if res.is_fastest:
                item_flost = QTableWidgetItem("—")
                item_flost.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_flost.setForeground(QColor("#6b7280"))
            else:
                item_flost = QTableWidgetItem(f"+{res.delta_frames} fr")
                item_flost.setForeground(QColor("#f87171"))
                item_flost.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 5, item_flost)

            # % Slower
            if res.is_fastest:
                item_pct = QTableWidgetItem("0.00%")
                item_pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_pct.setForeground(QColor("#34d399"))
            else:
                item_pct = QTableWidgetItem(f"+{res.percent_slower:.2f}%")
                item_pct.setForeground(QColor("#fb923c"))
                item_pct.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 6, item_pct)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self._results):
            res = self._results[row]
            if res.segment.in_frame is not None:
                self.seek_requested.emit(res.segment.in_frame)

    def _copy_summary_to_clipboard(self) -> None:
        if not self._results:
            return
        lines = [res.summary_line() for res in self._results]
        text = "\n".join(lines)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
