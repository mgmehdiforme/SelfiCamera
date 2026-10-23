"""Threaded camera capture worker with atomic depth-1 frame queue and V4L2 backend."""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple
import cv2
import numpy as np
from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

logger = logging.getLogger(__name__)


class CameraCaptureWorker(QThread):
    """Background QThread for non-blocking V4L2 camera capture."""

    frame_ready = Signal(np.ndarray)
    error_occurred = Signal(str)
    device_changed = Signal(str, int, int)

    def __init__(
        self,
        device_path: str = "/dev/video0",
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        mock_mode: bool = False,
    ) -> None:
        super().__init__()
        self.device_path = device_path
        self.width = width
        self.height = height
        self.fps = max(1, fps)
        self.mock_mode = mock_mode

        self._running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._mutex = QMutex()
        self._consecutive_errors = 0
        self._mock_frame_counter = 0

        # Pending device change request
        self._pending_change: Optional[Tuple[str, int, int]] = None

    def change_device(self, new_device_path: str, width: int = 1280, height: int = 720) -> None:
        """Schedule a clean switch to a new camera device or resolution."""
        with QMutexLocker(self._mutex):
            self._pending_change = (new_device_path, width, height)

    def stop(self) -> None:
        """Gracefully stop the worker thread."""
        self._running = False
        self.wait(1500)

    def _open_camera(self) -> bool:
        """Open V4L2 device descriptor and apply properties."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

        if self.mock_mode:
            logger.info("Operating in mock camera mode (synthetic test feed).")
            return True

        device_index = 0
        if "video" in self.device_path:
            digits = "".join(filter(str.isdigit, self.device_path))
            if digits:
                device_index = int(digits)

        try:
            self._cap = cv2.VideoCapture(device_index, cv2.CAP_V4L2)
            if not self._cap.isOpened():
                # Fallback to default backend
                self._cap = cv2.VideoCapture(device_index)

            if not self._cap.isOpened():
                msg = f"Cannot open camera device {self.device_path} (index {device_index})"
                logger.error(msg)
                self.error_occurred.emit(msg)
                return False

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)
            # Try MJPG hardware decompression
            fourcc_mjpg = cv2.VideoWriter_fourcc(*"MJPG")
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc_mjpg)

            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info("Camera opened: %s at %dx%d (requested %dx%d)", self.device_path, actual_w, actual_h, self.width, self.height)
            return True
        except Exception as e:
            msg = f"Exception opening camera {self.device_path}: {e}"
            logger.error(msg)
            self.error_occurred.emit(msg)
            return False

    def _generate_mock_frame(self) -> np.ndarray:
        """Generate synthetic 1280x720 BGR test frame with moving target and timestamp."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Dynamic gradient background
        y_coords = np.linspace(30, 80, self.height, dtype=np.uint8)[:, None]
        frame[:, :, 0] = y_coords
        frame[:, :, 1] = 45
        frame[:, :, 2] = 60

        # Synthetic presenter avatar (centered circle)
        cx = self.width // 2
        cy = self.height // 2
        radius = min(self.width, self.height) // 3

        # Draw head & shoulders simulation
        cv2.circle(frame, (cx, cy - 20), radius // 2, (180, 150, 140), -1)
        cv2.ellipse(frame, (cx, cy + radius // 2), (radius // 2 + 60, radius // 2), 0, 0, 360, (120, 80, 70), -1)

        # Moving indicator dot
        self._mock_frame_counter += 1
        indicator_x = int(cx + (radius // 2) * np.sin(self._mock_frame_counter * 0.1))
        cv2.circle(frame, (indicator_x, cy - 100), 12, (0, 230, 255), -1)

        # Status text
        cv2.putText(frame, f"Mock V4L2 Feed #{self._mock_frame_counter}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(frame, f"Target: {self.width}x{self.height} @ {self.fps}fps", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        return frame

    def run(self) -> None:
        """Main acquisition loop."""
        self._running = True
        self._open_camera()

        frame_interval = 1.0 / self.fps

        while self._running:
            loop_start = time.perf_counter()

            # Handle dynamic device / resolution switch
            with QMutexLocker(self._mutex):
                if self._pending_change is not None:
                    new_dev, new_w, new_h = self._pending_change
                    self._pending_change = None
                    self.device_path = new_dev
                    self.width = new_w
                    self.height = new_h
                    self._open_camera()
                    self.device_changed.emit(self.device_path, self.width, self.height)

            if self.mock_mode or self._cap is None:
                frame = self._generate_mock_frame()
                self.frame_ready.emit(frame)
                elapsed = time.perf_counter() - loop_start
                sleep_time = max(0.001, frame_interval - elapsed)
                self.msleep(int(sleep_time * 1000))
                continue

            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._consecutive_errors += 1
                if self._consecutive_errors >= 3:
                    msg = f"Camera read failed consecutively for {self.device_path}"
                    logger.warning(msg)
                    self.error_occurred.emit(msg)
                    # Produce clean fallback placeholder
                    placeholder = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    cv2.putText(
                        placeholder,
                        "Camera Unavailable",
                        (self.width // 4, self.height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.2,
                        (0, 0, 255),
                        2,
                    )
                    self.frame_ready.emit(placeholder)
                self.msleep(30)
                continue

            self._consecutive_errors = 0
            # Emit frame immediately (atomic depth-1 queue semantics: downstream slot uses it immediately)
            self.frame_ready.emit(frame)

            # Throttle if acquisition completes faster than target framerate
            elapsed = time.perf_counter() - loop_start
            if elapsed < frame_interval:
                sleep_ms = int((frame_interval - elapsed) * 1000)
                if sleep_ms > 0:
                    self.msleep(sleep_ms)

        # Clean shutdown
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        logger.info("Camera capture worker terminated cleanly.")
