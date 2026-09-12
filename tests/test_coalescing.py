"""Tests for input coalescing and anti-lag navigation."""

import os
import tempfile
import av
from PySide6.QtCore import Qt
import pytest

from stratlab.ui.main_window import MainWindow


@pytest.fixture
def sample_video():
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "coalescing_test.mp4")

    container = av.open(filepath, mode="w")
    stream = container.add_stream("libx264", rate=60)
    stream.width = 320
    stream.height = 240
    stream.pix_fmt = "yuv420p"

    for i in range(120):
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


def test_rapid_navigation_coalescing(qtbot, sample_video):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Load video
    window.load_video(sample_video)
    qtbot.waitUntil(lambda: window.metadata is not None, timeout=3000)

    # Track how many seeks are actually sent to the worker
    seek_requests_sent = 0
    def on_seek_requested(f):
        nonlocal seek_requests_sent
        seek_requests_sent += 1

    window.request_seek.connect(on_seek_requested)

    # Simulate rapid keypresses: user hammers Shift+Right 20 times rapidly
    for _ in range(20):
        window.navigate_step(10)

    # Desired frame must immediately be 119 (clamped to max frame)
    assert window._desired_frame == min(200, window.metadata.total_frames - 1)

    # Wait until all decoding settles
    qtbot.waitUntil(
        lambda: window._displayed_frame == window._desired_frame,
        timeout=3000,
    )

    # Invariant: Seeks sent must be vastly fewer than the 20 raw input events!
    # With coalescing, only 1-3 seeks should have ever been dispatched.
    print(f"Sent {seek_requests_sent} seeks for 20 rapid keypresses.")
    assert seek_requests_sent <= 4
    assert window._displayed_frame == window._desired_frame
    assert not window._seek_in_flight

    # Reversal test: user rapidly steps backwards 10 times
    seek_requests_sent = 0
    for _ in range(10):
        window.navigate_step(-10)

    expected_back = max(0, window._desired_frame)
    qtbot.waitUntil(
        lambda: window._displayed_frame == expected_back,
        timeout=3000,
    )
    assert seek_requests_sent <= 4
    assert window._displayed_frame == expected_back

    window.close()
