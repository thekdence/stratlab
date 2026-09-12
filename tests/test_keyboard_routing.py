"""Integration tests for window-wide keyboard shortcut routing and focus states."""

from fractions import Fraction
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QApplication

from stratlab.ui.main_window import MainWindow
from stratlab.video.reader import VideoMetadata


@pytest.fixture
def active_window(qtbot):
    """Fixture providing an initialized MainWindow with dummy metadata."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    # Provide valid metadata for navigation and marking
    window.metadata = VideoMetadata(
        filepath="test.mp4",
        filename="test.mp4",
        width=1920,
        height=1080,
        fps=Fraction(60, 1),
        fps_display="60 FPS",
        duration_seconds=100.0,
        total_frames=6000,
        codec_name="h264",
    )
    window._desired_frame = 100
    window._displayed_frame = 100

    yield window
    window.close()


def test_keyboard_io_auto_attempt_workflow(qtbot, active_window):
    """Test pressing 'I' and 'O' via actual Qt key events across workflow."""
    window = active_window
    window.attempt_panel.set_segments([])

    # 1. At frame 100, press 'I' -> Creates Attempt 1 with IN=100
    window._displayed_frame = 100
    window._desired_frame = 100
    qtbot.keyClick(window, Qt.Key.Key_I)

    segs = window.attempt_panel.get_segments()
    assert len(segs) == 1
    assert segs[0].name == "Attempt 1"
    assert segs[0].in_frame == 100
    assert segs[0].out_frame is None

    # 2. Seek to frame 250, press 'O' -> Completes Attempt 1 with OUT=250
    window._displayed_frame = 250
    window._desired_frame = 250
    qtbot.keyClick(window, Qt.Key.Key_O)

    segs = window.attempt_panel.get_segments()
    assert len(segs) == 1
    assert segs[0].out_frame == 250
    assert segs[0].is_valid
    assert segs[0].duration_frames == 150

    # 3. Seek to frame 400, press 'I' -> Auto-creates Attempt 2 with IN=400!
    window._displayed_frame = 400
    window._desired_frame = 400
    qtbot.keyClick(window, Qt.Key.Key_I)

    segs = window.attempt_panel.get_segments()
    assert len(segs) == 2
    assert segs[1].name == "Attempt 2"
    assert segs[1].in_frame == 400
    assert segs[1].out_frame is None

    # 4. Seek to frame 520, press 'O' -> Completes Attempt 2 with OUT=520
    window._displayed_frame = 520
    window._desired_frame = 520
    qtbot.keyClick(window, Qt.Key.Key_O)

    segs = window.attempt_panel.get_segments()
    assert len(segs) == 2
    assert segs[1].out_frame == 520
    assert segs[1].is_valid
    assert segs[1].duration_frames == 120


def test_keyboard_routing_with_child_widget_focus(qtbot, active_window):
    """Test navigation and marking when child widgets (table, buttons, player) have focus."""
    window = active_window
    window.attempt_panel.set_segments([])

    # Focus the attempt table
    table = window.attempt_panel.table
    table.setFocus()
    qtbot.waitUntil(lambda: table.hasFocus(), timeout=1000)

    # Initial frame
    window._desired_frame = 200
    window._displayed_frame = 200

    # Test Right arrow (+1 frame) while table has focus
    qtbot.keyClick(table, Qt.Key.Key_Right)
    assert window._desired_frame == 201

    # Test Left arrow (-1 frame) while table has focus
    qtbot.keyClick(table, Qt.Key.Key_Left)
    assert window._desired_frame == 200

    # Test Shift+Right (+10 frames) while table has focus
    qtbot.keyClick(table, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert window._desired_frame == 210

    # Test Shift+Left (-10 frames) while table has focus
    qtbot.keyClick(table, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert window._desired_frame == 200

    # Test 'I' and 'O' while table has focus
    window._displayed_frame = 200
    qtbot.keyClick(table, Qt.Key.Key_I)
    assert len(window.attempt_panel.get_segments()) == 1
    assert window.attempt_panel.get_segments()[0].in_frame == 200

    window._displayed_frame = 350
    window._desired_frame = 350
    qtbot.keyClick(table, Qt.Key.Key_O)
    assert window.attempt_panel.get_segments()[0].out_frame == 350

    # Test Space while button has focus
    btn = window.transport.btn_play
    btn.setFocus()
    qtbot.waitUntil(lambda: btn.hasFocus(), timeout=1000)

    play_toggled = False
    def on_play():
        nonlocal play_toggled
        play_toggled = True

    window.request_toggle_play.connect(on_play)
    qtbot.keyClick(btn, Qt.Key.Key_Space)
    assert play_toggled


def test_typing_in_line_edit_not_intercepted(qtbot, active_window):
    """Test that typing letters (I, O, arrows) into a QLineEdit is NOT swallowed by shortcuts."""
    window = active_window
    window.attempt_panel.set_segments([])

    # Create a temporary QLineEdit inside the window
    line_edit = QLineEdit(window)
    window.layout().addWidget(line_edit)
    line_edit.show()
    line_edit.setFocus()
    qtbot.waitUntil(lambda: line_edit.hasFocus(), timeout=1000)

    # Initial frame
    window._desired_frame = 50
    window._displayed_frame = 50

    # Type 'I' into the QLineEdit
    qtbot.keyClicks(line_edit, "I")
    assert line_edit.text() == "I"
    # Verify no attempt was created!
    assert len(window.attempt_panel.get_segments()) == 0

    # Type 'O' into the QLineEdit
    qtbot.keyClicks(line_edit, "O")
    assert line_edit.text() == "IO"
    assert len(window.attempt_panel.get_segments()) == 0

    # Arrow keys should navigate text cursor, not step the video
    qtbot.keyClick(line_edit, Qt.Key.Key_Left)
    assert window._desired_frame == 50  # Frame untouched!
    assert line_edit.cursorPosition() == 1
