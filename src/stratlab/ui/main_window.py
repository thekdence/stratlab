"""Main application window for StratLab."""

from __future__ import annotations
from fractions import Fraction
import os
from typing import Optional
from PySide6.QtCore import Qt, QThread, Slot, Signal, QKeyCombination
from PySide6.QtGui import QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QFileDialog,
    QMessageBox,
    QLabel,
    QApplication,
)

from stratlab.core.segment import Segment
from stratlab.core.project import Project, PROJECT_FILE_EXTENSION
from stratlab.core.timing import parse_fps
from stratlab.video.reader import VideoMetadata
from stratlab.video.worker import VideoWorker
from stratlab.ui.video_player import VideoPlayer, VIDEO_EXTENSIONS
from stratlab.ui.timeline import TimelineWidget
from stratlab.ui.transport import TransportControls
from stratlab.ui.segment_list import SegmentListWidget
from stratlab.ui.results_view import ResultsViewWidget
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

        # Setup worker thread
        self.worker_thread = QThread(self)
        self.worker = VideoWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.initialize)

        # Wire UI request signals to worker slots (QueuedConnection across threads)
        self.request_open_video.connect(self.worker.open_video)
        self.request_seek.connect(self.worker.seek)
        self.request_step.connect(self.worker.step_frames)
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

        self._build_ui()
        self._setup_shortcuts()

        if initial_video and os.path.isfile(initial_video):
            self.load_video(initial_video)

    def _build_ui(self) -> None:
        self._setup_menubar()

        # Central container
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Main splitter dividing Video Player (left) and Segments / Results (right)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left pane: Video + Timeline + Transport
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self.player = VideoPlayer()
        self.player.file_dropped.connect(self.load_video)
        self.player.clicked.connect(self.request_toggle_play.emit)
        left_layout.addWidget(self.player, stretch=1)

        self.timeline = TimelineWidget()
        self.timeline.seek_requested.connect(self.seek_to_frame)
        left_layout.addWidget(self.timeline)

        self.transport = TransportControls()
        self.transport.step_requested.connect(self.request_step.emit)
        self.transport.play_toggled.connect(self.request_toggle_play.emit)
        self.transport.mark_in_requested.connect(self.mark_in_at_playhead)
        self.transport.mark_out_requested.connect(self.mark_out_at_playhead)
        left_layout.addWidget(self.transport)

        self.main_splitter.addWidget(left_pane)

        # Right pane: Segments list (top) + Results comparison (bottom)
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.segment_list = SegmentListWidget()
        self.segment_list.seek_requested.connect(self.seek_to_frame)
        self.segment_list.play_segment_requested.connect(self.request_play_segment.emit)
        self.segment_list.segments_changed.connect(self._on_segments_changed)
        self.segment_list.segment_selected.connect(self._on_segment_selection_changed)
        right_splitter.addWidget(self.segment_list)

        self.results_view = ResultsViewWidget()
        self.results_view.seek_requested.connect(self.seek_to_frame)
        right_splitter.addWidget(self.results_view)

        # Equal proportion for segment list and results view
        right_splitter.setSizes([350, 350])
        self.main_splitter.addWidget(right_splitter)

        # 65% for video, 35% for sidebar
        self.main_splitter.setSizes([850, 430])
        main_layout.addWidget(self.main_splitter)

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
        act_new_proj.triggered.connect(self.new_project)
        menu_file.addAction(act_new_proj)

        act_open_video = QAction("&Open Video...", self)
        act_open_video.setShortcut(QKeySequence("Ctrl+O"))
        act_open_video.triggered.connect(self.open_video_dialog)
        menu_file.addAction(act_open_video)

        menu_file.addSeparator()

        act_open_proj = QAction("Open &Project...", self)
        act_open_proj.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_open_proj.triggered.connect(self.open_project_dialog)
        menu_file.addAction(act_open_proj)

        act_save_proj = QAction("&Save Project", self)
        act_save_proj.setShortcut(QKeySequence("Ctrl+S"))
        act_save_proj.triggered.connect(self.save_project)
        menu_file.addAction(act_save_proj)

        act_save_as = QAction("Save Project &As...", self)
        act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
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
        act_mark_in.setShortcut(QKeySequence("I"))
        act_mark_in.triggered.connect(self.mark_in_at_playhead)
        menu_attempt.addAction(act_mark_in)

        act_mark_out = QAction("Mark &OUT", self)
        act_mark_out.setShortcut(QKeySequence("O"))
        act_mark_out.triggered.connect(self.mark_out_at_playhead)
        menu_attempt.addAction(act_mark_out)

        menu_attempt.addSeparator()

        act_add_attempt = QAction("&Add New Attempt", self)
        act_add_attempt.setShortcut(QKeySequence("Ctrl+T"))
        act_add_attempt.triggered.connect(lambda: self.segment_list.add_segment())
        menu_attempt.addAction(act_add_attempt)

        # Help Menu
        menu_help = menubar.addMenu("&Help")
        act_shortcuts = QAction("&Keyboard Shortcuts", self)
        act_shortcuts.triggered.connect(self._show_shortcuts_dialog)
        menu_help.addAction(act_shortcuts)

        act_about = QAction("&About StratLab", self)
        act_about.triggered.connect(self._show_about_dialog)
        menu_help.addAction(act_about)

    def _setup_shortcuts(self) -> None:
        """Global keyboard navigation and frame stepping shortcuts."""
        # Frame stepping: Left / Right
        shortcut_prev1 = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        shortcut_prev1.activated.connect(lambda: self.request_step.emit(-1))

        shortcut_next1 = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        shortcut_next1.activated.connect(lambda: self.request_step.emit(1))

        # Multi-frame stepping: Shift+Left / Shift+Right
        shortcut_prev10 = QShortcut(QKeySequence("Shift+Left"), self)
        shortcut_prev10.activated.connect(lambda: self.request_step.emit(-10))

        shortcut_next10 = QShortcut(QKeySequence("Shift+Right"), self)
        shortcut_next10.activated.connect(lambda: self.request_step.emit(10))

        # Playback toggle: Space
        shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        shortcut_space.activated.connect(self.request_toggle_play.emit)

        # Mark IN / OUT: I / O
        shortcut_in = QShortcut(QKeySequence("I"), self)
        shortcut_in.activated.connect(self.mark_in_at_playhead)

        shortcut_out = QShortcut(QKeySequence("O"), self)
        shortcut_out.activated.connect(self.mark_out_at_playhead)

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

        self.setWindowTitle(f"StratLab — {meta.filename}")
        self.timeline.set_range(meta.total_frames, meta.fps)
        self.transport.set_position(0, meta.total_frames, meta.fps)
        self.segment_list.set_fps(meta.fps)

        if self.project.segments:
            self.segment_list.set_segments(
                self.project.segments,
                self.project.selected_segment_index,
            )
        elif not self.segment_list.get_segments():
            self.segment_list.add_segment()

        self._update_all_views()

        # Update status bar with detailed metadata
        self.status_info.setText(
            f"{meta.filename} | {meta.resolution_display} | {meta.codec_name.upper()} | "
            f"{meta.fps_display} | {meta.duration_display} ({meta.total_frames} frames)"
        )

    @Slot(int, object)
    def _on_frame_ready(self, frame_idx: int, qimage) -> None:
        self.player.set_frame(qimage)
        self.timeline.set_current_frame(frame_idx)
        total = self.metadata.total_frames if self.metadata else 0
        fps = self.metadata.fps if self.metadata else Fraction(60, 1)
        self.transport.set_position(frame_idx, total, fps)
        self.project.current_frame = frame_idx

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

    @Slot(int)
    def seek_to_frame(self, frame: int) -> None:
        self.request_seek.emit(frame)

    @Slot()
    def mark_in_at_playhead(self) -> None:
        cur_frame = self.project.current_frame
        self.segment_list.mark_in_current_attempt(cur_frame)
        self._update_all_views()

    @Slot()
    def mark_out_at_playhead(self) -> None:
        cur_frame = self.project.current_frame
        self.segment_list.mark_out_current_attempt(cur_frame)
        self._update_all_views()

    def _on_segments_changed(self) -> None:
        self.project.segments = self.segment_list.get_segments()
        self.project.mark_dirty()
        self._update_all_views()

    def _on_segment_selection_changed(self, index: int) -> None:
        self.project.selected_segment_index = index
        self._sync_timeline_segments()

    def _update_all_views(self) -> None:
        segments = self.segment_list.get_segments()
        fps = self.metadata.fps if self.metadata else parse_fps(self.project.fps_str)
        self.results_view.update_results(segments, fps)
        self._sync_timeline_segments()

    def _sync_timeline_segments(self) -> None:
        segments = self.segment_list.get_segments()
        active_seg = self.segment_list.get_selected_segment()
        active_id = active_seg.id if active_seg else None
        self.timeline.set_segments(segments, active_id)

    # --- Project Persistence Actions ---

    def new_project(self) -> None:
        self.project = Project()
        self.metadata = None
        self.player.clear()
        self.segment_list.set_segments([])
        self.results_view.update_results([], Fraction(60, 1))
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

            # Check if source video exists
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

            # Populate segments
            self.segment_list.set_segments(proj.segments, proj.selected_segment_index)
            self.segment_list.set_fps(proj.fps)
            self._update_all_views()
            if proj.current_frame > 0:
                self.seek_to_frame(proj.current_frame)
        except Exception as e:
            QMessageBox.critical(self, "Project Load Error", f"Failed to load project:\n{e}")

    def save_project(self) -> bool:
        if not self.project.filepath:
            return self.save_project_as()

        try:
            self.project.segments = self.segment_list.get_segments()
            self.project.selected_segment_index = self.segment_list.get_selected_index()
            self.project.current_frame = self.worker.current_frame
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
            self.project.segments = self.segment_list.get_segments()
            self.project.selected_segment_index = self.segment_list.get_selected_index()
            self.project.current_frame = self.worker.current_frame
            saved_path = self.project.save(filepath)
            self.status_project.setText(f"Project: {os.path.basename(saved_path)}")
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
            "• <b>I:</b> Mark IN point for active attempt<br>"
            "• <b>O:</b> Mark OUT point for active attempt<br><br>"
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
            "<b>StratLab v0.1.0</b><br>"
            "A frame-accurate speedrun attempt comparison utility.<br><br>"
            "Designed for comparing multiple gameplay strategies from a single recording.<br>"
            "Powered by PySide6 &amp; PyAV."
        )
        QMessageBox.about(self, "About StratLab", about_text)

    def closeEvent(self, event) -> None:
        """Clean shutdown of worker thread and resources."""
        self.request_cleanup.emit()
        self.worker_thread.quit()
        self.worker_thread.wait(2000)
        super().closeEvent(event)
