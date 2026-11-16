"""Background compositing: blur, solid color, image and transparent removal."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def hex_to_bgr(color: str) -> Tuple[int, int, int]:
    c = color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return (b, g, r)


def cover_fit(image: np.ndarray, w: int, h: int) -> np.ndarray:
    """Scale and center-crop an image to exactly (h, w)."""
    ih, iw = image.shape[:2]
    scale = max(w / iw, h / ih)
    nw, nh = max(w, int(round(iw * scale))), max(h, int(round(ih * scale)))
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return resized[y0 : y0 + h, x0 : x0 + w]


class BackgroundCompositor:
    """Composites a person over a replacement background using a [0, 1] mask."""

    def __init__(self) -> None:
        self._image_path: str = ""
        self._image: Optional[np.ndarray] = None
        self._image_fit_key: Optional[Tuple[int, int]] = None
        self._image_fit: Optional[np.ndarray] = None

    def set_image(self, path: str) -> bool:
        if path == self._image_path:
            return self._image is not None
        self._image_path = path
        self._image = None
        self._image_fit = None
        self._image_fit_key = None
        if not path:
            return False
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("Could not read background image %s", path)
            return False
        # Keep memory bounded.
        h, w = img.shape[:2]
        if max(h, w) > 1920:
            s = 1920 / max(h, w)
            img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        self._image = img
        return True

    @property
    def has_image(self) -> bool:
        return self._image is not None

    @staticmethod
    def blur_plate(frame: np.ndarray, strength: int) -> np.ndarray:
        """Fast photographic blur: downscale, Gaussian blur, upscale."""
        h, w = frame.shape[:2]
        s = max(0, min(100, int(strength))) / 100.0
        if s <= 0:
            return frame
        scale = 2 if s < 0.35 else 4
        sw, sh = max(1, w // scale), max(1, h // scale)
        small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
        # Kernel relative to the image so the look is the same at any bubble size.
        k = int(min(sw, sh) * (0.02 + 0.16 * s)) | 1
        k = max(3, k)
        small = cv2.GaussianBlur(small, (k, k), 0)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

    def _plate(self, mode: str, frame: np.ndarray, strength: int, color: str) -> np.ndarray:
        h, w = frame.shape[:2]
        if mode == "blur":
            return self.blur_plate(frame, strength)
        if mode == "image" and self._image is not None:
            if self._image_fit_key != (w, h):
                self._image_fit = cover_fit(self._image, w, h)
                self._image_fit_key = (w, h)
            assert self._image_fit is not None
            return self._image_fit
        # "color", or "image" without a readable image.
        plate = np.empty_like(frame)
        plate[:] = hex_to_bgr(color)
        return plate

    def composite(self, frame: np.ndarray, mask: np.ndarray, mode: str, strength: int = 60, color: str = "#00B140") -> np.ndarray:
        """Return BGR (for blur/color/image) or BGRA (for remove)."""
        if mode == "remove":
            alpha = np.clip(mask * 255.0 + 0.5, 0, 255).astype(np.uint8)
            return np.dstack([frame, alpha])
        plate = self._plate(mode, frame, strength, color)
        m = np.ascontiguousarray(mask, dtype=np.float32)
        return cv2.blendLinear(frame, plate, m, 1.0 - m)
