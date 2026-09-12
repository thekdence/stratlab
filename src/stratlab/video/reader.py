"""PyAV video reader with frame-accurate random access and metadata extraction."""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import os
import av
from PySide6.QtGui import QImage

from stratlab.core.timing import parse_fps, format_fps, format_duration
from stratlab.video.cache import FrameCache


@dataclass
class VideoMetadata:
    """Metadata extracted from the video stream and container."""
    filepath: str
    filename: str
    width: int
    height: int
    fps: Fraction
    fps_display: str
    duration_seconds: float
    total_frames: int
    codec_name: str

    @property
    def resolution_display(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def duration_display(self) -> str:
        return format_duration(self.duration_seconds)


class VideoReader:
    """Decodes video frames with frame-accurate seeking and metadata caching."""

    def __init__(self, filepath: str, cache_size: int = 150):
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Video file not found: {filepath}")

        self.filepath = os.path.abspath(filepath)
        self.container = av.open(self.filepath)
        if not self.container.streams.video:
            raise ValueError(f"No video streams found in: {filepath}")

        self.stream = self.container.streams.video[0]
        # Prevent multithreading packet reordering artifacts in PyAV
        self.stream.thread_type = "AUTO"

        # Determine exact fractional FPS
        raw_fps = self.stream.average_rate or self.stream.base_rate or self.stream.guessed_rate or Fraction(60, 1)
        self.fps: Fraction = parse_fps(raw_fps)

        # Duration & total frames
        time_base = float(self.stream.time_base)
        if self.stream.duration is not None:
            self.duration: float = float(self.stream.duration) * time_base
        elif self.container.duration is not None:
            self.duration = float(self.container.duration) / float(av.time_base)
        else:
            self.duration = 0.0

        if self.stream.frames and self.stream.frames > 0:
            self.total_frames: int = self.stream.frames
        elif self.duration > 0:
            self.total_frames = max(1, int(round(self.duration * float(self.fps))))
        else:
            self.total_frames = 1

        self.start_pts: int = self.stream.start_time if self.stream.start_time is not None else 0

        self.metadata = VideoMetadata(
            filepath=self.filepath,
            filename=os.path.basename(self.filepath),
            width=self.stream.codec_context.width or 1920,
            height=self.stream.codec_context.height or 1080,
            fps=self.fps,
            fps_display=format_fps(self.fps),
            duration_seconds=self.duration,
            total_frames=self.total_frames,
            codec_name=self.stream.codec_context.name or "unknown",
        )

        # QImages hold expanded RGB pixels.  Bound by bytes as well as frame
        # count so a 1440p recording cannot turn the navigation cache into a
        # multi-gigabyte allocation.  Small test/preview videos still retain
        # the requested frame-count cache.
        self.cache = FrameCache(max_frames=cache_size)
        self._current_frame_idx: int = -1
        self._decoder_iter = None

    def _frame_to_qimage(self, frame: av.VideoFrame) -> QImage:
        """Convert PyAV VideoFrame to an independent QImage."""
        rgb_frame = frame.to_rgb()
        plane = rgb_frame.planes[0]
        buf = bytes(plane)
        qimg = QImage(
            buf,
            rgb_frame.width,
            rgb_frame.height,
            plane.line_size,
            QImage.Format.Format_RGB888,
        )
        return qimg.copy()

    def _pts_to_frame_idx(self, pts: int) -> int:
        """Calculate authoritative 0-based frame index from PTS."""
        rel_pts = pts - self.start_pts
        time_sec = float(rel_pts) * float(self.stream.time_base)
        idx = int(round(time_sec * float(self.fps)))
        return max(0, min(idx, self.total_frames - 1))

    def _frame_idx_to_pts(self, frame_idx: int) -> int:
        """Calculate container PTS for a given 0-based frame index."""
        time_sec = float(frame_idx) / float(self.fps)
        pts = int(round(time_sec / float(self.stream.time_base))) + self.start_pts
        return pts

    def get_frame(self, target_frame: int) -> tuple[int, QImage]:
        """Fetch a specific frame by authoritative index.

        Returns (actual_frame_idx, QImage).
        """
        # Clamp to valid range
        target_frame = max(0, min(target_frame, self.total_frames - 1))

        # Check LRU cache first
        cached = self.cache.get(target_frame)
        if cached is not None:
            # A cache hit may jump away from the suspended PyAV generator.  Do
            # not resume that generator as if it were positioned at the cache
            # hit; doing so can return a different frame on the next step.
            if target_frame != self._current_frame_idx:
                self._decoder_iter = None
            self._current_frame_idx = target_frame
            return target_frame, cached

        # Check if we can simply step forward sequentially (within a 45-frame forward window)
        can_step_forward = (
            self._decoder_iter is not None
            and self._current_frame_idx < target_frame
            and (target_frame - self._current_frame_idx) <= 45
        )

        if not can_step_forward:
            target_pts = self._frame_idx_to_pts(target_frame)
            self.container.seek(target_pts, stream=self.stream, backward=True)
            self._decoder_iter = self.container.decode(self.stream)

        # Decode frames sequentially until target frame is reached
        last_frame = None

        for frame in self._decoder_iter:
            pts = frame.pts if frame.pts is not None else frame.dts
            if pts is None:
                continue

            idx = self._pts_to_frame_idx(pts)
            self._current_frame_idx = idx
            last_frame = frame

            # Only perform costly RGB conversion and allocation on the target frame
            if idx >= target_frame:
                qimg = self._frame_to_qimage(frame)
                self.cache.put(idx, qimg)
                return idx, qimg

        if last_frame is not None:
            qimg = self._frame_to_qimage(last_frame)
            self.cache.put(self._current_frame_idx, qimg)
            self._decoder_iter = None
            return self._current_frame_idx, qimg

        # Fallback: if decode yielded no frame, return empty blank image
        fallback = QImage(self.metadata.width, self.metadata.height, QImage.Format.Format_RGB888)
        fallback.fill(0)
        return target_frame, fallback

    def close(self) -> None:
        """Close container and clear cache."""
        self._decoder_iter = None
        if hasattr(self, "container") and self.container:
            try:
                self.container.close()
            except Exception:
                pass
        self.cache.clear()
