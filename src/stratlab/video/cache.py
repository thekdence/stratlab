"""Thread-safe LRU frame cache for StratLab."""

from __future__ import annotations
from collections import OrderedDict
import threading
from PySide6.QtGui import QImage


class FrameCache:
    """Thread-safe LRU cache storing decoded QImage frames by frame index."""

    def __init__(self, max_frames: int = 150, max_bytes: int = 128 * 1024 * 1024):
        self.max_frames = max_frames
        self.max_bytes = max(0, max_bytes)
        self._cache: OrderedDict[int, QImage] = OrderedDict()
        self._cache_bytes = 0
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

            image_bytes = int(image.sizeInBytes()) if not image.isNull() else 0
            if self.max_frames <= 0 or (self.max_bytes and image_bytes > self.max_bytes):
                return

            while self._cache and (
                len(self._cache) >= self.max_frames
                or (self.max_bytes and self._cache_bytes + image_bytes > self.max_bytes)
            ):
                _, evicted = self._cache.popitem(last=False)
                self._cache_bytes -= int(evicted.sizeInBytes()) if not evicted.isNull() else 0

            self._cache[frame_idx] = image
            self._cache_bytes += image_bytes

    def has(self, frame_idx: int) -> bool:
        """Check if frame is in cache without modifying LRU order."""
        with self._lock:
            return frame_idx in self._cache

    def clear(self) -> None:
        """Clear all cached frames."""
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)
