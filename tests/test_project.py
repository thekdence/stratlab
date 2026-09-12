from fractions import Fraction
import os
import tempfile
import pytest

from stratlab.core.segment import Segment
from stratlab.core.project import Project


def test_project_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_file = os.path.join(tmpdir, "test_session.stratlab")

        proj = Project(
            video_path=os.path.join(tmpdir, "recording.mp4"),
            fps_str="60000/1001",
            current_frame=250,
            selected_segment_index=1,
            segments=[
                Segment(name="Strat A", in_frame=100, out_frame=351),
                Segment(name="Strat B", in_frame=500, out_frame=756),
            ],
        )

        saved_path = proj.save(proj_file)
        assert os.path.exists(saved_path)

        loaded = Project.load(saved_path)
        assert loaded.video_path == proj.video_path
        assert loaded.fps_str == "60000/1001"
        assert loaded.fps == Fraction(60000, 1001)
        assert loaded.current_frame == 250
        assert loaded.selected_segment_index == 1
        assert len(loaded.segments) == 2
        assert loaded.segments[0].name == "Strat A"
        assert loaded.segments[0].in_frame == 100
        assert loaded.segments[0].out_frame == 351
        assert loaded.segments[1].name == "Strat B"
        assert loaded.segments[1].in_frame == 500
        assert loaded.segments[1].out_frame == 756


def test_project_missing_video_handling():
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_file = os.path.join(tmpdir, "missing.stratlab")
        non_existent_video = os.path.join(tmpdir, "does_not_exist.mp4")

        proj = Project(video_path=non_existent_video)
        assert not proj.video_exists

        proj.save(proj_file)
        loaded = Project.load(proj_file)
        # Should not raise exception
        assert not loaded.video_exists
        assert loaded.video_path == non_existent_video
