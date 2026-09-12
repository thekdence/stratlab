"""Tests for automatic attempt creation workflow with I and O keys."""

from fractions import Fraction
import pytest
from stratlab.ui.attempt_panel import AttemptPanel


def test_auto_attempt_creation_workflow(qtbot):
    panel = AttemptPanel()
    qtbot.addWidget(panel)
    panel.set_fps(Fraction(60, 1))

    status_messages = []
    panel.status_message.connect(status_messages.append)

    # 1. No attempts exist -> Press I at frame 30
    panel.mark_in(30)
    segs = panel.get_segments()
    assert len(segs) == 1
    assert segs[0].name == "Attempt 1"
    assert segs[0].in_frame == 30
    assert segs[0].out_frame is None
    assert not segs[0].is_complete

    # 2. Incomplete attempt -> user adjusts IN to frame 35
    panel.mark_in(35)
    segs = panel.get_segments()
    assert len(segs) == 1
    assert segs[0].in_frame == 35

    # 3. Mark OUT <= IN (invalid: frame 30 <= 35)
    panel.mark_out(30)
    segs = panel.get_segments()
    assert segs[0].out_frame is None  # Rejection without corrupting data
    assert any("must be after IN" in m for m in status_messages)

    # 4. Valid OUT -> frame 286 (251 frames, 4.183s)
    panel.mark_out(286)
    segs = panel.get_segments()
    assert segs[0].out_frame == 286
    assert segs[0].is_valid
    assert segs[0].duration_frames == 251
    assert any("Completed Attempt 1" in m for m in status_messages)

    # 5. Active attempt is now complete!
    # User moves to next section and presses I at frame 500
    # StratLab MUST automatically create Attempt 2 and set its IN!
    panel.mark_in(500)
    segs = panel.get_segments()
    assert len(segs) == 2
    assert segs[1].name == "Attempt 2"
    assert segs[1].in_frame == 500
    assert segs[1].out_frame is None

    # 6. Complete Attempt 2 at frame 756 (256 frames, 4.267s)
    panel.mark_out(756)
    segs = panel.get_segments()
    assert len(segs) == 2
    assert segs[1].out_frame == 756
    assert segs[1].is_valid
    assert segs[1].duration_frames == 256

    # 7. Press I again at frame 900 -> automatically creates Attempt 3!
    panel.mark_in(900)
    segs = panel.get_segments()
    assert len(segs) == 3
    assert segs[2].name == "Attempt 3"
    assert segs[2].in_frame == 900

    # 8. Complete Attempt 3 at frame 1173 (273 frames)
    panel.mark_out(1173)
    segs = panel.get_segments()
    assert len(segs) == 3
    assert segs[2].duration_frames == 273

    # Ranking check: Attempt 1 (251 fr) should be fastest
    panel.refresh()
    assert panel.btn_compare.isEnabled()
    assert panel.table.item(0, 1).text() == "Attempt 1"
    assert panel.table.item(0, 4).text() == "FASTEST"


def test_mark_out_without_in(qtbot):
    panel = AttemptPanel()
    qtbot.addWidget(panel)
    status_messages = []
    panel.status_message.connect(status_messages.append)

    # Pressing O with no attempt created yet
    panel.mark_out(100)
    assert len(panel.get_segments()) == 0
    assert any("Press 'I' first" in m for m in status_messages)
