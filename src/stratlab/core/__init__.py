"""Core models and timing calculations for StratLab."""

from stratlab.core.timing import (
    parse_fps,
    frame_to_seconds,
    seconds_to_frame,
    format_timecode,
    format_duration,
    format_fps,
)
from stratlab.core.segment import Segment
from stratlab.core.results import AttemptResult, calculate_results
from stratlab.core.project import Project

__all__ = [
    "parse_fps",
    "frame_to_seconds",
    "seconds_to_frame",
    "format_timecode",
    "format_duration",
    "format_fps",
    "Segment",
    "AttemptResult",
    "calculate_results",
    "Project",
]
