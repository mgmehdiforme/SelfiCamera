"""Frame pipeline: mirror -> framing crop -> resize to display -> light & color -> background.

The processor is called from the capture thread. Settings are changed from the GUI
thread through :meth:`FrameProcessor.configure`, which is lock-protected and applied
atomically between frames.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from selficamera.processor.background import BackgroundCompositor
from selficamera.processor.enhance import TemporalDenoiser, sharpen, soft_skin
from selficamera.processor.face import Box, FaceDetector
from selficamera.processor.framing import AutoFramer, CropRect, compute_crop
from selficamera.processor.lighting import ImageAdjuster, Meter
from selficamera.processor.segmentation import SegmentationEngine

logger = logging.getLogger(__name__)

MAX_OUTPUT_SIDE = 1280
AUTOFRAME_EVERY_N = 4
METER_EVERY_N = 4  # face detection (auto light, soft skin) runs on every 4th frame (~7.5 Hz)
FACE_HOLD_FRAMES = 8  # keep using the last face for ~1 s if it is briefly lost

PROCESSOR_KEYS = (
    "mirror",
    "zoom",
    "pan_x",
    "pan_y",
    "auto_frame",
    "auto_light",
    "brightness",
    "contrast",
    "saturation",
    "warmth",
    "background_mode",
    "blur_strength",
    "background_color",
    "background_image",
    "denoise",
    "soft_skin",
    "sharpen",
)


class FrameProcessor:
    """Stateful per-frame processor."""

    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None,
        output_size: Tuple[int, int] = (260, 260),
        segmentation: Optional[SegmentationEngine] = None,
        model_path: Optional[str] = None,
        face_detector: Optional[FaceDetector] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.mirror = True
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.auto_frame = False
        self.background_mode = "none"
        self.blur_strength = 60
        self.background_color = "#00B140"
        self.background_image = ""
        self.denoise = 0
        self.soft_skin = 0
        self.sharpen = 0

        self.adjuster = ImageAdjuster()
        self.segmentation = segmentation or SegmentationEngine(model_path=model_path)
        self.compositor = BackgroundCompositor()
        self.framer = AutoFramer()
        self.face = face_detector if face_detector is not None else FaceDetector()
        self.denoiser = TemporalDenoiser()
        self._meter: Optional[Meter] = None
        self._faces: List[Box] = []
        self._faces_checked = False
        self._face_misses = 0
        self._last_mask: Optional[np.ndarray] = None
        self._output_size = self._sanitize_size(output_size)
        self._frame_index = 0
        self.last_timings: Dict[str, float] = {}
        if settings:
            self.configure(**{k: v for k, v in settings.items() if k in PROCESSOR_KEYS})

    # ---------------------------------------------------------------- settings
    @staticmethod
    def _sanitize_size(size: Tuple[int, int]) -> Tuple[int, int]:
        w, h = int(size[0]), int(size[1])
        w, h = max(16, w), max(16, h)
        longest = max(w, h)
        if longest > MAX_OUTPUT_SIDE:
            s = MAX_OUTPUT_SIDE / longest
            w, h = int(w * s), int(h * s)
        return (w, h)

    @property
    def output_size(self) -> Tuple[int, int]:
        return self._output_size

    def set_output_size(self, width: int, height: int) -> None:
        with self._lock:
            new = self._sanitize_size((width, height))
            if new != self._output_size:
                self._output_size = new
                self.segmentation.reset()
                self._meter = None
                self._faces = []
                self._faces_checked = False
                self._last_mask = None
                self.denoiser.reset()

    def configure(self, **settings: Any) -> None:
        with self._lock:
            for key, value in settings.items():
                if key not in PROCESSOR_KEYS:
                    continue
                if key in ("auto_light", "brightness", "contrast", "saturation", "warmth"):
                    setattr(self.adjuster, key, value)
                elif key == "background_image":
                    self.background_image = value or ""
                    self.compositor.set_image(self.background_image)
                elif key == "auto_frame":
                    self.auto_frame = bool(value)
                    if not value:
                        self.framer.reset()
                else:
                    setattr(self, key, value)

    @property
    def needs_mask(self) -> bool:
        return self.background_mode != "none"

    # -------------------------------------------------------------- processing
    def crop_rect(self, frame_w: int, frame_h: int) -> CropRect:
        """Crop rectangle in *source* (unmirrored) frame coordinates.

        Pan is expressed in what the viewer sees, so it is flipped when mirroring.
        The auto-frame focus is tracked in source coordinates.
        """
        ow, oh = self._output_size
        pan_x = -self.pan_x if self.mirror else self.pan_x
        return compute_crop(
            frame_w,
            frame_h,
            ow / oh,
            zoom=self.zoom,
            pan_x=pan_x,
            pan_y=self.pan_y,
            focus=self.framer.focus if self.auto_frame else None,
        )

    def _update_autoframe(self, frame: np.ndarray) -> None:
        if not self.auto_frame or not self.segmentation.is_neural:
            return
        if self._frame_index % AUTOFRAME_EVERY_N != 0:
            return
        h, w = frame.shape[:2]
        # Letterbox to a square so the model sees undistorted proportions.
        side = max(h, w)
        square = np.zeros((side, side, 3), dtype=np.uint8)
        y0, x0 = (side - h) // 2, (side - w) // 2
        square[y0 : y0 + h, x0 : x0 + w] = frame
        raw = self.segmentation.infer_raw(square)
        mh, mw = raw.shape[:2]
        sy0, sx0 = int(y0 / side * mh), int(x0 / side * mw)
        sy1, sx1 = int((y0 + h) / side * mh), int((x0 + w) / side * mw)
        mask = raw[sy0:sy1, sx0:sx1]
        crop = compute_crop(w, h, self._output_size[0] / self._output_size[1], zoom=self.zoom)
        self.framer.update(mask, w, h, crop.h)

    @property
    def auto_light_source(self) -> str:
        """What auto light can meter on: 'face', 'person' or 'center'."""
        if self.face.available:
            return "face"
        return "person" if self.segmentation.is_neural else "center"

    @property
    def needs_faces(self) -> bool:
        return self.face.available and (self.adjuster.auto_light or self.soft_skin > 0)

    def _update_faces(self, out: np.ndarray) -> None:
        """Track faces for auto light and soft skin (throttled; holds briefly when lost)."""
        if not self.needs_faces:
            self._faces, self._faces_checked = [], False
            return
        # Offset by one so face detection never lands on a frame where the background
        # model runs (it infers on even frames) and the two costs never stack.
        if self._frame_index % METER_EVERY_N != 1 and self._faces_checked:
            return
        self._faces_checked = True
        boxes = self.face.detect(out)
        if boxes:
            self._faces, self._face_misses = boxes, 0
        else:
            self._face_misses += 1
            if self._face_misses > FACE_HOLD_FRAMES:
                self._faces = []

    def _update_meter(self, out: np.ndarray) -> None:
        """Decide what auto light meters on (runs before light & color are applied)."""
        if self._faces:
            self._meter = ("face", self._faces)
            return
        if self.face.available and self._meter is not None and self._meter[0] == "face" and self._face_misses <= FACE_HOLD_FRAMES:
            return
        if self.segmentation.is_neural:
            if self.needs_mask and self._last_mask is not None:
                self._meter = ("person", self._last_mask)
            elif self._frame_index % (2 * METER_EVERY_N) == 0 or self._meter is None or self._meter[0] != "person":
                self._meter = ("person", self.segmentation.infer_raw(out))
            return
        self._meter = None

    @property
    def enhance_status(self) -> Dict[str, Any]:
        return {
            "faces": len(self._faces),
        }

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Return BGR (opaque) or BGRA (background removed) at output size."""
        if frame is None or frame.size == 0:
            return frame
        with self._lock:
            t0 = time.perf_counter()
            self._frame_index += 1
            if frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            self._update_autoframe(frame)
            fh, fw = frame.shape[:2]
            r = self.crop_rect(fw, fh)
            crop = frame[r.y : r.y + r.h, r.x : r.x + r.w]
            ow, oh = self._output_size
            # Halve with a Gaussian pyramid (cheap, alias-free) before the final linear resize.
            while crop.shape[1] >= 2 * ow and crop.shape[0] >= 2 * oh:
                crop = cv2.pyrDown(crop)
            out = cv2.resize(crop, (ow, oh), interpolation=cv2.INTER_LINEAR)
            if self.mirror:
                # Mirror the small output instead of the full camera frame.
                out = cv2.flip(out, 1)
            t1 = time.perf_counter()

            # Enhance, in an order that keeps each step honest: denoise first (so nothing
            # amplifies grain), then light & color, then face touch-up, sharpening last.
            out = self.denoiser.process(out, self.denoise)
            self._update_faces(out)
            if self.adjuster.auto_light:
                self._update_meter(out)
            out = self.adjuster.process(out, self._meter if self.adjuster.auto_light else None)
            out = soft_skin(out, self._faces, self.soft_skin)
            out = sharpen(out, self.sharpen)
            t2 = time.perf_counter()

            if self.needs_mask:
                mask = self.segmentation.mask(out, ow, oh)
                self._last_mask = mask
                out = self.compositor.composite(out, mask, self.background_mode, self.blur_strength, self.background_color)
            t3 = time.perf_counter()
            self.last_timings = {
                "crop_ms": (t1 - t0) * 1000,
                "adjust_ms": (t2 - t1) * 1000,  # enhance + light & color
                "background_ms": (t3 - t2) * 1000,
                "total_ms": (t3 - t0) * 1000,
            }
            return out


def to_qimage(processed: np.ndarray):
    """Convert a processed BGR/BGRA frame to a detached QImage."""
    from PySide6.QtGui import QImage

    h, w = processed.shape[:2]
    if processed.ndim == 3 and processed.shape[2] == 4:
        rgba = cv2.cvtColor(processed, cv2.COLOR_BGRA2RGBA)
        return QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
    rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
