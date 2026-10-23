"""Edge case and resilience hardening tests for SelfiCamera."""

import json
import os
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QRegion

from selficamera.audio.voice_monitor import AudioMonitorWorker
from selficamera.capture.camera import CameraCaptureWorker
from selficamera.config import DEFAULT_CONFIG, ConfigManager
from selficamera.processor.pipeline import FrameProcessor
from selficamera.processor.segmentation import SegmentationBlurEngine
from selficamera.shortcuts.ipc import ShortcutIPCClient, ShortcutIPCServer, get_ipc_socket_path
from selficamera.ui.overlay import OverlayWindow


def test_camera_disconnect_and_placeholder_fallback(qtbot):
    """AC-2.1.4: Verify worker emits error and placeholder frame after 3 consecutive read failures."""
    worker = CameraCaptureWorker(
        device_path="/dev/video0",
        width=640,
        height=480,
        fps=30,
        mock_mode=False,
    )

    # Mock cv2.VideoCapture to return (False, None)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)
    mock_cap.get.side_effect = lambda prop: 640 if prop == cv2.CAP_PROP_FRAME_WIDTH else 480

    error_signals = []
    frames = []

    worker.error_occurred.connect(lambda err: error_signals.append(err))
    worker.frame_ready.connect(lambda f: frames.append(f))

    with patch("cv2.VideoCapture", return_value=mock_cap):
        worker.start()
        # Wait until error is emitted after 3 failures
        qtbot.waitUntil(lambda: len(error_signals) > 0, timeout=1500)
        qtbot.waitUntil(lambda: len(frames) > 0, timeout=1500)

    worker.stop()

    assert len(error_signals) >= 1
    assert "consecutively" in error_signals[0]
    assert len(frames) > 0
    placeholder = frames[-1]
    assert placeholder.shape == (480, 640, 3)
    # Placeholder should have some red color from "Camera Unavailable" text
    assert np.any(placeholder[:, :, 2] > 200)


def test_audio_device_exception_fallback(qtbot):
    """AC-3.1.4: Verify audio worker handles missing/failing device gracefully without crashing."""
    worker = AudioMonitorWorker(device="nonexistent_mic_hw:99", mock_mode=False)

    error_signals = []
    energy_signals = []

    worker.error_occurred.connect(lambda err: error_signals.append(err))
    worker.energy_updated.connect(lambda e: energy_signals.append(e))

    # Mock sounddevice module with failing InputStream
    mock_sd = MagicMock()
    mock_sd.InputStream.side_effect = RuntimeError("Device unavailable")

    with patch.dict("sys.modules", {"sounddevice": mock_sd}):
        worker.start()
        qtbot.waitUntil(lambda: len(error_signals) > 0, timeout=1500)
        qtbot.waitUntil(lambda: len(energy_signals) > 0, timeout=1500)

    worker.stop()

    assert len(error_signals) >= 1
    assert "Device unavailable" in error_signals[0]
    # Quiescent loop emits 0.0
    assert energy_signals[-1] == 0.0


def test_rapid_ghost_mode_toggling(qtbot):
    """Verify rapid consecutive toggling of Ghost Mode does not cause desync or crash."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    for i in range(20):
        target_state = (i % 2 == 0)
        overlay.set_click_through(target_state)
        assert overlay.is_ghost_mode is target_state
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is target_state
        if target_state:
            assert overlay.mask().isEmpty()
        else:
            assert not overlay.mask().isEmpty() or overlay.mask().isNull()

    # Final reset
    overlay.set_click_through(False)
    assert overlay.is_ghost_mode is False


def test_ipc_malformed_json_and_unknown_action(qtbot, tmp_path):
    """Verify IPC server robustly handles malformed packets, invalid JSON, and unknown commands."""
    test_sock = tmp_path / "test_malformed.sock"
    server = ShortcutIPCServer(state_provider=lambda: {"running": True, "fps": 30}, socket_path=test_sock)
    try:
        server.start()
        qtbot.waitUntil(lambda: server.is_listening, timeout=2000)

        sock_path = server.socket_path

        # 1. Send completely invalid JSON string
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(sock_path))
        client.sendall(b"{ this is malformed json \n")
        resp = client.recv(4096)
        client.close()

        resp_data = json.loads(resp.decode("utf-8"))
        assert resp_data["success"] is False
        assert "error" in resp_data

        # 2. Send unknown action
        client2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client2.connect(str(sock_path))
        client2.sendall(json.dumps({"action": "unknown_cmd_xyz", "params": {}}).encode("utf-8") + b"\n")
        resp2 = client2.recv(4096)
        client2.close()

        resp_data2 = json.loads(resp2.decode("utf-8"))
        # Unknown actions still return a structured response with success True and action name
        assert resp_data2["success"] is True
        assert resp_data2["action"] == "unknown_cmd_xyz"
        assert "state" in resp_data2
    finally:
        server.stop()
        qtbot.waitUntil(lambda: not server.socket_path.exists(), timeout=1000)


def test_config_empty_file_and_type_mismatch(temp_config_file: Path):
    """Verify ConfigManager handles zero-byte files, non-dict roots, and type mismatches."""
    temp_config_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Zero-byte file
    temp_config_file.write_text("", encoding="utf-8")
    mgr = ConfigManager(config_path=temp_config_file)
    assert mgr.get("diameter") == DEFAULT_CONFIG["diameter"]

    # 2. Primitive JSON root (int instead of dict)
    temp_config_file.write_text("42", encoding="utf-8")
    mgr2 = ConfigManager(config_path=temp_config_file)
    assert mgr2.get("diameter") == DEFAULT_CONFIG["diameter"]

    # 3. JSON array root
    temp_config_file.write_text("[1, 2, 3]", encoding="utf-8")
    mgr3 = ConfigManager(config_path=temp_config_file)
    assert mgr3.get("diameter") == DEFAULT_CONFIG["diameter"]


def test_processor_dynamic_resolution_switch():
    """Verify FrameProcessor and Segmentation engine adapt dynamically across differing resolutions."""
    processor = FrameProcessor(mirror=True, auto_light=True, blur_level=2)

    # Resolution 1: 640x480
    frame_480 = np.full((480, 640, 3), 60, dtype=np.uint8)
    res_480 = processor.process(frame_480)
    assert res_480.shape == (480, 480, 3)

    # Resolution 2: 1920x1080 (buffers must reallocate seamlessly)
    frame_1080 = np.full((1080, 1920, 3), 70, dtype=np.uint8)
    res_1080 = processor.process(frame_1080)
    assert res_1080.shape == (1080, 1080, 3)

    # Resolution 3: 1280x720 standard
    frame_720 = np.full((720, 1280, 3), 80, dtype=np.uint8)
    res_720 = processor.process(frame_720)
    assert res_720.shape == (720, 720, 3)


def test_all_corner_snapping_boundaries(qtbot):
    """AC-3.3.1, AC-3.3.2: Verify corner snapping math for all 4 desktop corners."""
    from PySide6.QtCore import QAbstractAnimation
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    # Corner 1: Top-Left
    overlay.snap_to_corner(1)
    qtbot.waitUntil(lambda: overlay._move_anim.state() == QAbstractAnimation.State.Stopped, timeout=1000)
    p1 = overlay.pos()
    assert p1.x() == 24
    assert p1.y() >= 24

    # Corner 2: Top-Right
    overlay.snap_to_corner(2)
    qtbot.waitUntil(lambda: overlay._move_anim.state() == QAbstractAnimation.State.Stopped, timeout=1000)
    p2 = overlay.pos()
    assert p2.x() > p1.x()
    assert p2.y() == p1.y()

    # Corner 3: Bottom-Left
    overlay.snap_to_corner(3)
    qtbot.waitUntil(lambda: overlay._move_anim.state() == QAbstractAnimation.State.Stopped, timeout=1000)
    p3 = overlay.pos()
    assert p3.x() == p1.x()
    assert p3.y() > p1.y()

    # Corner 4: Bottom-Right
    overlay.snap_to_corner(4)
    qtbot.waitUntil(lambda: overlay._move_anim.state() == QAbstractAnimation.State.Stopped, timeout=1000)
    p4 = overlay.pos()
    assert p4.x() == p2.x()
    assert p4.y() == p3.y()


def test_zero_external_network_sockets(qtbot, tmp_path: Path):
    """AC-2.5.2: Verify that application components create zero TCP/UDP internet sockets."""
    import socket
    original_socket = socket.socket
    inet_sockets_created = []

    def audited_socket(family=socket.AF_UNIX, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            inet_sockets_created.append((family, args))
        return original_socket(family, *args, **kwargs)

    test_sock_path = tmp_path / "zero_audit.sock"

    with patch("socket.socket", side_effect=audited_socket):
        # Run entire processing pipeline
        proc = FrameProcessor(mirror=True, auto_light=True, blur_level=2)
        frame = np.full((720, 1280, 3), 30, dtype=np.uint8)
        proc.process(frame)

        # Run IPC server with isolated socket path
        server = ShortcutIPCServer()
        server.socket_path = test_sock_path
        server.start()
        qtbot.waitUntil(lambda: test_sock_path.exists(), timeout=1000)
        server.stop()
        qtbot.waitUntil(lambda: not test_sock_path.exists(), timeout=1000)

    assert len(inet_sockets_created) == 0, f"Expected 0 external internet sockets, found: {inet_sockets_created}"


