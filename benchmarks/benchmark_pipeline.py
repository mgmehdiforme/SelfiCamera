"""End-to-end performance and latency benchmarking suite for SelfiCamera."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import cv2
import numpy as np
import psutil

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selficamera.processor.pipeline import FrameProcessor


def generate_benchmark_frame(width: int = 1280, height: int = 720) -> np.ndarray:
    """Generate realistic 720p BGR test frame with presenter silhouette."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.linspace(40, 80, height, dtype=np.uint8)[:, None]
    frame[:, :, 1] = 50
    frame[:, :, 2] = 60

    cx, cy = width // 2, height // 2
    cv2.circle(frame, (cx, cy - 30), 120, (180, 150, 140), -1)
    cv2.ellipse(frame, (cx, cy + 220), (220, 150), 0, 0, 360, (120, 80, 70), -1)
    return frame


def run_benchmark(num_frames: int = 500, blur_tier: int = 2) -> dict:
    """Execute end-to-end processing across frames, profiling latencies and CPU utilization."""
    print(f"\n=================================================================")
    print(f" SelfiCamera Pipeline Benchmark: {num_frames} frames @ 720p (Tier {blur_tier})")
    print(f"=================================================================")

    processor = FrameProcessor(mirror=True, auto_light=True, blur_level=blur_tier)
    test_frame = generate_benchmark_frame()

    # Warmup
    print("Warming up pipeline (20 frames)...")
    for _ in range(20):
        processor.process(test_frame)

    latencies_total = []
    latencies_mirror = []
    latencies_light = []
    latencies_crop = []
    latencies_seg = []

    process = psutil.Process(os.getpid())
    cpu_percent_start = process.cpu_percent(interval=None)
    bench_start_time = time.perf_counter()

    print(f"Running {num_frames} benchmark frames...")
    for i in range(num_frames):
        t_start = time.perf_counter()

        # 1. Mirror
        t0 = time.perf_counter()
        f_mirrored = cv2.flip(test_frame, 1) if processor.mirror_enabled else test_frame
        t_mirror = time.perf_counter() - t0

        # 2. Lighting
        t0 = time.perf_counter()
        f_lit = processor.auto_light.process(f_mirrored)
        t_light = time.perf_counter() - t0

        # 3. Center crop to 1:1 square
        t0 = time.perf_counter()
        f_cropped = processor.crop_center_square(f_lit)
        t_crop = time.perf_counter() - t0

        # 4. Segmentation blur on 1:1 square
        t0 = time.perf_counter()
        f_blurred = processor.segmentation.process(f_cropped)
        t_seg = time.perf_counter() - t0

        t_total = time.perf_counter() - t_start

        latencies_total.append(t_total * 1000.0)
        latencies_mirror.append(t_mirror * 1000.0)
        latencies_light.append(t_light * 1000.0)
        latencies_crop.append(t_crop * 1000.0)
        latencies_seg.append(t_seg * 1000.0)

    bench_elapsed = time.perf_counter() - bench_start_time
    cpu_percent = process.cpu_percent(interval=None) / psutil.cpu_count(logical=True)
    fps_achieved = num_frames / bench_elapsed

    stats = {
        "frames": num_frames,
        "fps_achieved": fps_achieved,
        "cpu_percent": cpu_percent,
        "total_mean": float(np.mean(latencies_total)),
        "total_median": float(np.median(latencies_total)),
        "total_p95": float(np.percentile(latencies_total, 95)),
        "total_max": float(np.max(latencies_total)),
        "mirror_mean": float(np.mean(latencies_mirror)),
        "light_mean": float(np.mean(latencies_light)),
        "crop_mean": float(np.mean(latencies_crop)),
        "seg_mean": float(np.mean(latencies_seg)),
    }

    # Print results table
    print("\n-----------------------------------------------------------------")
    print(f" Stage Breakdown (Mean Latency):")
    print(f"   - Horizontal Mirror:    {stats['mirror_mean']:.3f} ms")
    print(f"   - Auto-Light Boost:     {stats['light_mean']:.3f} ms")
    print(f"   - 1:1 Center Crop:      {stats['crop_mean']:.3f} ms")
    print(f"   - Segmentation & Bokeh: {stats['seg_mean']:.3f} ms")
    print("-----------------------------------------------------------------")
    print(f" End-to-End Latency Metrics:")
    print(f"   - Mean Latency:         {stats['total_mean']:.2f} ms")
    print(f"   - Median (P50) Latency: {stats['total_median']:.2f} ms")
    print(f"   - 95th Percentile (P95):{stats['total_p95']:.2f} ms")
    print(f"   - Max Latency:          {stats['total_max']:.2f} ms")
    print(f"   - Throughput:           {stats['fps_achieved']:.1f} FPS")
    print(f"   - CPU Utilization:      {stats['cpu_percent']:.1f}%")
    print("=================================================================\n")

    # Strict latency assertion: 95th percentile must be < 25.0ms (hard limit 30.0ms)
    assert stats["total_p95"] < 25.0, f"P95 latency {stats['total_p95']:.2f}ms exceeds 25.0ms ceiling!"
    print("✓ Latency Budget Gate Passed: P95 < 25.0 ms")

    return stats


if __name__ == "__main__":
    run_benchmark(num_frames=500, blur_tier=2)
