"""Camera worker: V4L2 capture + processing off the GUI thread, with auto-reconnect.

The worker owns a :class:`FrameProcessor`. Each processed frame is placed in a
single-slot mailbox; the GUI is notified only when it has consumed the previous
frame, so a slow UI never builds up a queue of stale frames.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from selficamera.processor.pipeline import FrameProcessor, to_qimage

logger = logging.getLogger(__name__)

RETRY_INTERVAL_S = 2.0
MAX_READ_FAILURES = 8


class CameraStatus:
    STARTING = "starting"
    LIVE = "live"
    ERROR = "error"


class CameraWorker(QThread):
    """Background thread capturing, processing and publishing frames."""

    frame_available = Signal()
    status_changed = Signal(str, str)  # (state, human readable message)
    fps_measured = Signal(float)

    def __init__(
        self,
        processor: FrameProcessor,
        device_path: str = "/dev/video0",
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        mock_mode: bool = False,
    ) -> None:
        super().__init__()
        self.processor = processor
        self.device_path = device_path
        self.width = int(width)
        self.height = int(height)
        self.fps = max(1, int(fps))
        self.mock_mode = mock_mode

        self._running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._pending_change: Optional[Tuple[str, int, int, int]] = None
        self._latest: Optional[QImage] = None
        self._notified = False
        self._mock_counter = 0
        self._paused = False
        self.state = CameraStatus.STARTING
        self.actual_resolution: Tuple[int, int] = (self.width, self.height)

    # ----------------------------------------------------------------- control
    def change_source(self, device_path: str, width: int, height: int, fps: int) -> None:
        with self._lock:
            self._pending_change = (device_path, int(width), int(height), max(1, int(fps)))

    def change_device(self, device_path: str, width: int = 1280, height: int = 720) -> None:
        self.change_source(device_path, width, height, self.fps)

    def set_paused(self, paused: bool) -> None:
        """Pause capture (e.g. while the bubble is hidden) to free the camera and CPU."""
        self._paused = paused

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

    def take_frame(self) -> Optional[QImage]:
        """Called from the GUI thread to fetch the newest frame."""
        with self._lock:
            img = self._latest
            self._latest = None
            self._notified = False
            return img

    # --------------------------------------------------------------- internals
    def _set_status(self, state: str, message: str) -> None:
        if state != self.state or state == CameraStatus.ERROR:
            self.state = state
            self.status_changed.emit(state, message)

    def _release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _open(self) -> bool:
        self._release()
        if self.mock_mode:
            self._set_status(CameraStatus.LIVE, "Demo feed")
            return True
        if not os.path.exists(self.device_path):
            self._set_status(CameraStatus.ERROR, "Camera not found.\nPlug it in or pick another in Settings.")
            return False
        if not os.access(self.device_path, os.R_OK | os.W_OK):
            self._set_status(CameraStatus.ERROR, "No permission to use the camera.\nAdd your user to the 'video' group.")
            return False
        cap = cv2.VideoCapture(self.device_path, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap.release()
            self._set_status(CameraStatus.ERROR, "Camera is busy or disconnected.\nRetrying…")
            return False
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.actual_resolution = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        logger.info(
            "Camera %s opened at %dx%d (requested %dx%d @ %d fps)",
            self.device_path,
            *self.actual_resolution,
            self.width,
            self.height,
            self.fps,
        )
        self._cap = cap
        self._set_status(CameraStatus.STARTING, "Starting camera…")
        return True

    def generate_mock_frame(self) -> np.ndarray:
        """Synthetic presenter feed for demos and tests."""
        self._mock_counter += 1
        w, h = self.width, self.height
        t = self._mock_counter / max(1, self.fps)
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
        frame = np.empty((h, w, 3), dtype=np.uint8)
        frame[..., 0] = (90 + 60 * yy + 20 * xx).astype(np.uint8)
        frame[..., 1] = (70 + 40 * xx).astype(np.uint8)
        frame[..., 2] = (60 + 30 * yy).astype(np.uint8)
        for i in range(6):  # bookshelf-ish background detail
            x0 = int(w * (0.05 + i * 0.16))
            cv2.rectangle(frame, (x0, int(h * 0.12)), (x0 + int(w * 0.09), int(h * 0.42)), (40 + i * 25, 120, 200 - i * 20), -1)
        cx = int(w / 2 + np.sin(t * 0.7) * w * 0.06)
        cy = int(h * 0.48)
        r = min(w, h) // 3
        cv2.ellipse(frame, (cx, h), (int(r * 1.15), int(r * 0.85)), 0, 180, 360, (95, 70, 60), -1)
        cv2.circle(frame, (cx, cy), int(r * 0.55), (150, 175, 220), -1)
        cv2.ellipse(frame, (cx, cy - int(r * 0.28)), (int(r * 0.58), int(r * 0.34)), 0, 180, 360, (40, 45, 60), -1)
        eye_dy = int(r * 0.05)
        for dx in (-int(r * 0.2), int(r * 0.2)):
            cv2.circle(frame, (cx + dx, cy - eye_dy), max(2, r // 22), (40, 30, 30), -1)
        cv2.ellipse(frame, (cx, cy + int(r * 0.2)), (int(r * 0.16), int(r * 0.07)), 0, 0, 180, (60, 60, 160), 3)
        return frame

    def _publish(self, raw: np.ndarray) -> None:
        processed = self.processor.process(raw)
        qimg = to_qimage(processed)
        notify = False
        with self._lock:
            self._latest = qimg
            if not self._notified:
                self._notified = True
                notify = True
        if notify:
            self.frame_available.emit()

    def run(self) -> None:  # noqa: C901 - main loop
        self._running = True
        self._open()
        failures = 0
        last_retry = time.monotonic()
        fps_window_start = time.monotonic()
        fps_frames = 0
        interval = 1.0 / self.fps

        while self._running:
            loop_start = time.monotonic()

            with self._lock:
                change = self._pending_change
                self._pending_change = None
            if change is not None:
                self.device_path, self.width, self.height, self.fps = change
                interval = 1.0 / self.fps
                self.processor.framer.reset()
                self._open()
                failures = 0

            if self._paused:
                if self._cap is not None:
                    self._release()
                self.msleep(100)
                continue

            if self.mock_mode:
                self._publish(self.generate_mock_frame())
                self._set_status(CameraStatus.LIVE, "Demo feed")
                elapsed = time.monotonic() - loop_start
                self.msleep(max(1, int((interval - elapsed) * 1000)))
            elif self._cap is None:
                if time.monotonic() - last_retry >= RETRY_INTERVAL_S:
                    last_retry = time.monotonic()
                    self._open()
                else:
                    self.msleep(100)
                continue
            else:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= MAX_READ_FAILURES:
                        logger.warning("Camera %s stopped delivering frames; reconnecting.", self.device_path)
                        self._release()
                        self._set_status(CameraStatus.ERROR, "Camera disconnected.\nRetrying…")
                        last_retry = time.monotonic()
                    else:
                        self.msleep(20)
                    continue
                failures = 0
                try:
                    self._publish(frame)
                except Exception:
                    logger.exception("Frame processing failed")
                    continue
                self._set_status(CameraStatus.LIVE, "")

            fps_frames += 1
            now = time.monotonic()
            if now - fps_window_start >= 2.0:
                self.fps_measured.emit(fps_frames / (now - fps_window_start))
                fps_window_start, fps_frames = now, 0

        self._release()
        logger.info("Camera worker stopped.")
