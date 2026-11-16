"""Small vector icon set (original 24x24 stroke icons) rendered through QtSvg."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "sliders": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/>'
    '<circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "flip": '<path d="M12 3v18" stroke-dasharray="2 2.5"/><path d="M9 7 3 17h6z"/><path d="M15 7l6 10h-6z"/>',
    "background": '<rect x="2.5" y="2.5" width="19" height="19" rx="4" stroke-dasharray="3 2.6"/>'
    '<circle cx="12" cy="10" r="3.2"/><path d="M6 19.5c1.3-3 3.5-4.5 6-4.5s4.7 1.5 6 4.5"/>',
    "spotlight": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M3 12s3.2-6.5 9-6.5S21 12 21 12s-3.2 6.5-9 6.5S3 12 3 12z"/>'
    '<circle cx="12" cy="12" r="2.8"/><path d="M4 4l16 16"/>',
    "eye": '<path d="M3 12s3.2-6.5 9-6.5S21 12 21 12s-3.2 6.5-9 6.5S3 12 3 12z"/><circle cx="12" cy="12" r="2.8"/>',
    "camera": '<rect x="3" y="7" width="13" height="10" rx="2.5"/><path d="M16 10.5l5-2.5v8l-5-2.5"/>',
    "shape": '<circle cx="9" cy="9" r="6"/><rect x="11" y="11" width="10" height="10" rx="2.5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2'
    'M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    "layers": '<path d="M12 3 3 8l9 5 9-5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "keyboard": '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/>'
    '<path d="M6 10h1M10 10h1M14 10h1M18 10h0.5M7 14h10"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "trash": '<path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="2"/><path d="M4 18l5-5 4 4 3-3 4 4"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "power": '<path d="M12 3v8"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/>',
    "ghost": '<path d="M5 20V11a7 7 0 0 1 14 0v9l-2.5-2-2.3 2-2.2-2-2.2 2-2.3-2z"/><circle cx="9.5" cy="11" r="1"/><circle cx="14.5" cy="11" r="1"/>',
    "pin": '<path d="M9 3h6l-1 6 4 4H6l4-4z"/><path d="M12 13v8"/>',
    "move": '<path d="M12 3v18M3 12h18M12 3l-2.5 2.5M12 3l2.5 2.5M12 21l-2.5-2.5M12 21l2.5-2.5'
    'M3 12l2.5-2.5M3 12l2.5 2.5M21 12l-2.5-2.5M21 12l-2.5 2.5"/>',
    "frame": '<path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4"/><circle cx="12" cy="10" r="2.5"/><path d="M8 17c1-2 2.4-3 4-3s3 1 4 3"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
}

ICON_NAMES = tuple(_PATHS.keys())


def _svg(name: str, color: str, stroke: float) -> bytes:
    body = _PATHS[name]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    ).encode("utf-8")


@lru_cache(maxsize=256)
def icon_image(name: str, size: int = 20, color: str = "#ECEDF1", stroke: float = 1.8, dpr: float = 2.0) -> QImage:
    px = max(1, int(round(size * dpr)))
    img = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(_svg(name, color, stroke)))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()
    img.setDevicePixelRatio(dpr)
    return img


def icon(name: str, size: int = 20, color: str = "#ECEDF1", stroke: float = 1.8) -> QIcon:
    """Return a QIcon for ``name`` drawn in ``color``."""
    qicon = QIcon()
    for dpr in (1.0, 2.0):
        qicon.addPixmap(QPixmap.fromImage(icon_image(name, size, color, stroke, dpr)))
    return qicon


def app_icon() -> QIcon:
    """Application / tray icon: a ring with a person silhouette."""
    qicon = QIcon()
    for px in (16, 22, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(px, px)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = px / 64.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#7C5CFF"))
        p.drawEllipse(QRectF(2 * s, 2 * s, 60 * s, 60 * s))
        p.setBrush(QColor("#121318"))
        p.drawEllipse(QRectF(7 * s, 7 * s, 50 * s, 50 * s))
        clip = QPainterPath()
        clip.addEllipse(QRectF(7 * s, 7 * s, 50 * s, 50 * s))
        p.setClipPath(clip)
        p.setBrush(QColor("#ECEDF1"))
        p.drawEllipse(QRectF(24 * s, 16 * s, 16 * s, 16 * s))
        p.drawChord(QRectF(15 * s, 35 * s, 34 * s, 34 * s), 0, 180 * 16)
        p.end()
        qicon.addPixmap(pm)
    return qicon
