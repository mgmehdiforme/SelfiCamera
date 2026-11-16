"""Digital framing: aspect-correct crop with zoom, pan and smoothed auto-framing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class CropRect:
    x: int
    y: int
    w: int
    h: int


def compute_crop(
    frame_w: int,
    frame_h: int,
    aspect: float,
    zoom: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    focus: Optional[Tuple[float, float]] = None,
) -> CropRect:
    """Compute the crop rectangle for a target aspect ratio (width / height).

    * ``zoom`` >= 1 shrinks the crop around its center.
    * ``pan_x``/``pan_y`` in [-1, 1] shift the crop within the available slack.
    * ``focus`` (pixel coordinates) overrides the default center; pan is then ignored.
    """
    aspect = max(0.05, float(aspect))
    zoom = max(1.0, float(zoom))

    if frame_w / frame_h > aspect:
        base_h = float(frame_h)
        base_w = base_h * aspect
    else:
        base_w = float(frame_w)
        base_h = base_w / aspect

    crop_w = max(2.0, base_w / zoom)
    crop_h = max(2.0, base_h / zoom)
    slack_x = (frame_w - crop_w) / 2.0
    slack_y = (frame_h - crop_h) / 2.0

    if focus is not None:
        cx, cy = focus
    else:
        cx = frame_w / 2.0 + max(-1.0, min(1.0, pan_x)) * slack_x
        cy = frame_h / 2.0 + max(-1.0, min(1.0, pan_y)) * slack_y

    x0 = min(max(cx - crop_w / 2.0, 0.0), frame_w - crop_w)
    y0 = min(max(cy - crop_h / 2.0, 0.0), frame_h - crop_h)
    return CropRect(int(round(x0)), int(round(y0)), int(round(crop_w)), int(round(crop_h)))


class AutoFramer:
    """Turns a person mask into a smoothed focus point (head in the upper third)."""

    def __init__(self, smoothing: float = 0.12) -> None:
        self.smoothing = smoothing
        self._focus: Optional[Tuple[float, float]] = None

    @property
    def focus(self) -> Optional[Tuple[float, float]]:
        return self._focus

    def reset(self) -> None:
        self._focus = None

    def update(self, mask: np.ndarray, frame_w: int, frame_h: int, crop_h: float) -> Optional[Tuple[float, float]]:
        """Update the focus from a [0, 1] mask that covers the whole frame."""
        if mask is None or mask.size == 0:
            return self._focus
        binary = mask > 0.5
        coverage = float(binary.mean())
        if coverage < 0.01:
            # Nobody in frame: drift back to center.
            target = (frame_w / 2.0, frame_h / 2.0)
        else:
            mh, mw = binary.shape[:2]
            ys, xs = np.nonzero(binary)
            cx = float(xs.mean()) / mw * frame_w
            top = float(np.percentile(ys, 2)) / mh * frame_h
            # Place the top of the head ~12% below the crop's top edge.
            cy = top - 0.12 * crop_h + crop_h / 2.0
            target = (cx, cy)

        if self._focus is None:
            self._focus = target
        else:
            a = self.smoothing
            self._focus = (
                (1 - a) * self._focus[0] + a * target[0],
                (1 - a) * self._focus[1] + a * target[1],
            )
        return self._focus
