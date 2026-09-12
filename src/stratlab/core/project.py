"""Project model and JSON persistence for StratLab.

Saves and loads speedrun comparison sessions, including source video path,
segment definitions, IN/OUT frames, and playback state.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction
import json
import os
from pathlib import Path
from typing import Any

from stratlab.core.segment import Segment
from stratlab.core.timing import parse_fps


PROJECT_FILE_EXTENSION = ".stratlab"


@dataclass
class Project:
    """A StratLab comparison project."""
    video_path: str = ""
    segments: list[Segment] = field(default_factory=list)
    fps_str: str = "60"
    current_frame: int = 0
    selected_segment_index: int = 0
    filepath: str | None = None
    is_dirty: bool = False

    @property
    def fps(self) -> Fraction:
        return parse_fps(self.fps_str)

    @property
    def video_exists(self) -> bool:
        if not self.video_path:
            return False
        return os.path.exists(self.video_path)

    def mark_dirty(self) -> None:
        self.is_dirty = True

    def mark_clean(self) -> None:
        self.is_dirty = False

    def to_dict(self) -> dict[str, Any]:
        """Convert project data to a JSON-serializable dictionary."""
        return {
            "version": 1,
            "video_path": self.video_path,
            "fps": self.fps_str,
            "current_frame": self.current_frame,
            "selected_segment_index": self.selected_segment_index,
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], filepath: str | None = None) -> Project:
        """Create a Project instance from a dictionary."""
        video_path = data.get("video_path", "")

        # If filepath is known and video_path is relative, resolve relative to project file
        if filepath and video_path and not os.path.isabs(video_path):
            project_dir = os.path.dirname(os.path.abspath(filepath))
            candidate = os.path.normpath(os.path.join(project_dir, video_path))
            if os.path.exists(candidate):
                video_path = candidate

        segments_data = data.get("segments", [])
        segments = [Segment.from_dict(s) for s in segments_data]

        return cls(
            video_path=video_path,
            segments=segments,
            fps_str=str(data.get("fps", "60")),
            current_frame=int(data.get("current_frame", 0)),
            selected_segment_index=int(data.get("selected_segment_index", 0)),
            filepath=filepath,
            is_dirty=False,
        )

    def save(self, filepath: str | None = None) -> str:
        """Save project to a JSON file. Returns saved path."""
        target_path = filepath or self.filepath
        if not target_path:
            raise ValueError("Cannot save project without a destination filepath.")

        target = Path(target_path)
        if not target.suffix:
            target = target.with_suffix(PROJECT_FILE_EXTENSION)

        data = self.to_dict()
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self.filepath = str(target.resolve())
        self.is_dirty = False
        return self.filepath

    @classmethod
    def load(cls, filepath: str) -> Project:
        """Load project from a JSON file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data, filepath=str(path.resolve()))
