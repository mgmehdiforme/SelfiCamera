"""Tests for FrameProcessor pipeline and image transformations."""

import numpy as np
from PySide6.QtGui import QImage
from selficamera.processor.pipeline import FrameProcessor


def test_horizontal_mirror():
    """Verify that horizontal mirror flips columns."""
    processor = FrameProcessor(mirror=True, auto_light=False, blur_level=0)

    # Frame with distinct left and right colors
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :50, :] = 255  # Left is white
    frame[:, 50:, :] = 0    # Right is black

    processed = processor.process(frame)

    # In mirrored frame, left should now be black and right should be white
    assert np.all(processed[:, :50, :] == 0)
    assert np.all(processed[:, 50:, :] == 255)


def test_mirror_disabled():
    """Verify that un-mirrored frame retains original orientation."""
    processor = FrameProcessor(mirror=False, auto_light=False, blur_level=0)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, :50, :] = 255
    frame[:, 50:, :] = 0

    processed = processor.process(frame)
    np.testing.assert_array_equal(processed, frame)


def test_center_square_crop():
    """Verify 16:9 widescreen frame is center-cropped to exact 1:1 square."""
    processor = FrameProcessor(mirror=False, auto_light=False, blur_level=0)

    widescreen = np.zeros((720, 1280, 3), dtype=np.uint8)
    cropped = processor.crop_center_square(widescreen)

    assert cropped.shape == (720, 720, 3)


def test_process_to_qimage(mock_frame: np.ndarray):
    """Verify conversion to QImage returns valid RGB888 square image."""
    processor = FrameProcessor(mirror=True, auto_light=True, blur_level=2)

    qimg = processor.process_to_qimage(mock_frame)
    assert isinstance(qimg, QImage)
    assert not qimg.isNull()
    assert qimg.width() == 720
    assert qimg.height() == 720
    assert qimg.format() == QImage.Format.Format_RGB888
