"""Frameless circular presentation overlay window with anti-aliasing, soft shadow, drag, scroll-resize, and ghost mode."""

from __future__ import annotations

import logging
import math
from typing import Optional, Tuple
from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QGuiApplication,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QRegion,
    QWheelEvent,
)
from PySide6.QtWidgets import QMenu, QWidget

from selficamera.ui.aura import VoiceAuraRing
from selficamera.ui.hud import AutoHidingHUD

logger = logging.getLogger(__name__)

MIN_DIAMETER = 120
MAX_DIAMETER = 600
PRESET_DIAMETERS = [160, 260, 380]
DEFAULT_SHADOW_MARGIN = 16
CORNER_MARGIN = 24


class OverlayWindow(QWidget):
    """Floating borderless circular camera bubble for desktop presenters."""

    diameter_changed = Signal(int)
    diameter_completed = Signal(int)
    position_changed = Signal(int, int)
    drag_completed = Signal(int, int)
    ghost_mode_changed = Signal(bool)
    always_on_top_changed = Signal(bool)
    settings_requested = Signal()
    light_toggle_requested = Signal()

    def __init__(
        self,
        initial_diameter: int = 260,
        initial_pos: Optional[Tuple[int, int]] = None,
        shadow_margin: int = DEFAULT_SHADOW_MARGIN,
        always_on_top: bool = True,
    ) -> None:
        super().__init__()
        self._diameter = max(MIN_DIAMETER, min(MAX_DIAMETER, int(initial_diameter)))
        self.shadow_margin = shadow_margin
        self._always_on_top = always_on_top
        self._voice_energy: float = 0.0
        self._is_ghost_mode: bool = False
        self._current_frame: Optional[QImage] = None

        # Dragging and resizing states
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._is_dragging_resize = False
        self._is_resizing = False

        # Voice aura renderer
        self.aura_renderer = VoiceAuraRing(shadow_margin=self.shadow_margin)

        # Setup frameless transparent window flags
        self._setup_window_flags()

        # HUD setup
        self.hud = AutoHidingHUD(self)
        self.hud.settings_clicked.connect(self.settings_requested)
        self.hud.size_down_clicked.connect(lambda: self.step_resize_delta(-25))
        self.hud.size_up_clicked.connect(lambda: self.step_resize_delta(25))
        self.hud.light_clicked.connect(self.light_toggle_requested)

        # Resize animation
        self._resize_anim = QPropertyAnimation(self, b"diameter", self)
        self._resize_anim.setDuration(180)
        self._resize_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._resize_anim.finished.connect(lambda: self.diameter_completed.emit(self._diameter))

        # Move/Snap animation
        self._move_anim = QPropertyAnimation(self, b"pos", self)
        self._move_anim.setDuration(200)
        self._move_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._move_anim.finished.connect(lambda: self.drag_completed.emit(self.pos().x(), self.pos().y()))

        # Initialize window geometry
        total_dim = self._diameter + (2 * self.shadow_margin)
        self.resize(total_dim, total_dim)

        if initial_pos is not None:
            self.move(initial_pos[0], initial_pos[1])
        else:
            self.snap_to_corner(4)  # Default: Bottom-Right

        # Canonical Float Center-Point Anchor (Frozen during resizing to guarantee 0.0px drift)
        self._center_point = QPointF(self.x() + self.width() / 2.0, self.y() + self.height() / 2.0)
        self._reposition_hud()

    def _setup_window_flags(self) -> None:
        """Apply essential flags for floating presenter overlay."""
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

    def moveEvent(self, event) -> None:
        """Update canonical center point when window moves outside resizing operations."""
        super().moveEvent(event)
        if not self._is_resizing:
            self._center_point = QPointF(self.x() + self.width() / 2.0, self.y() + self.height() / 2.0)

    def set_always_on_top(self, enabled: bool) -> None:
        """Dynamically toggle WindowStaysOnTopHint while preserving window visibility."""
        self._always_on_top = enabled
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()  # Crucial: Qt hides window upon flag modification!
        self.always_on_top_changed.emit(enabled)
        logger.info("Always-on-top %s", "ENABLED" if enabled else "DISABLED")

    @property
    def is_always_on_top(self) -> bool:
        return self._always_on_top

    # Qt Property for smooth diameter resizing
    def get_diameter(self) -> int:
        return self._diameter

    def set_diameter(self, val: int | float) -> None:
        val = int(round(max(MIN_DIAMETER, min(MAX_DIAMETER, val))))
        if self._diameter == val:
            return
        self._is_resizing = True
        try:
            self._diameter = val
            total_dim = self._diameter + (2 * self.shadow_margin)
            new_x = int(round(self._center_point.x() - total_dim / 2.0))
            new_y = int(round(self._center_point.y() - total_dim / 2.0))
            self.setGeometry(new_x, new_y, total_dim, total_dim)
            self._reposition_hud()
            self.update()
            self.diameter_changed.emit(self._diameter)
        finally:
            self._is_resizing = False

    diameter = Property(int, get_diameter, set_diameter)

    def animate_to_diameter(self, target_diameter: int) -> None:
        """Smoothly animate overlay diameter to target value with zero center drift."""
        target_diameter = max(MIN_DIAMETER, min(MAX_DIAMETER, int(target_diameter)))
        if target_diameter != self._diameter:
            self._resize_anim.stop()
            self._resize_anim.setStartValue(self._diameter)
            self._resize_anim.setEndValue(target_diameter)
            self._resize_anim.start()

    def step_resize_delta(self, delta: int) -> None:
        """Step diameter by delta (e.g. +25 or -25px) with center anchoring."""
        new_d = max(MIN_DIAMETER, min(MAX_DIAMETER, self._diameter + delta))
        self.animate_to_diameter(new_d)

    def _reposition_hud(self) -> None:
        """Position HUD capsule near bottom arc of circle with small-diameter adaptation."""
        if self._diameter < 190:
            self.hud.set_compact_mode(True)
            hud_w = min(self._diameter - 10, 160)
            hud_h = 26
            y = self.shadow_margin + self._diameter - hud_h - 10
        else:
            self.hud.set_compact_mode(False)
            hud_w = min(264, self.width() - (2 * self.shadow_margin) + 8)
            hud_h = 32
            y = self.shadow_margin + self._diameter - hud_h - 14

        x = max(0, (self.width() - hud_w) // 2)
        self.hud.setGeometry(x, y, hud_w, hud_h)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Pop up dark styled presenter context menu with settings and quick toggles."""
        if self._is_ghost_mode:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 10px;
                border-radius: 4px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #313244;
                color: #89B4FA;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 20);
                margin: 4px 6px;
            }
        """)

        action_settings = menu.addAction("⚙ Settings...")
        action_settings.triggered.connect(self.settings_requested)

        menu.addSeparator()

        action_aot = menu.addAction("Always-On-Top")
        action_aot.setCheckable(True)
        action_aot.setChecked(self._always_on_top)
        action_aot.triggered.connect(lambda checked: self.set_always_on_top(checked))

        action_ghost = menu.addAction("Click-Through Ghost Mode")
        action_ghost.triggered.connect(lambda: self.set_click_through(True))

        menu.addSeparator()

        preset_menu = menu.addMenu("Size Presets")
        preset_menu.setStyleSheet(menu.styleSheet())
        for size in PRESET_DIAMETERS:
            act = preset_menu.addAction(f"{size} px")
            act.triggered.connect(lambda checked, s=size: self.set_diameter(s))

        menu.exec(event.globalPos())
        event.accept()

    def set_click_through(self, enabled: bool) -> None:
        """Toggle click-through Ghost Mode passing mouse clicks directly to underlying windows."""
        self._is_ghost_mode = enabled
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)

        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowTransparentForInput
            self.hud.trigger_hide()
        else:
            flags &= ~Qt.WindowType.WindowTransparentForInput

        self.setWindowFlags(flags)
        self.clearMask()
        self.show()

        self.update()
        self.ghost_mode_changed.emit(enabled)
        logger.info("Ghost mode %s", "ENABLED" if enabled else "DISABLED")

    def toggle_click_through(self) -> bool:
        """Toggle ghost mode state."""
        self.set_click_through(not self._is_ghost_mode)
        return self._is_ghost_mode

    @property
    def is_ghost_mode(self) -> bool:
        return self._is_ghost_mode

    def update_frame_image(self, image: QImage) -> None:
        """Update active video frame and schedule repaint."""
        self._current_frame = image
        self.update()

    def update_voice_energy(self, energy: float) -> None:
        """Update active vocal energy and schedule repaint."""
        self._voice_energy = energy
        self.update()

    def step_resize(self, step_up: bool) -> None:
        """Step diameter to next larger or smaller preset with smooth cubic easing animation."""
        if self._diameter in PRESET_DIAMETERS:
            idx = PRESET_DIAMETERS.index(self._diameter)
            new_idx = max(0, min(len(PRESET_DIAMETERS) - 1, idx + (1 if step_up else -1)))
            target_diameter = PRESET_DIAMETERS[new_idx]
        else:
            if step_up:
                candidates = [p for p in PRESET_DIAMETERS if p > self._diameter]
                target_diameter = candidates[0] if candidates else PRESET_DIAMETERS[-1]
            else:
                candidates = [p for p in PRESET_DIAMETERS if p < self._diameter]
                target_diameter = candidates[-1] if candidates else PRESET_DIAMETERS[0]

        if target_diameter != self._diameter:
            self._resize_anim.stop()
            self._resize_anim.setStartValue(self._diameter)
            self._resize_anim.setEndValue(target_diameter)
            self._resize_anim.start()

    def snap_to_corner(self, corner_id: int) -> None:
        """Snap window to one of four desktop corners or center (1: TL, 2: TR, 3: BL, 4: BR, 5: Center)."""
        screen = (
            self.screen()
            or QGuiApplication.screenAt(self._center_point.toPoint())
            or QGuiApplication.primaryScreen()
        )
        avail_geo = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

        win_w = self.width()
        win_h = self.height()

        margin = CORNER_MARGIN
        # Corner math respecting top bar and docks
        if corner_id == 1:  # Top-Left
            target_x = avail_geo.left() + margin
            target_y = avail_geo.top() + margin
        elif corner_id == 2:  # Top-Right
            target_x = avail_geo.right() - win_w - margin + 1
            target_y = avail_geo.top() + margin
        elif corner_id == 3:  # Bottom-Left
            target_x = avail_geo.left() + margin
            target_y = avail_geo.bottom() - win_h - margin + 1
        elif corner_id == 5:  # Center
            target_x = avail_geo.left() + (avail_geo.width() - win_w) // 2
            target_y = avail_geo.top() + (avail_geo.height() - win_h) // 2
        else:  # 4: Bottom-Right (Default)
            target_x = avail_geo.right() - win_w - margin + 1
            target_y = avail_geo.bottom() - win_h - margin + 1

        self._move_anim.stop()
        self._move_anim.setStartValue(self.pos())
        self._move_anim.setEndValue(QPoint(target_x, target_y))
        self._move_anim.start()
        self.position_changed.emit(target_x, target_y)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Initiate drag-to-move or radial resize if clicked inside circle or on border aura."""
        if event.button() == Qt.MouseButton.LeftButton and not self._is_ghost_mode:
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            dist = math.hypot(event.position().x() - cx, event.position().y() - cy)
            r = self._diameter / 2.0

            # 1. Radial perimeter resize zone [r - 14, r + 16]
            if (r - 14.0) <= dist <= (r + 16.0):
                self._is_dragging_resize = True
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                event.accept()
                return

            # 2. Window drag zone (inside circle + glowing aura border)
            if dist <= (r + 4.0):
                self._is_dragging = True
                self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Execute smooth drag-to-move across all displays or radial resizing."""
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        dist = math.hypot(event.position().x() - cx, event.position().y() - cy)
        r = self._diameter / 2.0

        # Hover cursor feedback when not dragging
        if not self._is_ghost_mode and not self._is_dragging and not self._is_dragging_resize:
            if (r - 14.0) <= dist <= (r + 16.0):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif dist <= (r - 14.0):
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.unsetCursor()

        # Continuous radial resize drag
        if self._is_dragging_resize and (event.buttons() & Qt.MouseButton.LeftButton):
            new_diameter = int(round(2.0 * dist))
            self.set_diameter(new_diameter)
            event.accept()
            return

        # Continuous window reposition drag across multi-monitor setup
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            target_pos = event.globalPosition().toPoint() - self._drag_start_pos

            screens = QGuiApplication.screens()
            if screens:
                virtual_rect = screens[0].geometry()
                for s in screens[1:]:
                    virtual_rect = virtual_rect.united(s.geometry())
                clamped_x = max(virtual_rect.left(), min(virtual_rect.right() - self.width() + 1, target_pos.x()))
                clamped_y = max(virtual_rect.top(), min(virtual_rect.bottom() - self.height() + 1, target_pos.y()))
                target_pos = QPoint(clamped_x, clamped_y)

            self.move(target_pos)
            self.position_changed.emit(target_pos.x(), target_pos.y())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Conclude dragging and emit completion signals for deferred disk persistence."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging_resize:
                self._is_dragging_resize = False
                self.diameter_completed.emit(self._diameter)
            if self._is_dragging:
                self._is_dragging = False
                self.drag_completed.emit(self.pos().x(), self.pos().y())
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Smooth continuous scroll-wheel resizing."""
        if not self._is_ghost_mode:
            delta = event.angleDelta().y()
            if delta != 0:
                step = int(round(delta / 120.0 * 15.0))
                if step == 0:
                    step = 15 if delta > 0 else -15
                new_d = max(MIN_DIAMETER, min(MAX_DIAMETER, self._diameter + step))
                self.set_diameter(new_d)
                self.diameter_completed.emit(self._diameter)
                event.accept()
                return
        super().wheelEvent(event)

    def enterEvent(self, event: QEvent) -> None:
        """Fade in HUD on mouse hover."""
        super().enterEvent(event)
        if not self._is_ghost_mode:
            self.hud.trigger_show()

    def leaveEvent(self, event: QEvent) -> None:
        """Fade out HUD after leaving."""
        super().leaveEvent(event)
        self.hud.trigger_hide_delayed()

    def paintEvent(self, event) -> None:
        """High-precision rendering: soft drop shadow, circular clipped video, dynamic aura, stroke."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        center = QPointF(cx, cy)
        radius = self._diameter / 2.0

        # 1. Outer soft Gaussian drop shadow
        self.aura_renderer.draw_drop_shadow(painter, center, radius)

        # 2. Aspect-ratio locked video feed clipped to exact 1:1 circle
        clip_path = QPainterPath()
        clip_path.addEllipse(center, radius, radius)

        painter.save()
        painter.setClipPath(clip_path)

        if self._current_frame is not None and not self._current_frame.isNull():
            # Render video frame scaled to circle
            target_rect = QRectF(self.shadow_margin, self.shadow_margin, self._diameter, self._diameter)
            painter.drawImage(target_rect, self._current_frame)
        else:
            # Standby placeholder
            painter.fillRect(self.rect(), QColor(24, 24, 37))
            painter.setPen(QColor(140, 140, 160))
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "SelfiCamera\nConnecting...")

        painter.restore()

        # 3. Dynamic Voice Aura border ring & inner stroke
        self.aura_renderer.draw_aura(painter, center, radius, self._voice_energy, self._is_ghost_mode)
