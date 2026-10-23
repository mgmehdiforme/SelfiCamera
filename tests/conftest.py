"""Pytest test fixtures and synthetic test feed generators for SelfiCamera."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator
import cv2
import numpy as np
import pytest

from selficamera.audio.voice_monitor import AudioMonitorWorker
from selficamera.capture.camera import CameraCaptureWorker
from selficamera.config import ConfigManager
from selficamera.processor.pipeline import FrameProcessor
from selficamera.processor.segmentation import SegmentationBlurEngine


@pytest.fixture
def mock_frame() -> np.ndarray:
    """Generate a synthetic 1280x720 BGR test frame with a simulated person and background."""
    h, w = 720, 1280
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    # Background pattern (subtle blue-gray gradient)
    for y in range(h):
        val = int(40 + (y / h) * 40)
        frame[y, :, 0] = val
        frame[y, :, 1] = 50
        frame[y, :, 2] = 60

    # Draw centered simulated presenter (head and torso)
    cx, cy = w // 2, h // 2
    # Torso
    cv2.ellipse(frame, (cx, cy + 180), (140, 100), 0, 0, 360, (130, 90, 80), -1)
    # Head
    cv2.circle(frame, (cx, cy - 30), 80, (180, 150, 140), -1)
    # Face details
    cv2.circle(frame, (cx - 25, cy - 40), 10, (50, 40, 30), -1)
    cv2.circle(frame, (cx + 25, cy - 40), 10, (50, 40, 30), -1)

    return frame


@pytest.fixture
def synthetic_presenter_frame() -> np.ndarray:
    """Generate a realistic 720p BGR test frame with high-frequency XOR checkerboard background
    and a distinct, textured presenter silhouette for anti-self-certifying tests.
    """
    h, w = 720, 1280
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    # 1. Background high-frequency XOR texture (V_bg > 200)
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            c = (((x // 8) % 2) ^ ((y // 8) % 2)) * 160 + 40
            frame[y : y + 8, x : x + 8, 0] = c
            frame[y : y + 8, x : x + 8, 1] = 120
            frame[y : y + 8, x : x + 8, 2] = 255 - c

    # 2. Centered presenter silhouette
    cx, cy = w // 2, h // 2
    # Torso: BGR (40, 140, 60)
    cv2.ellipse(frame, (cx, cy + 200), (220, 150), 0, 0, 360, (40, 140, 60), -1)
    # Head: BGR (220, 180, 160)
    cv2.circle(frame, (cx, cy - 40), 100, (220, 180, 160), -1)
    # Facial high-frequency features (eyes, eyebrows, mouth) -> V_fg > 1000
    cv2.circle(frame, (cx - 30, cy - 40), 12, (20, 20, 20), -1)
    cv2.circle(frame, (cx + 30, cy - 40), 12, (20, 20, 20), -1)
    cv2.ellipse(frame, (cx, cy + 10), (35, 15), 0, 0, 180, (20, 20, 80), 4)

    return frame


@pytest.fixture
def dark_frame() -> np.ndarray:
    """Generate a dark test frame with mean luminance Y < 45."""
    frame = np.full((720, 1280, 3), 35, dtype=np.uint8)
    return frame


@pytest.fixture
def bright_frame() -> np.ndarray:
    """Generate a well-lit test frame with mean luminance Y > 130."""
    frame = np.full((720, 1280, 3), 140, dtype=np.uint8)
    return frame


@pytest.fixture
def mock_audio_pcm_speech() -> np.ndarray:
    """Generate 512 samples of float32 PCM audio simulating speech (RMS around -20 dBFS)."""
    t = np.linspace(0, 0.012, 512, dtype=np.float32)
    # Fundamental + harmonics
    speech = 0.25 * np.sin(2 * np.pi * 220 * t) + 0.15 * np.sin(2 * np.pi * 440 * t)
    return speech.astype(np.float32)


@pytest.fixture
def mock_audio_pcm_silence() -> np.ndarray:
    """Generate 512 samples of float32 PCM audio simulating silence (RMS < -60 dBFS)."""
    return np.random.uniform(-0.0001, 0.0001, 512).astype(np.float32)


@pytest.fixture
def temp_config_file() -> Generator[Path, None, None]:
    """Provide a temporary config.json file path that cleans up after tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        yield cfg_path


@pytest.fixture
def mock_camera_worker() -> Generator[CameraCaptureWorker, None, None]:
    """Provide an initialized CameraCaptureWorker in mock mode."""
    worker = CameraCaptureWorker(
        device_path="/dev/video0",
        width=640,
        height=480,
        fps=30,
        mock_mode=True,
    )
    yield worker
    worker.stop()


@pytest.fixture
def mock_audio_worker() -> Generator[AudioMonitorWorker, None, None]:
    """Provide an initialized AudioMonitorWorker in mock mode."""
    worker = AudioMonitorWorker(mock_mode=True)
    yield worker
    worker.stop()
