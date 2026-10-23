"""Voice Aura ring visual renderer reacting to microphone speech energy."""

from __future__ import annotations

import math
from typing import Tuple
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient


class VoiceAuraRing:
    """Calculates colors, stroke widths, and paints dynamic glowing border rings."""

    def __init__(self, shadow_margin: int = 16) -> None:
        self.shadow_margin = shadow_margin

    @staticmethod
    def calculate_pen_width(energy: float) -> float:
        """Dynamic stroke width: 2.5px up to 7.0px based on vocal energy."""
        clamped = max(0.0, min(1.0, energy))
        return 2.5 + 4.5 * clamped

    @staticmethod
    def calculate_color(energy: float) -> QColor:
        """Calculate reactive color and alpha: cyan -> blue -> magenta/emerald."""
        clamped = max(0.0, min(1.0, energy))

        if clamped <= 0.05:
            # Ambient silence: subtle cyan with 20% alpha
            return QColor(0, 229, 255, 51)
        elif clamped <= 0.75:
            # Active speech: neon cyan/blue with 85% alpha
            t = (clamped - 0.05) / 0.70
            r = int(0 * (1 - t) + 0 * t)
            g = int(229 * (1 - t) + 176 * t)
            b = 255
            alpha = int(51 + (217 - 51) * t)
            return QColor(r, g, b, alpha)
        else:
            # High vocal energy peak: electric magenta
            t = (clamped - 0.75) / 0.25
            r = int(0 * (1 - t) + 213 * t)
            g = int(176 * (1 - t) + 0 * t)
            b = int(255 * (1 - t) + 249 * t)
            return QColor(r, g, b, 255)

    def draw_drop_shadow(self, painter: QPainter, center: QPointF, radius: float) -> None:
        """Render soft Gaussian radial drop shadow fading from circle border to margin edge."""
        outer_radius = radius + self.shadow_margin
        gradient = QRadialGradient(center, outer_radius)

        # Inner edge of shadow (at circle boundary)
        stop_inner = radius / outer_radius
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(max(0.0, stop_inner - 0.02), QColor(0, 0, 0, 0))
        gradient.setColorAt(stop_inner, QColor(0, 0, 0, 95))  # ~38% opacity
        gradient.setColorAt(min(1.0, stop_inner + (1.0 - stop_inner) * 0.5), QColor(0, 0, 0, 35))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(center, outer_radius, outer_radius)
        painter.restore()

    def draw_aura(self, painter: QPainter, center: QPointF, radius: float, energy: float, is_ghost_mode: bool = False) -> None:
        """Draw dynamic glowing voice aura ring."""
        pen_width = self.calculate_pen_width(energy)
        color = self.calculate_color(energy)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # If ghost mode is active, use dotted style with amber accent
        if is_ghost_mode:
            pen = QPen(QColor(255, 179, 0, 200), pen_width, Qt.PenStyle.DashDotLine)
        else:
            pen = QPen(color, pen_width, Qt.PenStyle.SolidLine)

        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)

        # Subtle 1px crisp inner stroke separating video feed
        inner_pen = QPen(QColor(255, 255, 255, 56), 1.0, Qt.PenStyle.SolidLine)
        painter.setPen(inner_pen)
        painter.drawEllipse(center, radius - 1.0, radius - 1.0)

        painter.restore()
