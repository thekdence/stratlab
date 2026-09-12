import os
import tempfile
import av
from PySide6.QtCore import Qt
import pytest

from stratlab.ui.main_window import MainWindow
from stratlab.core.segment import Segment


@pytest.fixture
def sample_video():
    """Create a temporary 60-frame 60fps MP4 video for UI integration tests."""
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "ui_test_sample.mp4")

    container = av.open(filepath, mode="w")
    stream = container.add_stream("libx264", rate=60)
    stream.width = 320
    stream.height = 240
    stream.pix_fmt = "yuv420p"

    for i in range(60):
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


def test_main_window_lifecycle_and_marking(qtbot, sample_video):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Load test video
    window.load_video(sample_video)
    qtbot.waitUntil(lambda: window.metadata is not None, timeout=3000)
    assert window.metadata.total_frames >= 58

    # Mark IN at frame 5
    window.seek_to_frame(5)
    qtbot.waitUntil(lambda: window.project.current_frame == 5, timeout=3000)
    window.mark_in_at_playhead()

    # Mark OUT at frame 35
    window.seek_to_frame(35)
    qtbot.waitUntil(lambda: window.project.current_frame == 35, timeout=3000)
    window.mark_out_at_playhead()

    segments = window.segment_list.get_segments()
    assert len(segments) >= 1
    assert segments[0].in_frame == 5
    assert segments[0].out_frame == 35
    assert segments[0].duration_frames == 30

    # Add second attempt
    seg2 = window.segment_list.add_segment(in_frame=10, out_frame=45)
    assert seg2.duration_frames == 35

    # Trigger view update
    window._update_all_views()

    # Results view should now have 2 ranked attempts
    assert window.results_view.table.isVisible()
    assert window.results_view.table.rowCount() == 2
    # Attempt 1 should be fastest (30 fr vs 35 fr)
    assert "Attempt 1" in window.results_view.table.item(0, 1).text()
    assert "FASTEST" in window.results_view.table.item(0, 4).text()

    # Close window cleanly
    window.close()
