from fractions import Fraction
import pytest

from stratlab.core.segment import Segment


def test_segment_validation():
    # Valid segment
    s_valid = Segment(name="Attempt 1", in_frame=100, out_frame=351)
    assert s_valid.is_valid
    assert s_valid.is_complete
    assert s_valid.validation_error is None
    assert s_valid.duration_frames == 251

    # Incomplete segments
    s_no_out = Segment(name="Attempt 2", in_frame=100, out_frame=None)
    assert not s_no_out.is_valid
    assert not s_no_out.is_complete
    assert s_no_out.validation_error == "Incomplete (needs OUT point)"
    assert s_no_out.duration_frames == 0

    s_no_in = Segment(name="Attempt 3", in_frame=None, out_frame=200)
    assert not s_no_in.is_valid
    assert not s_no_in.is_complete
    assert s_no_in.validation_error == "Incomplete (needs IN point)"

    s_empty = Segment(name="Attempt 4", in_frame=None, out_frame=None)
    assert not s_empty.is_valid
    assert "needs IN and OUT" in (s_empty.validation_error or "")

    # Invalid range: OUT == IN
    s_equal = Segment(name="Equal", in_frame=100, out_frame=100)
    assert not s_equal.is_valid
    assert "must be > IN" in (s_equal.validation_error or "")

    # Invalid range: OUT < IN
    s_reversed = Segment(name="Reversed", in_frame=150, out_frame=100)
    assert not s_reversed.is_valid
    assert "must be > IN" in (s_reversed.validation_error or "")

    # Negative IN
    s_neg = Segment(name="Neg", in_frame=-1, out_frame=100)
    assert not s_neg.is_valid
    assert "cannot be negative" in (s_neg.validation_error or "")


def test_segment_timing():
    fps = Fraction(60, 1)
    seg = Segment(name="Attempt 1", in_frame=0, out_frame=251)
    assert seg.duration_frames == 251
    assert seg.duration_seconds(fps) == pytest.approx(4.183333, abs=1e-5)
    assert seg.duration_ms(fps) == pytest.approx(4183.333, abs=1e-2)
    assert seg.duration_display(fps) == "4.183s"
    assert seg.in_timecode(fps) == "00:00.000"
    assert seg.out_timecode(fps) == "00:04.183"


def test_segment_serialization():
    seg = Segment(name="My Strat", in_frame=45, out_frame=120, id="custom-id")
    d = seg.to_dict()
    assert d == {
        "id": "custom-id",
        "name": "My Strat",
        "in_frame": 45,
        "out_frame": 120,
    }

    seg2 = Segment.from_dict(d)
    assert seg2.id == seg.id
    assert seg2.name == seg.name
    assert seg2.in_frame == seg.in_frame
    assert seg2.out_frame == seg.out_frame
    assert seg2.is_valid
