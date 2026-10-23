"""Real-time Auto-Light Boost adaptive luminance compensation using precomputed LUT."""

from __future__ import annotations

import logging
import math
from typing import Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class AutoLightBoost:
    """Adaptive low-light compensation applying temporal-smoothed gamma correction via LUT."""

    def __init__(
        self,
        enabled: bool = True,
        target_luminance: float = 125.0,
        low_light_threshold: float = 100.0,
        min_gamma: float = 0.45,
        smoothing_alpha: float = 0.15,
        manual_gamma: float = 1.0,
    ) -> None:
        self.enabled = enabled
        self.target_luminance = target_luminance
        self.low_light_threshold = low_light_threshold
        self.min_gamma = min_gamma
        self.smoothing_alpha = smoothing_alpha
        self.manual_gamma: float = float(manual_gamma)

        self._current_gamma: float = 1.0
        self._cached_gamma: Optional[float] = None
        self._cached_lut: Optional[np.ndarray] = None

    @property
    def current_gamma(self) -> float:
        """Return the currently applied smoothed gamma factor."""
        return self._current_gamma

    def set_manual_gamma(self, gamma: float) -> None:
        """Set manual brightness/gamma factor."""
        self.manual_gamma = float(gamma)

    def set_target_luminance(self, target: float) -> None:
        """Set target luminance for adaptive boost."""
        self.target_luminance = float(target)

    def reset(self) -> None:
        """Reset temporal smoothing state."""
        self._current_gamma = 1.0
        self._cached_gamma = None
        self._cached_lut = None

    def _build_lut(self, gamma: float) -> np.ndarray:
        """Precompute 256-entry uint8 gamma transformation look-up table."""
        if self._cached_gamma is not None and abs(self._cached_gamma - gamma) < 0.005:
            assert self._cached_lut is not None
            return self._cached_lut

        # Vectorized LUT generation using architecture specification: LUT[i] = 255 * (i/255)^gamma
        gamma_clamped = max(0.1, min(5.0, gamma))
        indices = np.arange(256, dtype=np.float32) / 255.0
        lut_vals = np.clip(np.power(indices, gamma_clamped) * 255.0, 0, 255).astype(np.uint8)
        self._cached_lut = lut_vals
        self._cached_gamma = gamma
        return self._cached_lut

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply adaptive gamma LUT if enabled and scene is underexposed, or manual gamma if disabled."""
        if not self.enabled:
            if abs(self.manual_gamma - 1.0) < 0.02:
                return frame
            lut = self._build_lut(self.manual_gamma)
            return cv2.LUT(frame, lut)

        h, w = frame.shape[:2]
        # Fast subsampling factor of 8 for instantaneous luminance estimation
        sub_h, sub_w = max(1, h // 8), max(1, w // 8)
        subsampled = cv2.resize(frame, (sub_w, sub_h), interpolation=cv2.INTER_NEAREST)

        # Convert to YCrCb to extract luminance Y
        ycrcb = cv2.cvtColor(subsampled, cv2.COLOR_BGR2YCrCb)
        mean_y = float(np.mean(ycrcb[:, :, 0]))

        # Adaptive gamma computation
        if mean_y < self.low_light_threshold:
            # Gamma calculation: (log(target/255)) / (log(mean_y/255))
            log_target = math.log(self.target_luminance / 255.0)
            log_current = math.log(max(mean_y, 10.0) / 255.0)
            computed_gamma = np.clip(log_target / log_current, self.min_gamma, 1.0)
        else:
            computed_gamma = 1.0

        # Temporal smoothing to prevent flicker
        self._current_gamma = (1.0 - self.smoothing_alpha) * self._current_gamma + self.smoothing_alpha * float(computed_gamma)

        effective_gamma = self._current_gamma * self.manual_gamma

        # If lighting is adequate and effective_gamma is close to 1.0, bypass LUT
        if abs(effective_gamma - 1.0) < 0.02:
            return frame

        lut = self._build_lut(effective_gamma)
        return cv2.LUT(frame, lut)
