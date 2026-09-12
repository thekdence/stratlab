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
from stratlab.ui.theme import PALETTE

# Column indices.  The table's column meanings are part of the app's public
# surface (validation scripts read them by index), so they are named here
# rather than spelled as literals.
COL_RANK = 0
COL_NAME = 1
COL_DURATION = 2
COL_FRAMES = 3
COL_DELTA = 4

ROW_HEIGHT = 34

# Fixed widths for every column except the stretching attempt name.
COLUMN_WIDTHS = {
    COL_RANK: 38,
    COL_DURATION: 76,
    COL_FRAMES: 70,
    COL_DELTA: 84,
}

_MONO = "Cascadia Mono"
_MONO_FALLBACK = "Consolas"


def _mono(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(_MONO, size, weight)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.insertSubstitution(_MONO, _MONO_FALLBACK)
    return font


def _ui(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return QFont("Segoe UI", size, weight)


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
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(10)

        # --- Header ---------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(2, 0, 0, 0)
        header_layout.setSpacing(8)

        self.lbl_title = QLabel("ATTEMPTS")
        self.lbl_title.setObjectName("panel-title")
        header_layout.addWidget(self.lbl_title)

        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("panel-count")
        header_layout.addWidget(self.lbl_count)

        header_layout.addStretch()

        self.btn_compare = QPushButton("Compare")
        self.btn_compare.setToolTip("Compare two attempts side-by-side with synchronized playback")
        self.btn_compare.clicked.connect(self.compare_requested.emit)
        self.btn_compare.setEnabled(False)
        header_layout.addWidget(self.btn_compare)

        self.btn_add = QPushButton("+")
        self.btn_add.setToolTip("Manually add a new empty attempt")
        self.btn_add.setProperty("flat", "true")
        self.btn_add.setFixedWidth(28)
        self.btn_add.clicked.connect(self.add_segment)
        header_layout.addWidget(self.btn_add)

        layout.addLayout(header_layout)

        # --- Ranked attempts table -----------------------------------------
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Rank", "Attempt", "Duration", "Frames", "Delta / Status"])
        # The numeric columns are held at fixed widths so the attempt name —
        # the only variable-length field — always keeps the leftover space
        # instead of being elided away by a long status string.
        header = self.table.horizontalHeader()
        for col, width in COLUMN_WIDTHS.items():
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, width)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)

        # The rows are self-describing (#1 / name / time / FASTEST), so the
        # header only adds spreadsheet chrome.
        self.table.horizontalHeader().setVisible(False)
        header.setMinimumSectionSize(26)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table)

        # --- Selected attempt detail (subordinate) --------------------------
        self.lbl_details = QLabel("No attempt selected")
        self.lbl_details.setObjectName("detail-line")
        self.lbl_details.setWordWrap(True)
        layout.addWidget(self.lbl_details)

        # --- Actions for the selected attempt -------------------------------
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)

        self.btn_play_seg = QPushButton("Play Run")
        self.btn_play_seg.setObjectName("btn-play")
        self.btn_play_seg.setToolTip("Play this attempt strictly from IN to OUT, then stop")
        self.btn_play_seg.clicked.connect(self._play_segment)
        action_layout.addWidget(self.btn_play_seg)

        self.btn_jump_in = QPushButton("IN")
        self.btn_jump_in.setToolTip("Seek video directly to attempt's IN frame")
        self.btn_jump_in.setProperty("flat", "true")
        self.btn_jump_in.clicked.connect(self._jump_to_in)
        action_layout.addWidget(self.btn_jump_in)

        self.btn_jump_out = QPushButton("OUT")
        self.btn_jump_out.setToolTip("Seek video directly to attempt's OUT frame")
        self.btn_jump_out.setProperty("flat", "true")
        self.btn_jump_out.clicked.connect(self._jump_to_out)
        action_layout.addWidget(self.btn_jump_out)

        action_layout.addStretch()

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setToolTip("Copy formatted comparison summary to clipboard")
        self.btn_copy.setProperty("flat", "true")
        self.btn_copy.clicked.connect(self._copy_summary)
        action_layout.addWidget(self.btn_copy)

        self.btn_delete = QPushButton("✕")
        self.btn_delete.setObjectName("btn-delete")
        self.btn_delete.setToolTip("Delete selected attempt")
        self.btn_delete.setFixedWidth(30)
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
        self.lbl_count.setText(str(len(self._segments)) if self._segments else "")

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
            is_fastest = bool(res and res.is_fastest)

            # Column 0: Rank — quiet ordinal, the fastest one earns the accent.
            if res:
                item_rank = QTableWidgetItem(f"#{res.rank}")
                item_rank.setFont(_mono(9, QFont.Weight.DemiBold))
                item_rank.setForeground(
                    QColor(PALETTE["good"]) if is_fastest else QColor(PALETTE["text_faint"])
                )
            elif seg.is_valid:
                item_rank = QTableWidgetItem("–")
                item_rank.setForeground(QColor(PALETTE["text_faint"]))
            else:
                item_rank = QTableWidgetItem("•")
                item_rank.setForeground(QColor(PALETTE["warn"]))
            item_rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_rank.setFlags(item_rank.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, COL_RANK, item_rank)

            # Column 1: Attempt name — plain UI type, incomplete runs recede.
            item_name = QTableWidgetItem(seg.name)
            item_name.setFont(_ui(10, QFont.Weight.DemiBold if is_fastest else QFont.Weight.Normal))
            item_name.setForeground(
                QColor(PALETTE["text_hi"]) if seg.is_valid else QColor(PALETTE["text_lo"])
            )
            self.table.setItem(row, COL_NAME, item_name)

            # Column 2: Duration — the headline number for each row.
            if seg.is_valid:
                item_time = QTableWidgetItem(seg.duration_display(self._fps))
                item_time.setFont(_mono(11, QFont.Weight.DemiBold))
                item_time.setForeground(
                    QColor(PALETTE["good"]) if is_fastest else QColor(PALETTE["text_hi"])
                )
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item_time = QTableWidgetItem("–")
                item_time.setForeground(QColor(PALETTE["text_faint"]))
                item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_time.setFlags(item_time.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, COL_DURATION, item_time)

            # Column 3: Frame count — supporting precision, deliberately small.
            if seg.is_valid:
                item_fr = QTableWidgetItem(f"{seg.duration_frames} fr")
                item_fr.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item_fr = QTableWidgetItem("–")
                item_fr.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_fr.setFont(_mono(9))
            item_fr.setForeground(QColor(PALETTE["text_faint"]))
            item_fr.setFlags(item_fr.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, COL_FRAMES, item_fr)

            # Column 4: Delta / status.
            if res:
                if res.is_fastest:
                    item_delta = QTableWidgetItem("FASTEST")
                    item_delta.setForeground(QColor(PALETTE["good"]))
                    item_delta.setFont(_ui(8, QFont.Weight.Bold))
                    item_delta.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    # Rendered two-tone by _DeltaDelegate; text stays intact.
                    item_delta = QTableWidgetItem(f"+{res.delta_seconds:.3f}s")
                    item_delta.setFont(_mono(10))
                    item_delta.setToolTip(
                        f"+{res.delta_seconds:.3f}s / +{res.delta_frames} frames "
                        f"/ +{res.percent_slower:.1f}% vs fastest"
                    )
                    item_delta.setForeground(QColor(PALETTE["bad"]))
                    item_delta.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            elif seg.validation_error:
                # The row shows the state; the full reason stays on hover so
                # this column cannot bully the attempt name out of the table.
                item_delta = QTableWidgetItem("Incomplete")
                item_delta.setToolTip(seg.validation_error)
                item_delta.setForeground(QColor(PALETTE["warn"]))
                item_delta.setFont(_ui(9))
                item_delta.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item_delta = QTableWidgetItem("–")
                item_delta.setForeground(QColor(PALETTE["text_faint"]))
                item_delta.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_delta.setFlags(item_delta.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, COL_DELTA, item_delta)

            self.table.setRowHeight(row, ROW_HEIGHT)

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

        faint = PALETTE["text_faint"]
        mid = PALETTE["text_mid"]

        def point(label: str, frame: Optional[int], timecode: str) -> str:
            if frame is None:
                return f"<span style='color:{faint}'>{label} —</span>"
            return (
                f"<span style='color:{faint}'>{label}</span> "
                f"<span style='color:{mid}'>{frame}</span> "
                f"<span style='color:{faint}'>{timecode}</span>"
            )

        parts = [
            point("IN", seg.in_frame, seg.in_timecode(self._fps)),
            point("OUT", seg.out_frame, seg.out_timecode(self._fps)),
        ]
        if not seg.is_valid:
            parts.append(f"<span style='color:{PALETTE['warn']}'>incomplete</span>")

        # The precise loss against the fastest run is detail, not headline:
        # the table shows the seconds, the full breakdown belongs here.
        res = next((r for r in self._results if r.segment.id == seg.id), None)
        if res and not res.is_fastest:
            parts.append(
                f"<span style='color:{PALETTE['bad']}'>+{res.delta_frames} frames</span> "
                f"<span style='color:{faint}'>(+{res.percent_slower:.1f}%)</span>"
            )

        sep = f"<span style='color:{faint}'> &nbsp;·&nbsp; </span>"
        self.lbl_details.setText(sep.join(parts))

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
        if hasattr(self, "_display_segments") and col == COL_NAME and 0 <= row < len(self._display_segments):
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
