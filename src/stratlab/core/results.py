"""Speedrun comparison and ranking calculations for StratLab.

Ranks attempts by duration, identifies the fastest strategy, and calculates
exact deltas in seconds, frames, and percentage slower.
"""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction

from stratlab.core.segment import Segment
from stratlab.core.timing import format_duration


@dataclass
class AttemptResult:
    """Calculated comparison metrics for an attempt relative to the fastest."""
    rank: int
    segment: Segment
    duration_frames: int
    duration_seconds: float
    duration_ms: float
    delta_seconds: float
    delta_frames: int
    percent_slower: float
    is_fastest: bool

    @property
    def name(self) -> str:
        return self.segment.name

    def delta_display(self) -> str:
        """Formatted delta string (e.g. 'FASTEST' or '+0.084s / +5 frames / +2.01%')."""
        if self.is_fastest:
            return "FASTEST"
        sec_str = f"+{self.delta_seconds:.3f}s"
        frames_str = f"+{self.delta_frames} frames"
        pct_str = f"+{self.percent_slower:.2f}%"
        return f"{sec_str} / {frames_str} / {pct_str}"

    def summary_line(self) -> str:
        """Single line representation matching speedrun utility convention."""
        dur_str = format_duration(self.duration_seconds)
        frames_str = f"{self.duration_frames} frames"
        if self.is_fastest:
            return f"{self.name} — {dur_str} — {frames_str} — FASTEST"
        return f"{self.name} — {dur_str} — {frames_str} — +{self.delta_seconds:.3f}s / +{self.delta_frames} frames / +{self.percent_slower:.2f}%"


def calculate_results(
    segments: list[Segment],
    fps: Fraction | float | int,
) -> list[AttemptResult]:
    """Calculate ranked comparison results for all valid segments.

    Requires at least two valid segments to produce comparative results.
    Returns an empty list if fewer than two valid segments exist.
    """
    valid_segments = [s for s in segments if s.is_valid]
    if len(valid_segments) < 2:
        return []

    # Sort primarily by duration in frames (authoritative), then by name
    sorted_segments = sorted(
        valid_segments,
        key=lambda s: (s.duration_frames, s.name),
    )

    fastest_segment = sorted_segments[0]
    fastest_frames = fastest_segment.duration_frames
    fastest_duration = fastest_segment.duration_seconds(fps)

    results: list[AttemptResult] = []
    for idx, segment in enumerate(sorted_segments):
        cur_frames = segment.duration_frames
        cur_duration = segment.duration_seconds(fps)
        cur_ms = segment.duration_ms(fps)

        delta_sec = cur_duration - fastest_duration
        delta_fr = cur_frames - fastest_frames

        if fastest_duration > 0:
            pct_slower = ((cur_duration - fastest_duration) / fastest_duration) * 100.0
        else:
            pct_slower = 0.0

        is_fastest = (idx == 0) or (cur_frames == fastest_frames)
        rank = idx + 1

        results.append(
            AttemptResult(
                rank=rank,
                segment=segment,
                duration_frames=cur_frames,
                duration_seconds=cur_duration,
                duration_ms=cur_ms,
                delta_seconds=delta_sec,
                delta_frames=delta_fr,
                percent_slower=pct_slower,
                is_fastest=is_fastest,
            )
        )

    return results
