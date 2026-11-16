"""The camera bubble: a frameless, shaped, always-on-top window.

Geometry is anchored on the content *center* so resizing, shape changes and
spotlight animations never drift. Positions are persisted as center coordinates.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from selficamera.config import MAX_SIZE, MIN_SIZE
from selficamera.ui import icons
from selficamera.ui.hud import HoverControls
from selficamera.ui.shapes import content_size, edge_distance_px, normalized_distance, shape_path
from selficamera.ui.voice_wave import VoiceWave

logger = logging.getLogger(__name__)

MARGIN = 30  # room for shadow, border and the voice wave around the content
SNAP_MARGIN = 24
EDGE_ZONE = 10.0
WHEEL_STEP = 20

# Snap targets
TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT, CENTER = 1, 2, 3, 4, 5
POSITION_LABELS = {
    TOP_LEFT: "Top left",
    TOP_RIGHT: "Top right",
    BOTTOM_LEFT: "Bottom left",
    BOTTOM_RIGHT: "Bottom right",
    CENTER: "Center",
}


class BubbleWindow(QWidget):
    """Floating camera bubble."""

    position_committed = Signal(int, int)  # content center
    size_changed = Signal(int)
    size_committed = Signal(int)
    render_size_changed = Signal(int, int)  # device pixels for the processor
    settings_requested = Signal()
    context_menu_requested = Signal(QPoint)
    spotlight_changed = Signal(bool)

    def __init__(
        self,
        shape: str = "circle",
        size: int = 260,
        center: Optional[Tuple[int, int]] = None,
        always_on_top: bool = True,
    ) -> None:
        super().__init__()
        self._shape = shape
        self._size = int(max(MIN_SIZE, min(MAX_SIZE, size)))
        self._center = QPointF(0, 0)
        self._always_on_top = always_on_top
        self._ghost = False
        self._border_width = 3
        self._border_color = QColor("#FFFFFF")
        self._voice_glow = True
        self._shadow = True
        self._energy = 0.0
        self._frame: Optional[QImage] = None
        self._status_state = "starting"
        self._status_text = "Starting camera…"
        self._toast_text = ""
        self._toast_until = 0.0
        self._render_size: Tuple[int, int] = (0, 0)
        self._shadow_cache_key: Optional[tuple] = None
        self._shadow_cache: Optional[QImage] = None
        self._setting_geometry = False

        self._drag_offset: Optional[QPointF] = None
        self._resize_start: Optional[Tuple[float, int]] = None
        self._press_global: Optional[QPointF] = None

        self._spotlight_saved: Optional[Tuple[QPointF, int]] = None

        self._apply_window_flags()
        self.setMouseTracking(True)
        self.setWindowTitle("SelfiCamera")

        self.hud = HoverControls(self)
        self.hud.settings_clicked.connect(self.settings_requested)
        self.hud.spotlight_clicked.connect(self.toggle_spotlight)

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._on_anim_step)
        self._anim.finished.connect(self._on_anim_finished)
        self._anim_from: Tuple[QPointF, int] = (QPointF(), self._size)
        self._anim_to: Tuple[QPointF, int] = (QPointF(), self._size)
        self._anim_commit_size = False

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.update)

        self.wave = VoiceWave()
        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(16)
        self._wave_timer.timeout.connect(self._on_wave_tick)
        self._wave_last = time.monotonic()

        self._apply_geometry()
        if center is not None and self._point_on_any_screen(QPointF(*center)):
            self._center = QPointF(*center)
            self._apply_geometry()
        else:
            self.snap_to(BOTTOM_RIGHT, animate=False)

    # ---------------------------------------------------------------- flags
    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if self._ghost:
            flags |= Qt.WindowType.WindowTransparentForInput
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if was_visible:
            self.show()
            self._apply_geometry()

    def set_always_on_top(self, enabled: bool) -> None:
        if enabled != self._always_on_top:
            self._always_on_top = enabled
            self._apply_window_flags()

    @property
    def is_always_on_top(self) -> bool:
        return self._always_on_top

    def set_click_through(self, enabled: bool) -> None:
        if enabled == self._ghost:
            return
        self._ghost = enabled
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        if enabled:
            self.hud.hide_now()
        self._apply_window_flags()
        self.update()

    @property
    def is_click_through(self) -> bool:
        return self._ghost

    # -------------------------------------------------------------- geometry
    @staticmethod
    def _point_on_any_screen(p: QPointF) -> bool:
        return QGuiApplication.screenAt(p.toPoint()) is not None

    def _screen_geometry(self) -> QRect:
        screen = QGuiApplication.screenAt(self._center.toPoint()) or self.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    @property
    def shape(self) -> str:
        return self._shape

    @property
    def size_value(self) -> int:
        return self._size

    def get_diameter(self) -> int:  # backwards compatible name
        return self._size

    @property
    def center(self) -> QPointF:
        return QPointF(self._center)

    def content_rect(self) -> QRectF:
        cw, ch = content_size(self._shape, self._size)
        return QRectF(MARGIN, MARGIN, cw, ch)

    def _apply_geometry(self) -> None:
        cw, ch = content_size(self._shape, self._size)
        tw, th = cw + 2 * MARGIN, ch + 2 * MARGIN
        x = int(round(self._center.x() - tw / 2.0))
        y = int(round(self._center.y() - th / 2.0))
        self._setting_geometry = True
        try:
            self.setGeometry(x, y, tw, th)
        finally:
            self._setting_geometry = False
        self._layout_hud()
        dpr = self.devicePixelRatioF() if self.windowHandle() else 1.0
        render = (max(16, int(cw * dpr)), max(16, int(ch * dpr)))
        if render != self._render_size:
            self._render_size = render
            self.render_size_changed.emit(*render)
        self.update()

    @property
    def render_size(self) -> Tuple[int, int]:
        return self._render_size

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if not self._setting_geometry and self._anim.state() != QVariantAnimation.State.Running:
            self._center = QPointF(self.x() + self.width() / 2.0, self.y() + self.height() / 2.0)

    def _layout_hud(self) -> None:
        cw, ch = content_size(self._shape, self._size)
        self.hud.set_compact(cw < 210)
        hint = self.hud.preferred_size()
        w, h = min(hint.width(), cw - 12), hint.height()
        x = MARGIN + (cw - w) / 2.0
        bottom_pad = 14 if self._shape != "circle" else max(14, int(ch * 0.07))
        y = MARGIN + ch - h - bottom_pad
        self.hud.setGeometry(int(x), int(y), int(w), int(h))

    def set_shape(self, shape: str) -> None:
        if shape != self._shape:
            self._shape = shape
            self._shadow_cache_key = None
            self._apply_geometry()

    def set_size(self, size: int, animate: bool = False) -> None:
        size = int(max(MIN_SIZE, min(MAX_SIZE, size)))
        if animate:
            self._animate_to(self._center, size, commit_size=True)
            return
        if size != self._size:
            self._size = size
            self._apply_geometry()
            self.size_changed.emit(size)

    set_diameter = set_size

    def step_size(self, delta: int) -> None:
        self.set_size(self._size + delta, animate=True)

    def move_center_to(self, cx: float, cy: float, animate: bool = False) -> None:
        if animate:
            self._animate_to(QPointF(cx, cy), self._size)
        else:
            self._center = QPointF(cx, cy)
            self._apply_geometry()

    def snap_target(self, position: int, size: Optional[int] = None) -> QPointF:
        avail = self._screen_geometry()
        cw, ch = content_size(self._shape, size if size is not None else self._size)
        hw, hh = cw / 2.0, ch / 2.0
        left = avail.left() + SNAP_MARGIN + hw
        right = avail.left() + avail.width() - SNAP_MARGIN - hw
        top = avail.top() + SNAP_MARGIN + hh
        bottom = avail.top() + avail.height() - SNAP_MARGIN - hh
        mid = QPointF(avail.left() + avail.width() / 2.0, avail.top() + avail.height() / 2.0)
        return {
            TOP_LEFT: QPointF(left, top),
            TOP_RIGHT: QPointF(right, top),
            BOTTOM_LEFT: QPointF(left, bottom),
            BOTTOM_RIGHT: QPointF(right, bottom),
            CENTER: mid,
        }.get(position, QPointF(right, bottom))

    def snap_to(self, position: int, animate: bool = True) -> None:
        target = self.snap_target(position)
        self._spotlight_saved = None
        if animate and self.isVisible():
            self._animate_to(target, self._size)
        else:
            self._center = target
            self._apply_geometry()
            self.position_committed.emit(int(target.x()), int(target.y()))

    snap_to_corner = snap_to

    def clamp_on_screen(self) -> None:
        """Keep at least the content fully inside the current screen."""
        avail = self._screen_geometry()
        cw, ch = content_size(self._shape, self._size)
        cx = min(max(self._center.x(), avail.left() + cw / 2.0), avail.left() + avail.width() - cw / 2.0)
        cy = min(max(self._center.y(), avail.top() + ch / 2.0), avail.top() + avail.height() - ch / 2.0)
        if (cx, cy) != (self._center.x(), self._center.y()):
            self._center = QPointF(cx, cy)
            self._apply_geometry()

    # ------------------------------------------------------------- animation
    def _animate_to(self, center: QPointF, size: int, commit_size: bool = False, duration: int = 260) -> None:
        self._anim.stop()
        self._anim_from = (QPointF(self._center), self._size)
        self._anim_to = (QPointF(center), int(size))
        self._anim_commit_size = commit_size or size != self._size
        if not self.isVisible():
            self._on_anim_step(1.0)
            self._on_anim_finished()
            return
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _on_anim_step(self, t) -> None:
        t = float(t)
        (c0, s0), (c1, s1) = self._anim_from, self._anim_to
        self._center = QPointF(c0.x() + (c1.x() - c0.x()) * t, c0.y() + (c1.y() - c0.y()) * t)
        new_size = int(round(s0 + (s1 - s0) * t))
        size_changed = new_size != self._size
        self._size = new_size
        self._apply_geometry()
        if size_changed:
            self.size_changed.emit(new_size)

    def _on_anim_finished(self) -> None:
        self.position_committed.emit(int(self._center.x()), int(self._center.y()))
        if self._anim_commit_size:
            self.size_committed.emit(self._size)

    @property
    def is_animating(self) -> bool:
        return self._anim.state() == QVariantAnimation.State.Running

    # -------------------------------------------------------------- spotlight
    @property
    def in_spotlight(self) -> bool:
        return self._spotlight_saved is not None

    def spotlight_size(self, scale: float = 0.62) -> int:
        avail = self._screen_geometry()
        short = min(avail.width(), avail.height()) * scale
        cw, ch = content_size(self._shape, int(short))
        f = min(1.0, avail.width() * 0.92 / cw, avail.height() * 0.92 / ch)
        return int(max(MIN_SIZE, min(MAX_SIZE, short * f)))

    def toggle_spotlight(self, scale: float = 0.62) -> None:
        if self._spotlight_saved is None:
            self._spotlight_saved = (QPointF(self._center), self._size)
            avail = self._screen_geometry()
            target = QPointF(avail.left() + avail.width() / 2.0, avail.top() + avail.height() / 2.0)
            self._animate_to(target, self.spotlight_size(scale), duration=420)
            self.spotlight_changed.emit(True)
        else:
            center, size = self._spotlight_saved
            self._spotlight_saved = None
            self._animate_to(center, size, duration=380)
            self.spotlight_changed.emit(False)

    def _leave_spotlight_silently(self) -> None:
        if self._spotlight_saved is not None:
            self._spotlight_saved = None
            self.spotlight_changed.emit(False)

    # --------------------------------------------------------------- styling
    def set_border(self, width: int, color: str) -> None:
        self._border_width = int(width)
        self._border_color = QColor(color)
        self.update()

    def set_voice_glow(self, enabled: bool) -> None:
        self._voice_glow = enabled
        if not enabled:
            self.wave.set_energy(0.0)
            self.wave.level = 0.0
            self.wave.ripples.clear()
            self._wave_timer.stop()
        self.update()

    def set_shadow(self, enabled: bool) -> None:
        self._shadow = enabled
        self.update()

    def set_controls_on_hover(self, enabled: bool) -> None:
        self.hud.set_controls_enabled(enabled)

    # --------------------------------------------------------------- content
    def set_frame(self, image: Optional[QImage]) -> None:
        if image is not None and not image.isNull():
            self._frame = image
            self.update()

    update_frame_image = set_frame

    def set_status(self, state: str, message: str) -> None:
        self._status_state = state
        self._status_text = message
        self.update()

    def set_voice_energy(self, energy: float) -> None:
        energy = max(0.0, min(1.0, float(energy)))
        self._energy = energy
        if not self._voice_glow:
            return
        self.wave.set_energy(energy)
        if self.wave.active and not self._wave_timer.isActive() and self.isVisible():
            self._wave_last = time.monotonic()
            self._wave_timer.start()

    def _on_wave_tick(self) -> None:
        now = time.monotonic()
        alive = self.wave.tick(now - self._wave_last)
        self._wave_last = now
        if not alive:
            self._wave_timer.stop()
        self.update()

    update_voice_energy = set_voice_energy

    def show_toast(self, text: str, ms: int = 3200) -> None:
        self._toast_text = text
        self._toast_until = time.monotonic() + ms / 1000.0
        self._toast_timer.start(ms + 20)
        self.update()

    @property
    def toast_text(self) -> str:
        return self._toast_text if time.monotonic() < self._toast_until else ""

    # ------------------------------------------------------------------ input
    def _zone(self, pos: QPointF) -> str:
        rect = self.content_rect()
        d = edge_distance_px(self._shape, rect, pos)
        if -EDGE_ZONE <= d <= EDGE_ZONE:
            return "edge"
        if d < -EDGE_ZONE:
            return "inside"
        return "outside"

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._ghost:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            zone = self._zone(pos)
            self._anim.stop()
            if zone == "edge":
                nd = normalized_distance(self._shape, self.content_rect(), pos)
                self._resize_start = (max(0.2, nd), self._size)
                event.accept()
                return
            if zone == "inside" and QGuiApplication.platformName().startswith("wayland") and self.windowHandle():
                # Native Wayland: only the compositor may move windows.
                self.windowHandle().startSystemMove()
                event.accept()
                return
            if zone == "inside":
                self._drag_offset = event.globalPosition() - self._center
                self._press_global = event.globalPosition()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._ghost:
            return
        pos = event.position()
        if self._resize_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
            nd0, s0 = self._resize_start
            nd = normalized_distance(self._shape, self.content_rect(), pos) * self._size / s0
            # nd is measured against the current rect; convert to scale of the original
            self._leave_spotlight_silently()
            self.set_size(int(round(s0 * nd / nd0)))
            event.accept()
            return
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._leave_spotlight_silently()
            self._center = event.globalPosition() - self._drag_offset
            self._apply_geometry()
            event.accept()
            return
        zone = self._zone(pos)
        if zone == "edge":
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif zone == "inside":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._resize_start is not None:
                self._resize_start = None
                self.size_committed.emit(self._size)
            if self._drag_offset is not None:
                self._drag_offset = None
                self.clamp_on_screen()
                self.position_committed.emit(int(self._center.x()), int(self._center.y()))
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if not self._ghost and event.button() == Qt.MouseButton.LeftButton and self._zone(event.position()) == "inside":
            self.toggle_spotlight()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._ghost:
            return
        delta = event.angleDelta().y()
        if delta:
            step = int(round(delta / 120.0 * WHEEL_STEP)) or (WHEEL_STEP if delta > 0 else -WHEEL_STEP)
            self._leave_spotlight_silently()
            self.set_size(self._size + step)
            self.size_committed.emit(self._size)
            event.accept()
            return
        super().wheelEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if not self._ghost:
            self.context_menu_requested.emit(event.globalPos())
            event.accept()

    def enterEvent(self, event: QEvent) -> None:
        super().enterEvent(event)
        if not self._ghost:
            self.hud.reveal()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self.hud.schedule_hide()

    # ---------------------------------------------------------------- render
    def _shadow_image(self) -> QImage:
        cw, ch = content_size(self._shape, self._size)
        key = (self._shape, cw, ch)
        if key == self._shadow_cache_key and self._shadow_cache is not None:
            return self._shadow_cache
        w, h = cw + 2 * MARGIN, ch + 2 * MARGIN
        alpha = np.zeros((h, w), dtype=np.uint8)
        img = QImage(alpha.data, w, h, w, QImage.Format.Format_Grayscale8)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255))
        p.drawPath(shape_path(self._shape, QRectF(MARGIN, MARGIN + 5, cw, ch)))
        p.end()
        blurred = cv2.GaussianBlur(alpha, (0, 0), sigmaX=9)
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 3] = (blurred.astype(np.float32) * 0.55).astype(np.uint8)
        shadow = QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
        self._shadow_cache_key, self._shadow_cache = key, shadow
        return shadow

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = self.content_rect()
        path = shape_path(self._shape, rect)

        transparent_bg = self._frame is not None and self._frame.hasAlphaChannel()
        if self._shadow and not transparent_bg:
            p.drawImage(0, 0, self._shadow_image())

        p.save()
        p.setClipPath(path)
        live = self._frame is not None and self._status_state != "error"
        if self._frame is not None:
            p.drawImage(rect, self._frame)
        if not live:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            alpha = 200 if self._frame is not None else 255
            grad.setColorAt(0, QColor(34, 37, 46, alpha))
            grad.setColorAt(1, QColor(18, 19, 24, alpha))
            p.fillRect(rect, grad)
            self._paint_status(p, rect)
        p.restore()

        if self._voice_glow:
            base = self._border_width / 2.0 + 0.5
            self.wave.paint(p, self._shape, rect, self._border_color, base, MARGIN - base - 5, QRectF(self.rect()))
        self._paint_border(p, path)

        toast = self.toast_text
        if toast:
            self._paint_toast(p, rect, toast)
        p.end()

    def _paint_status(self, p: QPainter, rect: QRectF) -> None:
        name = "camera"
        color = "#9AA0AE" if self._status_state != "error" else "#F5B83D"
        icon_px = max(18, min(40, int(rect.height() * 0.16)))
        img = icons.icon_image(name, icon_px, color, 1.8, 2.0)
        cy = rect.center().y() - icon_px * 0.9
        p.drawImage(QRectF(rect.center().x() - icon_px / 2, cy - icon_px / 2, icon_px, icon_px), img)
        font = QFont(self.font())
        font.setPixelSize(max(10, min(15, int(rect.width() / 17))))
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor("#ECEDF1"))
        text_rect = QRectF(rect.left() + rect.width() * 0.12, cy + icon_px * 0.6, rect.width() * 0.76, rect.height() * 0.4)
        p.drawText(text_rect, int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), self._status_text or "Starting camera…")

    def _paint_border(self, p: QPainter, path: QPainterPath) -> None:
        bw = self._border_width
        color = QColor(self._border_color)
        if bw > 0:
            pen = QPen(color, bw)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

    def _paint_toast(self, p: QPainter, rect: QRectF, text: str) -> None:
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        max_w = rect.width() * 0.86
        metrics = p.fontMetrics()
        br = metrics.boundingRect(QRect(0, 0, int(max_w) - 20, 400), int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter), text)
        w, h = br.width() + 22, br.height() + 12
        top = rect.top() + (rect.height() * 0.12 if self._shape == "circle" else 12)
        box = QRectF(rect.center().x() - w / 2, top, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 19, 24, 225))
        p.drawRoundedRect(box, h / 2 if h < 30 else 10, h / 2 if h < 30 else 10)
        p.setPen(QColor("#ECEDF1"))
        p.drawText(box, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), text)
