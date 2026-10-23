"""Continuous stress benchmarking harness: 1000 frames at Tier 3 with full pipeline."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selficamera.processor.pipeline import FrameProcessor
from benchmarks.adversarial_stress_suite import generate_test_presenter_frame


def run_continuous_stress(num_frames: int = 1000, resolution=(1280, 720), tier: int = 3):
    w, h = resolution
    print("\n" + "=" * 80)
    print(f" CONTINUOUS STRESS BENCHMARK: {num_frames} frames @ {w}x{h} (Tier {tier} Heavy Bokeh)")
    print("=" * 80)

    frame = generate_test_presenter_frame(w, h)
    proc = FrameProcessor(mirror=True, auto_light=True, blur_level=tier)

    # Warmup
    print("Warming up pipeline (30 frames)...")
    for _ in range(30):
        proc.process(frame)

    process = psutil.Process(os.getpid())
    rss_start_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent_start = process.cpu_percent(interval=None)

    latencies_ms = []
    start_total_time = time.perf_counter()

    print(f"Running continuous stress test over {num_frames} consecutive frames...")
    for i in range(num_frames):
        t0 = time.perf_counter()
        out = proc.process(frame)
        t_frame = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(t_frame)

        if (i + 1) % 200 == 0:
            print(f"  Processed {i + 1}/{num_frames} frames... (current P50: {np.median(latencies_ms):.2f} ms)")

    elapsed_s = time.perf_counter() - start_total_time
    fps = num_frames / elapsed_s
    rss_end_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent = process.cpu_percent(interval=None) / psutil.cpu_count(logical=True)

    latencies_arr = np.array(latencies_ms)
    min_lat = float(np.min(latencies_arr))
    mean_lat = float(np.mean(latencies_arr))
    median_lat = float(np.median(latencies_arr))
    p95_lat = float(np.percentile(latencies_arr, 95))
    p99_lat = float(np.percentile(latencies_arr, 99))
    max_lat = float(np.max(latencies_arr))

    print("\n" + "-" * 80)
    print(" CONTINUOUS STRESS RESULTS SUMMARY")
    print("-" * 80)
    print(f"  Total Frames Processed:    {num_frames}")
    print(f"  Total Duration:            {elapsed_s:.2f} s")
    print(f"  Average Throughput:        {fps:.1f} FPS (Target: >= 30.0 FPS)")
    print(f"  CPU Utilization:           {cpu_percent:.1f}%")
    print(f"  Memory Footprint:          {rss_start_mb:.1f} MB -> {rss_end_mb:.1f} MB (Delta: {rss_end_mb - rss_start_mb:+.1f} MB)")
    print(" Latency Statistics:")
    print(f"   - Min Latency:            {min_lat:.2f} ms")
    print(f"   - Mean Latency:           {mean_lat:.2f} ms")
    print(f"   - Median (P50) Latency:   {median_lat:.2f} ms")
    print(f"   - 95th Percentile (P95):  {p95_lat:.2f} ms (Ceiling: < 25.0 ms / Budget: < 30.0 ms)")
    print(f"   - 99th Percentile (P99):  {p99_lat:.2f} ms")
    print(f"   - Max Latency:            {max_lat:.2f} ms")
    print("=" * 80)

    # Assertions
    assert fps >= 30.0, f"Throughput failure: {fps:.1f} FPS < 30.0 FPS"
    assert p95_lat < 30.0, f"Latency budget exceeded: P95 {p95_lat:.2f} ms >= 30.0 ms"
    assert p95_lat < 25.0, f"P95 latency {p95_lat:.2f} ms >= 25.0 ms quality gate"
    assert abs(rss_end_mb - rss_start_mb) < 50.0, f"Potential memory leak detected: {rss_end_mb - rss_start_mb:.1f} MB growth"

    print("✓ CONTINUOUS STRESS PERFORMANCE CRITERIA ALL SATISFIED!")
    return {
        "num_frames": num_frames,
        "fps": fps,
        "mean_lat": mean_lat,
        "median_lat": median_lat,
        "p95_lat": p95_lat,
        "p99_lat": p99_lat,
        "max_lat": max_lat,
        "cpu_percent": cpu_percent,
        "mem_delta_mb": rss_end_mb - rss_start_mb,
    }


if __name__ == "__main__":
    run_continuous_stress(num_frames=1000, resolution=(1280, 720), tier=3)
