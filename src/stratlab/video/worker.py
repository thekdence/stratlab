"""Asynchronous video worker thread for non-blocking decoding and playback."""

from __future__ import annotations
import time
from typing import Optional
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer, Qt
from PySide6.QtGui import QImage

from stratlab.video.reader import VideoReader, VideoMetadata


class VideoWorker(QObject):
    """Worker object that runs inside a background QThread."""

    # Signals emitted to UI
    video_loaded = Signal(object)              # VideoMetadata
    frame_ready = Signal(int, QImage)          # frame_idx, QImage
    playback_state_changed = Signal(bool)      # is_playing
    segment_playback_finished = Signal(int)    # out_frame
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.reader: Optional[VideoReader] = None
        self.current_frame: int = 0
        self.is_playing: bool = False
        self._target_seek_frame: Optional[int] = None
        self._segment_out_frame: Optional[int] = None
        self._timer: Optional[QTimer] = None
        self._playback_start_time: float = 0.0
        self._playback_start_frame: int = 0
        self._last_rendered_frame: int = -1

    @Slot()
    def initialize(self) -> None:
        """Called inside worker thread after thread starts."""
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_play_tick)

    @Slot(str)
    def open_video(self, filepath: str) -> None:
        """Open a video file asynchronously."""
        try:
            self.stop_playback()
            if self.reader:
                self.reader.close()
                self.reader = None

            self.reader = VideoReader(filepath)
            self.current_frame = 0
            self._target_seek_frame = None
            self._segment_out_frame = None

            # Decode initial frame 0
            idx, img = self.reader.get_frame(0)
            self.current_frame = idx

            # Update timer interval for video FPS
            if self._timer:
                interval_ms = max(1, int(round(1000.0 / float(self.reader.fps))))
                self._timer.setInterval(interval_ms)

            self.video_loaded.emit(self.reader.metadata)
            self.frame_ready.emit(idx, img)
        except Exception as e:
            self.error_occurred.emit(f"Failed to open video: {e}")

    @Slot(int)
    def seek(self, target_frame: int) -> None:
        """Seek to a target frame number."""
        if not self.reader:
            return
        try:
            target_frame = max(0, min(target_frame, self.reader.total_frames - 1))
            self._target_seek_frame = target_frame
            self._decode_current_or_pending()
        except Exception as e:
            self.error_occurred.emit(f"Failed to seek video: {e}")

    @Slot(int)
    def step_frames(self, delta: int) -> None:
        """Step current frame by delta (+1, -1, +10, -10)."""
        if not self.reader:
            return
        try:
            self.stop_playback()
            new_frame = self.current_frame + delta
            self.seek(new_frame)
        except Exception as e:
            self.error_occurred.emit(f"Failed to step video: {e}")

    @Slot()
    def toggle_playback(self) -> None:
        """Toggle play/pause."""
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    @Slot()
    def start_playback(self) -> None:
        """Start regular video playback."""
        if not self.reader or self.is_playing:
            return
        try:
            self._segment_out_frame = None

            # Play from the beginning when the last source frame is already
            # displayed.  Decode it before the first timed tick so restarting
            # at EOF is visible immediately and never shows a stale EOF frame.
            if self.current_frame >= self.reader.total_frames - 1:
                self._emit_decoded_frame(0)

            self.is_playing = True
            self._playback_start_time = time.perf_counter()
            self._playback_start_frame = self.current_frame
            self._last_rendered_frame = self.current_frame
            if self._timer:
                self._timer.start()
            self.playback_state_changed.emit(True)
        except Exception as e:
            self.is_playing = False
            if self._timer:
                self._timer.stop()
            self.error_occurred.emit(f"Failed to start playback: {e}")

    @Slot(int, int)
    def play_segment(self, in_frame: int, out_frame: int) -> None:
        """Play strictly from in_frame to out_frame, then pause."""
        if not self.reader:
            return
        try:
            self.stop_playback()
            in_frame = max(0, min(in_frame, self.reader.total_frames - 1))
            out_frame = max(in_frame, min(out_frame, self.reader.total_frames - 1))
            self._segment_out_frame = out_frame
            self._target_seek_frame = in_frame
            self._decode_current_or_pending()

            self.is_playing = True
            self._playback_start_time = time.perf_counter()
            self._playback_start_frame = self.current_frame
            self._last_rendered_frame = self.current_frame
            if self._timer:
                self._timer.start()
            self.playback_state_changed.emit(True)
        except Exception as e:
            self.is_playing = False
            if self._timer:
                self._timer.stop()
            self._segment_out_frame = None
            self.error_occurred.emit(f"Failed to play segment: {e}")

    @Slot()
    def stop_playback(self) -> None:
        """Pause playback."""
        was_playing = self.is_playing
        self.is_playing = False
        if self._timer:
            self._timer.stop()
        self._segment_out_frame = None
        if was_playing:
            self.playback_state_changed.emit(False)

    def _on_play_tick(self) -> None:
        """Executed on each timer tick during playback."""
        if not self.reader or not self.is_playing:
            return
        try:
            elapsed = max(0.0, time.perf_counter() - self._playback_start_time)
            target_frame = self._playback_start_frame + int(elapsed * float(self.reader.fps))
            end_frame = (
                self._segment_out_frame
                if self._segment_out_frame is not None
                else self.reader.total_frames - 1
            )

            # The wall clock owns playback position.  If decoding falls behind,
            # jump directly to the newest frame instead of slowly replaying
            # obsolete frames and accumulating latency.
            if target_frame >= end_frame:
                if self.current_frame < end_frame:
                    self._emit_decoded_frame(end_frame)
                out_frame = self._segment_out_frame
                self.stop_playback()
                if out_frame is not None:
                    self.segment_playback_finished.emit(out_frame)
                return

            if target_frame > self._last_rendered_frame:
                self._emit_decoded_frame(target_frame)
                self._last_rendered_frame = self.current_frame
        except Exception as e:
            self.stop_playback()
            self.error_occurred.emit(f"Playback decode failed: {e}")

    def _decode_current_or_pending(self) -> None:
        """Decode the latest pending seek target."""
        if not self.reader or self._target_seek_frame is None:
            return

        target = self._target_seek_frame
        self._target_seek_frame = None

        self._emit_decoded_frame(target)

    def _emit_decoded_frame(self, target_frame: int) -> None:
        """Decode one frame and publish it as the worker's current frame."""
        if not self.reader:
            return
        idx, img = self.reader.get_frame(target_frame)
        self.current_frame = idx
        self.frame_ready.emit(idx, img)

    @Slot()
    def cleanup(self) -> None:
        """Clean up resources before thread termination."""
        self.stop_playback()
        if self.reader:
            self.reader.close()
            self.reader = None
