"""Adversarial stress-testing suite for SelfiCamera ONNX model and blur engine."""

from __future__ import annotations

import sys
import time
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selficamera.processor.segmentation import SegmentationBlurEngine, DEFAULT_MODEL_PATH

def generate_test_presenter_frame(w: int = 1280, h: int = 720) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            c = (((x // 8) % 2) ^ ((y // 8) % 2)) * 160 + 40
            frame[y : y + 8, x : x + 8, 0] = c
            frame[y : y + 8, x : x + 8, 1] = 120
            frame[y : y + 8, x : x + 8, 2] = 255 - c
    cx, cy = w // 2, h // 2
    cv2.ellipse(frame, (cx, cy + 200), (220, 150), 0, 0, 360, (40, 140, 60), -1)
    cv2.circle(frame, (cx, cy - 40), 100, (220, 180, 160), -1)
    cv2.circle(frame, (cx - 30, cy - 40), 12, (20, 20, 20), -1)
    cv2.circle(frame, (cx + 30, cy - 40), 12, (20, 20, 20), -1)
    cv2.ellipse(frame, (cx, cy + 10), (35, 15), 0, 0, 180, (20, 20, 80), 4)
    return frame


def run_adversarial_suite():
    print("=" * 70)
    print(" SELFI CAMERA ADVERSARIAL STRESS SUITE (CHALLENGER 2)")
    print("=" * 70)

    # 1. Direct ONNX Session Stress
    session = ort.InferenceSession(str(DEFAULT_MODEL_PATH), providers=["CPUExecutionProvider"])
    in_name = session.get_inputs()[0].name
    out_name = session.get_outputs()[0].name

    print("\n[1] ONNX Graph Inspection:")
    import onnx
    model_proto = onnx.load(str(DEFAULT_MODEL_PATH))
    node_types = {}
    for node in model_proto.graph.node:
        node_types[node.op_type] = node_types.get(node.op_type, 0) + 1
    print(f"  Total nodes: {len(model_proto.graph.node)}")
    print(f"  Node breakdown: {node_types}")
    print(f"  Model file size: {DEFAULT_MODEL_PATH.stat().st_size / 1024:.2f} KB")
    assert "Add" in node_types, "No Add nodes in ONNX graph!"
    assert node_types.get("Add", 0) >= 2, f"Expected at least 2 Add nodes, found {node_types.get('Add', 0)}"

    # 2. Extreme Inputs on Model & Engine
    engine = SegmentationBlurEngine(tier=2)

    # Prepare fixtures
    h, w = 720, 1280
    syn_frame = generate_test_presenter_frame(w, h)

    test_inputs = {}

    # a) Pure black
    test_inputs["Pure Black (Zeros)"] = np.zeros((h, w, 3), dtype=np.uint8)

    # b) Pure white
    test_inputs["Pure White (Ones)"] = np.full((h, w, 3), 255, dtype=np.uint8)

    # c) Uniform Grey variants
    test_inputs["Uniform Grey (64)"] = np.full((h, w, 3), 64, dtype=np.uint8)
    test_inputs["Uniform Grey (128)"] = np.full((h, w, 3), 128, dtype=np.uint8)
    test_inputs["Uniform Grey (192)"] = np.full((h, w, 3), 192, dtype=np.uint8)

    # d) Pure Gaussian noise
    rng = np.random.RandomState(42)
    noise_normal = np.clip(rng.normal(128, 50, (h, w, 3)), 0, 255).astype(np.uint8)
    test_inputs["Gaussian Noise (std=50)"] = noise_normal
    noise_uniform = rng.randint(0, 256, (h, w, 3), dtype=np.uint8)
    test_inputs["Uniform Random Noise"] = noise_uniform

    # e) High-frequency checkerboards
    for block_size in [1, 2, 4, 8, 16]:
        y_grid, x_grid = np.mgrid[0:h, 0:w]
        checker = (((x_grid // block_size) % 2) ^ ((y_grid // block_size) % 2)) * 255
        test_inputs[f"Checkerboard ({block_size}x{block_size}px)"] = np.stack([checker, checker, checker], axis=-1).astype(np.uint8)

    # f) Inverted colors of synthetic presenter
    test_inputs["Inverted Presenter"] = 255 - syn_frame

    # g) Extreme gradient grating
    grating_vert = (np.sin(np.linspace(0, 100 * np.pi, w)) * 127 + 128).astype(np.uint8)
    test_inputs["High-Freq Sine Grating"] = np.tile(grating_vert, (h, 1))[:, :, None].repeat(3, axis=-1)

    # h) Color extremes (Pure Red, Pure Green, Pure Blue)
    pure_red = np.zeros((h, w, 3), dtype=np.uint8)
    pure_red[:, :, 2] = 255
    test_inputs["Pure Red Canvas"] = pure_red
    pure_green = np.zeros((h, w, 3), dtype=np.uint8)
    pure_green[:, :, 1] = 255
    test_inputs["Pure Green Canvas"] = pure_green
    pure_blue = np.zeros((h, w, 3), dtype=np.uint8)
    pure_blue[:, :, 0] = 255
    test_inputs["Pure Blue Canvas"] = pure_blue

    # Normal presenter fixture
    test_inputs["Synthetic Presenter (Ground Truth)"] = syn_frame

    print("\n[2] Stress-Testing Extreme Inputs Through ONNX Model & SegmentationBlurEngine:")
    print("-" * 105)
    print(f"{'Input Name':<32} | {'Raw Min':<7} | {'Raw Max':<7} | {'Raw Var':<8} | {'Engine Min':<10} | {'Engine Max':<10} | {'Status'}")
    print("-" * 105)

    results = []
    for name, frame in test_inputs.items():
        # Test directly on ONNX session (resized to 256x256 float32)
        rgb_256 = cv2.cvtColor(cv2.resize(frame, (256, 256)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        raw_out = session.run([out_name], {in_name: rgb_256[None, ...]})[0]
        raw_mask = raw_out[0, :, :, 0]

        raw_min = float(raw_mask.min())
        raw_max = float(raw_mask.max())
        raw_var = float(raw_mask.var())
        raw_uniques = len(np.unique(raw_mask))

        # Test through SegmentationBlurEngine
        out_frame = engine.process(frame)
        assert out_frame.shape == frame.shape
        assert out_frame.dtype == np.uint8
        assert np.isfinite(out_frame).all()

        eng_min = int(out_frame.min())
        eng_max = int(out_frame.max())

        status = "PASS"
        if not np.isfinite(raw_mask).all():
            status = "FAIL (Non-finite raw mask)"
        elif raw_uniques < 10 and "Pure" not in name:
            status = "WARN (Low unique values)"

        print(f"{name:<32} | {raw_min:7.4f} | {raw_max:7.4f} | {raw_var:8.5f} | {eng_min:<10} | {eng_max:<10} | {status} (uniques={raw_uniques})")
        results.append({
            "name": name,
            "raw_min": raw_min,
            "raw_max": raw_max,
            "raw_var": raw_var,
            "raw_uniques": raw_uniques,
            "eng_min": eng_min,
            "eng_max": eng_max,
            "status": status,
        })

    print("-" * 105)

    # 3. Robustness on Malformed / Out-of-Bounds Floating Point Inputs
    print("\n[3] Robustness on Malformed / Out-of-bounds Inputs:")
    nan_frame = np.full((720, 1280, 3), np.nan, dtype=np.float32)
    # Convert nan frame to uint8 using clip / nan_to_num as real pipelines would or test engine._validate_and_refine_mask directly
    test_nan_mask = np.full((256, 256), np.nan, dtype=np.float32)
    refined_nan = engine._validate_and_refine_mask(test_nan_mask)
    assert np.isfinite(refined_nan).all(), "NaN mask refinement failed to produce finite output!"
    print(f"  ✓ NaN mask fallback: finite={np.isfinite(refined_nan).all()}, range=[{refined_nan.min():.4f}, {refined_nan.max():.4f}]")

    inf_mask = np.full((256, 256), np.inf, dtype=np.float32)
    refined_inf = engine._validate_and_refine_mask(inf_mask)
    assert np.isfinite(refined_inf).all(), "Inf mask refinement failed to produce finite output!"
    print(f"  ✓ Inf mask fallback: finite={np.isfinite(refined_inf).all()}, range=[{refined_inf.min():.4f}, {refined_inf.max():.4f}]")

    unbounded_logits = np.random.uniform(-100.0, 100.0, (256, 256)).astype(np.float32)
    refined_logits = engine._validate_and_refine_mask(unbounded_logits)
    assert 0.0 <= refined_logits.min() and refined_logits.max() <= 1.0, "Unbounded logits failed to clamp/sigmoid!"
    print(f"  ✓ Unbounded logits [-100, 100] sigmoid clamp: range=[{refined_logits.min():.4f}, {refined_logits.max():.4f}]")

    # 4. Aspect Ratio and Resolution Stress
    print("\n[4] Aspect Ratio and Extreme Resolution Stress:")
    resolutions = [
        ("Tiny Square (64x64)", 64, 64),
        ("Portrait (360x640)", 360, 640),
        ("Standard HD (1280x720)", 1280, 720),
        ("Full HD (1920x1080)", 1920, 1080),
        ("Ultra-wide (2560x1080)", 2560, 1080),
        ("4K UHD (3840x2160)", 3840, 2160),
    ]
    for rname, rw, rh in resolutions:
        rframe = np.full((rh, rw, 3), 120, dtype=np.uint8)
        cv2.circle(rframe, (rw // 2, rh // 2), min(rw, rh) // 4, (200, 160, 140), -1)
        t0 = time.perf_counter()
        out = engine.process(rframe)
        dt = (time.perf_counter() - t0) * 1000.0
        assert out.shape == (rh, rw, 3)
        print(f"  ✓ {rname:<25}: latency={dt:6.2f} ms, shape={out.shape}")

    print("\nAdversarial test suite complete without crashes or integrity failures!")
    return results


if __name__ == "__main__":
    run_adversarial_suite()
