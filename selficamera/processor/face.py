"""Lightweight face detection for face-based auto light (OpenCV YuNet).

YuNet (MIT license, ~230 KB ONNX) runs inside OpenCV's own DNN module, so it
needs no extra runtime. Detection takes a few milliseconds on a laptop CPU and the
pipeline only calls it every few frames.

The model is discovered next to the segmentation model; nothing is downloaded at
runtime (``selficamera --install-model`` fetches it once).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from selficamera.processor.segmentation import PACKAGE_MODEL_DIR, user_model_dir

logger = logging.getLogger(__name__)

FACE_MODEL_FILENAME = "face_detection_yunet_2023mar.onnx"
DETECT_SIDE = 160  # short side the detector sees; a bubble face is large, so this is plenty

Box = Tuple[int, int, int, int, float]  # x, y, w, h, score


def discover_face_model() -> Optional[Path]:
    env = os.environ.get("SELFICAMERA_FACE_MODEL")
    if env and Path(env).expanduser().is_file():
        return Path(env).expanduser()
    for directory in (PACKAGE_MODEL_DIR, user_model_dir()):
        candidate = directory / FACE_MODEL_FILENAME
        if candidate.is_file():
            return candidate
    return None


class FaceDetector:
    """Finds faces in BGR frames. ``available`` is False when no model is installed."""

    def __init__(self, model_path: Optional[str | Path] = None, score_threshold: float = 0.6) -> None:
        self.model_path: Optional[Path] = None
        self._det = None
        self._input: Tuple[int, int] = (0, 0)
        path = Path(model_path) if model_path else discover_face_model()
        if path is None or not hasattr(cv2, "FaceDetectorYN"):
            return
        try:
            self._det = cv2.FaceDetectorYN.create(str(path), "", (320, 320), score_threshold, 0.3, 50)
            self.model_path = path
            logger.info("Face model loaded: %s (auto light meters on your face)", path.name)
        except cv2.error as exc:
            logger.error("Could not load face model %s: %s", path, exc)
            self._det = None

    @property
    def available(self) -> bool:
        return self._det is not None

    def detect(self, bgr: np.ndarray) -> List[Box]:
        """Return faces in ``bgr`` coordinates, largest first."""
        if self._det is None or bgr is None or bgr.size == 0:
            return []
        h, w = bgr.shape[:2]
        scale = DETECT_SIDE / max(1, min(h, w))
        if abs(scale - 1.0) < 0.05:
            scale = 1.0
        img = bgr if scale == 1.0 else cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
        ih, iw = img.shape[:2]
        if (iw, ih) != self._input:
            self._det.setInputSize((iw, ih))
            self._input = (iw, ih)
        try:
            _, faces = self._det.detect(img)
        except cv2.error as exc:
            logger.error("Face detection failed (%s); auto light falls back to the person mask.", exc)
            self._det = None
            return []
        if faces is None:
            return []
        out: List[Box] = []
        for f in faces:
            x, y, fw, fh = (float(v) / scale for v in f[:4])
            x0, y0 = max(0, int(x)), max(0, int(y))
            x1, y1 = min(w, int(x + fw)), min(h, int(y + fh))
            if x1 - x0 >= 4 and y1 - y0 >= 4:
                out.append((x0, y0, x1 - x0, y1 - y0, float(f[-1])))
        out.sort(key=lambda b: b[2] * b[3], reverse=True)
        return out
