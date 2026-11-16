"""Light & color: adaptive auto-light plus brightness/contrast/saturation/warmth.

Auto light meters exposure on what matters, in this order of preference:

1. **Your face**, found by a small face-detection model (``processor/face.py``):
   a dark, backlit face is lifted and a blown-out face is pulled down, whatever
   the background is doing.
2. **You**, using the person mask from the segmentation model.
3. **The center** of the picture (no AI model installed): only dim scenes are brightened.

Faces and people inside a comfortable band are left alone, so the effect never
"normalises" skin tones. Everything except saturation is folded into a single
per-channel 256-entry lookup table, so the per-frame cost is one ``cv2.LUT`` call.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple, Union

import cv2
import numpy as np

# Comfortable exposure band for the subject (8-bit luma). Outside it, auto light
# moves the subject to the nearest target; inside it, nothing changes.
SUBJECT_DARK, SUBJECT_DARK_TARGET = 98.0, 124.0
SUBJECT_BRIGHT, SUBJECT_BRIGHT_TARGET = 205.0, 178.0
MAX_GAMMA = 1.35

# What auto light meters on: ("face", [(x, y, w, h, score), ...]) or ("person", mask HxW float)
Meter = Tuple[str, Union[Sequence[Tuple[int, int, int, int, float]], np.ndarray]]


def _gamma_for(current: float, target: float, lo: float, hi: float) -> float:
    log_target = math.log(target / 255.0)
    log_current = math.log(min(250.0, max(current, 8.0)) / 255.0)
    return float(np.clip(log_target / log_current, lo, hi))


class ImageAdjuster:
    """Applies auto-light and manual color adjustments to BGR frames."""

    def __init__(
        self,
        auto_light: bool = True,
        brightness: int = 0,
        contrast: int = 0,
        saturation: int = 0,
        warmth: int = 0,
        target_luminance: float = 118.0,
        low_light_threshold: float = 105.0,
        min_gamma: float = 0.45,
        smoothing: float = 0.12,
    ) -> None:
        self.auto_light = auto_light
        self.brightness = int(brightness)
        self.contrast = int(contrast)
        self.saturation = int(saturation)
        self.warmth = int(warmth)
        self.target_luminance = target_luminance
        self.low_light_threshold = low_light_threshold
        self.min_gamma = min_gamma
        self.smoothing = smoothing

        self._gamma = 1.0
        self._lut_key: Optional[Tuple[float, int, int, int]] = None
        self._lut: Optional[np.ndarray] = None
        self.metering = "center"  # what the last auto-light decision was based on
        self.subject_luma: Optional[float] = None

    @property
    def current_gamma(self) -> float:
        return self._gamma

    def reset(self) -> None:
        self._gamma = 1.0
        self._lut_key = None
        self._lut = None

    def is_identity(self) -> bool:
        return (
            not self.auto_light
            and self.brightness == 0
            and self.contrast == 0
            and self.saturation == 0
            and self.warmth == 0
        )

    @staticmethod
    def subject_gamma(luma: float, min_gamma: float = 0.45) -> float:
        """Gamma that moves a subject's luma into the comfortable band (1.0 inside it)."""
        if luma < SUBJECT_DARK:
            return _gamma_for(luma, SUBJECT_DARK_TARGET, min_gamma, 1.0)
        if luma > SUBJECT_BRIGHT:
            return _gamma_for(luma, SUBJECT_BRIGHT_TARGET, 1.0, MAX_GAMMA)
        return 1.0

    def _face_luma(self, gray: np.ndarray, boxes: Sequence[Tuple[int, int, int, int, float]]) -> Optional[float]:
        values = []
        weights = []
        for x, y, w, h, _score in boxes[:3]:
            # Inner face (skip hair, ears and background at the box edges).
            x0, x1 = int(x + 0.22 * w), int(x + 0.78 * w)
            y0, y1 = int(y + 0.25 * h), int(y + 0.85 * h)
            patch = gray[max(0, y0) : max(0, y1), max(0, x0) : max(0, x1)]
            if patch.size >= 16:
                values.append(float(np.median(patch)))
                weights.append(float(w * h))
        if not values:
            return None
        return float(np.average(values, weights=weights))

    @staticmethod
    def _person_luma(gray: np.ndarray, mask: np.ndarray) -> Optional[float]:
        if mask.shape[:2] != gray.shape[:2]:
            mask = cv2.resize(mask, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR)
        weight = np.clip(mask.astype(np.float32), 0.0, 1.0)
        # Weight the upper part of the person (face and shoulders) over clothes.
        rows = np.linspace(1.6, 0.6, gray.shape[0], dtype=np.float32)[:, None]
        weight = weight * rows
        total = float(weight.sum())
        if total < 0.03 * gray.size:  # nobody in frame
            return None
        return float((gray.astype(np.float32) * weight).sum() / total)

    def _measure_gamma(self, frame: np.ndarray, meter: Optional[Meter] = None) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if meter is not None:
            kind, data = meter
            luma = None
            if kind == "face" and len(data):
                luma = self._face_luma(gray, data)  # type: ignore[arg-type]
            elif kind == "person" and isinstance(data, np.ndarray):
                luma = self._person_luma(gray, data)
            if luma is not None:
                self.metering, self.subject_luma = kind, luma
                return self.subject_gamma(luma, self.min_gamma)
        h, w = frame.shape[:2]
        small = cv2.resize(gray, (max(1, w // 8), max(1, h // 8)), interpolation=cv2.INTER_AREA)
        mean_y = float(small.mean())
        self.metering, self.subject_luma = "center", mean_y
        if mean_y >= self.low_light_threshold:
            return 1.0
        return _gamma_for(mean_y, self.target_luminance, self.min_gamma, 1.0)

    @staticmethod
    def build_lut(gamma: float, brightness: int, contrast: int, warmth: int) -> np.ndarray:
        """Build a (256, 1, 3) uint8 BGR lookup table."""
        x = np.arange(256, dtype=np.float32) / 255.0
        x = np.power(x, max(0.1, gamma))
        c = 1.0 + contrast / 100.0 * 1.2
        x = (x - 0.5) * c + 0.5
        x = x + brightness / 100.0 * 0.6
        w = warmth / 50.0
        r = x * (1.0 + 0.10 * w)
        g = x * (1.0 + 0.02 * w)
        b = x * (1.0 - 0.10 * w)
        lut = np.stack([b, g, r], axis=-1)
        return np.clip(lut * 255.0 + 0.5, 0, 255).astype(np.uint8).reshape(256, 1, 3)

    def process(self, frame: np.ndarray, meter: Optional[Meter] = None) -> np.ndarray:
        if self.auto_light:
            target = self._measure_gamma(frame, meter)
            self._gamma = (1 - self.smoothing) * self._gamma + self.smoothing * target
        else:
            self._gamma = 1.0

        gamma_q = round(self._gamma, 2)
        if not (abs(gamma_q - 1.0) < 0.015 and self.brightness == 0 and self.contrast == 0 and self.warmth == 0):
            key = (gamma_q, self.brightness, self.contrast, self.warmth)
            if key != self._lut_key or self._lut is None:
                self._lut = self.build_lut(*key)
                self._lut_key = key
            frame = cv2.LUT(frame, self._lut)

        if self.saturation != 0:
            s = 1.0 + self.saturation / 100.0
            gray = cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
            frame = cv2.addWeighted(frame, s, gray, 1.0 - s, 0.0)
        return frame
