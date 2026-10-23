"""Offline 3-tier background blur engine powered by local ONNX segmentation."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "selfie_segmentation.onnx"


class SegmentationBlurEngine:
    """Performs neural background segmentation and multi-tier photographic bokeh blur."""

    TIER_OFF = 0
    TIER_SUBTLE = 1
    TIER_BALANCED = 2
    TIER_HEAVY = 3

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        tier: int = 2,
        intensity: Optional[int] = None,
    ) -> None:
        self.tier = max(0, min(3, int(tier)))
        if intensity is not None:
            self.intensity = max(0, min(100, int(intensity)))
        else:
            tier_to_intensity = {
                self.TIER_OFF: 0,
                self.TIER_SUBTLE: 25,
                self.TIER_BALANCED: 50,
                self.TIER_HEAVY: 85,
            }
            self.intensity = tier_to_intensity.get(self.tier, 50)

        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._session = None
        self._input_name: Optional[str] = None
        self._input_shape: Optional[Tuple[int, ...]] = None
        self._output_name: Optional[str] = None
        self._is_nchw: bool = False

        # Preallocated buffers for zero-allocation in-loop execution
        self._input_tensor_buf = np.empty((1, 256, 256, 3), dtype=np.float32)
        self._input_tensor_nchw_buf = np.empty((1, 3, 256, 256), dtype=np.float32)
        self._fallback_prior_buf = self._create_presenter_prior(256, 256)

        self._mask_u8_buf: Optional[np.ndarray] = None
        self._mask_3ch_buf: Optional[np.ndarray] = None
        self._inv_3ch_buf: Optional[np.ndarray] = None
        self._fg_part_buf: Optional[np.ndarray] = None
        self._bg_part_buf: Optional[np.ndarray] = None
        self._bokeh_small_buf: Optional[np.ndarray] = None
        self._bokeh_blur_buf: Optional[np.ndarray] = None
        self._bokeh_out_buf: Optional[np.ndarray] = None

        self._init_session()

    def _create_presenter_prior(self, h: int = 256, w: int = 256) -> np.ndarray:
        """Create an anatomical head and torso presenter prior mask."""
        mask = np.zeros((h, w), dtype=np.float32)
        cx = w // 2
        cv2.ellipse(mask, (cx, int(h * 0.78)), (int(w * 0.38), int(h * 0.28)), 0, 0, 360, 1.0, -1)
        cv2.circle(mask, (cx, int(h * 0.40)), int(min(h, w) * 0.24), 1.0, -1)
        return cv2.GaussianBlur(mask, (31, 31), 0)

    def _init_session(self) -> None:
        """Initialize local ONNX runtime CPU session."""
        if not self.model_path.exists():
            logger.warning("ONNX model not found at %s. Operating with synthetic fallback mask.", self.model_path)
            return

        try:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )

            input_meta = self._session.get_inputs()[0]
            self._input_name = input_meta.name
            self._input_shape = tuple(input_meta.shape)
            if len(self._input_shape) == 4 and self._input_shape[1] == 3:
                self._is_nchw = True

            self._output_name = self._session.get_outputs()[0].name
            logger.info("ONNX Segmentation session loaded: %s (input: %s, shape: %s)", self.model_path.name, self._input_name, self._input_shape)
        except Exception as e:
            logger.error("Failed to load ONNX model %s: %s. Using synthetic fallback.", self.model_path, e)
            self._session = None

    def set_tier(self, tier: int) -> None:
        """Set the active blur tier (0=Off, 1=Subtle, 2=Balanced, 3=Heavy) and map to discrete intensity."""
        self.tier = max(0, min(3, int(tier)))
        tier_to_intensity = {
            self.TIER_OFF: 0,
            self.TIER_SUBTLE: 25,
            self.TIER_BALANCED: 50,
            self.TIER_HEAVY: 85,
        }
        self.intensity = tier_to_intensity.get(self.tier, 50)

    def set_intensity(self, intensity: int) -> None:
        """Set continuous blur intensity (0-100) and sync active tier."""
        self.intensity = max(0, min(100, int(intensity)))
        if self.intensity == 0:
            self.tier = self.TIER_OFF
        elif self.intensity < 38:
            self.tier = self.TIER_SUBTLE
        elif self.intensity < 68:
            self.tier = self.TIER_BALANCED
        else:
            self.tier = self.TIER_HEAVY

    def cycle_tier(self) -> int:
        """Cycle blur tier: 0 -> 1 -> 2 -> 3 -> 0."""
        self.set_tier((self.tier + 1) % 4)
        return self.tier

    def _validate_and_refine_mask(self, raw_mask: np.ndarray) -> np.ndarray:
        """Validate raw mask against degenerate outputs and apply S-curve smoothstep windowing."""
        if not np.isfinite(raw_mask).all():
            raw_mask = np.nan_to_num(raw_mask, nan=0.0, posinf=1.0, neginf=0.0)

        # Detect unbounded logits
        if raw_mask.min() < 0.0 or raw_mask.max() > 1.0:
            raw_mask = 1.0 / (1.0 + np.exp(-np.clip(raw_mask, -12.0, 12.0)))

        # Degenerate flat mask check (catches invariant/broken models)
        dynamic_range = float(raw_mask.max() - raw_mask.min())
        variance = float(raw_mask.var())
        if dynamic_range < 0.15 or variance < 0.005:
            logger.warning(
                "Degenerate segmentation mask detected (range=%.4f, var=%.6f). "
                "Falling back to anatomical presenter prior.",
                dynamic_range, variance
            )
            return self._fallback_prior_buf.copy()

        # Polarity check: center vs perimeter
        h, w = raw_mask.shape[:2]
        center_val = float(raw_mask[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4].mean())
        border_val = float(
            raw_mask[: h // 8, :].mean() + raw_mask[-h // 8 :, :].mean() +
            raw_mask[:, : w // 8].mean() + raw_mask[:, -w // 8 :].mean()
        ) / 4.0

        if center_val < border_val - 0.20:
            raw_mask = 1.0 - raw_mask

        # S-curve smoothstep windowing [0.30, 0.70] for 100% foreground sharpness
        low, high = 0.30, 0.70
        t = np.clip((raw_mask - low) / (high - low), 0.0, 1.0)
        refined = t * t * (3.0 - 2.0 * t)

        # Anti-aliased Gaussian feathering at 256x256 resolution
        refined = cv2.GaussianBlur(refined, (5, 5), 0)
        return refined

    def _infer_mask(self, bgr_frame: np.ndarray) -> np.ndarray:
        """Run ONNX segmentation model to produce validated 256x256 float32 person probability mask."""
        if self._session is None:
            return self._fallback_prior_buf.copy()

        # In-place normalized resize directly into input buffer (converting 256x256 BGR->RGB)
        resized_bgr = cv2.resize(bgr_frame, (256, 256), interpolation=cv2.INTER_LINEAR)
        rgb_256 = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
        np.multiply(rgb_256, 1.0 / 255.0, out=self._input_tensor_buf[0], dtype=np.float32)

        if self._is_nchw:
            self._input_tensor_nchw_buf[0] = self._input_tensor_buf[0].transpose(2, 0, 1)
            tensor_in = self._input_tensor_nchw_buf
        else:
            tensor_in = self._input_tensor_buf

        outputs = self._session.run([self._output_name], {self._input_name: tensor_in})
        raw_mask = outputs[0]

        if raw_mask.ndim == 4:
            if raw_mask.shape[1] == 1:
                mask = raw_mask[0, 0, :, :]
            elif raw_mask.shape[1] == 2:
                mask = raw_mask[0, 1, :, :]
            elif raw_mask.shape[-1] == 1:
                mask = raw_mask[0, :, :, 0]
            elif raw_mask.shape[-1] == 2:
                mask = raw_mask[0, :, :, 1]
            else:
                mask = np.squeeze(raw_mask)
        else:
            mask = np.squeeze(raw_mask)

        return self._validate_and_refine_mask(mask.astype(np.float32))

    def _render_bokeh(self, frame: np.ndarray) -> np.ndarray:
        """Generate photographic bokeh blurred background using downscale-blur-upscale with preallocated buffers."""
        h, w = frame.shape[:2]

        if self.intensity == 25:
            scale = 2
            ksize = (15, 15)
        elif self.intensity == 50:
            scale = 4
            ksize = (21, 21)
        elif self.intensity == 85:
            scale = 4
            ksize = (35, 35)
        else:
            scale = 2 if self.intensity <= 35 else 4
            k = max(3, int(self.intensity * 0.35) * 2 + 1)
            ksize = (k, k)

        down_w, down_h = max(1, w // scale), max(1, h // scale)

        if self._bokeh_small_buf is None or self._bokeh_small_buf.shape != (down_h, down_w, 3):
            self._bokeh_small_buf = np.empty((down_h, down_w, 3), dtype=np.uint8)
            self._bokeh_blur_buf = np.empty((down_h, down_w, 3), dtype=np.uint8)
            self._bokeh_out_buf = np.empty((h, w, 3), dtype=np.uint8)

        cv2.resize(frame, (down_w, down_h), dst=self._bokeh_small_buf, interpolation=cv2.INTER_LINEAR)
        cv2.GaussianBlur(self._bokeh_small_buf, ksize, 0, dst=self._bokeh_blur_buf)
        cv2.resize(self._bokeh_blur_buf, (w, h), dst=self._bokeh_out_buf, interpolation=cv2.INTER_LINEAR)
        return self._bokeh_out_buf

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply 3-tier background blur with soft feathering and fast difference alpha blending."""
        if self.tier == self.TIER_OFF or self.intensity == 0:
            return frame

        h, w = frame.shape[:2]

        # 1. Run inference directly on BGR frame to get validated 256x256 probability mask
        mask_256 = self._infer_mask(frame)

        # 2. Upscale mask to target frame resolution
        mask = cv2.resize(mask_256, (w, h), interpolation=cv2.INTER_LINEAR)

        # 3. Generate photographic bokeh background plate
        blurred_bg = self._render_bokeh(frame)

        # 4. Fast zero-allocation uint8 alpha blending
        if self._mask_u8_buf is None or self._mask_u8_buf.shape != (h, w):
            self._mask_u8_buf = np.empty((h, w), dtype=np.uint8)
            self._mask_3ch_buf = np.empty((h, w, 3), dtype=np.uint8)
            self._inv_3ch_buf = np.empty((h, w, 3), dtype=np.uint8)
            self._fg_part_buf = np.empty((h, w, 3), dtype=np.uint8)
            self._bg_part_buf = np.empty((h, w, 3), dtype=np.uint8)

        cv2.convertScaleAbs(mask, self._mask_u8_buf, alpha=255.0)
        cv2.merge([self._mask_u8_buf, self._mask_u8_buf, self._mask_u8_buf], dst=self._mask_3ch_buf)
        cv2.bitwise_not(self._mask_3ch_buf, dst=self._inv_3ch_buf)

        cv2.multiply(frame, self._mask_3ch_buf, self._fg_part_buf, scale=1.0 / 255.0)
        cv2.multiply(blurred_bg, self._inv_3ch_buf, self._bg_part_buf, scale=1.0 / 255.0)
        cv2.add(self._fg_part_buf, self._bg_part_buf, dst=self._fg_part_buf)
        return self._fg_part_buf.copy()
