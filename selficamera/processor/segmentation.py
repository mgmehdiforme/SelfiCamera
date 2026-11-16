"""Person segmentation with pluggable offline backends.

Backends, in order of preference:

1. **LiteRT / TFLite** (``ai-edge-litert`` or ``tflite-runtime``) for ``*.tflite`` models,
   e.g. Google MediaPipe *Selfie Segmenter* (Apache-2.0).
2. **ONNX Runtime** for ``*.onnx`` models with an NHWC float input and a single-channel
   probability (or logit) output.
3. **Basic** — a static head-and-shoulders prior. Used only when no trained model is
   installed; the UI labels this mode so users know edges will not be accurate.

Models are discovered in ``$SELFICAMERA_MODEL``, the package ``models/`` directory and
``~/.local/share/selficamera/models/``. Nothing is ever downloaded at runtime.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

PACKAGE_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_FILENAMES = ("selfie_segmenter.tflite", "selfie_segmenter.onnx", "selfie_multiclass_256x256.tflite")


def user_model_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "selficamera" / "models"


def discover_model() -> Optional[Path]:
    env = os.environ.get("SELFICAMERA_MODEL")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
        logger.warning("SELFICAMERA_MODEL=%s does not exist", env)
    for directory in (PACKAGE_MODEL_DIR, user_model_dir()):
        for name in MODEL_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def create_presenter_prior(h: int, w: int) -> np.ndarray:
    """Soft head-and-shoulders silhouette used by the basic fallback."""
    mask = np.zeros((h, w), dtype=np.float32)
    cx = w // 2
    cv2.ellipse(mask, (cx, int(h * 0.92)), (int(w * 0.40), int(h * 0.36)), 0, 0, 360, 1.0, -1)
    cv2.ellipse(mask, (cx, int(h * 0.42)), (int(w * 0.20), int(h * 0.25)), 0, 0, 360, 1.0, -1)
    k = max(3, (min(h, w) // 12) | 1)
    return np.clip(cv2.GaussianBlur(mask, (k, k), 0), 0.0, 1.0)


class _Backend:
    name = "basic"
    input_hw: Tuple[int, int] = (256, 256)

    def run(self, rgb01: np.ndarray) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class _LiteRTBackend(_Backend):
    name = "litert"

    def __init__(self, path: Path, threads: int = 2) -> None:
        try:
            from ai_edge_litert.interpreter import Interpreter  # type: ignore
        except ImportError:
            from tflite_runtime.interpreter import Interpreter  # type: ignore
        self._interp = Interpreter(model_path=str(path), num_threads=threads)
        self._interp.allocate_tensors()
        inp = self._interp.get_input_details()[0]
        out = self._interp.get_output_details()[0]
        self._in_index = inp["index"]
        self._out_index = out["index"]
        self._out_shape = tuple(out["shape"])
        shape = inp["shape"]
        self.input_hw = (int(shape[1]), int(shape[2]))

    def run(self, rgb01: np.ndarray) -> np.ndarray:
        self._interp.set_tensor(self._in_index, rgb01[None, ...])
        self._interp.invoke()
        return np.asarray(self._interp.get_tensor(self._out_index))


class _OnnxBackend(_Backend):
    name = "onnx"

    def __init__(self, path: Path, threads: int = 2) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.log_severity_level = 3
        self._sess = ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])
        meta = self._sess.get_inputs()[0]
        self._in_name = meta.name
        shape = [d if isinstance(d, int) else -1 for d in meta.shape]
        self._nchw = len(shape) == 4 and shape[1] == 3
        if self._nchw:
            self.input_hw = (shape[2] if shape[2] > 0 else 256, shape[3] if shape[3] > 0 else 256)
        else:
            self.input_hw = (shape[1] if shape[1] > 0 else 256, shape[2] if shape[2] > 0 else 256)
        self._out_name = self._sess.get_outputs()[0].name

    def run(self, rgb01: np.ndarray) -> np.ndarray:
        x = rgb01.transpose(2, 0, 1)[None, ...] if self._nchw else rgb01[None, ...]
        return np.asarray(self._sess.run([self._out_name], {self._in_name: np.ascontiguousarray(x)})[0])


def _to_single_channel(raw: np.ndarray) -> np.ndarray:
    a = np.asarray(raw, dtype=np.float32)
    a = np.squeeze(a)
    if a.ndim == 3:
        # Multi-class output (e.g. background/person or MediaPipe multiclass): channel 0 is background.
        if a.shape[-1] <= 8:
            a = 1.0 - a[..., 0]
        elif a.shape[0] <= 8:
            a = 1.0 - a[0]
    if not np.isfinite(a).all():
        a = np.nan_to_num(a, nan=0.0, posinf=1.0, neginf=0.0)
    if a.min() < -0.01 or a.max() > 1.01:
        a = 1.0 / (1.0 + np.exp(-np.clip(a, -16.0, 16.0)))
    return a.astype(np.float32)


class SegmentationEngine:
    """Produces smooth person masks at any output size."""

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        threads: int = 2,
        temporal_smoothing: float = 0.55,
        infer_every: int = 2,
    ) -> None:
        self.temporal_smoothing = temporal_smoothing
        # Run the model on every Nth frame and reuse the smoothed mask in between:
        # halves AI CPU cost at 30 fps with no visible lag.
        self.infer_every = max(1, int(infer_every))
        self._mask_calls = 0
        self._backend: Optional[_Backend] = None
        self.model_path: Optional[Path] = None
        self._prev_mask: Optional[np.ndarray] = None
        self._prior_cache: dict = {}

        path = Path(model_path) if model_path else discover_model()
        if path is not None:
            self._load(path, threads)
        if self._backend is None:
            logger.warning(
                "No trained segmentation model found. Background effects use the basic "
                "center prior. Run 'selficamera --install-model' or see README."
            )

    def _load(self, path: Path, threads: int) -> None:
        try:
            if path.suffix == ".tflite":
                self._backend = _LiteRTBackend(path, threads)
            else:
                self._backend = _OnnxBackend(path, threads)
            self.model_path = path
            logger.info("Segmentation model loaded: %s (%s, input %s)", path.name, self._backend.name, self._backend.input_hw)
        except Exception as exc:
            logger.error("Could not load segmentation model %s: %s", path, exc)
            self._backend = None

    @property
    def backend_name(self) -> str:
        return self._backend.name if self._backend else "basic"

    @property
    def is_neural(self) -> bool:
        return self._backend is not None

    @property
    def model_name(self) -> str:
        return self.model_path.name if (self._backend and self.model_path) else "Basic (no AI model installed)"

    def reset(self) -> None:
        self._prev_mask = None

    def _prior(self, h: int, w: int) -> np.ndarray:
        key = (h, w)
        if key not in self._prior_cache:
            self._prior_cache = {key: create_presenter_prior(h, w)}
        return self._prior_cache[key]

    def infer_raw(self, bgr: np.ndarray) -> np.ndarray:
        """Return the model-resolution mask in [0, 1] (no temporal smoothing)."""
        if self._backend is None:
            h, w = self._backend_hw()
            return self._prior(h, w)
        ih, iw = self._backend.input_hw
        rgb = cv2.cvtColor(cv2.resize(bgr, (iw, ih), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        rgb01 = rgb.astype(np.float32) * (1.0 / 255.0)
        try:
            return _to_single_channel(self._backend.run(rgb01))
        except Exception as exc:
            logger.error("Segmentation inference failed (%s); switching to basic mode.", exc)
            self._backend = None
            return self._prior(ih, iw)

    def _backend_hw(self) -> Tuple[int, int]:
        return self._backend.input_hw if self._backend else (256, 256)

    def mask(self, bgr: np.ndarray, out_w: int, out_h: int, smooth: bool = True) -> np.ndarray:
        """Return a refined float32 (out_h, out_w) mask in [0, 1]."""
        self._mask_calls += 1
        reuse = (
            smooth
            and self.is_neural
            and self._prev_mask is not None
            and self._mask_calls % self.infer_every != 0
        )
        if reuse:
            mask = cv2.resize(self._prev_mask, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
            k = max(3, (min(out_w, out_h) // 90) | 1)
            return cv2.GaussianBlur(mask, (k, k), 0)
        raw = self.infer_raw(bgr)
        if self.is_neural:
            # Sharpen the transition band, keep a soft anti-aliased edge.
            t = np.clip((raw - 0.3) / 0.4, 0.0, 1.0)
            raw = t * t * (3.0 - 2.0 * t)
        if smooth and self.is_neural:
            if self._prev_mask is not None and self._prev_mask.shape == raw.shape:
                a = self.temporal_smoothing
                raw = a * raw + (1.0 - a) * self._prev_mask
            self._prev_mask = raw
        mask = cv2.resize(raw, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        k = max(3, (min(out_w, out_h) // 90) | 1)
        return cv2.GaussianBlur(mask, (k, k), 0)


def list_model_candidates() -> List[Path]:
    """All model files the engine would consider (for diagnostics)."""
    out: List[Path] = []
    for directory in (PACKAGE_MODEL_DIR, user_model_dir()):
        for name in MODEL_FILENAMES:
            if (directory / name).is_file():
                out.append(directory / name)
    return out
