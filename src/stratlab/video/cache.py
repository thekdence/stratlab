"""Thread-safe LRU frame cache for StratLab."""

from __future__ import annotations
from collections import OrderedDict
import threading
from PySide6.QtGui import QImage


class FrameCache:
    """Thread-safe LRU cache storing decoded QImage frames by frame index."""

    def __init__(self, max_frames: int = 150):
        self.max_frames = max_frames
        self._cache: OrderedDict[int, QImage] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, frame_idx: int) -> QImage | None:
        """Retrieve cached frame if present, updating LRU order."""
        with self._lock:
            if frame_idx in self._cache:
                self._cache.move_to_end(frame_idx)
                return self._cache[frame_idx]
            return None

    def put(self, frame_idx: int, image: QImage) -> None:
        """Add decoded frame to cache, evicting oldest entry if full."""
        with self._lock:
            if frame_idx in self._cache:
                self._cache.move_to_end(frame_idx)
                return
            if len(self._cache) >= self.max_frames:
                self._cache.popitem(last=False)
            self._cache[frame_idx] = image

    def has(self, frame_idx: int) -> bool:
        """Check if frame is in cache without modifying LRU order."""
        with self._lock:
            return frame_idx in self._cache

    def clear(self) -> None:
        """Clear all cached frames."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)
