"""Unified attempt management and ranked comparison results panel."""

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
    QApplication,
)
from PySide6.QtGui import QColor, QFont

from stratlab.core.segment import Segment
from stratlab.core.results import AttemptResult, calculate_results
from stratlab.core.timing import frame_to_seconds, format_timecode, format_duration


class AttemptPanel(QWidget):
    """Unified side panel combining attempt logging and speedrun rankings."""

    seek_requested = Signal(int)               # target frame
    play_segment_requested = Signal(int, int)  # in_frame, out_frame
    compare_requested = Signal()               # open side-by-side compare
    segments_changed = Signal()
    segment_selected = Signal(int)
    status_message = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._segments: list[Segment] = []
        self._fps: Fraction = Fraction(60, 1)
        self._selected_index: int = 0
        self._updating_ui: bool = False
        self._results: list[AttemptResult] = []

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(2, 2, 2, 2)
        header_layout.setSpacing(6)

        self.lbl_title = QLabel("ATTEMPTS")
        font_t = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.lbl_title.setFont(font_t)
        self.lbl_title.setStyleSheet("color: #9ca3af; letter-spacing: 0.5px;")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        # Compare button
        self.btn_compare = QPushButton("⚡ Compare")
        self.btn_compare.setToolTip("Compare two attempts side-by-side with synchronized playback")
        self.btn_compare.setStyleSheet(
            "background-color: #1e3a8a; border-color: #2563eb; color: #93c5fd; font-weight: bold; padding: 4px 10px;"
        )
        self.btn_compare.clicked.connect(self.compare_requested.emit)
        self.btn_compare.setEnabled(False)
        header_layout.addWidget(self.btn_compare)

        # Manual Add button
        self.btn_add = QPushButton("+ Add")
        self.btn_add.setToolTip("Manually add a new empty attempt")
        self.btn_add.setStyleSheet("padding: 4px 8px;")
        self.btn_add.clicked.connect(self.add_segment)
        header_layout.addWidget(self.btn_add)

        layout.addLayout(header_layout)

        # 5-column Table: Rank, Name, Duration, Frames, Delta/Status
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Rank", "Attempt", "Duration", "Frames", "Delta / Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table)

        # Selected attempt details banner
        self.lbl_details = QLabel("No attempt selected")
        self.lbl_details.setStyleSheet(
            "color: #9ca3af; font-size: 11px; background-color: #1a1c22; "
            "padding: 3px 6px; border-radius: 3px; border: 1px solid #2d3036;"
        )
        layout.addWidget(self.lbl_details)

        # Bottom action bar for selected attempt
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(2, 2, 2, 2)
        action_layout.setSpacing(4)

        self.btn_jump_in = QPushButton("Jump IN")
        self.btn_jump_in.setToolTip("Seek video directly to attempt's IN frame")
        self.btn_jump_in.clicked.connect(self._jump_to_in)
        action_layout.addWidget(self.btn_jump_in)

        self.btn_jump_out = QPushButton("Jump OUT")
        self.btn_jump_out.setToolTip("Seek video directly to attempt's OUT frame")
        self.btn_jump_out.clicked.connect(self._jump_to_out)
        action_layout.addWidget(self.btn_jump_out)

        self.btn_play_seg = QPushButton("▶ Play Run")
        self.btn_play_seg.setObjectName("btn-play")
        self.btn_play_seg.setToolTip("Play this attempt strictly from IN to OUT, then stop")
        self.btn_play_seg.clicked.connect(self._play_segment)
        action_layout.addWidget(self.btn_play_seg)

        action_layout.addStretch()

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setToolTip("Copy formatted comparison summary to clipboard")
        self.btn_copy.clicked.connect(self._copy_summary)
        action_layout.addWidget(self.btn_copy)

        self.btn_delete = QPushButton("✕")
        self.btn_delete.setObjectName("btn-delete")
        self.btn_delete.setToolTip("Delete selected attempt")
        self.btn_delete.setFixedWidth(26)
        self.btn_delete.clicked.connect(self.delete_selected_segment)
        action_layout.addWidget(self.btn_delete)

        layout.addLayout(action_layout)

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

    def mark_in_current_attempt(self, frame: int) -> None:
        """Alias for backward compatibility."""
        self.mark_in(frame)

    def mark_out_current_attempt(self, frame: int) -> None:
        """Alias for backward compatibility."""
        self.mark_out(frame)

    def mark_in(self, frame: int) -> None:
        """Mark IN point with intelligent automatic attempt creation."""
        active_seg = self.get_selected_segment()

        # Case 1: No segments exist at all
        if not self._segments:
            seg = Segment(name="Attempt 1", in_frame=frame)
            self._segments.append(seg)
            self._selected_index = 0
            self.refresh()
            self.segments_changed.emit()
            self.status_message.emit(f"Created Attempt 1: IN marked at frame {frame}")
            return

        # Case 2: Active segment is already complete -> automatically start next attempt!
        if active_seg and active_seg.is_valid:
            next_idx = len(self._segments) + 1
            new_seg = Segment(name=f"Attempt {next_idx}", in_frame=frame)
            self._segments.append(new_seg)
            self._selected_index = len(self._segments) - 1
            self.refresh()
            self.segments_changed.emit()
            self.status_message.emit(f"Started {new_seg.name}: IN marked at frame {frame}")
            return

        # Case 3: Incomplete active segment -> update its IN point
        if active_seg:
            active_seg.in_frame = frame
            # If OUT was set and is now invalid, clear OUT
            if active_seg.out_frame is not None and active_seg.out_frame <= frame:
                active_seg.out_frame = None
            self.refresh()
            self.segments_changed.emit()
            self.status_message.emit(f"Updated {active_seg.name} IN to frame {frame}")

    def mark_out(self, frame: int) -> None:
        """Mark OUT point for active attempt."""
        active_seg = self.get_selected_segment()
        if not active_seg or active_seg.in_frame is None:
            self.status_message.emit("Press 'I' first to mark the start of an attempt")
            return

        if frame <= active_seg.in_frame:
            self.status_message.emit(
                f"Cannot mark OUT: frame {frame} must be after IN ({active_seg.in_frame})"
            )
            return

        active_seg.out_frame = frame
        self.refresh()
        self.segments_changed.emit()
        dur_str = active_seg.duration_display(self._fps)
        self.status_message.emit(
            f"Completed {active_seg.name}: {dur_str} ({active_seg.duration_frames} fr). Ready for next run (press 'I')."
        )

    def refresh(self) -> None:
        """Re-render attempt list with speedrun rankings and deltas."""
        self._updating_ui = True

        valid_segments = [s for s in self._segments if s.is_valid]
        self._results = calculate_results(self._segments, self._fps) if len(valid_segments) >= 2 else []

        # Enable compare button when >= 2 valid attempts exist
        self.btn_compare.setEnabled(len(valid_segments) >= 2)
        count_str = f"({len(self._segments)})" if self._segments else ""
        self.lbl_title.setText(f"ATTEMPTS {count_str}")

        # Build rank map: segment_id -> AttemptResult
        res_map = {r.segment.id: r for r in self._results}

        # Sort display order by rank: valid attempts sorted by duration ascending, incomplete at bottom
        self._display_segments = sorted(
            self._segments,
            key=lambda s: (0 if s.is_valid else 1, s.duration_frames if s.is_valid else 999999, s.name),
        )

        self.table.setRowCount(len(self._display_segments))

        for row, seg in enumerate(self._display_segments):
            res = res_map.get(seg.id)

            # Column 0: Rank
            if res:
                item_rank = QTableWidgetItem(f"#{res.rank}")
                item_rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if res.is_fastest:
                    item_rank.setForeground(QColor("#34d399"))
            elif seg.is_valid:
                item_rank = QTableWidgetItem("—")
                item_rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_rank.setForeground(QColor("#9ca3af"))
            else:
                item_rank = QTableWidgetItem("•")
                item_rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_rank.setForeground(QColor("#fb923c"))
            item_rank.setFlags(item_rank.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item_rank)

            # Column 1: Attempt Name
            item_name = QTableWidgetItem(seg.name)
            if res and res.is_fastest:
                item_name.setForeground(QColor("#34d399"))
            self.table.setItem(row, 1, item_name)

            # Column 2: Duration Time
            if seg.is_valid:
                dur_str = seg.duration_display(self._fps)
                item_time = QTableWidgetItem(dur_str)
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_time.setForeground(QColor("#38bdf8"))
            else:
                item_time = QTableWidgetItem("—")
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_time.setForeground(QColor("#6b7280"))
            item_time.setFlags(item_time.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, item_time)

            # Column 3: Frames
            if seg.is_valid:
                item_fr = QTableWidgetItem(f"{seg.duration_frames} fr")
                item_fr.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_fr.setForeground(QColor("#9ca3af"))
            else:
                item_fr = QTableWidgetItem("—")
                item_fr.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_fr.setForeground(QColor("#6b7280"))
            item_fr.setFlags(item_fr.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, item_fr)

            # Column 4: Delta / Status Tag
            if res:
                if res.is_fastest:
                    item_delta = QTableWidgetItem("FASTEST")
                    item_delta.setForeground(QColor("#34d399"))
                    font_d = item_delta.font()
                    font_d.setBold(True)
                    item_delta.setFont(font_d)
                    item_delta.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    item_delta = QTableWidgetItem(f"+{res.delta_seconds:.3f}s  (+{res.percent_slower:.1f}%)")
                    item_delta.setForeground(QColor("#f87171"))
                    item_delta.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            elif seg.validation_error:
                item_delta = QTableWidgetItem(seg.validation_error)
                item_delta.setForeground(QColor("#fb923c"))
                item_delta.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item_delta = QTableWidgetItem("—")
                item_delta.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_delta.setFlags(item_delta.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, item_delta)

            self.table.setRowHeight(row, 30)

        # Restore selection
        selected_seg = self.get_selected_segment()
        if selected_seg and hasattr(self, "_display_segments") and selected_seg in self._display_segments:
            disp_row = self._display_segments.index(selected_seg)
            self.table.selectRow(disp_row)

        self._update_details_label()
        self._updating_ui = False

    def _update_details_label(self) -> None:
        seg = self.get_selected_segment()
        if not seg:
            self.lbl_details.setText("No attempt selected")
            return

        in_tc = seg.in_timecode(self._fps)
        out_tc = seg.out_timecode(self._fps)
        in_str = f"Frame {seg.in_frame} ({in_tc})" if seg.in_frame is not None else "None"
        out_str = f"Frame {seg.out_frame} ({out_tc})" if seg.out_frame is not None else "None"
        dur = f"{seg.duration_display(self._fps)} ({seg.duration_frames} fr)" if seg.is_valid else "Incomplete"

        self.lbl_details.setText(
            f"<b>{seg.name}</b>: IN {in_str} → OUT {out_str} | {dur}"
        )

    def _on_table_selection_changed(self) -> None:
        if self._updating_ui:
            return
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if hasattr(self, "_display_segments") and 0 <= row < len(self._display_segments):
                selected_seg = self._display_segments[row]
                self._selected_index = self._segments.index(selected_seg)
                self.segment_selected.emit(self._selected_index)
                self._update_details_label()
                if selected_seg.in_frame is not None:
                    self.seek_requested.emit(selected_seg.in_frame)

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating_ui:
            return
        if hasattr(self, "_display_segments") and col == 1 and 0 <= row < len(self._display_segments):
            item = self.table.item(row, col)
            if item:
                new_name = item.text().strip()
                target_seg = self._display_segments[row]
                if new_name and new_name != target_seg.name:
                    target_seg.name = new_name
                    self._update_details_label()
                    self.segments_changed.emit()

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if hasattr(self, "_display_segments") and 0 <= row < len(self._display_segments):
            seg = self._display_segments[row]
            if seg.in_frame is not None:
                self.seek_requested.emit(seg.in_frame)

    def _jump_to_in(self) -> None:
        seg = self.get_selected_segment()
        if seg and seg.in_frame is not None:
            self.seek_requested.emit(seg.in_frame)

    def _jump_to_out(self) -> None:
        seg = self.get_selected_segment()
        if seg and seg.out_frame is not None:
            self.seek_requested.emit(seg.out_frame)

    def _play_segment(self) -> None:
        seg = self.get_selected_segment()
        if seg and seg.is_valid and seg.in_frame is not None and seg.out_frame is not None:
            self.play_segment_requested.emit(seg.in_frame, seg.out_frame)

    def _copy_summary(self) -> None:
        if not self._results:
            return
        lines = [res.summary_line() for res in self._results]
        text = "\n".join(lines)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            self.status_message.emit("Copied comparison summary to clipboard")
