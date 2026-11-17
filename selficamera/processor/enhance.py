"""Webcam enhancement: denoise, soft skin and sharpen.

Everything here runs at the bubble's on-screen size, after framing, so the per-frame cost
stays small (a few milliseconds at 380 px). The AI part is the face detector: it tells soft
skin (and auto light) where your face is.

* :class:`TemporalDenoiser` averages still areas over time and leaves moving areas alone,
  which removes webcam grain without ghosting.
* :func:`soft_skin` smooths skin inside detected faces with an edge-preserving filter and
  puts fine texture back, so faces look rested rather than plastic.
* :func:`sharpen` restores crispness lost to cheap webcam lenses (applied after denoise).

Researched and deliberately not included (see docs/PRODUCT.md): generative face restoration
(GFPGAN, CodeFormer, GPEN) and learned low-light/exposure models (Zero-DCE++, SCI, IAT).
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

Box = Tuple[int, int, int, int, float]


class TemporalDenoiser:
    """Motion-adaptive temporal denoise: still pixels are averaged over frames, moving ones are not."""

    def __init__(self) -> None:
        self._acc: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._acc = None

    def process(self, bgr: np.ndarray, strength: int) -> np.ndarray:
        if strength <= 0:
            self._acc = None
            return bgr
        cur = bgr.astype(np.float32)
        if self._acc is None or self._acc.shape != cur.shape:
            self._acc = cur
            return bgr
        s = strength / 100.0
        # Per-pixel motion from a slightly blurred luma difference (noise alone stays small).
        diff = cv2.GaussianBlur(cv2.cvtColor(cv2.absdiff(cur, self._acc), cv2.COLOR_BGR2GRAY), (5, 5), 0)
        noise_floor = 4.0 + 10.0 * s  # differences below this are grain, above it real motion
        # Weight of the new frame: low for still pixels (strong averaging), 1 for motion.
        min_w = 0.6 - 0.45 * s  # 0.6 at low strength .. 0.15 at full strength
        w = cv2.min(cv2.max(diff * (1.0 / (2.0 * noise_floor)) + (min_w - 0.5), min_w), 1.0)
        self._acc = cv2.blendLinear(cur, self._acc, w, 1.0 - w)
        return cv2.convertScaleAbs(self._acc)


def _skin_mask(bgr: np.ndarray) -> np.ndarray:
    """Soft skin-tone likelihood in YCrCb (works across skin tones; brightness-independent)."""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    cr = (ycrcb[..., 1] - 153.0) * (1.0 / 18.0)
    cb = (ycrcb[..., 2] - 103.0) * (1.0 / 16.0)
    # Distance to the skin cluster centre, soft edge.
    return np.clip(1.6 - cv2.magnitude(cr, cb), 0.0, 1.0)


def soft_skin(bgr: np.ndarray, faces: Sequence[Box], strength: int) -> np.ndarray:
    """Smooth skin inside detected faces; eyes, brows, hair and edges stay sharp."""
    if strength <= 0 or not faces:
        return bgr
    s = strength / 100.0
    out = bgr
    h, w = bgr.shape[:2]
    for x, y, fw, fh, _score in faces[:2]:
        # Region: face box grown to include forehead, cheeks and jaw.
        x0, y0 = max(0, int(x - 0.15 * fw)), max(0, int(y - 0.25 * fh))
        x1, y1 = min(w, int(x + 1.15 * fw)), min(h, int(y + 1.15 * fh))
        if x1 - x0 < 24 or y1 - y0 < 24:
            continue
        roi = out[y0:y1, x0:x1]
        rh, rw = roi.shape[:2]
        hw, hh = max(8, rw // 2), max(8, rh // 2)
        # Everything except the final blend runs on a half-size copy: the edge-preserving
        # filter's cost grows with its window, so this keeps it ~1-2 ms at any face size.
        half = cv2.resize(roi, (hw, hh), interpolation=cv2.INTER_AREA)
        smooth = cv2.bilateralFilter(half, d=7, sigmaColor=18 + 30 * s, sigmaSpace=3.0)
        smooth = cv2.resize(smooth, (rw, rh), interpolation=cv2.INTER_LINEAR)
        # Put a little fine texture back so skin doesn't look plastic.
        texture = cv2.addWeighted(roi, 0.35, cv2.GaussianBlur(roi, (0, 0), 1.0), -0.35, 0.0, dtype=cv2.CV_16S)
        smooth = cv2.add(smooth, texture, dtype=cv2.CV_8U)
        # Mask: skin tone x soft face ellipse, feathered (computed at half size).
        sx, sy = hw / rw, hh / rh
        ellipse = np.zeros((hh, hw), np.float32)
        center = (int((x + fw / 2 - x0) * sx), int((y + fh * 0.48 - y0) * sy))
        cv2.ellipse(ellipse, center, (int(fw * 0.62 * sx), int(fh * 0.72 * sy)), 0, 0, 360, 1.0, -1)
        k = max(3, int(max(fw, fh) * sx / 10) | 1)
        mask = cv2.GaussianBlur(_skin_mask(half) * ellipse, (k, k), 0) * min(1.0, 0.35 + 0.75 * s)
        mask = cv2.resize(mask, (rw, rh), interpolation=cv2.INTER_LINEAR)
        if out is bgr:
            out = bgr.copy()
        out[y0:y1, x0:x1] = cv2.blendLinear(smooth, roi, mask, 1.0 - mask)
    return out


def sharpen(bgr: np.ndarray, strength: int) -> np.ndarray:
    """Unsharp mask; small radius so it brings back detail without halos."""
    if strength <= 0:
        return bgr
    amount = strength / 100.0 * 1.2
    blur = cv2.GaussianBlur(bgr, (0, 0), 1.1)
    return cv2.addWeighted(bgr, 1.0 + amount, blur, -amount, 0)
