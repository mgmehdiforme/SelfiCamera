"""Per-stage millisecond timing profiler across different resolutions and blur levels."""

from __future__ import annotations

import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from selficamera.processor.pipeline import FrameProcessor
from benchmarks.benchmark_pipeline import generate_benchmark_frame


def profile_configurations():
    """Profile different capture resolutions and blur levels."""
    resolutions = [
        ("480p (640x480)", 640, 480),
        ("720p (1280x720)", 1280, 720),
        ("1080p (1920x1080)", 1920, 1080),
    ]

    print("\n==========================================================================")
    print(" SelfiCamera Resolution & Blur Level Latency Matrix (100 iterations)")
    print("==========================================================================")
    print(f"{'Resolution':<20} | {'Tier 0 (Off)':<14} | {'Tier 1 (Subtle)':<16} | {'Tier 2 (Bal)':<14} | {'Tier 3 (Hvy)':<14}")
    print("---------------------+----------------+------------------+----------------+---------------")

    for name, w, h in resolutions:
        frame = generate_benchmark_frame(width=w, height=h)
        row = [f"{name:<20}"]
        for tier in [0, 1, 2, 3]:
            proc = FrameProcessor(mirror=True, auto_light=True, blur_level=tier)
            # Warmup
            for _ in range(5):
                proc.process(frame)

            times = []
            for _ in range(100):
                t0 = time.perf_counter()
                proc.process(frame)
                times.append((time.perf_counter() - t0) * 1000.0)

            mean_ms = np.mean(times)
            row.append(f"{mean_ms:6.2f} ms      ")

        print(" | ".join(row))
    print("==========================================================================\n")


if __name__ == "__main__":
    profile_configurations()
