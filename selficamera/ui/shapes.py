"""Bubble shape geometry shared by the overlay, processor sizing and tests."""

from __future__ import annotations

import math
from typing import Tuple

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath

ASPECTS = {
    "circle": 1.0,
    "rounded": 1.0,
    "landscape": 16.0 / 9.0,
    "portrait": 9.0 / 16.0,
}


def content_size(shape: str, size: int) -> Tuple[int, int]:
    """Content (video) size in logical pixels; ``size`` is the short side."""
    aspect = ASPECTS.get(shape, 1.0)
    if aspect >= 1.0:
        return (int(round(size * aspect)), int(size))
    return (int(size), int(round(size / aspect)))


def corner_radius(shape: str, w: float, h: float) -> float:
    short = min(w, h)
    if shape == "circle":
        return short / 2.0
    if shape == "rounded":
        return short * 0.2
    return short * 0.09


def shape_path(shape: str, rect: QRectF) -> QPainterPath:
    path = QPainterPath()
    if shape == "circle":
        path.addEllipse(rect)
    else:
        r = corner_radius(shape, rect.width(), rect.height())
        path.addRoundedRect(rect, r, r)
    return path


def normalized_distance(shape: str, rect: QRectF, point: QPointF) -> float:
    """~1.0 on the shape edge, < 1 inside, > 1 outside (used for edge-resize)."""
    cx, cy = rect.center().x(), rect.center().y()
    dx, dy = point.x() - cx, point.y() - cy
    hw, hh = rect.width() / 2.0, rect.height() / 2.0
    if shape == "circle":
        return math.hypot(dx, dy) / max(1.0, hw)
    return max(abs(dx) / max(1.0, hw), abs(dy) / max(1.0, hh))


def edge_distance_px(shape: str, rect: QRectF, point: QPointF) -> float:
    """Approximate signed pixel distance from the edge (negative = inside)."""
    nd = normalized_distance(shape, rect, point)
    hw, hh = rect.width() / 2.0, rect.height() / 2.0
    if shape == "circle":
        return (nd - 1.0) * hw
    cx, cy = rect.center().x(), rect.center().y()
    dx, dy = abs(point.x() - cx), abs(point.y() - cy)
    return max(dx - hw, dy - hh)
