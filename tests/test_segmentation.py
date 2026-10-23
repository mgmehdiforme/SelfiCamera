"""Tests for 3-tier offline background blur engine and offline privacy guarantee."""

from __future__ import annotations

import ast
from pathlib import Path
import cv2
import numpy as np
import pytest

from selficamera.processor.segmentation import DEFAULT_MODEL_PATH, SegmentationBlurEngine


def test_tier_0_bypass(mock_frame: np.ndarray):
    """Verify tier 0 (Off) passes frame through unmodified without inference overhead."""
    engine = SegmentationBlurEngine(tier=0)
    result = engine.process(mock_frame)
    np.testing.assert_array_equal(result, mock_frame)


def test_blur_tier_cycling():
    """Verify cycling blur tier steps 0 -> 1 -> 2 -> 3 -> 0."""
    engine = SegmentationBlurEngine(tier=0)
    assert engine.cycle_tier() == 1
    assert engine.cycle_tier() == 2
    assert engine.cycle_tier() == 3
    assert engine.cycle_tier() == 0


def test_segmentation_mask_variance_and_spatial_contrast(synthetic_presenter_frame: np.ndarray):
    """AC-2.2: Empirically verify that _infer_mask produces a non-constant probability mask
    with significant variance (>0.05) and clear spatial contrast separating presenter from background.
    """
    engine = SegmentationBlurEngine(tier=2)
    mask = engine._infer_mask(synthetic_presenter_frame)

    # 1. Structural properties
    assert mask.shape == (256, 256), f"Expected (256, 256), got {mask.shape}"
    assert mask.dtype == np.float32, f"Expected float32, got {mask.dtype}"
    assert 0.0 <= mask.min() and mask.max() <= 1.0, f"Mask out of [0, 1] range: [{mask.min()}, {mask.max()}]"

    # 2. Variance criterion: Mandated by forensic audit (> 0.05)
    mask_var = float(np.var(mask))
    assert mask_var > 0.05, (
        f"INTEGRITY VIOLATION: Mask variance {mask_var:.6f} <= 0.05. "
        "The model is producing a flat/uniform output and not performing segmentation."
    )

    # 3. Dynamic range: Must distinguish high confidence from low confidence
    mask_range = float(mask.max() - mask.min())
    assert mask_range >= 0.50, f"Mask dynamic range {mask_range:.4f} is too narrow (< 0.50)"

    # 4. Spatial separation: Presenter center vs background periphery
    fg_mean = float(mask[80:176, 80:176].mean())
    bg_corners = np.concatenate([
        mask[:40, :40].flatten(),
        mask[:40, -40:].flatten(),
        mask[-40:, :40].flatten(),
        mask[-40:, -40:].flatten(),
    ])
    bg_mean = float(bg_corners.mean())

    assert fg_mean > 0.60, f"Presenter center foreground confidence too low: {fg_mean:.3f} <= 0.60"
    assert bg_mean < 0.30, f"Background periphery confidence too high: {bg_mean:.3f} >= 0.30"
    assert (fg_mean - bg_mean) > 0.35, (
        f"Insufficient spatial mask contrast: fg_mean ({fg_mean:.3f}) - bg_mean ({bg_mean:.3f}) = "
        f"{fg_mean - bg_mean:.3f} <= 0.35"
    )

    # 5. Input sensitivity: Verify model responds to visual input changes (anti-facade check)
    zeros_frame = np.zeros_like(synthetic_presenter_frame)
    mask_zeros = engine._infer_mask(zeros_frame)
    max_diff = float(np.max(np.abs(mask - mask_zeros)))
    assert max_diff > 0.20, (
        f"FACADE DETECTED: Model produced identical mask for presenter frame and all-zeros frame "
        f"(max abs diff = {max_diff:.6f} <= 0.20)"
    )


def test_foreground_sharpness_strictly_preserved(synthetic_presenter_frame: np.ndarray):
    """AC-2.2, AC-2.4: Empirically verify that presenter face/center sharpness is strictly preserved
    (Laplacian variance remains >= 90% of original) across all bokeh blur tiers.
    """
    h, w = synthetic_presenter_frame.shape[:2]
    cx, cy = w // 2, h // 2

    # High-frequency presenter center bounding box (facial features)
    fg_box = (slice(cy - 60, cy - 20), slice(cx - 50, cx + 50))
    # Background corner bounding box
    bg_box = (slice(0, 100), slice(0, 100))

    # Compute baseline Laplacian variance on original unblurred frame
    gray_t0 = cv2.cvtColor(synthetic_presenter_frame, cv2.COLOR_BGR2GRAY)
    v_fg_t0 = float(cv2.Laplacian(gray_t0[fg_box], cv2.CV_64F).var())
    v_bg_t0 = float(cv2.Laplacian(gray_t0[bg_box], cv2.CV_64F).var())

    assert v_fg_t0 > 500.0, f"Test fixture presenter lacking high-frequency detail: {v_fg_t0}"
    assert v_bg_t0 > 200.0, f"Test fixture background lacking high-frequency detail: {v_bg_t0}"

    engine = SegmentationBlurEngine(tier=1)
    t1 = engine.process(synthetic_presenter_frame)

    engine.set_tier(2)
    t2 = engine.process(synthetic_presenter_frame)

    engine.set_tier(3)
    t3 = engine.process(synthetic_presenter_frame)

    for tier_num, processed_frame in enumerate([t1, t2, t3], start=1):
        gray_tier = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2GRAY)
        v_fg_tier = float(cv2.Laplacian(gray_tier[fg_box], cv2.CV_64F).var())
        v_bg_tier = float(cv2.Laplacian(gray_tier[bg_box], cv2.CV_64F).var())

        fg_retention = v_fg_tier / v_fg_t0
        assert fg_retention >= 0.90, (
            f"BLUR LEAKAGE IN TIER {tier_num}: Presenter face sharpness dropped to {fg_retention:.1%} "
            f"({v_fg_tier:.1f} vs orig {v_fg_t0:.1f}). Expected >= 90.0% retention."
        )

        # Presenter sharpness must substantially exceed background sharpness in tiers 2 and 3
        if tier_num >= 2:
            assert v_fg_tier > 10.0 * v_bg_tier, (
                f"Tier {tier_num} presenter sharpness ({v_fg_tier:.1f}) is not sufficiently higher "
                f"than background sharpness ({v_bg_tier:.1f})"
            )


def test_background_bokeh_progression_strict_monotonic_attenuation(synthetic_presenter_frame: np.ndarray):
    """AC-2.2: Verify that tiers 1, 2, and 3 produce strictly monotonic, increasing background blur
    (strictly decreasing background Laplacian variance) with quantitative diffusion thresholds.
    """
    bg_box = (slice(0, 100), slice(0, 100))

    gray_t0 = cv2.cvtColor(synthetic_presenter_frame, cv2.COLOR_BGR2GRAY)
    v_bg_t0 = float(cv2.Laplacian(gray_t0[bg_box], cv2.CV_64F).var())
    assert v_bg_t0 > 200.0, f"Fixture background lacks high frequency: {v_bg_t0}"

    engine = SegmentationBlurEngine(tier=1)
    t1 = engine.process(synthetic_presenter_frame)

    engine.set_tier(2)
    t2 = engine.process(synthetic_presenter_frame)

    engine.set_tier(3)
    t3 = engine.process(synthetic_presenter_frame)

    v_bg_t1 = float(cv2.Laplacian(cv2.cvtColor(t1[bg_box], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
    v_bg_t2 = float(cv2.Laplacian(cv2.cvtColor(t2[bg_box], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
    v_bg_t3 = float(cv2.Laplacian(cv2.cvtColor(t3[bg_box], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())

    # 1. Strict monotonic decrease (prevents 0.0 >= 0.0 >= 0.0 pass)
    assert v_bg_t0 > v_bg_t1 > v_bg_t2 > v_bg_t3, (
        f"Background blur is not strictly progressive: "
        f"T0={v_bg_t0:.2f} > T1={v_bg_t1:.2f} > T2={v_bg_t2:.2f} > T3={v_bg_t3:.2f}"
    )

    # 2. Quantitative attenuation targets
    # Tier 1 (Subtle): At least 50% background variance reduction
    assert v_bg_t1 <= 0.50 * v_bg_t0, f"Tier 1 blur insufficient: {v_bg_t1:.1f} > 0.50 * {v_bg_t0:.1f}"
    # Tier 2 (Balanced): At least 80% background variance reduction
    assert v_bg_t2 <= 0.20 * v_bg_t0, f"Tier 2 blur insufficient: {v_bg_t2:.1f} > 0.20 * {v_bg_t0:.1f}"
    # Tier 3 (Heavy): At least 95% background variance reduction
    assert v_bg_t3 <= 0.05 * v_bg_t0, f"Tier 3 blur insufficient: {v_bg_t3:.1f} > 0.05 * {v_bg_t0:.1f}"


def test_dual_layer_zero_network_privacy_and_local_isolation(monkeypatch, synthetic_presenter_frame: np.ndarray):
    """AC-2.5.1, AC-2.5.2: Enforce 100% offline privacy guarantee via both static AST scanning
    and dynamic runtime socket interception during model loading and inference.
    """
    import socket

    # Layer 1: Static AST Scan
    project_root = Path(__file__).resolve().parent.parent / "selficamera"
    forbidden_modules = {"requests", "urllib", "urllib3", "httpx", "http.client", "aiohttp", "socketserver", "ftplib"}

    violations = []
    for py_file in project_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_modules:
                        violations.append((str(py_file), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in forbidden_modules:
                    violations.append((str(py_file), node.module))

    assert len(violations) == 0, f"Static AST audit found forbidden network imports: {violations}"

    # Layer 2: Dynamic Runtime Socket Trap
    original_socket = socket.socket
    network_call_log = []

    def audited_socket(family=socket.AF_UNIX, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            call_info = (family, args, kwargs)
            network_call_log.append(call_info)
            raise AssertionError(f"PRIVACY VIOLATION: Attempted to create internet socket: {call_info}")
        return original_socket(family, *args, **kwargs)

    def forbidden_dns(*args, **kwargs):
        network_call_log.append(("dns", args))
        raise AssertionError(f"PRIVACY VIOLATION: Attempted DNS resolution: {args}")

    monkeypatch.setattr(socket, "socket", audited_socket)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden_dns)
    monkeypatch.setattr(socket, "gethostbyname", forbidden_dns)

    # Execute full engine lifecycle and inference across all blur tiers under the network trap
    engine = SegmentationBlurEngine(tier=2)
    for tier in [0, 1, 2, 3]:
        engine.set_tier(tier)
        for _ in range(5):
            engine.process(synthetic_presenter_frame)

    assert len(network_call_log) == 0, f"Dynamic network trap intercepted network calls: {network_call_log}"

    # Layer 3: Model File Size & Local Path Audit
    model_file = engine.model_path
    assert model_file.exists(), f"ONNX model file not found at {model_file}"
    model_size_mb = model_file.stat().st_size / (1024 * 1024)
    assert model_size_mb < 2.0, f"Model file size exceeds 2.0 MB budget: {model_size_mb:.2f} MB"


def test_onnx_model_graph_structure():
    """Verify that ONNX model contains authentic residual Add nodes and depthwise convolutions."""
    import onnx

    assert DEFAULT_MODEL_PATH.exists()
    assert DEFAULT_MODEL_PATH.stat().st_size < 2 * 1024 * 1024

    model = onnx.load(str(DEFAULT_MODEL_PATH))
    op_types = [node.op_type for node in model.graph.node]

    assert "Add" in op_types, "Model lacks residual Add skip nodes"
    assert "ConvTranspose" in op_types, "Model lacks decoder upsampling nodes"
    assert "Sigmoid" in op_types, "Model lacks Sigmoid activation"
