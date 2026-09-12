"""Regression coverage for the main and comparison playback state machines."""

from __future__ import annotations

import os
import tempfile

import av
import pytest

from stratlab.core.segment import Segment
from stratlab.ui.main_window import MainWindow


@pytest.fixture
def playback_video():
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "playback_regression.mp4")

    container = av.open(filepath, mode="w")
    stream = container.add_stream("libx264", rate=60)
    stream.width = 320
    stream.height = 240
    stream.pix_fmt = "yuv420p"

    # Keep every frame visually distinct so a real frame change is observable
    # if this fixture is inspected during a failure.
    for i in range(120):
        frame = av.VideoFrame(320, 240, "rgb24")
        for plane in frame.planes:
            plane.update(bytes([(i * 7) % 256]) * plane.buffer_size)
        for packet in stream.encode(frame):
            container.mux(packet)

    for packet in stream.encode():
        container.mux(packet)
    container.close()

    yield filepath

    try:
        os.remove(filepath)
        os.rmdir(temp_dir)
    except OSError:
        pass


@pytest.fixture
def loaded_window(qtbot, playback_video):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.load_video(playback_video)
    qtbot.waitUntil(lambda: window.metadata is not None, timeout=5000)
    yield window
    window.close()


def wait_for_frame(qtbot, window, frame: int, timeout: int = 5000) -> None:
    qtbot.waitUntil(lambda: window._displayed_frame == frame, timeout=timeout)


def test_main_play_pause_seek_step_and_eof_restart(qtbot, loaded_window):
    window = loaded_window

    # Play must advance monotonically instead of seeking back to the stale
    # paused target.
    window.toggle_playback()
    qtbot.waitUntil(lambda: window._is_playing, timeout=2000)
    qtbot.waitUntil(lambda: window._displayed_frame >= 8, timeout=3000)
    assert window._desired_frame == window._displayed_frame

    window.toggle_playback()
    qtbot.waitUntil(lambda: not window._is_playing, timeout=2000)
    paused_frame = window._displayed_frame
    qtbot.wait(100)
    assert window._displayed_frame == paused_frame

    # Resume continues from the displayed frame, not from an old desired
    # target.
    window.toggle_playback()
    qtbot.waitUntil(lambda: window._displayed_frame > paused_frame, timeout=3000)
    window.toggle_playback()
    qtbot.waitUntil(lambda: not window._is_playing, timeout=2000)

    # A seek or step while playing is a clean pause-and-navigate operation.
    window.toggle_playback()
    qtbot.waitUntil(lambda: window._displayed_frame >= paused_frame + 3, timeout=3000)
    window.seek_to_frame(70)
    wait_for_frame(qtbot, window, 70)
    assert not window._is_playing
    assert not window._seek_in_flight

    window.toggle_playback()
    qtbot.waitUntil(lambda: window._displayed_frame > 70, timeout=3000)
    window.navigate_step(10)
    wait_for_frame(qtbot, window, window._desired_frame)
    assert window._desired_frame >= 80
    assert not window._is_playing

    # Reaching EOF displays the final source frame, stops, and Play immediately
    # restarts at frame 0.
    last_frame = window.metadata.total_frames - 1
    window.seek_to_frame(last_frame)
    wait_for_frame(qtbot, window, last_frame)
    window.toggle_playback()
    qtbot.waitUntil(lambda: window._is_playing and window._displayed_frame == 0, timeout=4000)
    window.toggle_playback()


def test_main_segment_playback_stops_on_out(qtbot, loaded_window):
    window = loaded_window

    window.request_play_segment.emit(10, 30)
    qtbot.waitUntil(lambda: window._is_playing, timeout=2000)
    qtbot.waitUntil(
        lambda: not window._is_playing and window._displayed_frame == 30,
        timeout=4000,
    )
    assert window._desired_frame == 30
    assert not window._seek_in_flight


def test_compare_end_restart_restart_step_selection_and_reentry(qtbot, loaded_window):
    window = loaded_window
    segments = [
        Segment(name="Short", in_frame=10, out_frame=30),
        Segment(name="Long", in_frame=50, out_frame=90),
        Segment(name="Other", in_frame=15, out_frame=55),
    ]
    window.attempt_panel.set_segments(segments)
    window.enter_compare_mode()
    view = window.compare_view

    qtbot.waitUntil(lambda: view._displayed_rel_frame == 0, timeout=5000)
    assert view.max_rel_frame == 40

    # Normal completion must stop both clocks at the longest duration while
    # the shorter pane remains frozen on OUT.
    window.request_compare_toggle_play.emit()
    qtbot.waitUntil(lambda: view._is_playing, timeout=3000)
    qtbot.waitUntil(
        lambda: not view._is_playing and not window.compare_worker.is_playing,
        timeout=6000,
    )
    assert view._displayed_rel_frame == view.max_rel_frame
    assert "FINISHED / FROZEN" in view.left_status.text()
    assert view._desired_rel_frame == view._displayed_rel_frame

    # Play at the end must synchronously wrap both panes to relative frame 0.
    window.request_compare_toggle_play.emit()
    qtbot.waitUntil(
        lambda: view._is_playing and view._displayed_rel_frame == 0,
        timeout=4000,
    )
    window.request_compare_stop_play.emit()
    qtbot.waitUntil(lambda: not view._is_playing, timeout=2000)

    # Restart always decodes frame 0, even when the view already believes it
    # is stopped.
    view.seek_relative(view.max_rel_frame)
    qtbot.waitUntil(lambda: view._displayed_rel_frame == view.max_rel_frame, timeout=4000)
    view.restart()
    qtbot.waitUntil(lambda: view._displayed_rel_frame == 0, timeout=4000)
    assert window.compare_worker.rel_frame == 0

    # Backward stepping from the end remains frame-accurate.
    view.seek_relative(view.max_rel_frame)
    qtbot.waitUntil(lambda: view._displayed_rel_frame == view.max_rel_frame, timeout=4000)
    view.step_relative(-1)
    qtbot.waitUntil(lambda: view._displayed_rel_frame == view.max_rel_frame - 1, timeout=4000)

    # Selection changes reset the relative state and do not inherit the ended
    # playback clock.  Switching out and back in also starts fresh.
    view.combo_left.setCurrentIndex(1)
    qtbot.waitUntil(lambda: view.seg_left.name == "Long", timeout=4000)
    qtbot.waitUntil(lambda: view._displayed_rel_frame == 0, timeout=4000)
    window.exit_compare_mode()
    assert window.stacked_widget.currentIndex() == 0
    window.enter_compare_mode()
    qtbot.waitUntil(lambda: view._displayed_rel_frame == 0, timeout=5000)
    assert not view._is_playing


def test_reader_cache_hit_does_not_resume_stale_decoder(playback_video):
    from stratlab.video.reader import VideoReader

    reader = VideoReader(playback_video, cache_size=8)
    try:
        reader.get_frame(20)
        reader.get_frame(10)
        idx, _ = reader.get_frame(11)
        assert idx == 11
    finally:
        reader.close()


def test_closing_while_playing_stops_worker_threads(qtbot, loaded_window):
    window = loaded_window
    window.toggle_playback()
    qtbot.waitUntil(lambda: window._is_playing, timeout=2000)

    window.close()

    assert not window.worker_thread.isRunning()
    assert not window.compare_thread.isRunning()
