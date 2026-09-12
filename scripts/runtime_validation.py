"""End-to-end runtime verification script for StratLab.

Generates synthetic test video, loads it into StratLab UI, steps frames,
marks attempts, calculates speedrun results, and validates project persistence.
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

from stratlab.ui.main_window import MainWindow
from stratlab.core.project import Project


def wait_for_action(action, signal, timeout_ms: int = 5000):
    """Execute action and wait for a Qt signal with a strict watchdog timeout."""
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    signal.connect(loop.quit)

    timer.start(timeout_ms)
    action()
    loop.exec()

    if not timer.isActive():
        raise TimeoutError(f"Signal wait timed out after {timeout_ms}ms")
    timer.stop()


def generate_test_video(out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return

    print(f"Generating synthetic 60fps test video: {out_path}")
    # 10 seconds of 60fps testsrc2 video = 600 frames
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "testsrc2=duration=10:size=640x360:rate=60",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg generation failed: {res.stderr}")
    print(f"Generated {out_path} ({out_path.stat().st_size} bytes)")


def run_verification():
    project_root = Path(__file__).resolve().parent.parent
    test_assets = project_root / "test_assets"
    video_path = test_assets / "gameplay_test_60fps.mp4"
    project_file = test_assets / "session_verify.stratlab"

    generate_test_video(video_path)

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)

    print("\n--- 1. Testing Video Loading & Metadata ---")
    window = MainWindow()
    window.show()

    # Load video
    wait_for_action(
        lambda: window.load_video(str(video_path)),
        window.worker.video_loaded,
        timeout_ms=5000,
    )

    assert window.metadata is not None
    print(f"Loaded: {window.metadata.filename}")
    print(f"Resolution: {window.metadata.resolution_display}")
    print(f"FPS: {window.metadata.fps_display} ({window.metadata.fps})")
    print(f"Duration: {window.metadata.duration_display} ({window.metadata.total_frames} frames)")
    assert window.metadata.total_frames == 600

    print("\n--- 2. Testing Seeking and Single-Frame Stepping ---")
    # Seek to frame 150
    wait_for_action(
        lambda: window.seek_to_frame(150),
        window.worker.frame_ready,
        timeout_ms=3000,
    )
    assert window.project.current_frame == 150
    print(f"Seek to 150 OK: current frame = {window.project.current_frame}")

    # Step +1
    wait_for_action(
        lambda: window.request_step.emit(1),
        window.worker.frame_ready,
        timeout_ms=2000,
    )
    assert window.project.current_frame == 151
    print(f"Step +1 OK: current frame = {window.project.current_frame}")

    # Step -1
    wait_for_action(
        lambda: window.request_step.emit(-1),
        window.worker.frame_ready,
        timeout_ms=2000,
    )
    assert window.project.current_frame == 150
    print(f"Step -1 OK: current frame = {window.project.current_frame}")

    # Step +10
    wait_for_action(
        lambda: window.request_step.emit(10),
        window.worker.frame_ready,
        timeout_ms=2000,
    )
    assert window.project.current_frame == 160
    print(f"Step +10 OK: current frame = {window.project.current_frame}")

    # Step -10
    wait_for_action(
        lambda: window.request_step.emit(-10),
        window.worker.frame_ready,
        timeout_ms=2000,
    )
    assert window.project.current_frame == 150
    print(f"Step -10 OK: current frame = {window.project.current_frame}")

    print("\n--- 3. Testing Attempt Creation & IN/OUT Marking ---")
    # Setup Attempt 1: Strat A (251 frames, 4.183s)
    window.segment_list.set_segments([])
    seg1 = window.segment_list.add_segment()
    seg1.name = "Strat A"
    wait_for_action(lambda: window.seek_to_frame(30), window.worker.frame_ready, timeout_ms=3000)
    window.mark_in_at_playhead()
    wait_for_action(lambda: window.seek_to_frame(281), window.worker.frame_ready, timeout_ms=3000)
    window.mark_out_at_playhead()
    assert seg1.duration_frames == 251
    print(f"Strat A marked: IN={seg1.in_frame}, OUT={seg1.out_frame}, duration={seg1.duration_frames} frames ({seg1.duration_display(window.metadata.fps)})")

    # Setup Attempt 2: Strat B (256 frames, 4.267s)
    seg2 = window.segment_list.add_segment()
    seg2.name = "Strat B"
    wait_for_action(lambda: window.seek_to_frame(100), window.worker.frame_ready, timeout_ms=3000)
    window.mark_in_at_playhead()
    wait_for_action(lambda: window.seek_to_frame(356), window.worker.frame_ready, timeout_ms=3000)
    window.mark_out_at_playhead()
    assert seg2.duration_frames == 256
    print(f"Strat B marked: IN={seg2.in_frame}, OUT={seg2.out_frame}, duration={seg2.duration_frames} frames ({seg2.duration_display(window.metadata.fps)})")

    # Setup Attempt 3: Strat C (273 frames, 4.550s)
    seg3 = window.segment_list.add_segment()
    seg3.name = "Strat C"
    wait_for_action(lambda: window.seek_to_frame(200), window.worker.frame_ready, timeout_ms=3000)
    window.mark_in_at_playhead()
    wait_for_action(lambda: window.seek_to_frame(473), window.worker.frame_ready, timeout_ms=3000)
    window.mark_out_at_playhead()
    assert seg3.duration_frames == 273
    print(f"Strat C marked: IN={seg3.in_frame}, OUT={seg3.out_frame}, duration={seg3.duration_frames} frames ({seg3.duration_display(window.metadata.fps)})")

    window._update_all_views()

    print("\n--- 4. Testing Comparison Results Calculation ---")
    assert window.results_view.table.isVisible()
    assert window.results_view.table.rowCount() == 3

    r0_name = window.results_view.table.item(0, 1).text()
    r0_dur = window.results_view.table.item(0, 2).text()
    r0_fr = window.results_view.table.item(0, 3).text()
    r0_delta = window.results_view.table.item(0, 4).text()
    print(f"Rank 1: {r0_name} | {r0_dur} | {r0_fr} | {r0_delta}")
    assert r0_name == "Strat A"
    assert r0_delta == "FASTEST"

    r1_name = window.results_view.table.item(1, 1).text()
    r1_dur = window.results_view.table.item(1, 2).text()
    r1_fr = window.results_view.table.item(1, 3).text()
    r1_delta = window.results_view.table.item(1, 4).text()
    print(f"Rank 2: {r1_name} | {r1_dur} | {r1_fr} | {r1_delta}")
    assert r1_name == "Strat B"
    assert "+0.083s" in r1_delta or "+0.084s" in r1_delta
    assert "256 fr" in r1_fr

    r2_name = window.results_view.table.item(2, 1).text()
    r2_dur = window.results_view.table.item(2, 2).text()
    r2_fr = window.results_view.table.item(2, 3).text()
    r2_delta = window.results_view.table.item(2, 4).text()
    print(f"Rank 3: {r2_name} | {r2_dur} | {r2_fr} | {r2_delta}")
    assert r2_name == "Strat C"
    assert "+0.367s" in r2_delta
    assert "273 fr" in r2_fr

    print("\n--- 5. Testing Project Persistence (Save & Reload) ---")
    window.project.segments = window.segment_list.get_segments()
    saved_file = window.project.save(str(project_file))
    print(f"Project saved: {saved_file}")
    assert Path(saved_file).exists()

    window.close()

    # Load project into fresh window
    print("Opening saved project in a new window...")
    window2 = MainWindow()
    window2.show()
    loaded_proj = Project.load(saved_file)
    window2.project = loaded_proj
    wait_for_action(
        lambda: window2.load_video(loaded_proj.video_path),
        window2.worker.video_loaded,
        timeout_ms=5000,
    )

    window2.segment_list.set_segments(loaded_proj.segments)
    window2._update_all_views()

    assert len(window2.segment_list.get_segments()) == 3
    assert window2.results_view.table.rowCount() == 3
    assert window2.results_view.table.item(0, 1).text() == "Strat A"
    print("Project reloaded successfully with all 3 attempts and identical rankings!")

    window2.close()
    print("\nALL RUNTIME BEHAVIORAL VERIFICATIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_verification()
