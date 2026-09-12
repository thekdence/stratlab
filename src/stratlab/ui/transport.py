"""Transport and playback controls bar for StratLab."""

from __future__ import annotations
from fractions import Fraction
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
)

from stratlab.core.timing import frame_to_seconds, format_timecode, format_fps


class TransportControls(QWidget):
    """Playback buttons, frame stepping controls, and timecode displays."""

    step_requested = Signal(int)
    play_toggled = Signal()
    mark_in_requested = Signal()
    mark_out_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._fps: Fraction = Fraction(60, 1)
        self._total_frames: int = 0
        self._current_frame: int = 0
        self._is_playing: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Step -10 frames
        self.btn_prev10 = QPushButton("« -10")
        self.btn_prev10.setToolTip("Step -10 frames (Shift+Left)")
        self.btn_prev10.clicked.connect(lambda: self.step_requested.emit(-10))
        layout.addWidget(self.btn_prev10)

        # Step -1 frame
        self.btn_prev1 = QPushButton("‹ -1")
        self.btn_prev1.setToolTip("Step -1 frame (Left Arrow)")
        self.btn_prev1.clicked.connect(lambda: self.step_requested.emit(-1))
        layout.addWidget(self.btn_prev1)

        # Play / Pause
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setObjectName("btn-play")
        self.btn_play.setToolTip("Play / Pause (Space)")
        self.btn_play.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self.btn_play)

        # Step +1 frame
        self.btn_next1 = QPushButton("+1 ›")
        self.btn_next1.setToolTip("Step +1 frame (Right Arrow)")
        self.btn_next1.clicked.connect(lambda: self.step_requested.emit(1))
        layout.addWidget(self.btn_next1)

        # Step +10 frames
        self.btn_next10 = QPushButton("+10 »")
        self.btn_next10.setToolTip("Step +10 frames (Shift+Right)")
        self.btn_next10.clicked.connect(lambda: self.step_requested.emit(10))
        layout.addWidget(self.btn_next10)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #2d3036;")
        layout.addWidget(sep1)

        # Mark IN button
        self.btn_mark_in = QPushButton("[ Mark IN")
        self.btn_mark_in.setObjectName("btn-in")
        self.btn_mark_in.setToolTip("Mark IN frame at current position (I)")
        self.btn_mark_in.clicked.connect(self.mark_in_requested.emit)
        layout.addWidget(self.btn_mark_in)

        # Mark OUT button
        self.btn_mark_out = QPushButton("] Mark OUT")
        self.btn_mark_out.setObjectName("btn-out")
        self.btn_mark_out.setToolTip("Mark OUT frame at current position (O)")
        self.btn_mark_out.clicked.connect(self.mark_out_requested.emit)
        layout.addWidget(self.btn_mark_out)

        layout.addStretch()

        # Frame counter label
        self.label_frame = QLabel("FRAME: 0 / 0")
        self.label_frame.setObjectName("frame-label")
        layout.addWidget(self.label_frame)

        # Timecode label
        self.label_timecode = QLabel("TIME: 00:00.000 / 00:00.000")
        self.label_timecode.setObjectName("timecode-label")
        layout.addWidget(self.label_timecode)

        # FPS badge
        self.label_fps = QLabel("60.00 FPS")
        self.label_fps.setObjectName("fps-badge")
        layout.addWidget(self.label_fps)

    def set_position(self, frame: int, total_frames: int, fps: Fraction) -> None:
        self._current_frame = frame
        self._total_frames = total_frames
        self._fps = fps

        cur_sec = frame_to_seconds(frame, fps)
        total_sec = frame_to_seconds(total_frames, fps)

        pad = len(str(max(1, total_frames)))
        self.label_frame.setText(f"FRAME: {frame:0{pad}d} / {total_frames:0{pad}d}")
        self.label_timecode.setText(
            f"TIME: {format_timecode(cur_sec)} / {format_timecode(total_sec)}"
        )
        self.label_fps.setText(format_fps(fps))

    def set_playing(self, is_playing: bool) -> None:
        self._is_playing = is_playing
        if is_playing:
            self.btn_play.setText("⏸ Pause")
            self.btn_play.setStyleSheet("background-color: #854d0e; border-color: #ca8a04; color: #fef08a;")
        else:
            self.btn_play.setText("▶ Play")
            self.btn_play.setStyleSheet("")

    def set_fps(self, fps: Fraction) -> None:
        self._fps = fps
        self.label_fps.setText(format_fps(fps))
