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
    QSlider,
)
from PySide6.QtGui import QFont, QImage

from stratlab.core.segment import Segment
from stratlab.core.timing import frame_to_seconds, format_timecode, format_duration
from stratlab.ui.video_player import VideoPlayer
from stratlab.ui.theme import PALETTE


def _restyle(widget: QWidget) -> None:
    """Re-run the stylesheet after a dynamic property changes."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


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
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # --- Header: exit, then the verdict ---------------------------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)

        self.btn_exit = QPushButton("← Attempts")
        self.btn_exit.setToolTip("Return to single-video editor (Esc)")
        self.btn_exit.setProperty("flat", "true")
        self.btn_exit.clicked.connect(self.exit_requested.emit)
        header_layout.addWidget(self.btn_exit, 0, Qt.AlignmentFlag.AlignVCenter)

        # The verdict reads as a sentence; the arithmetic sits beneath it.
        verdict_box = QVBoxLayout()
        verdict_box.setContentsMargins(0, 0, 0, 0)
        verdict_box.setSpacing(1)

        self.delta_banner = QLabel("Select two attempts to compare")
        self.delta_banner.setObjectName("compare-summary")
        self.delta_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        verdict_box.addWidget(self.delta_banner)

        self.delta_detail = QLabel("")
        self.delta_detail.setObjectName("compare-summary-sub")
        self.delta_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        verdict_box.addWidget(self.delta_detail)

        header_layout.addLayout(verdict_box, stretch=1)

        # Balances the exit button so the verdict stays optically centred.
        spacer = QWidget()
        spacer.setFixedWidth(self.btn_exit.sizeHint().width())
        header_layout.addWidget(spacer)

        layout.addLayout(header_layout)

        # --- Dual video panes ------------------------------------------------
        panes_layout = QHBoxLayout()
        panes_layout.setSpacing(14)

        left_box, self.combo_left, self.left_badge, self.player_left, self.left_status = (
            self._build_pane(self._on_left_selection_changed)
        )
        panes_layout.addWidget(left_box, stretch=1)

        right_box, self.combo_right, self.right_badge, self.player_right, self.right_status = (
            self._build_pane(self._on_right_selection_changed)
        )
        panes_layout.addWidget(right_box, stretch=1)

        layout.addLayout(panes_layout, stretch=1)

        # --- Shared scrubber -------------------------------------------------
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.seek_relative)
        layout.addWidget(self.slider)

        # --- Shared transport ------------------------------------------------
        transport_layout = QHBoxLayout()
        transport_layout.setContentsMargins(0, 0, 0, 0)
        transport_layout.setSpacing(3)

        self.btn_restart = QPushButton("Restart")
        self.btn_restart.setToolTip("Restart both segments from relative frame 0")
        self.btn_restart.setProperty("flat", "true")
        self.btn_restart.clicked.connect(self.restart)
        transport_layout.addWidget(self.btn_restart)

        transport_layout.addSpacing(18)

        self.btn_prev10 = QPushButton("−10")
        self.btn_prev10.setToolTip("Step -10 relative frames")
        self.btn_prev10.clicked.connect(lambda: self.step_relative(-10))
        transport_layout.addWidget(self.btn_prev10)

        self.btn_prev1 = QPushButton("−1")
        self.btn_prev1.setToolTip("Step -1 relative frame")
        self.btn_prev1.clicked.connect(lambda: self.step_relative(-1))
        transport_layout.addWidget(self.btn_prev1)

        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("btn-play")
        self.btn_play.setToolTip("Play / Pause synchronized comparison (Space)")
        self.btn_play.clicked.connect(self.request_toggle_playback)
        transport_layout.addWidget(self.btn_play)

        self.btn_next1 = QPushButton("+1")
        self.btn_next1.setToolTip("Step +1 relative frame")
        self.btn_next1.clicked.connect(lambda: self.step_relative(1))
        transport_layout.addWidget(self.btn_next1)

        self.btn_next10 = QPushButton("+10")
        self.btn_next10.setToolTip("Step +10 relative frames")
        self.btn_next10.clicked.connect(lambda: self.step_relative(10))
        transport_layout.addWidget(self.btn_next10)

        transport_layout.addStretch()

        cap_rel = QLabel("RELATIVE")
        cap_rel.setObjectName("readout-unit")
        transport_layout.addWidget(cap_rel, 0, Qt.AlignmentFlag.AlignVCenter)
        transport_layout.addSpacing(5)

        self.lbl_counter = QLabel("0 / 0")
        self.lbl_counter.setObjectName("readout-primary")
        transport_layout.addWidget(self.lbl_counter, 0, Qt.AlignmentFlag.AlignVCenter)

        transport_layout.addSpacing(20)

        self.lbl_timecode = QLabel("00:00.000 / 00:00.000")
        self.lbl_timecode.setObjectName("readout-secondary")
        transport_layout.addWidget(self.lbl_timecode, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(transport_layout)

    def _build_pane(self, on_selection_changed):
        """Build one comparison pane: identity row, viewer, relative counter."""
        box = QWidget()
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)

        # The selector sizes to the attempt it names rather than stretching
        # across the pane, so the pair reads as a caption above the video.
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.currentIndexChanged.connect(on_selection_changed)
        header.addWidget(combo, 0, Qt.AlignmentFlag.AlignVCenter)

        badge = QLabel("—")
        badge.setObjectName("state-chip")
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        header.addStretch()
        vbox.addLayout(header)

        player = VideoPlayer()
        vbox.addWidget(player, stretch=1)

        status = QLabel("Frame: 0 / 0")
        status.setObjectName("pane-status")
        vbox.addWidget(status)

        return box, combo, badge, player, status

    def _set_badge(self, badge: QLabel, text: str, tone: str) -> None:
        badge.setText(text)
        badge.setProperty("tone", tone)
        _restyle(badge)

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
            self.delta_banner.setText(f"{self.seg_left.name} is FASTEST")
            self.delta_detail.setText(
                f"−{diff_sec:.3f}s   −{diff_fr} frames   −{pct:.2f}%   vs {self.seg_right.name}"
            )
            self._set_badge(self.left_badge, "FASTEST", "good")
            self._set_badge(self.right_badge, f"+{diff_sec:.3f}s", "slow")
        elif right_dur < left_dur:
            diff_sec = left_sec - right_sec
            diff_fr = left_dur - right_dur
            pct = (diff_sec / right_sec) * 100.0 if right_sec > 0 else 0.0
            self.delta_banner.setText(f"{self.seg_right.name} is FASTEST")
            self.delta_detail.setText(
                f"−{diff_sec:.3f}s   −{diff_fr} frames   −{pct:.2f}%   vs {self.seg_left.name}"
            )
            self._set_badge(self.right_badge, "FASTEST", "good")
            self._set_badge(self.left_badge, f"+{diff_sec:.3f}s", "slow")
        else:
            self.delta_banner.setText("Tied")
            self.delta_detail.setText(f"Both attempts took {left_sec:.3f}s   {left_dur} frames")
            self._set_badge(self.left_badge, "TIED", "tied")
            self._set_badge(self.right_badge, "TIED", "tied")

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
            self._update_pane_status(self.left_status, self.seg_left, rel_frame, left_frozen)

        if self.seg_right:
            self._update_pane_status(self.right_status, self.seg_right, rel_frame, right_frozen)

        # Coalescing check: dispatch newest target if changed while in flight.
        if self._desired_rel_frame != self._displayed_rel_frame:
            self._dispatch_seek_if_idle()

    def _update_pane_status(
        self, label: QLabel, seg: Segment, rel_frame: int, frozen: bool
    ) -> None:
        cur = min(rel_frame, seg.duration_frames)
        total = seg.duration_frames
        cur_sec = frame_to_seconds(cur, self.fps)
        freeze_txt = "   FINISHED / FROZEN" if frozen else ""
        label.setText(f"{cur} / {total} fr   {format_timecode(cur_sec)}{freeze_txt}")
        label.setProperty("frozen", "true" if frozen else "false")
        _restyle(label)

    def _update_counter_labels(self, rel_frame: int) -> None:
        cur_sec = frame_to_seconds(rel_frame, self.fps)
        tot_sec = frame_to_seconds(self.max_rel_frame, self.fps)
        self.lbl_counter.setText(f"{rel_frame} / {self.max_rel_frame}")
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
        self.btn_play.setText("Pause" if is_playing else "Play")
        self.btn_play.setProperty("playing", "true" if is_playing else "false")
        _restyle(self.btn_play)
