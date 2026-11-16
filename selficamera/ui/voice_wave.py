"""Voice wave: a sound-reactive wave ring around the camera bubble.

While you talk, layered waves flow around the edge of the shape and grow with your
voice, and each new phrase sends a ripple outward. When you're quiet nothing is
drawn, so recordings stay clean.

The geometry is cached per shape/size; each frame only offsets the cached outline
along its normals, so painting stays cheap at 60 fps.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF

from selficamera.ui.shapes import shape_path

SAMPLES = 192
RIPPLE_SECONDS = 1.1
# (lobe multiplier, speed, phase offset, amplitude share, fill alpha)
LAYERS = (
    (1.0, 1.0, 0.0, 1.00, 60),
    (1.6, -1.3, 2.1, 0.70, 80),
    (2.3, 0.8, 4.2, 0.45, 105),
)


class VoiceWave:
    """Animation state and painter for the voice wave."""

    def __init__(self) -> None:
        self.level = 0.0  # displayed (smoothed) loudness 0..1
        self._target = 0.0
        self._slow = 0.0  # slow loudness average, for onset detection
        self._phase = 0.0
        self._since_ripple = 10.0
        self.ripples: List[List[float]] = []  # [age 0..1, strength]
        self._geom_key: Optional[Tuple] = None
        self._pts: Optional[np.ndarray] = None
        self._normals: Optional[np.ndarray] = None
        self._s: Optional[np.ndarray] = None
        self._lobes = 6

    # ------------------------------------------------------------- animation
    def set_energy(self, energy: float) -> None:
        self._target = max(0.0, min(1.0, float(energy)))

    @property
    def active(self) -> bool:
        return self.level > 0.01 or self._target > 0.02 or bool(self.ripples)

    def tick(self, dt: float) -> bool:
        """Advance the animation by ``dt`` seconds. Returns True while anything is visible."""
        dt = max(0.0, min(0.1, dt))
        # Fast attack, slower release, so the wave breathes with speech.
        rate = 18.0 if self._target > self.level else 5.0
        self.level += (self._target - self.level) * min(1.0, rate * dt)
        if self.level < 0.004 and self._target == 0.0:
            self.level = 0.0
        self._phase = (self._phase + dt * (1.4 + 4.0 * self.level)) % (2.0 * math.pi * 64)

        # A new phrase or a stressed syllable sends a ripple outward.
        self._since_ripple += dt
        if self._target - self._slow > 0.14 and self._target > 0.25 and self._since_ripple > 0.32:
            self.ripples.append([0.0, min(1.0, 0.5 + self._target)])
            self._since_ripple = 0.0
        self._slow += (self._target - self._slow) * min(1.0, 2.5 * dt)
        for r in self.ripples:
            r[0] += dt / RIPPLE_SECONDS
        self.ripples = [r for r in self.ripples if r[0] < 1.0][-4:]
        return self.active

    # -------------------------------------------------------------- geometry
    def _geometry(self, shape: str, rect: QRectF) -> None:
        key = (shape, round(rect.x(), 1), round(rect.y(), 1), round(rect.width(), 1), round(rect.height(), 1))
        if key == self._geom_key:
            return
        path = shape_path(shape, rect)
        s = np.arange(SAMPLES, dtype=np.float64) / SAMPLES
        pts = np.array([[path.pointAtPercent(t).x(), path.pointAtPercent(t).y()] for t in s])
        tangent = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
        normals = np.stack([tangent[:, 1], -tangent[:, 0]], axis=1)
        normals /= np.maximum(1e-6, np.linalg.norm(normals, axis=1, keepdims=True))
        center = np.array([rect.center().x(), rect.center().y()])
        outward = np.sign(np.sum(normals * (pts - center), axis=1, keepdims=True))
        outward[outward == 0] = 1.0
        self._pts, self._normals, self._s = pts, normals * outward, s
        perimeter = float(path.length())
        self._lobes = max(3, int(round(perimeter / 95.0)))
        self._geom_key = key

    def outline(self, shape: str, rect: QRectF, offsets: np.ndarray) -> QPolygonF:
        self._geometry(shape, rect)
        assert self._pts is not None and self._normals is not None
        p = self._pts + self._normals * offsets[:, None]
        return QPolygonF([QPointF(float(x), float(y)) for x, y in p])

    def layer_offsets(self, shape: str, rect: QRectF, base: float, amp: float, layer: int) -> np.ndarray:
        self._geometry(shape, rect)
        assert self._s is not None
        mult, speed, phase0, share, _alpha = LAYERS[layer]
        n = max(2, int(round(self._lobes * mult)))
        ph = self._phase * speed + phase0
        two_pi_s = 2.0 * math.pi * self._s
        # Two waves with different lobe counts travel in opposite directions; their sum
        # keeps the motion organic without a low harmonic that would square the circle.
        wave = 0.62 * (0.5 + 0.5 * np.sin(n * two_pi_s + ph)) + 0.38 * (0.5 + 0.5 * np.sin((n + 3) * two_pi_s - 1.7 * ph + phase0))
        return base + amp * share * self.level * wave

    # ----------------------------------------------------------------- paint
    def paint(self, p: QPainter, shape: str, rect: QRectF, color: QColor, base: float, max_amp: float, canvas: QRectF) -> None:
        if not self.active:
            return
        self._geometry(shape, rect)
        p.save()
        # Only paint outside the video: the wave never covers your face.
        outside = QPainterPath()
        outside.addRect(canvas)
        outside = outside.subtracted(shape_path(shape, rect))
        p.setClipPath(outside)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.level > 0.01:
            for i in range(len(LAYERS)):
                offs = self.layer_offsets(shape, rect, base, max_amp, i)
                c = QColor(color)
                c.setAlpha(int(LAYERS[i][4] * min(1.0, 0.35 + self.level)))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c)
                p.drawPolygon(self.outline(shape, rect, offs))
            # Crisp crest line on the outer wave.
            crest = QColor(color)
            crest.setAlpha(int(200 * min(1.0, 0.3 + self.level)))
            pen = QPen(crest, 1.6)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(self.outline(shape, rect, self.layer_offsets(shape, rect, base, max_amp, 0)))

        for age, strength in self.ripples:
            ease = 1.0 - (1.0 - age) ** 3
            offs = np.full(SAMPLES, base + ease * (max_amp + 2.0))
            c = QColor(color)
            c.setAlpha(int(170 * strength * (1.0 - age) ** 2))
            pen = QPen(c, 2.2 * (1.0 - age) + 0.6)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(self.outline(shape, rect, offs))
        p.restore()
