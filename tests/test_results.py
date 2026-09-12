from fractions import Fraction
import pytest

from stratlab.core.segment import Segment
from stratlab.core.results import calculate_results


def test_calculate_results_empty_or_single():
    fps = Fraction(60, 1)

    # Empty list
    assert calculate_results([], fps) == []

    # Only 1 valid segment
    s1 = Segment(name="Attempt 1", in_frame=0, out_frame=60)
    assert calculate_results([s1], fps) == []

    # 1 valid and 1 incomplete segment
    s2 = Segment(name="Attempt 2", in_frame=100, out_frame=None)
    assert calculate_results([s1, s2], fps) == []


def test_calculate_results_prompt_example():
    """Verify calculation results against prompt example numbers.

    Prompt example:
    - Strat A — 4.183s — 251 frames — FASTEST
    - Strat B — 4.267s — 256 frames — +0.084s / +5 frames / +2.01%
    - Strat C — 4.550s — 273 frames — +0.367s / +22 frames / +8.77%
    """
    fps = Fraction(60, 1)
    strat_a = Segment(name="Strat A", in_frame=0, out_frame=251)
    strat_b = Segment(name="Strat B", in_frame=0, out_frame=256)
    strat_c = Segment(name="Strat C", in_frame=0, out_frame=273)

    # Pass in shuffled order
    results = calculate_results([strat_c, strat_a, strat_b], fps)
    assert len(results) == 3

    # Rank 1: Strat A
    res_a = results[0]
    assert res_a.rank == 1
    assert res_a.name == "Strat A"
    assert res_a.duration_frames == 251
    assert res_a.duration_seconds == pytest.approx(4.183333, abs=1e-4)
    assert res_a.delta_seconds == 0.0
    assert res_a.delta_frames == 0
    assert res_a.percent_slower == 0.0
    assert res_a.is_fastest is True
    assert res_a.delta_display() == "FASTEST"

    # Rank 2: Strat B
    res_b = results[1]
    assert res_b.rank == 2
    assert res_b.name == "Strat B"
    assert res_b.duration_frames == 256
    assert res_b.duration_seconds == pytest.approx(4.266667, abs=1e-4)
    assert res_b.delta_seconds == pytest.approx(0.083333, abs=1e-4)
    assert res_b.delta_frames == 5
    # Exact percent slower = (256 - 251) / 251 * 100 = 1.992%
    assert res_b.percent_slower == pytest.approx(1.992, abs=0.01)
    assert res_b.is_fastest is False

    # Rank 3: Strat C
    res_c = results[2]
    assert res_c.rank == 3
    assert res_c.name == "Strat C"
    assert res_c.duration_frames == 273
    assert res_c.duration_seconds == pytest.approx(4.550000, abs=1e-4)
    assert res_c.delta_seconds == pytest.approx(0.366667, abs=1e-4)
    assert res_c.delta_frames == 22
    # Exact percent slower = (273 - 251) / 251 * 100 = 8.7649%
    assert res_c.percent_slower == pytest.approx(8.765, abs=0.01)
    assert res_c.is_fastest is False


def test_calculate_results_fractional_fps():
    """Verify calculations with 59.94 FPS (Fraction(60000, 1001))."""
    fps = Fraction(60000, 1001)

    s1 = Segment(name="Attempt 1", in_frame=0, out_frame=60000)  # 1001.0 seconds
    s2 = Segment(name="Attempt 2", in_frame=0, out_frame=60600)  # +600 frames = +10.01 seconds

    results = calculate_results([s1, s2], fps)
    assert len(results) == 2
    assert results[0].is_fastest
    assert results[0].duration_seconds == pytest.approx(1001.0, abs=1e-5)

    assert not results[1].is_fastest
    assert results[1].delta_frames == 600
    assert results[1].delta_seconds == pytest.approx(10.01, abs=1e-2)
    assert results[1].percent_slower == pytest.approx(1.0, abs=1e-2)


def test_calculate_results_ties():
    fps = Fraction(60, 1)
    s1 = Segment(name="Attempt 1", in_frame=0, out_frame=120)
    s2 = Segment(name="Attempt 2", in_frame=100, out_frame=220)  # identical 120 frames

    results = calculate_results([s1, s2], fps)
    assert len(results) == 2
    assert results[0].is_fastest
    assert results[1].is_fastest
    assert results[1].delta_frames == 0
    assert results[1].percent_slower == 0.0
