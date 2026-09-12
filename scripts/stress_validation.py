"""Stress test and runtime validation with realistic heavy video profile (2560x1440, 60fps, 2 minutes)."""

import os
import sys
import subprocess
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

from stratlab.ui.main_window import MainWindow
from stratlab.core.project import Project


def wait_for_condition(condition, timeout_ms: int = 10000, poll_interval_ms: int = 20):
    """Wait for condition to become true using a Qt event loop with hard watchdog timeout."""
    start_time = time.perf_counter()
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(poll_interval_ms)

    def check():
        elapsed = (time.perf_counter() - start_time) * 1000
        if condition():
            timer.stop()
            loop.quit()
        elif elapsed >= timeout_ms:
            timer.stop()
            loop.quit()

    timer.timeout.connect(check)
    timer.start()
    loop.exec()

    if not condition():
        raise TimeoutError(f"Condition not met within {timeout_ms}ms watchdog timeout.")


def generate_heavy_test_video(out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return

    print(f"Generating realistic 2560x1440 @ 60 FPS video (2 minutes = 7200 frames)...")
    t0 = time.perf_counter()
    # 2 minutes = 120 seconds of 2560x1440 60fps video
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "testsrc2=duration=120:size=2560x1440:rate=60",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg generation failed: {res.stderr}")
    print(f"Generated {out_path} ({out_path.stat().st_size / (1024*1024):.1f} MB) in {time.perf_counter() - t0:.1f}s")


def run_stress_validation():
    project_root = Path(__file__).resolve().parent.parent
    test_assets = project_root / "test_assets"
    video_path = test_assets / "heavy_1440p60.mp4"
    project_file = test_assets / "heavy_session.stratlab"

    generate_heavy_test_video(video_path)

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)

    print("\n--- 1. Testing Heavy Video Loading (2560x1440, 60fps, 120s) ---")
    window = MainWindow()
    window.show()

    window.load_video(str(video_path))
    wait_for_condition(lambda: window.metadata is not None, timeout_ms=8000)

    meta = window.metadata
    print(f"Loaded: {meta.filename}")
    print(f"Resolution: {meta.resolution_display}")
    print(f"FPS: {meta.fps_display} ({meta.fps})")
    print(f"Duration: {meta.duration_display} ({meta.total_frames} frames)")
    assert meta.width == 2560
    assert meta.height == 1440
    assert meta.total_frames >= 7195  # 120s at 60fps
    print("Heavy video loaded and verified successfully.")

    print("\n--- 2. Stress Testing Input Coalescing (Rapid +10 Keypresses) ---")
    seek_count = 0
    def on_seek_dispatched(f):
        nonlocal seek_count
        seek_count += 1

    window.request_seek.connect(on_seek_dispatched)

    # Hammer navigate_step(+10) 100 times in a burst
    t0 = time.perf_counter()
    for _ in range(100):
        window.navigate_step(10)
    burst_duration = (time.perf_counter() - t0) * 1000
    print(f"Fired 100 +10 step requests in {burst_duration:.1f}ms")

    # Desired frame must update synchronously to 1000
    assert window._desired_frame == 1000
    print(f"Synchronous desired target frame: {window._desired_frame}")

    # Wait for the background worker to catch up
    t_wait = time.perf_counter()
    wait_for_condition(lambda: window._displayed_frame == 1000, timeout_ms=5000)
    catchup_duration = (time.perf_counter() - t_wait) * 1000
    print(f"Worker caught up to frame 1000 in {catchup_duration:.1f}ms with {seek_count} actual decodes dispatched.")

    # Invariant: 100 inputs coalesced into <= 5 actual decodes
    assert seek_count <= 5, f"Expected <= 5 seeks due to coalescing, got {seek_count}"
    assert not window._seek_in_flight

    print("\n--- 3. Stress Testing Rapid Direction Reversal ---")
    seek_count = 0
    # Step backwards 50 times (-10 each = -500), then forwards 20 times (+1 each = +20)
    for _ in range(50):
        window.navigate_step(-10)
    for _ in range(20):
        window.navigate_step(1)

    expected_reversal_target = 1000 - 500 + 20  # 520
    assert window._desired_frame == expected_reversal_target

    wait_for_condition(lambda: window._displayed_frame == expected_reversal_target, timeout_ms=5000)
    print(f"Direction reversal caught up to frame {expected_reversal_target} with {seek_count} seeks.")
    assert seek_count <= 5

    print("\n--- 4. Testing Automatic Attempt Creation Workflow ---")
    window.attempt_panel.set_segments([])

    # Attempt 1: IN=300, OUT=660 (360 frames = 6.000s)
    window.seek_to_frame(300)
    wait_for_condition(lambda: window._displayed_frame == 300, timeout_ms=3000)
    window.mark_in_at_playhead()

    window.seek_to_frame(660)
    wait_for_condition(lambda: window._displayed_frame == 660, timeout_ms=3000)
    window.mark_out_at_playhead()

    assert len(window.attempt_panel.get_segments()) == 1
    assert window.attempt_panel.get_segments()[0].is_valid
    assert window.attempt_panel.get_segments()[0].duration_frames == 360
    print("Attempt 1 completed: 360 frames (6.000s)")

    # Attempt 2: Auto-creation! Seek to 1200, press I
    window.seek_to_frame(1200)
    wait_for_condition(lambda: window._displayed_frame == 1200, timeout_ms=3000)
    window.mark_in_at_playhead()

    assert len(window.attempt_panel.get_segments()) == 2
    assert window.attempt_panel.get_segments()[1].name == "Attempt 2"
    assert window.attempt_panel.get_segments()[1].in_frame == 1200
    print("Attempt 2 auto-created on 'I' keypress!")

    window.seek_to_frame(1530)
    wait_for_condition(lambda: window._displayed_frame == 1530, timeout_ms=3000)
    window.mark_out_at_playhead()

    assert window.attempt_panel.get_segments()[1].duration_frames == 330
    print("Attempt 2 completed: 330 frames (5.500s) -> FASTEST")

    # Attempt 3: Auto-creation! Seek to 2000, press I
    window.seek_to_frame(2000)
    wait_for_condition(lambda: window._displayed_frame == 2000, timeout_ms=3000)
    window.mark_in_at_playhead()

    assert len(window.attempt_panel.get_segments()) == 3
    print("Attempt 3 auto-created on 'I' keypress!")

    window.seek_to_frame(2380)
    wait_for_condition(lambda: window._displayed_frame == 2380, timeout_ms=3000)
    window.mark_out_at_playhead()

    assert window.attempt_panel.get_segments()[2].duration_frames == 380
    print("Attempt 3 completed: 380 frames (6.333s)")

    # Verify rankings
    window.attempt_panel.refresh()
    assert window.attempt_panel.btn_compare.isEnabled()
    assert window.attempt_panel.table.item(0, 1).text() == "Attempt 2"
    assert window.attempt_panel.table.item(0, 4).text() == "FASTEST"

    print("\n--- 5. Testing Side-by-Side Compare Mode ---")
    window.enter_compare_mode()
    assert window.stacked_widget.currentIndex() == 1
    assert window.compare_view.combo_left.count() == 3
    assert window.compare_view.combo_right.count() == 3

    # Default pair should be Attempt 2 (330 fr, FASTEST) vs Attempt 1 (360 fr)
    assert window.compare_view.seg_left.name == "Attempt 2"
    assert window.compare_view.seg_right.name == "Attempt 1"
    assert window.compare_view.max_rel_frame == 360
    assert "Attempt 2 is FASTEST" in window.compare_view.delta_banner.text()
    print("Compare mode initialized with smart defaults: Attempt 2 vs Attempt 1")

    # Relative seek to frame 340 (past Attempt 2's 330fr duration -> Left pane must freeze!)
    left_frozen_detected = False
    def on_compare_frames(rel_f, img_l, img_r, l_froz, r_froz):
        nonlocal left_frozen_detected
        if rel_f == 340 and l_froz and not r_froz:
            left_frozen_detected = True

    window.compare_worker.frames_ready.connect(on_compare_frames)
    window.compare_view.seek_relative(340)

    wait_for_condition(lambda: left_frozen_detected, timeout_ms=15000)
    assert left_frozen_detected
    print("Freeze verification: At relative frame 340, Attempt 2 is FROZEN on its final frame while Attempt 1 continues!")

    # Test Restart
    window.compare_view.restart()
    wait_for_condition(lambda: window.compare_view._displayed_rel_frame == 0, timeout_ms=10000)
    assert window.compare_view._displayed_rel_frame == 0
    print("Restart verified: both panes synchronously reset to relative frame 0.")

    # 5b. Exercise Synchronized Playback Cadence for a representative interval
    print("\n--- 5b. Exercising Synchronized Compare Playback Cadence ---")
    rendered_frames = []
    def on_playback_frame(rel_f, img_l, img_r, l_froz, r_froz):
        rendered_frames.append((time.perf_counter(), rel_f))

    window.compare_worker.frames_ready.connect(on_playback_frame)

    t_play_start = time.perf_counter()
    window.request_compare_toggle_play.emit()

    # Play until at least 120 relative frames have passed (2.0s of 60fps video) or 2.5s wall-clock
    wait_for_condition(
        lambda: window.compare_view._displayed_rel_frame >= 120 or (time.perf_counter() - t_play_start) >= 2.5,
        timeout_ms=6000,
    )
    t_play_end = time.perf_counter()
    window.request_compare_stop_play.emit()
    window.compare_worker.frames_ready.disconnect(on_playback_frame)

    actual_elapsed_wall = t_play_end - t_play_start
    final_rel_frame = window.compare_view._displayed_rel_frame
    video_time_elapsed = final_rel_frame / 60.0

    cadence_ratio = video_time_elapsed / actual_elapsed_wall if actual_elapsed_wall > 0 else 0
    frames_rendered = len(rendered_frames)
    effective_display_fps = frames_rendered / actual_elapsed_wall if actual_elapsed_wall > 0 else 0

    print("Compare Playback Cadence Results (Dual 2560x1440 @ 60 FPS):", flush=True)
    print(f"  Wall-clock time elapsed:  {actual_elapsed_wall:.3f}s", flush=True)
    print(f"  Video frames advanced:    {final_rel_frame} frames ({video_time_elapsed:.3f}s)", flush=True)
    print(f"  Speed ratio vs real-time: {cadence_ratio:.2f}x (1.00x is real-time)", flush=True)
    print(f"  Unique frame renders:     {frames_rendered} frames ({effective_display_fps:.1f} display FPS)", flush=True)

    # Invariant: Playback must not silently run in severe slow-motion
    assert cadence_ratio >= 0.80, f"Playback was too slow: {cadence_ratio:.2f}x real-time"
    print("Compare playback cadence verified within real-time tolerances!")

    # Return to editor
    window.exit_compare_mode()
    assert window.stacked_widget.currentIndex() == 0
    print("Exited compare mode cleanly.")

    print("\n--- 6. Testing Project Persistence ---")
    # Direct save to project_file without blocking UI modal dialog
    window.project.segments = window.attempt_panel.get_segments()
    window.project.save(str(project_file))
    assert project_file.exists()
    print(f"Saved project: {project_file}", flush=True)

    window.close()
    app.processEvents()
    print("\nALL HEAVY LOAD AND COMPARE MODE VERIFICATIONS PASSED SUCCESSFULLY!", flush=True)


if __name__ == "__main__":
    run_stress_validation()
    sys.exit(0)
