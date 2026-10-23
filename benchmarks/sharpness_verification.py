"""Empirical sharpness and blur separation verification across Tiers 0, 1, 2, 3."""

from __future__ import annotations

import sys
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selficamera.processor.pipeline import FrameProcessor
from selficamera.processor.segmentation import SegmentationBlurEngine
from benchmarks.adversarial_stress_suite import generate_test_presenter_frame


def verify_sharpness_and_bokeh():
    print("\n" + "=" * 75)
    print(" FOREGROUND SHARPNESS & BACKGROUND BOKEH EMPIRICAL VERIFICATION")
    print("=" * 75)

    frame = generate_test_presenter_frame(1280, 720)
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2

    # Regions of Interest (ROI)
    # 1. Presenter Face Center ROI (features: eyes, nose, mouth)
    fg_roi = (slice(cy - 60, cy - 20), slice(cx - 50, cx + 50))
    # 2. Background Corner ROIs (XOR checkerboard)
    bg_tl_roi = (slice(0, 100), slice(0, 100))
    bg_tr_roi = (slice(0, 100), slice(w - 100, w))
    bg_bl_roi = (slice(h - 100, h), slice(0, 100))
    bg_br_roi = (slice(h - 100, h), slice(w - 100, w))

    def compute_var(img_bgr, roi):
        gray = cv2.cvtColor(img_bgr[roi], cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Baseline (Tier 0 / Unblurred)
    v_fg_base = compute_var(frame, fg_roi)
    v_bg_tl_base = compute_var(frame, bg_tl_roi)
    v_bg_tr_base = compute_var(frame, bg_tr_roi)
    v_bg_bl_base = compute_var(frame, bg_bl_roi)
    v_bg_br_base = compute_var(frame, bg_br_roi)
    v_bg_avg_base = (v_bg_tl_base + v_bg_tr_base + v_bg_bl_base + v_bg_br_base) / 4.0

    print(f"\nBaseline Unblurred (Tier 0):")
    print(f"  Presenter Face Center Var: {v_fg_base:8.2f}")
    print(f"  Background Corners Var:    {v_bg_avg_base:8.2f} (TL={v_bg_tl_base:.1f}, TR={v_bg_tr_base:.1f}, BL={v_bg_bl_base:.1f}, BR={v_bg_br_base:.1f})")

    engine = SegmentationBlurEngine(tier=0)

    tier_names = {
        0: "Tier 0 (Bypass/Off)",
        1: "Tier 1 (Subtle Bokeh)",
        2: "Tier 2 (Balanced Bokeh)",
        3: "Tier 3 (Heavy Bokeh)",
    }

    results = []

    print("\nTesting SegmentationBlurEngine across tiers:")
    print("-" * 95)
    print(f"{'Tier':<25} | {'FG Var':<10} | {'FG Ret %':<10} | {'BG Var':<10} | {'BG Atten %':<12} | {'Ratio FG/BG':<12}")
    print("-" * 95)

    for tier in [0, 1, 2, 3]:
        engine.set_tier(tier)
        processed = engine.process(frame)

        v_fg = compute_var(processed, fg_roi)
        v_bg_tl = compute_var(processed, bg_tl_roi)
        v_bg_tr = compute_var(processed, bg_tr_roi)
        v_bg_bl = compute_var(processed, bg_bl_roi)
        v_bg_br = compute_var(processed, bg_br_roi)
        v_bg_avg = (v_bg_tl + v_bg_tr + v_bg_bl + v_bg_br) / 4.0

        fg_retention = (v_fg / v_fg_base) * 100.0
        bg_attenuation = (v_bg_avg / v_bg_avg_base) * 100.0
        ratio = v_fg / max(1e-6, v_bg_avg)

        print(f"{tier_names[tier]:<25} | {v_fg:10.2f} | {fg_retention:9.2f}% | {v_bg_avg:10.2f} | {bg_attenuation:11.2f}% | {ratio:11.1f}x")

        # Assertions
        if tier > 0:
            assert fg_retention >= 90.0, f"Tier {tier} face sharpness retention {fg_retention:.1f}% dropped below 90% threshold!"
            assert bg_attenuation < 50.0, f"Tier {tier} background blur insufficient ({bg_attenuation:.1f}%)"
            assert v_fg > 10.0 * v_bg_avg, f"Tier {tier} foreground is not significantly sharper than background ({ratio:.1f}x)"

        results.append({
            "tier": tier,
            "v_fg": v_fg,
            "fg_retention": fg_retention,
            "v_bg": v_bg_avg,
            "bg_attenuation": bg_attenuation,
            "ratio": ratio,
        })

    print("-" * 95)

    # Monotonicity check on background variance
    assert results[0]["v_bg"] > results[1]["v_bg"] > results[2]["v_bg"] > results[3]["v_bg"], \
        "Background variance is not strictly monotonically decreasing across tiers!"
    print("✓ Monotonic Background Diffusion Confirmed: T0 > T1 > T2 > T3")

    # Full FrameProcessor Pipeline Test (Mirror + Lighting + Center Crop + Blur)
    print("\nTesting Full FrameProcessor Pipeline (Mirror=False, AutoLight=False, Blur Tiers 0..3):")
    print("-" * 95)
    for tier in [0, 1, 2, 3]:
        proc = FrameProcessor(mirror=False, auto_light=False, blur_level=tier)
        out = proc.process(frame)
        h_crop, w_crop = out.shape[:2]
        # In 1:1 center crop (720x720)
        cx_c, cy_c = w_crop // 2, h_crop // 2
        fg_crop_roi = (slice(cy_c - 60, cy_c - 20), slice(cx_c - 50, cx_c + 50))
        bg_crop_roi = (slice(0, 80), slice(0, 80))

        v_fg_p = compute_var(out, fg_crop_roi)
        v_bg_p = compute_var(out, bg_crop_roi)
        print(f"  {tier_names[tier]:<25}: Shape={out.shape}, FG Var={v_fg_p:8.2f}, BG Var={v_bg_p:8.2f}, Ratio={v_fg_p/max(1e-6, v_bg_p):.1f}x")

    print("\nSharpness and bokeh verification PASSED successfully!")
    return results


if __name__ == "__main__":
    verify_sharpness_and_bokeh()
