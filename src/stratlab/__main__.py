"""StratLab application entry point."""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from stratlab.ui.main_window import MainWindow
from stratlab.core.project import PROJECT_FILE_EXTENSION


def main() -> int:
    # Enable high-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("StratLab")
    app.setOrganizationName("SpeedrunTools")

    initial_video: str | None = None
    initial_project: str | None = None

    if len(sys.argv) > 1:
        arg_path = sys.argv[1]
        if os.path.isfile(arg_path):
            if arg_path.endswith(PROJECT_FILE_EXTENSION):
                initial_project = arg_path
            else:
                initial_video = arg_path

    window = MainWindow(initial_video=initial_video)
    if initial_project:
        window.project = window.project.load(initial_project)
        if window.project.video_path and os.path.isfile(window.project.video_path):
            window.load_video(window.project.video_path)
        window.segment_list.set_segments(
            window.project.segments,
            window.project.selected_segment_index,
        )
        window._update_all_views()

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
