"""Segment list management widget for StratLab."""

from __future__ import annotations
from fractions import Fraction
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QAbstractItemView,
)
from PySide6.QtGui import QColor, QFont

from stratlab.core.segment import Segment
from stratlab.core.timing import frame_to_seconds, format_timecode


class SegmentListWidget(QWidget):
    """Manages and displays speedrun attempt segments."""

    segment_selected = Signal(int)             # index
    seek_requested = Signal(int)               # target frame
    play_segment_requested = Signal(int, int)  # in_frame, out_frame
    segments_changed = Signal()                # emitted when segments added/removed/edited

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._segments: list[Segment] = []
        self._fps: Fraction = Fraction(60, 1)
        self._selected_index: int = 0
        self._updating_ui: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header toolbar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 4, 4, 2)
        header_layout.setSpacing(6)

        title = QLabel("ATTEMPTS / STRATEGIES")
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #9ca3af; letter-spacing: 0.5px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.btn_add = QPushButton("+ Add Attempt")
        self.btn_add.setStyleSheet("background-color: #1e3a8a; border-color: #2563eb; color: #93c5fd;")
        self.btn_add.clicked.connect(self.add_segment)
        header_layout.addWidget(self.btn_add)

        self.btn_up = QPushButton("▲")
        self.btn_up.setToolTip("Move selected attempt up")
        self.btn_up.setFixedWidth(28)
        self.btn_up.clicked.connect(self.move_segment_up)
        header_layout.addWidget(self.btn_up)

        self.btn_down = QPushButton("▼")
        self.btn_down.setToolTip("Move selected attempt down")
        self.btn_down.setFixedWidth(28)
        self.btn_down.clicked.connect(self.move_segment_down)
        header_layout.addWidget(self.btn_down)

        self.btn_delete = QPushButton("✕")
        self.btn_delete.setObjectName("btn-delete")
        self.btn_delete.setToolTip("Delete selected attempt")
        self.btn_delete.setFixedWidth(28)
        self.btn_delete.clicked.connect(self.delete_selected_segment)
        header_layout.addWidget(self.btn_delete)

        layout.addLayout(header_layout)

        # Table widget
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "IN Frame", "OUT Frame", "Duration", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 70)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table)

        # Quick action controls below table
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(4, 2, 4, 4)
        bottom_layout.setSpacing(6)

        self.btn_jump_in = QPushButton("Jump to IN")
        self.btn_jump_in.setToolTip("Seek video directly to selected attempt's IN frame")
        self.btn_jump_in.clicked.connect(self._jump_to_selected_in)
        bottom_layout.addWidget(self.btn_jump_in)

        self.btn_jump_out = QPushButton("Jump to OUT")
        self.btn_jump_out.setToolTip("Seek video directly to selected attempt's OUT frame")
        self.btn_jump_out.clicked.connect(self._jump_to_selected_out)
        bottom_layout.addWidget(self.btn_jump_out)

        self.btn_play_seg = QPushButton("▶ Play Attempt")
        self.btn_play_seg.setObjectName("btn-play")
        self.btn_play_seg.setToolTip("Play selected attempt strictly from IN to OUT, then stop")
        self.btn_play_seg.clicked.connect(self._play_selected_segment)
        bottom_layout.addWidget(self.btn_play_seg)

        layout.addLayout(bottom_layout)

    def set_fps(self, fps: Fraction) -> None:
        self._fps = fps
        self.refresh()

    def set_segments(self, segments: list[Segment], selected_index: int = 0) -> None:
        self._segments = list(segments)
        self._selected_index = max(0, min(selected_index, len(self._segments) - 1)) if self._segments else 0
        self.refresh()

    def get_segments(self) -> list[Segment]:
        return list(self._segments)

    def get_selected_segment(self) -> Optional[Segment]:
        if 0 <= self._selected_index < len(self._segments):
            return self._segments[self._selected_index]
        return None

    def get_selected_index(self) -> int:
        return self._selected_index

    def add_segment(self, in_frame: Optional[int] = None, out_frame: Optional[int] = None) -> Segment:
        idx = len(self._segments) + 1
        seg = Segment(name=f"Attempt {idx}", in_frame=in_frame, out_frame=out_frame)
        self._segments.append(seg)
        self._selected_index = len(self._segments) - 1
        self.refresh()
        self.segments_changed.emit()
        return seg

    def delete_selected_segment(self) -> None:
        if not self._segments or self._selected_index >= len(self._segments):
            return
        del self._segments[self._selected_index]
        self._selected_index = max(0, min(self._selected_index, len(self._segments) - 1))
        self.refresh()
        self.segments_changed.emit()

    def move_segment_up(self) -> None:
        idx = self._selected_index
        if idx > 0 and idx < len(self._segments):
            self._segments[idx], self._segments[idx - 1] = self._segments[idx - 1], self._segments[idx]
            self._selected_index = idx - 1
            self.refresh()
            self.segments_changed.emit()

    def move_segment_down(self) -> None:
        idx = self._selected_index
        if idx >= 0 and idx < len(self._segments) - 1:
            self._segments[idx], self._segments[idx + 1] = self._segments[idx + 1], self._segments[idx]
            self._selected_index = idx + 1
            self.refresh()
            self.segments_changed.emit()

    def mark_in_current_attempt(self, frame: int) -> None:
        """Set IN frame for currently selected attempt, or create one if empty."""
        if not self._segments:
            self.add_segment(in_frame=frame)
            return

        seg = self.get_selected_segment()
        if seg:
            seg.in_frame = frame
            self.refresh()
            self.segments_changed.emit()

    def mark_out_current_attempt(self, frame: int) -> None:
        """Set OUT frame for currently selected attempt, or create one if empty."""
        if not self._segments:
            self.add_segment(out_frame=frame)
            return

        seg = self.get_selected_segment()
        if seg:
            seg.out_frame = frame
            self.refresh()
            self.segments_changed.emit()

    def refresh(self) -> None:
        """Re-populate table rows without breaking active selection."""
        self._updating_ui = True
        self.table.setRowCount(len(self._segments))

        for row, seg in enumerate(self._segments):
            # Name (editable)
            item_name = QTableWidgetItem(seg.name)
            self.table.setItem(row, 0, item_name)

            # IN frame
            if seg.in_frame is not None:
                sec = frame_to_seconds(seg.in_frame, self._fps)
                tc = format_timecode(sec)
                item_in = QTableWidgetItem(f"{seg.in_frame} ({tc})")
            else:
                item_in = QTableWidgetItem("—")
                item_in.setForeground(QColor("#6b7280"))
            item_in.setFlags(item_in.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, item_in)

            # OUT frame
            if seg.out_frame is not None:
                sec = frame_to_seconds(seg.out_frame, self._fps)
                tc = format_timecode(sec)
                item_out = QTableWidgetItem(f"{seg.out_frame} ({tc})")
            else:
                item_out = QTableWidgetItem("—")
                item_out.setForeground(QColor("#6b7280"))
            item_out.setFlags(item_out.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, item_out)

            # Duration
            if seg.is_valid:
                dur_str = f"{seg.duration_display(self._fps)} ({seg.duration_frames} fr)"
                item_dur = QTableWidgetItem(dur_str)
                item_dur.setForeground(QColor("#38bdf8"))
            elif seg.validation_error:
                item_dur = QTableWidgetItem(seg.validation_error)
                item_dur.setForeground(QColor("#f87171") if "Invalid" in seg.validation_error else QColor("#9ca3af"))
            else:
                item_dur = QTableWidgetItem("—")
            item_dur.setFlags(item_dur.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, item_dur)

            # Play button widget
            btn_play = QPushButton("▶ Play")
            btn_play.setStyleSheet("padding: 2px 6px; font-size: 11px;")
            btn_play.setEnabled(seg.is_valid)
            btn_play.clicked.connect(lambda checked, s=seg: self._on_row_play_clicked(s))
            self.table.setCellWidget(row, 4, btn_play)

        # Restore selection
        if 0 <= self._selected_index < len(self._segments):
            self.table.selectRow(self._selected_index)

        self._updating_ui = False

    def _on_row_play_clicked(self, seg: Segment) -> None:
        if seg.is_valid and seg.in_frame is not None and seg.out_frame is not None:
            self.play_segment_requested.emit(seg.in_frame, seg.out_frame)

    def _on_table_selection_changed(self) -> None:
        if self._updating_ui:
            return
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self._selected_index = row
            self.segment_selected.emit(row)
            # Auto-seek to attempt's IN frame if marked
            seg = self.get_selected_segment()
            if seg and seg.in_frame is not None:
                self.seek_requested.emit(seg.in_frame)

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating_ui:
            return
        if col == 0 and 0 <= row < len(self._segments):
            item = self.table.item(row, col)
            if item:
                new_name = item.text().strip()
                if new_name:
                    self._segments[row].name = new_name
                    self.segments_changed.emit()

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if 0 <= row < len(self._segments):
            seg = self._segments[row]
            if col == 1 and seg.in_frame is not None:
                self.seek_requested.emit(seg.in_frame)
            elif col == 2 and seg.out_frame is not None:
                self.seek_requested.emit(seg.out_frame)

    def _jump_to_selected_in(self) -> None:
        seg = self.get_selected_segment()
        if seg and seg.in_frame is not None:
            self.seek_requested.emit(seg.in_frame)

    def _jump_to_selected_out(self) -> None:
        seg = self.get_selected_segment()
        if seg and seg.out_frame is not None:
            self.seek_requested.emit(seg.out_frame)

    def _play_selected_segment(self) -> None:
        seg = self.get_selected_segment()
        if seg and seg.is_valid and seg.in_frame is not None and seg.out_frame is not None:
            self.play_segment_requested.emit(seg.in_frame, seg.out_frame)
