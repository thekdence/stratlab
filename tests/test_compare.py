"""Tests for side-by-side strategy comparison and relative frame alignment."""

from fractions import Fraction
import os
import tempfile
import av
import pytest

from stratlab.core.segment import Segment
from stratlab.video.compare_worker import CompareWorker
from stratlab.ui.compare_view import CompareView


@pytest.fixture
def compare_video():
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "compare_test.mp4")

    container = av.open(filepath, mode="w")
    stream = container.add_stream("libx264", rate=60)
    stream.width = 320
    stream.height = 240
    stream.pix_fmt = "yuv420p"

    # 180 frames (3 seconds)
    for i in range(180):
        frame = av.VideoFrame(320, 240, "rgb24")
        packet = stream.encode(frame)
        container.mux(packet)

    for packet in stream.encode():
        container.mux(packet)

    container.close()
    yield filepath

    try:
        os.remove(filepath)
        os.rmdir(temp_dir)
    except Exception:
        pass


def test_compare_worker_relative_alignment_and_freeze(qtbot, compare_video):
    worker = CompareWorker()
    worker.initialize()

    # Attempt A: 20 frames long (IN=10, OUT=30)
    # Attempt B: 50 frames long (IN=100, OUT=150)
    seg_a = Segment(name="Strat Short", in_frame=10, out_frame=30)
    seg_b = Segment(name="Strat Long", in_frame=100, out_frame=150)
    fps = Fraction(60, 1)

    received_frames = []
    def on_frames_ready(rel_f, img_l, img_r, left_frozen, right_frozen):
        received_frames.append((rel_f, left_frozen, right_frozen))

    worker.frames_ready.connect(on_frames_ready)

    # 1. Setup comparison
    worker.setup_comparison(compare_video, seg_a, seg_b, fps)
    assert worker.max_rel_frame == 50
    assert worker.rel_frame == 0
    assert len(received_frames) == 1
    # At relative frame 0: neither is frozen
    assert received_frames[0] == (0, False, False)

    # 2. Seek to relative frame 15 (both active)
    worker.seek_relative(15)
    assert received_frames[-1] == (15, False, False)

    # 3. Seek to relative frame 25 (Attempt A has 20 frames, so it must FREEZE!)
    worker.seek_relative(25)
    rel_f, left_frozen, right_frozen = received_frames[-1]
    assert rel_f == 25
    assert left_frozen is True   # Shorter attempt is FROZEN on its final frame!
    assert right_frozen is False  # Longer attempt continues!

    # 4. Seek to relative frame 50 (Both finished)
    worker.seek_relative(50)
    rel_f, left_frozen, right_frozen = received_frames[-1]
    assert rel_f == 50
    assert left_frozen is True
    assert right_frozen is True

    # 5. Restart resets relative frame to 0
    worker.restart()
    rel_f, left_frozen, right_frozen = received_frames[-1]
    assert rel_f == 0
    assert left_frozen is False
    assert right_frozen is False

    # 6. Cleanup
    worker.cleanup()
    assert worker.reader_left is None
    assert worker.reader_right is None


def test_compare_view_ui_integration(qtbot, compare_video):
    view = CompareView()
    qtbot.addWidget(view)
    view.show()

    seg_a = Segment(name="Strat A", in_frame=10, out_frame=30)   # 20 fr
    seg_b = Segment(name="Strat B", in_frame=50, out_frame=100)  # 50 fr
    fps = Fraction(60, 1)

    view.set_comparison_session(compare_video, [seg_a, seg_b], fps)
    assert view.combo_left.count() == 2
    assert view.combo_right.count() == 2
    assert "FASTEST" in view.left_badge.text()
    assert "+0.500s" in view.right_badge.text()
    assert view.max_rel_frame == 50

    # Test stepping
    view.step_relative(1)
    assert view._desired_rel_frame == 1
    view.step_relative(10)
    assert view._desired_rel_frame == 11
    view.restart()
    assert view._desired_rel_frame == 0

    view.close()
