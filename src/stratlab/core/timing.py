"""Timing and frame conversion utilities for StratLab.

Handles exact fractional frame rates (such as 59.94, 29.97, 23.976)
and precise conversions between frame numbers, seconds, and timecodes.
"""

from __future__ import annotations
from fractions import Fraction
import math


# Known standard broadcast / gaming fractional frame rates
STANDARD_RATES: dict[float, Fraction] = {
    59.94: Fraction(60000, 1001),
    29.97: Fraction(30000, 1001),
    23.976: Fraction(24000, 1001),
    119.88: Fraction(120000, 1001),
    240.0: Fraction(240, 1),
    144.0: Fraction(144, 1),
    120.0: Fraction(120, 1),
    60.0: Fraction(60, 1),
    50.0: Fraction(50, 1),
    30.0: Fraction(30, 1),
    25.0: Fraction(25, 1),
    24.0: Fraction(24, 1),
}


def parse_fps(val: Fraction | float | int | str) -> Fraction:
    """Parse FPS input into an exact Fraction.

    Recognizes standard broadcast rates (e.g. 59.94 -> 60000/1001).
    """
    if isinstance(val, Fraction):
        return val
    if isinstance(val, int):
        return Fraction(val, 1)
    if isinstance(val, str):
        val = val.strip()
        if "/" in val:
            num, den = val.split("/", 1)
            return Fraction(int(num), int(den))
        val = float(val)

    # Check against known standard rates within floating tolerance
    for std_float, std_frac in STANDARD_RATES.items():
        if math.isclose(val, std_float, abs_tol=0.005):
            return std_frac

    # Fallback to limit_denominator
    frac = Fraction(val).limit_denominator(100100)
    return frac


def frame_to_seconds(frame: int, fps: Fraction | float | int) -> float:
    """Convert frame number to seconds using exact FPS."""
    if frame <= 0:
        return 0.0
    fps_frac = parse_fps(fps) if not isinstance(fps, Fraction) else fps
    # Exact fraction calculation converted to float
    return float(Fraction(frame, 1) / fps_frac)


def seconds_to_frame(seconds: float, fps: Fraction | float | int) -> int:
    """Convert seconds to closest authoritative frame number."""
    if seconds <= 0.0:
        return 0
    fps_frac = parse_fps(fps) if not isinstance(fps, Fraction) else fps
    # Round to nearest integer frame
    return int(round(seconds * float(fps_frac)))


def format_timecode(seconds: float, include_hours: bool = False) -> str:
    """Format seconds into MM:SS.mmm or HH:MM:SS.mmm timecode."""
    if seconds < 0:
        sign = "-"
        seconds = abs(seconds)
    else:
        sign = ""

    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    sec = total_sec % 60
    total_min = total_sec // 60
    minutes = total_min % 60
    hours = total_min // 60

    if hours > 0 or include_hours:
        return f"{sign}{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"
    return f"{sign}{minutes:02d}:{sec:02d}.{ms:03d}"


def format_duration(seconds: float) -> str:
    """Format seconds into standard speedrun duration (e.g. 4.183s)."""
    if seconds < 0:
        return f"-{abs(seconds):.3f}s"
    return f"{seconds:.3f}s"


def format_fps(fps: Fraction | float | int) -> str:
    """Format FPS cleanly for UI display (e.g. '59.94' or '60.00')."""
    fps_frac = parse_fps(fps) if not isinstance(fps, Fraction) else fps
    val = float(fps_frac)
    if val.is_integer():
        return f"{int(val)} FPS"
    return f"{val:.2f} FPS"
