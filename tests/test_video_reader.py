import os
import tempfile
import av
from fractions import Fraction
import pytest

from stratlab.video.reader import VideoReader


@pytest.fixture(scope="module")
def sample_video_path():
    """Create a minimal 30-frame 60fps MP4 video using PyAV for testing."""
    temp_dir = tempfile.mkdtemp()
    filepath = os.path.join(temp_dir, "test_sample.mp4")

    container = av.open(filepath, mode="w")
    stream = container.add_stream("libx264", rate=60)
    stream.width = 320
    stream.height = 240
    stream.pix_fmt = "yuv420p"

    for i in range(30):
        # Create a simple colored frame
        frame = av.VideoFrame(320, 240, "rgb24")
        # Fill with identifiable bytes
        plane = frame.planes[0]
        # In PyAV VideoFrame plane is writable
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


def test_video_reader_metadata(sample_video_path):
    reader = VideoReader(sample_video_path)
    try:
        assert reader.metadata.width == 320
        assert reader.metadata.height == 240
        assert reader.metadata.fps == Fraction(60, 1)
        assert reader.total_frames >= 28  # slight muxing difference
    finally:
        reader.close()


def test_video_reader_get_frame(sample_video_path):
    reader = VideoReader(sample_video_path)
    try:
        idx0, img0 = reader.get_frame(0)
        assert idx0 == 0
        assert not img0.isNull()
        assert img0.width() == 320
        assert img0.height() == 240

        # Test frame cache
        assert reader.cache.has(0)

        # Seek to frame 15
        idx15, img15 = reader.get_frame(15)
        assert idx15 == 15
        assert not img15.isNull()

        # Step back to 14
        idx14, img14 = reader.get_frame(14)
        assert idx14 == 14
        assert not img14.isNull()
    finally:
        reader.close()
