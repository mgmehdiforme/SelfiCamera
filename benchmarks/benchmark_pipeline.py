"""Per-frame latency benchmark for the processing pipeline.

Usage:  python benchmarks/benchmark_pipeline.py [--frames 300]
Reports p50/p95 per bubble size and background mode, and whether the AI model is active.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from selficamera.capture.camera import CameraWorker  # noqa: E402
from selficamera.processor.pipeline import FrameProcessor  # noqa: E402
from selficamera.ui.shapes import content_size  # noqa: E402

BUDGET_MS = 20.0  # p95 per frame; 30 fps leaves 33 ms


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--dpr", type=float, default=1.0, help="Device pixel ratio of the display")
    args = ap.parse_args()

    proc = FrameProcessor()
    feed = CameraWorker(proc, width=1280, height=720, mock_mode=True)
    frames = [feed.generate_mock_frame() for _ in range(8)]
    print(f"Segmentation: {proc.segmentation.model_name} ({proc.segmentation.backend_name})")
    print(f"{'shape':<10} {'size':>5} {'mode':<7} {'avg ms':>8} {'p95 ms':>8}")
    worst = 0.0
    for shape, size in (("circle", 260), ("circle", 380), ("landscape", 260), ("portrait", 260)):
        w, h = content_size(shape, size)
        proc.set_output_size(int(w * args.dpr), int(h * args.dpr))
        for mode in ("none", "blur", "remove"):
            proc.configure(background_mode=mode, auto_light=True)
            for i in range(10):
                proc.process(frames[i % len(frames)])
            samples = []
            for i in range(args.frames):
                t = time.perf_counter()
                proc.process(frames[i % len(frames)])
                samples.append((time.perf_counter() - t) * 1000)
            samples.sort()
            p50 = statistics.mean(samples)
            p95 = samples[int(len(samples) * 0.95) - 1]
            worst = max(worst, p95)
            print(f"{shape:<10} {size:>5} {mode:<7} {p50:>8.2f} {p95:>8.2f}")
    verdict = "PASS" if worst <= BUDGET_MS else "OVER BUDGET"
    print(f"\nWorst p95: {worst:.2f} ms (budget {BUDGET_MS} ms) -> {verdict}")
    return 0 if worst <= BUDGET_MS else 1


if __name__ == "__main__":
    sys.exit(main())
