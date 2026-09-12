"""Segment data model and validation for StratLab.

Each segment represents a single attempt or strategy marked by IN and OUT frames.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction
import uuid

from stratlab.core.timing import frame_to_seconds, format_timecode, format_duration


@dataclass
class Segment:
    """A single comparison attempt marked with IN and OUT frames."""
    name: str = "Attempt"
    in_frame: int | None = None
    out_frame: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def is_complete(self) -> bool:
        """True if both IN and OUT frames have been marked."""
        return self.in_frame is not None and self.out_frame is not None

    @property
    def is_valid(self) -> bool:
        """True if both frames are marked and OUT > IN."""
        return (
            self.in_frame is not None
            and self.out_frame is not None
            and self.out_frame > self.in_frame
            and self.in_frame >= 0
        )

    @property
    def validation_error(self) -> str | None:
        """User-facing validation status or error message."""
        if self.in_frame is None and self.out_frame is None:
            return "Not marked (needs IN and OUT)"
        if self.in_frame is None:
            return "Incomplete (needs IN point)"
        if self.out_frame is None:
            return "Incomplete (needs OUT point)"
        if self.in_frame < 0:
            return "Invalid: IN frame cannot be negative"
        if self.out_frame <= self.in_frame:
            return f"Invalid: OUT ({self.out_frame}) must be > IN ({self.in_frame})"
        return None

    @property
    def duration_frames(self) -> int:
        """Duration in authoritative frames."""
        if not self.is_valid:
            return 0
        assert self.out_frame is not None and self.in_frame is not None
        return self.out_frame - self.in_frame

    def duration_seconds(self, fps: Fraction | float | int) -> float:
        """Duration in seconds based on authoritative frame count."""
        if not self.is_valid:
            return 0.0
        return frame_to_seconds(self.duration_frames, fps)

    def duration_ms(self, fps: Fraction | float | int) -> float:
        """Duration in milliseconds."""
        return self.duration_seconds(fps) * 1000.0

    def in_timecode(self, fps: Fraction | float | int) -> str:
        """Formatted timecode for IN frame."""
        if self.in_frame is None:
            return "—"
        return format_timecode(frame_to_seconds(self.in_frame, fps))

    def out_timecode(self, fps: Fraction | float | int) -> str:
        """Formatted timecode for OUT frame."""
        if self.out_frame is None:
            return "—"
        return format_timecode(frame_to_seconds(self.out_frame, fps))

    def duration_display(self, fps: Fraction | float | int) -> str:
        """Human readable duration string (e.g. 4.183s)."""
        if not self.is_valid:
            return "—"
        return format_duration(self.duration_seconds(fps))

    def to_dict(self) -> dict:
        """Serialize segment to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "in_frame": self.in_frame,
            "out_frame": self.out_frame,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Segment:
        """Deserialize segment from dict."""
        return cls(
            name=data.get("name", "Attempt"),
            in_frame=data.get("in_frame"),
            out_frame=data.get("out_frame"),
            id=data.get("id", uuid.uuid4().hex[:8]),
        )
