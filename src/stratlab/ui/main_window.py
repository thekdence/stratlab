"""Main application window for StratLab."""

from __future__ import annotations
from fractions import Fraction
import os
from typing import Optional
from PySide6.QtCore import Qt, QThread, Slot, Signal, QEvent
from PySide6.QtGui import QKeySequence, QAction, QKeyEvent
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QFileDialog,
    QMessageBox,
    QLabel,
    QApplication,
    QLineEdit,
)

from stratlab.core.segment import Segment
from stratlab.core.project import Project, PROJECT_FILE_EXTENSION
from stratlab.core.timing import parse_fps
from stratlab.video.reader import VideoMetadata
from stratlab.video.worker import VideoWorker
from stratlab.video.compare_worker import CompareWorker
from stratlab.ui.video_player import VideoPlayer
from stratlab.ui.timeline import TimelineWidget
from stratlab.ui.transport import TransportControls
from stratlab.ui.attempt_panel import AttemptPanel
from stratlab.ui.compare_view import CompareView
from stratlab.ui.theme import DARK_STYLESHEET


class MainWindow(QMainWindow):
    """Primary StratLab desktop application window."""

    # Thread-safe signals to worker
    request_open_video = Signal(str)
    request_seek = Signal(int)
    request_step = Signal(int)
    request_toggle_play = Signal()
    request_play_segment = Signal(int, int)
    request_cleanup = Signal()

    def __init__(self, initial_video: Optional[str] = None):
        super().__init__()
        self.setWindowTitle("StratLab — Speedrun Attempt Comparison Utility")
        self.resize(1280, 780)
        self.setMinimumSize(960, 540)
        self.setStyleSheet(DARK_STYLESHEET)

        self.project = Project()
        self.metadata: Optional[VideoMetadata] = None

        # Input coalescing state
        self._desired_frame: int = 0
        self._displayed_frame: int = 0
        self._seek_in_flight: bool = False

        # Setup primary video worker thread
        self.worker_thread = QThread(self)
        self.worker = VideoWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.initialize)

        # Wire UI request signals to worker slots (QueuedConnection across threads)
        self.request_open_video.connect(self.worker.open_video)
        self.request_seek.connect(self.worker.seek)
        self.request_step.connect(self.navigate_step)
        self.request_toggle_play.connect(self.worker.toggle_playback)
        self.request_play_segment.connect(self.worker.play_segment)
        self.request_cleanup.connect(self.worker.cleanup)

        # Connect worker signals to UI slots
        self.worker.video_loaded.connect(self._on_video_loaded)
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.playback_state_changed.connect(self._on_playback_state_changed)
        self.worker.segment_playback_finished.connect(self._on_segment_playback_finished)
        self.worker.error_occurred.connect(self._on_worker_error)

        self.worker_thread.start()

        # Setup compare worker thread
        self.compare_thread = QThread(self)
        self.compare_worker = CompareWorker()
        self.compare_worker.moveToThread(self.compare_thread)
        self.compare_thread.started.connect(self.compare_worker.initialize)
        self.compare_thread.start()

        self._build_ui()
        self._setup_menubar()

        # Install authoritative window event filter for navigation shortcuts
        self.installEventFilter(self)

        if initial_video and os.path.isfile(initial_video):
            self.load_video(initial_video)

    # --- Backward compatibility aliases for existing tests & scripts ---
    @property
    def segment_list(self) -> AttemptPanel:
        return self.attempt_panel

    @property
    def results_view(self) -> AttemptPanel:
        return self.attempt_panel

    def _build_ui(self) -> None:
        # Central stacked container (Page 0: Editor, Page 1: Compare View)
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        # PAGE 0: Single Video Editor
        editor_page = QWidget()
        editor_layout = QHBoxLayout(editor_page)
        editor_layout.setContentsMargins(6, 6, 6, 6)
        editor_layout.setSpacing(6)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left pane: Video + Timeline + Transport
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self.player = VideoPlayer()
        self.player.file_dropped.connect(self.load_video)
        self.player.clicked.connect(self.toggle_playback)
        left_layout.addWidget(self.player, stretch=1)

        self.timeline = TimelineWidget()
        self.timeline.seek_requested.connect(self.seek_to_frame)
        left_layout.addWidget(self.timeline)

        self.transport = TransportControls()
        self.transport.step_requested.connect(self.navigate_step)
        self.transport.play_toggled.connect(self.toggle_playback)
        self.transport.mark_in_requested.connect(self.mark_in_at_playhead)
        self.transport.mark_out_requested.connect(self.mark_out_at_playhead)
        left_layout.addWidget(self.transport)

        self.main_splitter.addWidget(left_pane)

        # Right pane: Unified Attempt & Results Panel
        self.attempt_panel = AttemptPanel()
        self.attempt_panel.seek_requested.connect(self.seek_to_frame)
        self.attempt_panel.play_segment_requested.connect(self.request_play_segment.emit)
        self.attempt_panel.segments_changed.connect(self._on_segments_changed)
        self.attempt_panel.segment_selected.connect(self._on_segment_selection_changed)
        self.attempt_panel.compare_requested.connect(self.enter_compare_mode)
        self.attempt_panel.status_message.connect(self._show_status_message)
        self.main_splitter.addWidget(self.attempt_panel)

        # 68% for video, 32% for attempt panel
        self.main_splitter.setSizes([880, 400])
        editor_layout.addWidget(self.main_splitter)
        self.stacked_widget.addWidget(editor_page)

        # PAGE 1: Side-by-Side Compare View
        self.compare_view = CompareView()
        self.compare_view.exit_requested.connect(self.exit_compare_mode)
        self.compare_view.setup_requested.connect(self.compare_worker.setup_comparison)
        self.compare_view.seek_relative_requested.connect(self.compare_worker.seek_relative)
        self.compare_view.step_relative_requested.connect(self.compare_worker.step_relative)
        self.compare_view.restart_requested.connect(self.compare_worker.restart)
        self.compare_view.toggle_play_requested.connect(self.compare_worker.toggle_playback)

        self.compare_worker.frames_ready.connect(self.compare_view.on_frames_ready)
        self.compare_worker.playback_state_changed.connect(self.compare_view.on_playback_state_changed)
        self.compare_worker.error_occurred.connect(self._on_worker_error)

        self.stacked_widget.addWidget(self.compare_view)

        # Status bar
        self.status_bar = self.statusBar()
        self.status_info = QLabel("Ready. Open or drag & drop a video to begin.")
        self.status_bar.addWidget(self.status_info, stretch=1)

        self.status_project = QLabel("No project loaded")
        self.status_bar.addPermanentWidget(self.status_project)

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()

        # File Menu
        menu_file = menubar.addMenu("&File")

        act_new_proj = QAction("&New Project", self)
        act_new_proj.setShortcut(QKeySequence("Ctrl+N"))
        act_new_proj.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act_new_proj.triggered.connect(self.new_project)
        menu_file.addAction(act_new_proj)

        act_open_video = QAction("&Open Video...", self)
        act_open_video.setShortcut(QKeySequence("Ctrl+O"))
        act_open_video.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act_open_video.triggered.connect(self.open_video_dialog)
        menu_file.addAction(act_open_video)

        menu_file.addSeparator()

        act_open_proj = QAction("Open &Project...", self)
        act_open_proj.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_proj.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act_open_proj.triggered.connect(self.open_project_dialog)
        menu_file.addAction(act_open_proj)

        act_save_proj = QAction("&Save Project", self)
        act_save_proj.setShortcut(QKeySequence("Ctrl+S"))
        act_save_proj.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act_save_proj.triggered.connect(self.save_project)
        menu_file.addAction(act_save_proj)

        act_save_as = QAction("Save Project &As...", self)
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_save_as.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act_save_as.triggered.connect(self.save_project_as)
        menu_file.addAction(act_save_as)

        menu_file.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence("Alt+F4"))
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Attempt Menu
        menu_attempt = menubar.addMenu("&Attempt")

        act_mark_in = QAction("Mark &IN", self)
        act_mark_in.setText("Mark IN\tI")
        act_mark_in.triggered.connect(self.mark_in_at_playhead)
        menu_attempt.addAction(act_mark_in)

        act_mark_out = QAction("Mark &OUT", self)
        act_mark_out.setText("Mark OUT\tO")
        act_mark_out.triggered.connect(self.mark_out_at_playhead)
        menu_attempt.addAction(act_mark_out)

        menu_attempt.addSeparator()

        act_add_attempt = QAction("&Add New Attempt", self)
        act_add_attempt.setShortcut(QKeySequence("Ctrl+T"))
        act_add_attempt.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act_add_attempt.triggered.connect(lambda: self.attempt_panel.add_segment())
        menu_attempt.addAction(act_add_attempt)

        act_compare = QAction("&Compare Attempts", self)
        act_compare.triggered.connect(self.enter_compare_mode)
        menu_attempt.addAction(act_compare)

        # Help Menu
        menu_help = menubar.addMenu("&Help")
        act_shortcuts = QAction("&Keyboard Shortcuts", self)
        act_shortcuts.triggered.connect(self._show_shortcuts_dialog)
        menu_help.addAction(act_shortcuts)

        act_about = QAction("&About StratLab", self)
        act_about.triggered.connect(self._show_about_dialog)
        menu_help.addAction(act_about)

    def eventFilter(self, watched, event: QEvent) -> bool:
        """Authoritative global event filter handling navigation and marking shortcuts."""
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            modifiers = key_event.modifiers()

            # If user is typing in a text entry, let normal editing proceed
            focus_w = QApplication.focusWidget()
            if isinstance(focus_w, QLineEdit):
                return super().eventFilter(watched, event)

            # In Compare Mode: handle Esc and Space
            if self.stacked_widget.currentIndex() == 1:
                if key == Qt.Key.Key_Escape:
                    self.exit_compare_mode()
                    return True
                elif key == Qt.Key.Key_Space:
                    self.compare_worker.toggle_playback()
                    return True
                elif key == Qt.Key.Key_Left:
                    delta = -10 if (modifiers & Qt.KeyboardModifier.ShiftModifier) else -1
                    self.compare_view.step_relative(delta)
                    return True
                elif key == Qt.Key.Key_Right:
                    delta = 10 if (modifiers & Qt.KeyboardModifier.ShiftModifier) else 1
                    self.compare_view.step_relative(delta)
                    return True
                return super().eventFilter(watched, event)

            # In Single Video Editor Mode:
            if key == Qt.Key.Key_I and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                self.mark_in_at_playhead()
                return True
            elif key == Qt.Key.Key_O and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                self.mark_out_at_playhead()
                return True
            elif key == Qt.Key.Key_Left:
                delta = -10 if (modifiers & Qt.KeyboardModifier.ShiftModifier) else -1
                self.navigate_step(delta)
                return True
            elif key == Qt.Key.Key_Right:
                delta = 10 if (modifiers & Qt.KeyboardModifier.ShiftModifier) else 1
                self.navigate_step(delta)
                return True
            elif key == Qt.Key.Key_Space:
                self.toggle_playback()
                return True

        return super().eventFilter(watched, event)

    # --- Robust Input Coalescing Navigation ---

    @Slot(int)
    def navigate_step(self, delta: int) -> None:
        """Step current frame with immediate UI responsiveness and worker coalescing."""
        if not self.metadata or self.metadata.total_frames <= 0:
            return

        if self.transport._is_playing:
            self.request_toggle_play.emit()

        total = self.metadata.total_frames
        self._desired_frame = max(0, min(total - 1, self._desired_frame + delta))

        # Snappy immediate visual update
        self.timeline.set_current_frame(self._desired_frame)
        self.transport.set_position(self._desired_frame, total, self.metadata.fps)

        self._dispatch_seek_if_idle()

    @Slot(int)
    def seek_to_frame(self, frame: int) -> None:
        """Seek to target frame with coalesced worker execution."""
        if not self.metadata or self.metadata.total_frames <= 0:
            return

        total = self.metadata.total_frames
        self._desired_frame = max(0, min(total - 1, frame))

        self.timeline.set_current_frame(self._desired_frame)
        self.transport.set_position(self._desired_frame, total, self.metadata.fps)

        self._dispatch_seek_if_idle()

    def _dispatch_seek_if_idle(self) -> None:
        """Dispatch seek to worker only if worker is currently idle."""
        if self._seek_in_flight:
            return
        if self._desired_frame == self._displayed_frame:
            return

        self._seek_in_flight = True
        self.request_seek.emit(self._desired_frame)

    @Slot(int, object)
    def _on_frame_ready(self, frame_idx: int, qimage) -> None:
        """Handle decoded frame from worker."""
        self._displayed_frame = frame_idx
        self._seek_in_flight = False
        self.player.set_frame(qimage)
        self.project.current_frame = frame_idx

        # If user changed desired frame while decode was in flight, request latest target immediately
        if self._desired_frame != self._displayed_frame:
            self._dispatch_seek_if_idle()
        else:
            total = self.metadata.total_frames if self.metadata else 0
            fps = self.metadata.fps if self.metadata else Fraction(60, 1)
            self.timeline.set_current_frame(frame_idx)
            self.transport.set_position(frame_idx, total, fps)

    @Slot()
    def toggle_playback(self) -> None:
        self.request_toggle_play.emit()

    # --- Mode Switching ---

    @Slot()
    def enter_compare_mode(self) -> None:
        """Switch to side-by-side strategy comparison view."""
        if not self.metadata or not self.project.video_path:
            QMessageBox.information(self, "Compare", "Please load a video first.")
            return

        valid_segments = [s for s in self.attempt_panel.get_segments() if s.is_valid]
        if len(valid_segments) < 2:
            QMessageBox.information(
                self,
                "Compare Strategies",
                "You need at least 2 valid attempts (with IN and OUT points) to compare them side-by-side.",
            )
            return

        # Pause single video playback
        if self.transport._is_playing:
            self.request_toggle_play.emit()

        self.compare_view.set_comparison_session(
            self.project.video_path,
            valid_segments,
            self.metadata.fps,
        )
        self.stacked_widget.setCurrentIndex(1)
        self.status_info.setText("Compare Mode: Side-by-side synchronized attempt playback (Esc to exit)")

    @Slot()
    def exit_compare_mode(self) -> None:
        """Return to primary video editor."""
        self.compare_worker.stop_playback()
        self.stacked_widget.setCurrentIndex(0)
        self._update_all_views()
        self.status_info.setText("Ready. Mark attempts or press Compare.")

    # --- Video & Attempt Marking ---

    @Slot(str)
    def load_video(self, filepath: str) -> None:
        """Initiate video loading via worker thread."""
        if not os.path.isfile(filepath):
            QMessageBox.warning(self, "Video Error", f"Video file not found:\n{filepath}")
            return

        self.status_info.setText(f"Loading video: {os.path.basename(filepath)}...")
        self.request_open_video.emit(filepath)

    @Slot(object)
    def _on_video_loaded(self, meta: VideoMetadata) -> None:
        self.metadata = meta
        self.project.video_path = meta.filepath
        self.project.fps_str = str(meta.fps)

        self._desired_frame = 0
        self._displayed_frame = 0
        self._seek_in_flight = False

        self.setWindowTitle(f"StratLab — {meta.filename}")
        self.timeline.set_range(meta.total_frames, meta.fps)
        self.transport.set_position(0, meta.total_frames, meta.fps)
        self.attempt_panel.set_fps(meta.fps)

        if self.project.segments:
            self.attempt_panel.set_segments(
                self.project.segments,
                self.project.selected_segment_index,
            )
        elif not self.attempt_panel.get_segments():
            self.attempt_panel.add_segment()

        self._update_all_views()

        self.status_info.setText(
            f"{meta.filename} | {meta.resolution_display} | {meta.codec_name.upper()} | "
            f"{meta.fps_display} | {meta.duration_display} ({meta.total_frames} frames)"
        )

    @Slot(bool)
    def _on_playback_state_changed(self, is_playing: bool) -> None:
        self.transport.set_playing(is_playing)

    @Slot(int)
    def _on_segment_playback_finished(self, out_frame: int) -> None:
        self.transport.set_playing(False)

    @Slot(str)
    def _on_worker_error(self, message: str) -> None:
        self.status_info.setText(f"Error: {message}")
        QMessageBox.critical(self, "Video Engine Error", message)

    @Slot()
    def mark_in_at_playhead(self) -> None:
        """Mark IN with automatic attempt creation."""
        cur_frame = self._displayed_frame
        self.attempt_panel.mark_in(cur_frame)
        self._update_all_views()

    @Slot()
    def mark_out_at_playhead(self) -> None:
        """Mark OUT for active attempt."""
        cur_frame = self._displayed_frame
        self.attempt_panel.mark_out(cur_frame)
        self._update_all_views()

    def _on_segments_changed(self) -> None:
        self.project.segments = self.attempt_panel.get_segments()
        self.project.mark_dirty()
        self._update_all_views()

    def _on_segment_selection_changed(self, index: int) -> None:
        self.project.selected_segment_index = index
        self._sync_timeline_segments()

    def _show_status_message(self, message: str) -> None:
        self.status_info.setText(message)

    def _update_all_views(self) -> None:
        self._sync_timeline_segments()

    def _sync_timeline_segments(self) -> None:
        segments = self.attempt_panel.get_segments()
        active_seg = self.attempt_panel.get_selected_segment()
        active_id = active_seg.id if active_seg else None
        self.timeline.set_segments(segments, active_id)

    # --- Project Persistence Actions ---

    def new_project(self) -> None:
        self.project = Project()
        self.metadata = None
        self._desired_frame = 0
        self._displayed_frame = 0
        self._seek_in_flight = False
        self.player.clear()
        self.attempt_panel.set_segments([])
        self.timeline.set_range(0, Fraction(60, 1))
        self.transport.set_position(0, 0, Fraction(60, 1))
        self.setWindowTitle("StratLab — Speedrun Attempt Comparison Utility")
        self.status_project.setText("New project")
        self.status_info.setText("Ready. Open a video or project.")

    def open_video_dialog(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Gameplay Recording",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.ts);;All Files (*.*)",
        )
        if filepath:
            self.load_video(filepath)

    def open_project_dialog(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open StratLab Project",
            "",
            f"StratLab Projects (*{PROJECT_FILE_EXTENSION});;All Files (*.*)",
        )
        if not filepath:
            return

        try:
            proj = Project.load(filepath)
            self.project = proj
            self.status_project.setText(f"Project: {os.path.basename(filepath)}")

            if proj.video_path and os.path.isfile(proj.video_path):
                self.load_video(proj.video_path)
            elif proj.video_path:
                QMessageBox.warning(
                    self,
                    "Video Relocated",
                    f"The source video for this project could not be found at:\n{proj.video_path}\n\n"
                    f"Please relocate or select the video file.",
                )
                self.open_video_dialog()

            self.attempt_panel.set_segments(proj.segments, proj.selected_segment_index)
            self.attempt_panel.set_fps(proj.fps)
            self._update_all_views()
            if proj.current_frame > 0:
                self.seek_to_frame(proj.current_frame)
        except Exception as e:
            QMessageBox.critical(self, "Project Load Error", f"Failed to load project:\n{e}")

    def save_project(self) -> bool:
        if not self.project.filepath:
            return self.save_project_as()

        try:
            self.project.segments = self.attempt_panel.get_segments()
            self.project.selected_segment_index = self.attempt_panel.get_selected_index()
            self.project.current_frame = self._displayed_frame
            saved_path = self.project.save()
            self.status_project.setText(f"Saved: {os.path.basename(saved_path)}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{e}")
            return False

    def save_project_as(self) -> bool:
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save StratLab Project",
            "",
            f"StratLab Projects (*{PROJECT_FILE_EXTENSION})",
        )
        if not filepath:
            return False

        try:
            self.project.segments = self.attempt_panel.get_segments()
            self.project.selected_segment_index = self.attempt_panel.get_selected_index()
            self.project.current_frame = self._displayed_frame
            saved_path = self.project.save(filepath)
            self.status_project.setText(f"Saved: {os.path.basename(saved_path)}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{e}")
            return False

    def _show_shortcuts_dialog(self) -> None:
        shortcuts_text = (
            "<b>StratLab Frame Navigation Shortcuts:</b><br><br>"
            "• <b>Left Arrow:</b> Step -1 Frame<br>"
            "• <b>Right Arrow:</b> Step +1 Frame<br>"
            "• <b>Shift + Left Arrow:</b> Step -10 Frames<br>"
            "• <b>Shift + Right Arrow:</b> Step +10 Frames<br>"
            "• <b>Space:</b> Play / Pause<br>"
            "• <b>I:</b> Mark IN point (auto-creates next attempt when current is complete)<br>"
            "• <b>O:</b> Mark OUT point for active attempt<br>"
            "• <b>Esc:</b> Exit Compare Mode<br><br>"
            "<b>Project Shortcuts:</b><br>"
            "• <b>Ctrl + N:</b> New Project<br>"
            "• <b>Ctrl + O:</b> Open Video<br>"
            "• <b>Ctrl + S:</b> Save Project<br>"
            "• <b>Ctrl + Shift + S:</b> Save Project As<br>"
            "• <b>Ctrl + T:</b> Add New Attempt<br>"
        )
        QMessageBox.information(self, "StratLab Keyboard Shortcuts", shortcuts_text)

    def _show_about_dialog(self) -> None:
        about_text = (
            "<b>StratLab v0.2.0</b><br>"
            "A frame-accurate speedrun attempt comparison utility.<br><br>"
            "Features instant frame scrubbing, automatic attempt creation, "
            "and synchronized side-by-side strategy comparison.<br>"
            "Powered by PySide6 &amp; PyAV."
        )
        QMessageBox.about(self, "About StratLab", about_text)

    def closeEvent(self, event) -> None:
        """Clean shutdown of worker threads and resources."""
        self.request_cleanup.emit()
        self.worker_thread.quit()
        self.worker_thread.wait(2000)

        self.compare_worker.cleanup()
        self.compare_thread.quit()
        self.compare_thread.wait(2000)

        super().closeEvent(event)
