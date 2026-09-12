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
        self._last_tick_time: float = 0.0

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

        target_frame = max(0, min(target_frame, self.reader.total_frames - 1))
        self._target_seek_frame = target_frame
        self._decode_current_or_pending()

    @Slot(int)
    def step_frames(self, delta: int) -> None:
        """Step current frame by delta (+1, -1, +10, -10)."""
        if not self.reader:
            return
        if self.is_playing:
            self.stop_playback()

        new_frame = self.current_frame + delta
        self.seek(new_frame)

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
        self._segment_out_frame = None
        self.is_playing = True
        self._last_tick_time = time.perf_counter()
        if self._timer:
            self._timer.start()
        self.playback_state_changed.emit(True)

    @Slot(int, int)
    def play_segment(self, in_frame: int, out_frame: int) -> None:
        """Play strictly from in_frame to out_frame, then pause."""
        if not self.reader:
            return
        self.seek(in_frame)
        self._segment_out_frame = out_frame
        self.is_playing = True
        self._last_tick_time = time.perf_counter()
        if self._timer:
            self._timer.start()
        self.playback_state_changed.emit(True)

    @Slot()
    def stop_playback(self) -> None:
        """Pause playback."""
        if not self.is_playing:
            return
        self.is_playing = False
        if self._timer:
            self._timer.stop()
        self._segment_out_frame = None
        self.playback_state_changed.emit(False)

    def _on_play_tick(self) -> None:
        """Executed on each timer tick during playback."""
        if not self.reader or not self.is_playing:
            return

        next_frame = self.current_frame + 1

        # Check if we reached segment end
        if self._segment_out_frame is not None and next_frame > self._segment_out_frame:
            out_f = self._segment_out_frame
            self.stop_playback()
            self.segment_playback_finished.emit(out_f)
            return

        # Check if reached end of video
        if next_frame >= self.reader.total_frames:
            self.stop_playback()
            return

        self.current_frame = next_frame
        idx, img = self.reader.get_frame(next_frame)
        self.current_frame = idx
        self.frame_ready.emit(idx, img)

    def _decode_current_or_pending(self) -> None:
        """Decode the latest pending seek target."""
        if not self.reader or self._target_seek_frame is None:
            return

        target = self._target_seek_frame
        self._target_seek_frame = None

        idx, img = self.reader.get_frame(target)
        self.current_frame = idx
        self.frame_ready.emit(idx, img)

    @Slot()
    def cleanup(self) -> None:
        """Clean up resources before thread termination."""
        self.stop_playback()
        if self.reader:
            self.reader.close()
            self.reader = None
