from fractions import Fraction
import pytest

from stratlab.core.timing import (
    parse_fps,
    frame_to_seconds,
    seconds_to_frame,
    format_timecode,
    format_duration,
    format_fps,
)


def test_parse_fps():
    # Exact fractions
    assert parse_fps(Fraction(60, 1)) == Fraction(60, 1)
    assert parse_fps(Fraction(60000, 1001)) == Fraction(60000, 1001)

    # Standard broadcast fractional rates
    assert parse_fps(59.94) == Fraction(60000, 1001)
    assert parse_fps(29.97) == Fraction(30000, 1001)
    assert parse_fps(23.976) == Fraction(24000, 1001)
    assert parse_fps(60.0) == Fraction(60, 1)
    assert parse_fps(30.0) == Fraction(30, 1)

    # String format
    assert parse_fps("60000/1001") == Fraction(60000, 1001)
    assert parse_fps("59.94") == Fraction(60000, 1001)
    assert parse_fps("60") == Fraction(60, 1)


def test_frame_to_seconds():
    fps = Fraction(60, 1)
    assert frame_to_seconds(0, fps) == 0.0
    assert frame_to_seconds(60, fps) == 1.0
    assert frame_to_seconds(251, fps) == pytest.approx(4.1833333333, abs=1e-5)

    # Fractional 59.94
    fps_5994 = Fraction(60000, 1001)
    # 60000 frames is exactly 1001 seconds
    assert frame_to_seconds(60000, fps_5994) == 1001.0


def test_seconds_to_frame():
    fps = Fraction(60, 1)
    assert seconds_to_frame(0.0, fps) == 0
    assert seconds_to_frame(1.0, fps) == 60
    assert seconds_to_frame(4.183333, fps) == 251

    # Fractional 59.94
    fps_5994 = Fraction(60000, 1001)
    assert seconds_to_frame(1001.0, fps_5994) == 60000


def test_format_timecode():
    assert format_timecode(0.0) == "00:00.000"
    assert format_timecode(4.183) == "00:04.183"
    assert format_timecode(65.123) == "01:05.123"
    assert format_timecode(3665.456) == "01:01:05.456"
    assert format_timecode(12.5, include_hours=True) == "00:00:12.500"


def test_format_duration():
    assert format_duration(4.183) == "4.183s"
    assert format_duration(0.084) == "0.084s"
    assert format_duration(0.0) == "0.000s"


def test_format_fps():
    assert format_fps(Fraction(60, 1)) == "60 FPS"
    assert format_fps(Fraction(60000, 1001)) == "59.94 FPS"
    assert format_fps(59.94) == "59.94 FPS"
