"""Composite image processing pipeline linking mirror, auto-light boost, and segmentation blur."""

from __future__ import annotations

import logging
from typing import Optional
import cv2
import numpy as np
from PySide6.QtGui import QImage

from selficamera.processor.lighting import AutoLightBoost
from selficamera.processor.segmentation import SegmentationBlurEngine

logger = logging.getLogger(__name__)


class FrameProcessor:
    """Orchestrates end-to-end frame transformations: mirror, lighting, blur, and 1:1 cropping."""

    def __init__(
        self,
        mirror: bool = True,
        auto_light: bool = True,
        blur_level: int = 2,
        model_path: Optional[str] = None,
        manual_gamma: float = 1.0,
        target_luminance: float = 125.0,
        blur_intensity: Optional[int] = None,
    ) -> None:
        self.mirror_enabled = mirror
        self.auto_light = AutoLightBoost(
            enabled=auto_light,
            target_luminance=target_luminance,
            manual_gamma=manual_gamma,
        )
        self.segmentation = SegmentationBlurEngine(
            model_path=model_path,
            tier=blur_level,
            intensity=blur_intensity,
        )

    @property
    def auto_light_enabled(self) -> bool:
        return self.auto_light.enabled

    @auto_light_enabled.setter
    def auto_light_enabled(self, val: bool) -> None:
        self.auto_light.enabled = val

    @property
    def manual_gamma(self) -> float:
        return self.auto_light.manual_gamma

    def set_manual_gamma(self, gamma: float) -> None:
        """Set manual brightness/gamma factor."""
        self.auto_light.set_manual_gamma(gamma)

    @property
    def target_luminance(self) -> float:
        return self.auto_light.target_luminance

    def set_target_luminance(self, target: float) -> None:
        """Set target luminance for Auto-Light Boost."""
        self.auto_light.set_target_luminance(target)

    @property
    def blur_level(self) -> int:
        return self.segmentation.tier

    @blur_level.setter
    def blur_level(self, val: int) -> None:
        self.segmentation.set_tier(val)

    def set_blur_tier(self, tier: int) -> None:
        """Set background blur tier (0-3)."""
        self.segmentation.set_tier(tier)

    @property
    def blur_intensity(self) -> int:
        return self.segmentation.intensity

    def set_blur_intensity(self, intensity: int) -> None:
        """Set continuous background blur intensity (0-100)."""
        self.segmentation.set_intensity(intensity)

    def crop_center_square(self, frame: np.ndarray) -> np.ndarray:
        """Center-crop frame into an exact 1:1 aspect ratio square."""
        h, w = frame.shape[:2]
        if h == w:
            return frame

        dim = min(h, w)
        start_x = (w - dim) // 2
        start_y = (h - dim) // 2
        return frame[start_y : start_y + dim, start_x : start_x + dim]

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Run full processing pipeline: mirror -> auto-light -> center-crop -> blur."""
        if frame is None or frame.size == 0:
            return frame

        # 1. Horizontal mirror
        if self.mirror_enabled:
            frame = cv2.flip(frame, 1)

        # 2. Real-time Auto-Light Boost
        frame = self.auto_light.process(frame)

        # 3. Aspect-ratio locked 1:1 center crop (removes unseen outer pixels before blur)
        square_frame = self.crop_center_square(frame)

        # 4. Offline 3-tier bokeh background blur on 1:1 square
        if self.segmentation.tier != 0:
            square_frame = self.segmentation.process(square_frame)

        return square_frame

    def process_to_qimage(self, frame: np.ndarray) -> QImage:
        """Process frame and convert directly to a QImage suitable for QPainter rendering."""
        processed = self.process(frame)

        # Convert BGR to RGB for Qt rendering
        rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        # Create QImage wrapping numpy buffer
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        return qimg
