"""Custom timeline seek widget with segment range overlays."""

from __future__ import annotations
from fractions import Fraction
from typing import Optional
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPaintEvent, QColor, QPen, QBrush, QMouseEvent
from PySide6.QtWidgets import QWidget, QToolTip

from stratlab.core.segment import Segment
from stratlab.core.timing import frame_to_seconds, format_timecode
from stratlab.ui.theme import PALETTE


class TimelineWidget(QWidget):
    """Custom scrubber slider displaying playhead and highlighted segment ranges.

    Marked attempts all share one neutral band colour; only the selected
    attempt is drawn in the accent.  Rank is read in the attempts panel, so
    the timeline only has to answer "where am I" and "where is this run".
    """

    seek_requested = Signal(int)

    # Unselected attempt bands recede; the selected one steps forward.
    BAND_IDLE = QColor("#454d59")
    BAND_IDLE_EDGE = QColor("#5d6775")
    BAND_ACTIVE = QColor(PALETTE["accent"])
    BAND_ACTIVE_EDGE = QColor(PALETTE["accent_hi"])

    _SIDE_PAD = 10
    _TRACK_H = 8

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFixedHeight(34)
        self.setMinimumWidth(200)

        self._total_frames: int = 0
        self._current_frame: int = 0
        self._fps: Fraction = Fraction(60, 1)
        self._segments: list[Segment] = []
        self._selected_id: Optional[str] = None
        self._is_dragging: bool = False

    def set_range(self, total_frames: int, fps: Fraction) -> None:
        self._total_frames = max(0, total_frames)
        self._fps = fps
        self.update()

    def set_current_frame(self, frame: int) -> None:
        if self._current_frame != frame:
            self._current_frame = frame
            self.update()

    def set_segments(self, segments: list[Segment], selected_id: Optional[str] = None) -> None:
        self._segments = list(segments)
        self._selected_id = selected_id
        self.update()

    def _frame_to_x(self, frame: int) -> int:
        if self._total_frames <= 1:
            return 0
        track_w = self.width() - 2 * self._SIDE_PAD
        fraction = max(0.0, min(1.0, frame / (self._total_frames - 1)))
        return self._SIDE_PAD + int(round(fraction * track_w))

    def _x_to_frame(self, x: int) -> int:
        if self._total_frames <= 1:
            return 0
        track_w = max(1, self.width() - 2 * self._SIDE_PAD)
        x_clamped = max(self._SIDE_PAD, min(self.width() - self._SIDE_PAD, x))
        fraction = (x_clamped - self._SIDE_PAD) / track_w
        frame = int(round(fraction * (self._total_frames - 1)))
        return max(0, min(frame, self._total_frames - 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._total_frames > 0:
            self._is_dragging = True
            frame = self._x_to_frame(event.pos().x())
            self.seek_requested.emit(frame)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._total_frames > 0:
            frame = self._x_to_frame(event.pos().x())
            if self._is_dragging:
                self.seek_requested.emit(frame)
            else:
                # Show hover timecode tooltip
                sec = frame_to_seconds(frame, self._fps)
                tc = format_timecode(sec)
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"Frame {frame} ({tc})",
                    self,
                )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        track_h = self._TRACK_H
        track_y = (h - track_h) // 2
        track_x = self._SIDE_PAD
        track_w = w - 2 * self._SIDE_PAD

        # Base groove — a recess, not an outlined box.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(PALETTE["bg_sunken"])))
        painter.drawRoundedRect(QRect(track_x, track_y, track_w, track_h), 3, 3)

        if self._total_frames <= 0:
            return

        # Attempt ranges.  Draw unselected bands first so the selected one
        # always sits on top where ranges overlap.
        ordered = sorted(
            (s for s in self._segments if s.in_frame is not None and s.out_frame is not None
             and s.out_frame > s.in_frame),
            key=lambda s: s.id == self._selected_id,
        )

        for seg in ordered:
            x_in = self._frame_to_x(seg.in_frame)
            x_out = self._frame_to_x(seg.out_frame)
            seg_w = max(2, x_out - x_in)
            is_selected = (seg.id == self._selected_id)

            fill = QColor(self.BAND_ACTIVE if is_selected else self.BAND_IDLE)
            edge = QColor(self.BAND_ACTIVE_EDGE if is_selected else self.BAND_IDLE_EDGE)
            if not is_selected:
                fill.setAlpha(205)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(fill))
            painter.drawRoundedRect(QRect(x_in, track_y, seg_w, track_h), 3, 3)

            # IN / OUT edge ticks, taller on the selected attempt.
            tick_over = 5 if is_selected else 2
            painter.setBrush(QBrush(edge))
            painter.drawRect(QRect(x_in, track_y - tick_over, 1, track_h + 2 * tick_over))
            painter.drawRect(QRect(x_out - 1, track_y - tick_over, 1, track_h + 2 * tick_over))

        # Playhead — a single hairline plus a compact cap, so it stays legible
        # on top of a band without becoming decoration.
        playhead_x = self._frame_to_x(self._current_frame)
        playhead_color = QColor(PALETTE["accent_hi"])

        painter.setPen(QPen(playhead_color, 1))
        painter.drawLine(playhead_x, 4, playhead_x, h - 5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(playhead_color))
        painter.drawPolygon([
            QPoint(playhead_x - 4, 1),
            QPoint(playhead_x + 4, 1),
            QPoint(playhead_x, 7),
        ])
