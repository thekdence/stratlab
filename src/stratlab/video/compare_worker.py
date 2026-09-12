"""Dedicated background worker for side-by-side synchronized attempt comparison."""

from __future__ import annotations
import time
from fractions import Fraction
from typing import Optional
from PySide6.QtCore import QObject, Signal, Slot, QTimer, Qt
from PySide6.QtGui import QImage

from stratlab.core.segment import Segment
from stratlab.video.reader import VideoReader


class CompareWorker(QObject):
    """Background worker driving dual-video synchronized segment playback."""

    # Signals emitted to UI
    frames_ready = Signal(int, QImage, QImage, bool, bool)  # rel_frame, img_left, img_right, left_frozen, right_frozen
    playback_state_changed = Signal(bool)                  # is_playing
    comparison_finished = Signal()
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.reader_left: Optional[VideoReader] = None
        self.reader_right: Optional[VideoReader] = None
        self.video_path: str = ""

        self.seg_left: Optional[Segment] = None
        self.seg_right: Optional[Segment] = None
        self.fps: Fraction = Fraction(60, 1)

        self.rel_frame: int = 0
        self.max_rel_frame: int = 0
        self.is_playing: bool = False

        self._pending_rel_frame: Optional[int] = None
        self._timer: Optional[QTimer] = None

        # Wall-clock real-time pacing state
        self._playback_start_time: float = 0.0
        self._playback_start_rel_frame: int = 0
        self._last_rendered_rel_frame: int = -1

        # Frozen frame caches (saves 50% CPU decode once shorter attempt completes)
        self._frozen_img_left: Optional[QImage] = None
        self._frozen_img_right: Optional[QImage] = None

    @Slot()
    def initialize(self) -> None:
        """Called inside worker thread after startup."""
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_play_tick)

    @Slot(str, object, object, object)
    def setup_comparison(
        self,
        video_path: str,
        seg_left: Segment,
        seg_right: Segment,
        fps: Fraction,
    ) -> None:
        """Initialize or switch comparison segments with independent decoders."""
        try:
            self.stop_playback()

            # Reuse existing readers if the video path hasn't changed
            if self.video_path != video_path or not self.reader_left or not self.reader_right:
                self._close_readers()
                self.video_path = video_path
                self.reader_left = VideoReader(video_path, cache_size=200)
                self.reader_right = VideoReader(video_path, cache_size=200)

            self.seg_left = seg_left
            self.seg_right = seg_right
            self.fps = fps

            left_dur = seg_left.duration_frames if seg_left and seg_left.is_valid else 0
            right_dur = seg_right.duration_frames if seg_right and seg_right.is_valid else 0
            self.max_rel_frame = max(left_dur, right_dur)

            # Update timer interval for video FPS
            if self._timer:
                interval_ms = max(1, int(round(1000.0 / float(self.fps))))
                self._timer.setInterval(interval_ms)

            # Start at relative frame 0
            self._reset_position()
            self._decode_relative_frame(0)
        except Exception as e:
            self.error_occurred.emit(f"Failed to setup comparison: {e}")

    @Slot(int)
    def seek_relative(self, rel_frame: int) -> None:
        """Seek both panes to the specified relative frame."""
        if not self.seg_left or not self.seg_right:
            return
        try:
            # A user seek is a navigation command, not a third playback clock.
            # Stop before decoding so playback cannot overwrite the requested
            # relative frame on the next timer tick.
            self.stop_playback()
            self._frozen_img_left = None
            self._frozen_img_right = None
            rel_frame = max(0, min(rel_frame, self.max_rel_frame))
            self._pending_rel_frame = rel_frame
            self._decode_pending()
        except Exception as e:
            self.error_occurred.emit(f"Failed to seek comparison: {e}")

    @Slot(int)
    def step_relative(self, delta: int) -> None:
        """Step relative frame position by delta (+1, -1, +10, -10)."""
        if self.is_playing:
            self.stop_playback()

        new_rel = self.rel_frame + delta
        self.seek_relative(new_rel)

    @Slot()
    def restart(self) -> None:
        """Reset relative frame position to 0 (synchronous start)."""
        try:
            self.stop_playback()
            self._reset_position()
            self._decode_relative_frame(0)
        except Exception as e:
            self.error_occurred.emit(f"Failed to restart comparison: {e}")

    @Slot()
    def toggle_playback(self) -> None:
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    @Slot()
    def start_playback(self) -> None:
        if not self.reader_left or not self.reader_right or self.is_playing:
            return
        try:
            # If already at the end, wrap and render relative frame 0 before
            # the first timer tick.  This makes Play at EOF an immediate,
            # deterministic restart for both panes.
            if self.rel_frame >= self.max_rel_frame:
                self._reset_position()

            self.is_playing = True
            self._playback_start_time = time.perf_counter()
            self._playback_start_rel_frame = self.rel_frame
            self._last_rendered_rel_frame = self.rel_frame
            if self._timer:
                self._timer.start()
            self.playback_state_changed.emit(True)

            if self.rel_frame == 0 and self._last_rendered_rel_frame == 0:
                self._decode_relative_frame(0)
        except Exception as e:
            self.is_playing = False
            if self._timer:
                self._timer.stop()
            self.error_occurred.emit(f"Failed to start comparison playback: {e}")

    @Slot()
    def stop_playback(self) -> None:
        was_playing = self.is_playing
        self.is_playing = False
        if self._timer:
            self._timer.stop()
        if was_playing:
            self.playback_state_changed.emit(False)

    def _on_play_tick(self) -> None:
        if not self.is_playing:
            return
        try:
            elapsed = max(0.0, time.perf_counter() - self._playback_start_time)
            target_rel = self._playback_start_rel_frame + int(elapsed * float(self.fps))

            if target_rel >= self.max_rel_frame:
                self._decode_relative_frame(self.max_rel_frame)
                self.stop_playback()
                self.comparison_finished.emit()
                return

            if target_rel <= self._last_rendered_rel_frame:
                return

            # Decode only the newest wall-clock position.  A slow decode must
            # skip obsolete intermediate frames rather than turn playback into
            # slow motion or build a render backlog.
            self._decode_relative_frame(target_rel)
            self._last_rendered_rel_frame = target_rel
        except Exception as e:
            self.stop_playback()
            self.error_occurred.emit(f"Comparison playback decode failed: {e}")

    def _decode_pending(self) -> None:
        if self._pending_rel_frame is None:
            return
        target = self._pending_rel_frame
        self._pending_rel_frame = None
        self._decode_relative_frame(target)

    def _decode_relative_frame(self, target_rel: int) -> None:
        if not self.reader_left or not self.reader_right or not self.seg_left or not self.seg_right:
            return

        target_rel = max(0, min(target_rel, self.max_rel_frame))
        self.rel_frame = target_rel

        # Calculate absolute frames
        assert self.seg_left.in_frame is not None and self.seg_left.out_frame is not None
        assert self.seg_right.in_frame is not None and self.seg_right.out_frame is not None

        # Left pane source frame: clamps to OUT when finished (freeze frame)
        left_finished = target_rel >= self.seg_left.duration_frames
        left_src = min(self.seg_left.out_frame, self.seg_left.in_frame + target_rel)

        # Right pane source frame: clamps to OUT when finished (freeze frame)
        right_finished = target_rel >= self.seg_right.duration_frames
        right_src = min(self.seg_right.out_frame, self.seg_right.in_frame + target_rel)

        # Decode frames (caching frozen frames to avoid redundant decodes)
        if left_finished:
            if self._frozen_img_left is None:
                _, self._frozen_img_left = self.reader_left.get_frame(left_src)
            img_left = self._frozen_img_left
        else:
            self._frozen_img_left = None
            _, img_left = self.reader_left.get_frame(left_src)

        if right_finished:
            if self._frozen_img_right is None:
                _, self._frozen_img_right = self.reader_right.get_frame(right_src)
            img_right = self._frozen_img_right
        else:
            self._frozen_img_right = None
            _, img_right = self.reader_right.get_frame(right_src)

        self.frames_ready.emit(target_rel, img_left, img_right, left_finished, right_finished)

    def _reset_position(self) -> None:
        """Reset all position-dependent state without touching the readers."""
        self._frozen_img_left = None
        self._frozen_img_right = None
        self.rel_frame = 0
        self._pending_rel_frame = None
        self._last_rendered_rel_frame = -1

    def _close_readers(self) -> None:
        if self.reader_left:
            self.reader_left.close()
            self.reader_left = None
        if self.reader_right:
            self.reader_right.close()
            self.reader_right = None

    @Slot()
    def cleanup(self) -> None:
        """Clean shutdown releasing resources."""
        self.stop_playback()
        self._close_readers()
        self.video_path = ""
        self.seg_left = None
        self.seg_right = None
        self._frozen_img_left = None
        self._frozen_img_right = None
