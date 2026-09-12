"""High-performance letterboxed video display widget with drag-and-drop support."""

from __future__ import annotations
import os
from typing import Optional
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPaintEvent, QImage, QColor, QFont, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QWidget

from stratlab.ui.theme import PALETTE


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".ts"}


class VideoPlayer(QWidget):
    """Aspect-ratio preserving video frame rendering widget."""

    file_dropped = Signal(str)
    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 180)
        self.setStyleSheet(f"background-color: {PALETTE['bg_video']};")

        self._image: Optional[QImage] = None
        self._filename: Optional[str] = None

    def set_frame(self, image: QImage) -> None:
        """Update the currently displayed frame."""
        self._image = image
        self.update()

    def set_filename(self, filename: Optional[str]) -> None:
        self._filename = filename
        self.update()

    def clear(self) -> None:
        self._image = None
        self._filename = None
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Clear background with deep matte black
        painter.fillRect(self.rect(), QColor(PALETTE["bg_video"]))

        if self._image is not None and not self._image.isNull():
            img_w = self._image.width()
            img_h = self._image.height()
            w_space = self.width()
            h_space = self.height()

            # Preserve aspect ratio
            img_aspect = img_w / img_h
            widget_aspect = w_space / h_space

            if widget_aspect > img_aspect:
                # Height is the constraining dimension
                dest_h = h_space
                dest_w = int(round(h_space * img_aspect))
                dest_x = (w_space - dest_w) // 2
                dest_y = 0
            else:
                # Width is the constraining dimension
                dest_w = w_space
                dest_h = int(round(w_space / img_aspect))
                dest_x = 0
                dest_y = (h_space - dest_h) // 2

            dest_rect = QRect(dest_x, dest_y, dest_w, dest_h)
            painter.drawImage(dest_rect, self._image)
        else:
            # Empty state: a quiet invitation, not a poster.
            painter.setPen(QColor(PALETTE["text_lo"]))
            font = QFont("Segoe UI", 11, QFont.Weight.Normal)
            painter.setFont(font)
            painter.drawText(
                self.rect().adjusted(0, -14, 0, -14),
                Qt.AlignmentFlag.AlignCenter,
                "No video loaded",
            )

            font_sub = QFont("Segoe UI", 9)
            painter.setFont(font_sub)
            painter.setPen(QColor(PALETTE["text_faint"]))
            painter.drawText(
                self.rect().adjusted(0, 14, 0, 14),
                Qt.AlignmentFlag.AlignCenter,
                "Drop a video here  ·  Ctrl+O",
            )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = os.path.splitext(url.toLocalFile())[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            ext = os.path.splitext(filepath)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                self.file_dropped.emit(filepath)
                event.acceptProposedAction()
                return
        event.ignore()
