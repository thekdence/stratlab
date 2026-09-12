"""Side-by-side synchronized attempt comparison view."""

from __future__ import annotations
from fractions import Fraction
from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QFrame,
    QSlider,
)
from PySide6.QtGui import QFont, QImage

from stratlab.core.segment import Segment
from stratlab.core.timing import frame_to_seconds, format_timecode, format_duration
from stratlab.ui.video_player import VideoPlayer


class CompareView(QWidget):
    """Side-by-side strategy comparison interface with synchronized playback."""

    exit_requested = Signal()
    setup_requested = Signal(str, object, object, object)  # video_path, seg_left, seg_right, fps
    seek_relative_requested = Signal(int)
    step_relative_requested = Signal(int)
    restart_requested = Signal()
    toggle_play_requested = Signal()
    start_play_requested = Signal()
    stop_play_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.video_path: str = ""
        self.fps: Fraction = Fraction(60, 1)
        self.segments: list[Segment] = []

        self.seg_left: Optional[Segment] = None
        self.seg_right: Optional[Segment] = None

        self._desired_rel_frame: int = 0
        self._displayed_rel_frame: int = 0
        self._seek_in_flight: bool = False
        self._navigation_pending: bool = False
        self._is_playing: bool = False
        self._playback_intent: bool = False
        self._start_pending: bool = False
        self.max_rel_frame: int = 0

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 4)

        self.btn_exit = QPushButton("← Back to Attempts")
        self.btn_exit.setToolTip("Return to single-video editor (Esc)")
        self.btn_exit.clicked.connect(self.exit_requested.emit)
        header_layout.addWidget(self.btn_exit)

        self.delta_banner = QLabel("Select two attempts to compare")
        self.delta_banner.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #38bdf8; padding: 4px 12px; "
            "background-color: #1e293b; border-radius: 4px; border: 1px solid #0369a1;"
        )
        self.delta_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.delta_banner, stretch=1)

        layout.addLayout(header_layout)

        # Dual video panes layout
        panes_layout = QHBoxLayout()
        panes_layout.setSpacing(8)

        # Left pane
        left_box = QWidget()
        left_vbox = QVBoxLayout(left_box)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(4)

        left_header = QHBoxLayout()
        left_lbl = QLabel("Left:")
        left_lbl.setStyleSheet("font-weight: 600; color: #9ca3af;")
        left_header.addWidget(left_lbl)

        self.combo_left = QComboBox()
        self.combo_left.currentIndexChanged.connect(self._on_left_selection_changed)
        left_header.addWidget(self.combo_left, stretch=1)

        self.left_badge = QLabel("—")
        self.left_badge.setStyleSheet("font-weight: bold; padding: 2px 6px; border-radius: 3px;")
        left_header.addWidget(self.left_badge)
        left_vbox.addLayout(left_header)

        self.player_left = VideoPlayer()
        left_vbox.addWidget(self.player_left, stretch=1)

        self.left_status = QLabel("Frame: 0 / 0")
        self.left_status.setStyleSheet("color: #9ca3af; font-family: Consolas, monospace; font-size: 11px;")
        left_vbox.addWidget(self.left_status)
        panes_layout.addWidget(left_box, stretch=1)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #2d3036;")
        panes_layout.addWidget(sep)

        # Right pane
        right_box = QWidget()
        right_vbox = QVBoxLayout(right_box)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(4)

        right_header = QHBoxLayout()
        right_lbl = QLabel("Right:")
        right_lbl.setStyleSheet("font-weight: 600; color: #9ca3af;")
        right_header.addWidget(right_lbl)

        self.combo_right = QComboBox()
        self.combo_right.currentIndexChanged.connect(self._on_right_selection_changed)
        right_header.addWidget(self.combo_right, stretch=1)

        self.right_badge = QLabel("—")
        self.right_badge.setStyleSheet("font-weight: bold; padding: 2px 6px; border-radius: 3px;")
        right_header.addWidget(self.right_badge)
        right_vbox.addLayout(right_header)

        self.player_right = VideoPlayer()
        right_vbox.addWidget(self.player_right, stretch=1)

        self.right_status = QLabel("Frame: 0 / 0")
        self.right_status.setStyleSheet("color: #9ca3af; font-family: Consolas, monospace; font-size: 11px;")
        right_vbox.addWidget(self.right_status)
        panes_layout.addWidget(right_box, stretch=1)

        layout.addLayout(panes_layout, stretch=1)

        # Scrubber slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.seek_relative)
        layout.addWidget(self.slider)

        # Shared transport controls
        transport_layout = QHBoxLayout()
        transport_layout.setContentsMargins(4, 2, 4, 4)
        transport_layout.setSpacing(6)

        self.btn_restart = QPushButton("⏮ Restart")
        self.btn_restart.setToolTip("Restart both segments from relative frame 0")
        self.btn_restart.clicked.connect(self.restart)
        transport_layout.addWidget(self.btn_restart)

        self.btn_prev10 = QPushButton("« -10")
        self.btn_prev10.setToolTip("Step -10 relative frames")
        self.btn_prev10.clicked.connect(lambda: self.step_relative(-10))
        transport_layout.addWidget(self.btn_prev10)

        self.btn_prev1 = QPushButton("‹ -1")
        self.btn_prev1.setToolTip("Step -1 relative frame")
        self.btn_prev1.clicked.connect(lambda: self.step_relative(-1))
        transport_layout.addWidget(self.btn_prev1)

        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setObjectName("btn-play")
        self.btn_play.setToolTip("Play / Pause synchronized comparison (Space)")
        self.btn_play.clicked.connect(self.request_toggle_playback)
        transport_layout.addWidget(self.btn_play)

        self.btn_next1 = QPushButton("+1 ›")
        self.btn_next1.setToolTip("Step +1 relative frame")
        self.btn_next1.clicked.connect(lambda: self.step_relative(1))
        transport_layout.addWidget(self.btn_next1)

        self.btn_next10 = QPushButton("+10 »")
        self.btn_next10.setToolTip("Step +10 relative frames")
        self.btn_next10.clicked.connect(lambda: self.step_relative(10))
        transport_layout.addWidget(self.btn_next10)

        transport_layout.addStretch()

        self.lbl_counter = QLabel("REL: 0 / 0 fr")
        self.lbl_counter.setStyleSheet("font-family: Consolas, monospace; font-size: 13px; font-weight: bold; color: #60a5fa;")
        transport_layout.addWidget(self.lbl_counter)

        self.lbl_timecode = QLabel("00:00.000 / 00:00.000")
        self.lbl_timecode.setStyleSheet("font-family: Consolas, monospace; font-size: 13px; font-weight: bold; color: #60a5fa;")
        transport_layout.addWidget(self.lbl_timecode)

        layout.addLayout(transport_layout)

    def set_comparison_session(
        self,
        video_path: str,
        segments: list[Segment],
        fps: Fraction,
        default_left: Optional[Segment] = None,
        default_right: Optional[Segment] = None,
    ) -> None:
        """Configure segments and populate selector combos."""
        self.video_path = video_path
        self.fps = fps
        self.segments = [s for s in segments if s.is_valid]

        self.combo_left.blockSignals(True)
        self.combo_right.blockSignals(True)

        self.combo_left.clear()
        self.combo_right.clear()

        for seg in self.segments:
            dur = seg.duration_display(self.fps)
            label = f"{seg.name} ({dur})"
            self.combo_left.addItem(label, seg)
            self.combo_right.addItem(label, seg)

        # Smart defaults: fastest vs second fastest (or first two valid)
        sorted_segs = sorted(self.segments, key=lambda s: s.duration_frames)
        idx_left = 0
        idx_right = min(1, len(self.segments) - 1)

        if default_left in self.segments:
            idx_left = self.segments.index(default_left)
        elif sorted_segs:
            idx_left = self.segments.index(sorted_segs[0])

        if default_right in self.segments:
            idx_right = self.segments.index(default_right)
        elif len(sorted_segs) > 1:
            idx_right = self.segments.index(sorted_segs[1])

        self.combo_left.setCurrentIndex(idx_left)
        self.combo_right.setCurrentIndex(idx_right)

        self.combo_left.blockSignals(False)
        self.combo_right.blockSignals(False)

        self._refresh_selected_pair()

    def _refresh_selected_pair(self) -> None:
        if self.combo_left.count() == 0 or self.combo_right.count() == 0:
            return

        if self._is_playing:
            self._stop_for_navigation()

        self.seg_left = self.combo_left.currentData()
        self.seg_right = self.combo_right.currentData()

        if not self.seg_left or not self.seg_right:
            return

        left_dur = self.seg_left.duration_frames
        right_dur = self.seg_right.duration_frames
        self.max_rel_frame = max(left_dur, right_dur)

        self.slider.setRange(0, self.max_rel_frame)
        self._desired_rel_frame = 0
        self._displayed_rel_frame = 0
        self._seek_in_flight = False
        self._navigation_pending = False
        self._is_playing = False
        self._playback_intent = False
        self._start_pending = False

        # Update delta banner
        left_sec = self.seg_left.duration_seconds(self.fps)
        right_sec = self.seg_right.duration_seconds(self.fps)

        if left_dur < right_dur:
            diff_sec = right_sec - left_sec
            diff_fr = right_dur - left_dur
            pct = (diff_sec / left_sec) * 100.0 if left_sec > 0 else 0.0
            self.delta_banner.setText(
                f"{self.seg_left.name} is FASTEST: -{diff_sec:.3f}s / -{diff_fr} frames (-{pct:.2f}%) vs {self.seg_right.name}"
            )
            self.left_badge.setText("FASTEST")
            self.left_badge.setStyleSheet("color: #34d399; background-color: #064e3b; border: 1px solid #059669;")
            self.right_badge.setText(f"+{diff_sec:.3f}s")
            self.right_badge.setStyleSheet("color: #f87171; background-color: #3b181e; border: 1px solid #7f1d1d;")
        elif right_dur < left_dur:
            diff_sec = left_sec - right_sec
            diff_fr = left_dur - right_dur
            pct = (diff_sec / right_sec) * 100.0 if right_sec > 0 else 0.0
            self.delta_banner.setText(
                f"{self.seg_right.name} is FASTEST: -{diff_sec:.3f}s / -{diff_fr} frames (-{pct:.2f}%) vs {self.seg_left.name}"
            )
            self.right_badge.setText("FASTEST")
            self.right_badge.setStyleSheet("color: #34d399; background-color: #064e3b; border: 1px solid #059669;")
            self.left_badge.setText(f"+{diff_sec:.3f}s")
            self.left_badge.setStyleSheet("color: #f87171; background-color: #3b181e; border: 1px solid #7f1d1d;")
        else:
            self.delta_banner.setText(f"TIED: Both attempts took {left_sec:.3f}s ({left_dur} frames)")
            self.left_badge.setText("TIED")
            self.left_badge.setStyleSheet("color: #38bdf8; background-color: #1e293b;")
            self.right_badge.setText("TIED")
            self.right_badge.setStyleSheet("color: #38bdf8; background-color: #1e293b;")

        # Request setup in worker
        self.setup_requested.emit(self.video_path, self.seg_left, self.seg_right, self.fps)

    def _on_left_selection_changed(self) -> None:
        self._refresh_selected_pair()

    def _on_right_selection_changed(self) -> None:
        self._refresh_selected_pair()

    def seek_relative(self, rel_frame: int) -> None:
        """Coalesced relative seeking."""
        if self._is_playing:
            self._stop_for_navigation()

        self._desired_rel_frame = max(0, min(rel_frame, self.max_rel_frame))
        self.slider.setValue(self._desired_rel_frame)
        self._update_counter_labels(self._desired_rel_frame)
        self._begin_navigation()

    def step_relative(self, delta: int) -> None:
        """Coalesced relative stepping."""
        self.seek_relative(self._desired_rel_frame + delta)

    def restart(self) -> None:
        """Restart comparison from relative frame 0."""
        self._stop_for_navigation()
        self._desired_rel_frame = 0
        self.slider.setValue(0)
        self._update_counter_labels(0)
        self._navigation_pending = True
        self._seek_in_flight = True
        self.restart_requested.emit()

    def _stop_for_navigation(self) -> None:
        """Pause comparison before selection changes or user navigation."""
        self._playback_intent = False
        self._is_playing = False
        self._start_pending = False
        self._set_play_button(False)
        self.stop_play_requested.emit()

    def stop_playback(self) -> None:
        """Force the view to the stopped state when leaving Compare mode."""
        self._stop_for_navigation()

    def request_toggle_playback(self) -> None:
        """Request an explicit start/stop without toggling stale worker state."""
        if self._is_playing or self._playback_intent:
            self._playback_intent = False
            self._is_playing = False
            self._start_pending = False
            self._set_play_button(False)
            self.toggle_play_requested.emit()
            self.stop_play_requested.emit()
        else:
            self._playback_intent = True
            self._is_playing = True
            self._start_pending = True
            self._set_play_button(True)
            self.toggle_play_requested.emit()
            self.start_play_requested.emit()

    def _begin_navigation(self) -> None:
        if self._desired_rel_frame == self._displayed_rel_frame:
            self._navigation_pending = False
            self._seek_in_flight = False
            return
        self._navigation_pending = True
        self._dispatch_seek_if_idle()

    def _dispatch_seek_if_idle(self) -> None:
        if self._seek_in_flight or self._is_playing:
            return
        if self._desired_rel_frame == self._displayed_rel_frame:
            return
        self._seek_in_flight = True
        self.seek_relative_requested.emit(self._desired_rel_frame)

    @Slot(int, QImage, QImage, bool, bool)
    def on_frames_ready(
        self,
        rel_frame: int,
        img_left: QImage,
        img_right: QImage,
        left_frozen: bool,
        right_frozen: bool,
    ) -> None:
        """Render decoded frames on left and right players."""

        if self._navigation_pending and rel_frame != self._desired_rel_frame:
            # Ignore an older decode that was already queued when the user
            # changed the requested relative frame.
            self._seek_in_flight = False
            self._dispatch_seek_if_idle()
            return

        self._displayed_rel_frame = rel_frame
        self._seek_in_flight = False
        self._navigation_pending = False
        self._desired_rel_frame = rel_frame

        self.player_left.set_frame(img_left)
        self.player_right.set_frame(img_right)
        self.slider.setValue(rel_frame)

        self._update_counter_labels(rel_frame)

        # Update per-pane status lines
        if self.seg_left:
            cur_l = min(rel_frame, self.seg_left.duration_frames)
            tot_l = self.seg_left.duration_frames
            cur_l_sec = frame_to_seconds(cur_l, self.fps)
            freeze_txt = " [FINISHED / FROZEN]" if left_frozen else ""
            self.left_status.setText(f"Rel: {cur_l} / {tot_l} fr ({format_timecode(cur_l_sec)}){freeze_txt}")
            if left_frozen:
                self.left_status.setStyleSheet("color: #34d399; font-family: Consolas, monospace; font-size: 11px; font-weight: bold;")
            else:
                self.left_status.setStyleSheet("color: #9ca3af; font-family: Consolas, monospace; font-size: 11px;")

        if self.seg_right:
            cur_r = min(rel_frame, self.seg_right.duration_frames)
            tot_r = self.seg_right.duration_frames
            cur_r_sec = frame_to_seconds(cur_r, self.fps)
            freeze_txt = " [FINISHED / FROZEN]" if right_frozen else ""
            self.right_status.setText(f"Rel: {cur_r} / {tot_r} fr ({format_timecode(cur_r_sec)}){freeze_txt}")
            if right_frozen:
                self.right_status.setStyleSheet("color: #34d399; font-family: Consolas, monospace; font-size: 11px; font-weight: bold;")
            else:
                self.right_status.setStyleSheet("color: #9ca3af; font-family: Consolas, monospace; font-size: 11px;")

        # Coalescing check: dispatch newest target if changed while in flight.
        if self._desired_rel_frame != self._displayed_rel_frame:
            self._dispatch_seek_if_idle()

    def _update_counter_labels(self, rel_frame: int) -> None:
        cur_sec = frame_to_seconds(rel_frame, self.fps)
        tot_sec = frame_to_seconds(self.max_rel_frame, self.fps)
        self.lbl_counter.setText(f"REL: {rel_frame} / {self.max_rel_frame} fr")
        self.lbl_timecode.setText(f"{format_timecode(cur_sec)} / {format_timecode(tot_sec)}")

    @Slot(bool)
    def on_playback_state_changed(self, is_playing: bool) -> None:
        if is_playing:
            if not self._playback_intent:
                return
            self._is_playing = True
            self._start_pending = False
            self._set_play_button(True)
        else:
            if self._playback_intent and self._start_pending:
                return
            self._is_playing = False
            self._playback_intent = False
            self._start_pending = False
            self._set_play_button(False)

    def _set_play_button(self, is_playing: bool) -> None:
        if is_playing:
            self.btn_play.setText("⏸ Pause")
            self.btn_play.setStyleSheet("background-color: #854d0e; border-color: #ca8a04; color: #fef08a;")
        else:
            self.btn_play.setText("▶ Play")
            self.btn_play.setStyleSheet("")
