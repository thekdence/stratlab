"""Custom timeline seek widget with segment range overlays."""

from __future__ import annotations
from fractions import Fraction
from typing import Optional
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPaintEvent, QColor, QPen, QBrush, QMouseEvent
from PySide6.QtWidgets import QWidget, QToolTip

from stratlab.core.segment import Segment
from stratlab.core.timing import frame_to_seconds, format_timecode


class TimelineWidget(QWidget):
    """Custom scrubber slider displaying playhead and highlighted segment ranges."""

    seek_requested = Signal(int)

    # Palette for visual segment bands
    SEGMENT_COLORS = [
        QColor(59, 130, 246, 120),   # Blue
        QColor(168, 85, 247, 120),   # Purple
        QColor(236, 72, 153, 120),   # Pink
        QColor(20, 184, 166, 120),   # Teal
        QColor(245, 158, 11, 120),   # Amber
        QColor(34, 197, 94, 120),    # Emerald
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFixedHeight(28)
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
        track_w = self.width() - 16
        fraction = max(0.0, min(1.0, frame / (self._total_frames - 1)))
        return 8 + int(round(fraction * track_w))

    def _x_to_frame(self, x: int) -> int:
        if self._total_frames <= 1:
            return 0
        track_w = max(1, self.width() - 16)
        x_clamped = max(8, min(self.width() - 8, x))
        fraction = (x_clamped - 8) / track_w
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
        track_y = h // 2 - 3
        track_h = 6
        track_x = 8
        track_w = w - 16

        # Draw base track groove
        groove_rect = QRect(track_x, track_y, track_w, track_h)
        painter.fillRect(groove_rect, QColor("#1e2025"))
        painter.setPen(QPen(QColor("#2d3036"), 1))
        painter.drawRect(groove_rect)

        if self._total_frames <= 0:
            return

        # Draw segment ranges
        for idx, seg in enumerate(self._segments):
            if seg.in_frame is not None and seg.out_frame is not None and seg.out_frame > seg.in_frame:
                x_in = self._frame_to_x(seg.in_frame)
                x_out = self._frame_to_x(seg.out_frame)
                seg_w = max(2, x_out - x_in)

                is_selected = (seg.id == self._selected_id)
                base_color = self.SEGMENT_COLORS[idx % len(self.SEGMENT_COLORS)]

                if is_selected:
                    fill_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 190)
                    border_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 255)
                else:
                    fill_color = base_color
                    border_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 160)

                seg_rect = QRect(x_in, track_y - 2, seg_w, track_h + 4)
                painter.fillRect(seg_rect, fill_color)
                painter.setPen(QPen(border_color, 1))
                painter.drawRect(seg_rect)

                # Small IN and OUT markers
                painter.fillRect(QRect(x_in - 1, track_y - 4, 2, track_h + 8), border_color)
                painter.fillRect(QRect(x_out - 1, track_y - 4, 2, track_h + 8), border_color)

        # Draw playhead cursor
        playhead_x = self._frame_to_x(self._current_frame)
        playhead_color = QColor("#38bdf8")
        painter.setPen(QPen(playhead_color, 2))
        painter.drawLine(playhead_x, 2, playhead_x, h - 2)

        # Draw playhead handle diamond
        handle_poly = [
            QPoint(playhead_x, 2),
            QPoint(playhead_x + 4, 7),
            QPoint(playhead_x, 12),
            QPoint(playhead_x - 4, 7),
        ]
        painter.setBrush(QBrush(playhead_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(handle_poly)
