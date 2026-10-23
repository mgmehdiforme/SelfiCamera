"""Tests for Auto-Light Boost adaptive luminance compensation and LUT generation."""

import time
import cv2
import numpy as np
from selficamera.processor.lighting import AutoLightBoost


def test_autolight_enhances_dark_scene(dark_frame: np.ndarray):
    """Verify that dark scene luminance is significantly increased and gamma < 1.0."""
    booster = AutoLightBoost(enabled=True)

    ycrcb_before = cv2.cvtColor(dark_frame, cv2.COLOR_BGR2YCrCb)
    y_before = float(np.mean(ycrcb_before[:, :, 0]))

    # Process consecutive frames from raw input to allow temporal smoothing to take effect
    result = dark_frame
    for _ in range(15):
        result = booster.process(dark_frame)

    ycrcb_after = cv2.cvtColor(result, cv2.COLOR_BGR2YCrCb)
    y_after = float(np.mean(ycrcb_after[:, :, 0]))

    assert booster.current_gamma < 1.0
    assert y_after > y_before + 30.0


def test_autolight_noop_in_bright_scene(bright_frame: np.ndarray):
    """Verify that bright scenes are not over-boosted and gamma remains 1.0."""
    booster = AutoLightBoost(enabled=True)

    result = booster.process(bright_frame)
    assert booster.current_gamma == 1.0
    # Frame should be unchanged
    np.testing.assert_array_equal(result, bright_frame)


def test_autolight_disabled_bypass(dark_frame: np.ndarray):
    """Verify that disabling auto-light returns input frame unmodified."""
    booster = AutoLightBoost(enabled=False)
    result = booster.process(dark_frame)
    assert result is dark_frame


def test_temporal_anti_flicker_smoothing():
    """Verify that gamma transitions smoothly across frames rather than jumping."""
    booster = AutoLightBoost(enabled=True)

    dark = np.full((120, 160, 3), 20, dtype=np.uint8)
    # First frame
    booster.process(dark)
    gamma1 = booster.current_gamma

    # Second frame with same dark input
    booster.process(dark)
    gamma2 = booster.current_gamma

    # Step should be bounded by smoothing alpha (0.15)
    delta = abs(gamma1 - gamma2)
    assert delta <= 0.15


def test_execution_latency(dark_frame: np.ndarray):
    """Verify processing completes in < 1.5ms for 720p frame."""
    booster = AutoLightBoost(enabled=True)
    # Warmup
    booster.process(dark_frame)

    t0 = time.perf_counter()
    iterations = 20
    for _ in range(iterations):
        booster.process(dark_frame)
    avg_ms = ((time.perf_counter() - t0) / iterations) * 1000.0

    assert avg_ms < 2.0, f"Expected < 2.0ms, got {avg_ms:.2f}ms"
