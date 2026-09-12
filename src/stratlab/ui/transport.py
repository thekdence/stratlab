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
)

from stratlab.core.timing import frame_to_seconds, format_timecode, format_fps


class TransportControls(QWidget):
    """Playback buttons, frame stepping controls, and timecode displays.

    Grouping is carried entirely by spacing: stepping controls sit tight
    around Play, and the IN/OUT marking pair is pushed away from them so it
    reads as a separate action, without any dividers or boxes.
    """

    step_requested = Signal(int)
    play_toggled = Signal()
    mark_in_requested = Signal()
    mark_out_requested = Signal()

    # Horizontal gaps that do the grouping work.
    _GAP_WITHIN_GROUP = 3
    _GAP_BETWEEN_GROUPS = 18

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self._fps: Fraction = Fraction(60, 1)
        self._total_frames: int = 0
        self._current_frame: int = 0
        self._is_playing: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 8)
        layout.setSpacing(self._GAP_WITHIN_GROUP)

        # --- Navigation group: stepping wrapped tightly around play/pause ---

        self.btn_prev10 = QPushButton("−10")
        self.btn_prev10.setToolTip("Step -10 frames (Shift+Left)")
        self.btn_prev10.clicked.connect(lambda: self.step_requested.emit(-10))
        layout.addWidget(self.btn_prev10)

        self.btn_prev1 = QPushButton("−1")
        self.btn_prev1.setToolTip("Step -1 frame (Left Arrow)")
        self.btn_prev1.clicked.connect(lambda: self.step_requested.emit(-1))
        layout.addWidget(self.btn_prev1)

        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("btn-play")
        self.btn_play.setToolTip("Play / Pause (Space)")
        self.btn_play.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self.btn_play)

        self.btn_next1 = QPushButton("+1")
        self.btn_next1.setToolTip("Step +1 frame (Right Arrow)")
        self.btn_next1.clicked.connect(lambda: self.step_requested.emit(1))
        layout.addWidget(self.btn_next1)

        self.btn_next10 = QPushButton("+10")
        self.btn_next10.setToolTip("Step +10 frames (Shift+Right)")
        self.btn_next10.clicked.connect(lambda: self.step_requested.emit(10))
        layout.addWidget(self.btn_next10)

        layout.addSpacing(self._GAP_BETWEEN_GROUPS)

        # --- Marking group -------------------------------------------------

        self.btn_mark_in = QPushButton("Mark IN")
        self.btn_mark_in.setObjectName("btn-in")
        self.btn_mark_in.setToolTip("Mark IN frame at current position (I)")
        self.btn_mark_in.clicked.connect(self.mark_in_requested.emit)
        layout.addWidget(self.btn_mark_in)

        self.btn_mark_out = QPushButton("Mark OUT")
        self.btn_mark_out.setObjectName("btn-out")
        self.btn_mark_out.setToolTip("Mark OUT frame at current position (O)")
        self.btn_mark_out.clicked.connect(self.mark_out_requested.emit)
        layout.addWidget(self.btn_mark_out)

        layout.addStretch()

        # --- Readouts: current frame leads, everything else recedes --------

        self._cap_frame = QLabel("FRAME")
        self._cap_frame.setObjectName("readout-unit")
        layout.addWidget(self._cap_frame, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(5)

        self.label_frame = QLabel("0")
        self.label_frame.setObjectName("readout-primary")
        self.label_frame.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.label_frame)

        self.label_frame_total = QLabel("/ 0")
        self.label_frame_total.setObjectName("readout-secondary")
        self.label_frame_total.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.label_frame_total)

        layout.addSpacing(self._GAP_BETWEEN_GROUPS)

        self.label_timecode = QLabel("00:00.000 / 00:00.000")
        self.label_timecode.setObjectName("readout-secondary")
        self.label_timecode.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.label_timecode)

        layout.addSpacing(14)

        self.label_fps = QLabel("60.00 FPS")
        self.label_fps.setObjectName("readout-unit")
        layout.addWidget(self.label_fps, 0, Qt.AlignmentFlag.AlignVCenter)

    # Widths below which each supporting readout is dropped.  The seven
    # transport controls are never hidden; only the numeric context gives way,
    # least important first, so nothing can overlap in a narrow window.
    _W_SHOW_FPS = 820
    _W_SHOW_TIMECODE = 700
    _W_SHOW_TOTAL = 600

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = self.width()
        self.label_fps.setVisible(width >= self._W_SHOW_FPS)
        self.label_timecode.setVisible(width >= self._W_SHOW_TIMECODE)
        show_total = width >= self._W_SHOW_TOTAL
        self.label_frame_total.setVisible(show_total)
        self._cap_frame.setVisible(show_total)

    def set_position(self, frame: int, total_frames: int, fps: Fraction) -> None:
        self._current_frame = frame
        self._total_frames = total_frames
        self._fps = fps

        cur_sec = frame_to_seconds(frame, fps)
        total_sec = frame_to_seconds(total_frames, fps)

        # Reserve width for the widest frame number so the readout does not
        # jitter as digits are gained or lost.
        pad = len(str(max(1, total_frames)))
        self.label_frame.setMinimumWidth(10 * pad + 4)
        self.label_frame.setText(str(frame))
        self.label_frame_total.setText(f"/ {total_frames}")
        self.label_timecode.setText(
            f"{format_timecode(cur_sec)} / {format_timecode(total_sec)}"
        )
        self.label_fps.setText(format_fps(fps))

    def set_playing(self, is_playing: bool) -> None:
        self._is_playing = is_playing
        self.btn_play.setText("Pause" if is_playing else "Play")
        # Drive the visual state through a property so the stylesheet owns the
        # colours rather than an inline override.
        self.btn_play.setProperty("playing", "true" if is_playing else "false")
        style = self.btn_play.style()
        style.unpolish(self.btn_play)
        style.polish(self.btn_play)

    def set_fps(self, fps: Fraction) -> None:
        self._fps = fps
        self.label_fps.setText(format_fps(fps))
