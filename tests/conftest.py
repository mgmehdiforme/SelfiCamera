"""Shared fixtures. Every test runs with isolated XDG dirs and no real camera, mic or network."""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from pathlib import Path

import cv2
import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    # Short runtime dir: AF_UNIX paths are limited to ~107 bytes.
    runtime = Path("/tmp") / f"sc-test-{uuid.uuid4().hex[:8]}"
    runtime.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv("SELFICAMERA_MODEL", raising=False)
    yield tmp_path
    shutil.rmtree(runtime, ignore_errors=True)


@pytest.fixture
def config_path(tmp_path) -> Path:
    return tmp_path / "cfg" / "config.json"


@pytest.fixture
def presenter_frame() -> np.ndarray:
    """1280x720 frame: textured background with a person-like shape right of center."""
    h, w = 720, 1280
    yy, xx = np.mgrid[0:h, 0:w]
    checker = (((xx // 16) + (yy // 16)) % 2 * 120 + 60).astype(np.uint8)
    frame = np.dstack([checker, np.full_like(checker, 90), 255 - checker]).astype(np.uint8)
    cx = 760
    cv2.ellipse(frame, (cx, 720), (260, 200), 0, 180, 360, (90, 70, 60), -1)
    cv2.circle(frame, (cx, 380), 110, (150, 175, 220), -1)
    return frame


@pytest.fixture
def app_controller(qtbot, config_path):
    """A fully initialised app in demo mode (synthetic camera/mic, no tray)."""
    from selficamera.app import SelfiCameraApp

    ctl = SelfiCameraApp(config_path=str(config_path), mock_mode=True, enable_tray=False, enable_audio=False)
    ctl.initialize()
    qtbot.addWidget(ctl.bubble)
    ctl.start()
    yield ctl
    ctl._quitting = False
    ctl.quit()
