"""Tests for V4L2 Device Scanner and CameraCaptureWorker."""

import numpy as np
from selficamera.capture.camera import CameraCaptureWorker
from selficamera.capture.v4l2_devices import V4L2DeviceScanner


def test_device_scanner_nonexistent():
    """Verify that querying nonexistent device returns None."""
    info = V4L2DeviceScanner.query_device_capability("/dev/video999")
    assert info is None


def test_device_scanner_list():
    """Verify listing devices executes safely on system."""
    devices = V4L2DeviceScanner.list_devices()
    assert isinstance(devices, list)


def test_mock_camera_worker_frame_emission(qtbot):
    """Verify that CameraCaptureWorker emits valid numpy frames in mock mode."""
    worker = CameraCaptureWorker(
        device_path="/dev/video0",
        width=640,
        height=480,
        fps=30,
        mock_mode=True,
    )

    frames = []
    worker.frame_ready.connect(lambda f: frames.append(f))

    with qtbot.waitSignal(worker.frame_ready, timeout=1000):
        worker.start()

    assert len(frames) > 0
    frame = frames[-1]
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (480, 640, 3)
    assert frame.dtype == np.uint8

    worker.stop()


def test_mock_camera_resolution_change(qtbot):
    """Verify dynamic device / resolution change in CameraCaptureWorker."""
    worker = CameraCaptureWorker(
        device_path="/dev/video0",
        width=640,
        height=480,
        fps=30,
        mock_mode=True,
    )

    with qtbot.waitSignal(worker.frame_ready, timeout=1000):
        worker.start()

    # Request resolution change to 1280x720
    with qtbot.waitSignal(worker.device_changed, timeout=1000):
        worker.change_device("/dev/video0", 1280, 720)

    assert worker.width == 1280
    assert worker.height == 720

    worker.stop()
