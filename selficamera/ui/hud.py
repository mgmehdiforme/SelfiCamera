"""Auto-hiding on-hover HUD controls overlay with smooth opacity animations."""

from __future__ import annotations

import logging
from typing import Optional
from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

logger = logging.getLogger(__name__)

HUD_STYLE = """
QWidget#hud_container {
    background-color: rgba(30, 30, 46, 220);
    border: 1px solid rgba(255, 255, 255, 35);
    border-radius: 12px;
}
QPushButton {
    background-color: transparent;
    color: #CDD6F4;
    border: none;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 6px;
}
QPushButton:hover {
    background-color: rgba(137, 180, 250, 40);
    color: #89B4FA;
}
QPushButton:pressed {
    background-color: rgba(137, 180, 250, 80);
}
"""

HUD_STYLE_COMPACT = """
QWidget#hud_container {
    background-color: rgba(30, 30, 46, 230);
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 8px;
}
QPushButton {
    background-color: transparent;
    color: #CDD6F4;
    border: none;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 9px;
    font-weight: 600;
    padding: 2px 3px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: rgba(137, 180, 250, 40);
    color: #89B4FA;
}
QPushButton:pressed {
    background-color: rgba(137, 180, 250, 80);
}
"""

BLUR_LABELS = {
    0: "B:Off",
    1: "B:Sub",
    2: "B:Bal",
    3: "B:Hvy",
}


class AutoHidingHUD(QWidget):
    """Floating HUD control pill that fades in on mouse hover and fades out after inactivity."""

    flip_clicked = Signal()
    blur_clicked = Signal()
    light_clicked = Signal()
    settings_clicked = Signal()
    ghost_clicked = Signal()
    close_clicked = Signal()
    size_down_clicked = Signal()
    size_up_clicked = Signal()
    pin_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("hud_container")
        self.setStyleSheet(HUD_STYLE)
        self._current_blur_level: int = 2
        self._compact_mode: bool = False
        self._is_pinned: bool = False

        # When hidden (opacity 0.0), pass mouse clicks through so circle drag is not intercepted
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Controls
        self.btn_size_down = QPushButton("−", self)
        self.btn_size_down.setToolTip("Step Size Smaller (-25px)")
        self.btn_size_down.clicked.connect(self.size_down_clicked)

        self.btn_size_up = QPushButton("+", self)
        self.btn_size_up.setToolTip("Step Size Larger (+25px)")
        self.btn_size_up.clicked.connect(self.size_up_clicked)

        self.btn_flip = QPushButton("Flip", self)
        self.btn_flip.setToolTip("Toggle Horizontal Mirror")
        self.btn_flip.clicked.connect(self.flip_clicked)

        self.btn_blur = QPushButton("B:Bal", self)
        self.btn_blur.setToolTip("Cycle Background Blur Level (Off -> Subtle -> Balanced -> Heavy)")
        self.btn_blur.clicked.connect(self.blur_clicked)

        self.btn_light = QPushButton("Light", self)
        self.btn_light.setToolTip("Toggle Auto-Light Boost")
        self.btn_light.clicked.connect(self.light_clicked)

        self.btn_settings = QPushButton("⚙", self)
        self.btn_settings.setToolTip("Settings & Controls Panel")
        self.btn_settings.clicked.connect(self.settings_clicked)

        self.btn_pin = QPushButton("📌", self)
        self.btn_pin.setToolTip("Pin HUD (Keep Controls Permanently Visible)")
        self.btn_pin.clicked.connect(self._toggle_pin)

        self.btn_ghost = QPushButton("Ghost", self)
        self.btn_ghost.setToolTip("Activate Click-Through Ghost Mode (Super+Alt+X to exit)")
        self.btn_ghost.clicked.connect(self.ghost_clicked)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setToolTip("Quit SelfiCamera")
        self.btn_close.clicked.connect(self.close_clicked)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(3)
        layout.addWidget(self.btn_size_down)
        layout.addWidget(self.btn_size_up)
        layout.addWidget(self.btn_flip)
        layout.addWidget(self.btn_blur)
        layout.addWidget(self.btn_light)
        layout.addWidget(self.btn_settings)
        layout.addWidget(self.btn_pin)
        layout.addWidget(self.btn_ghost)
        layout.addWidget(self.btn_close)

        # Opacity animation & effect
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._anim.finished.connect(self._on_anim_finished)

        # Inactivity auto-hide timer (1200ms)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(1200)
        self._hide_timer.timeout.connect(self._start_fade_out)

    def _on_anim_finished(self) -> None:
        """Make transparent for mouse events when opacity reaches 0.0."""
        if self._opacity_effect.opacity() <= 0.01:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    @property
    def current_opacity(self) -> float:
        """Return the current opacity value."""
        return float(self._opacity_effect.opacity())

    @property
    def is_pinned(self) -> bool:
        """Return True if HUD is pinned visible."""
        return self._is_pinned

    def _toggle_pin(self) -> None:
        """Toggle pinned state keeping HUD permanently visible on screen."""
        self._is_pinned = not self._is_pinned
        if self._is_pinned:
            self._hide_timer.stop()
            self.trigger_show()
            self.btn_pin.setStyleSheet("color: #A6E3A1; font-weight: bold; background-color: rgba(166, 227, 161, 40);")
        else:
            self.btn_pin.setStyleSheet("")
            self.trigger_hide_delayed()
        self.pin_toggled.emit(self._is_pinned)

    def set_pinned(self, pinned: bool) -> None:
        """Set pinned state explicitly."""
        if self._is_pinned == pinned:
            return
        self._toggle_pin()

    def update_blur_label(self, level: int) -> None:
        """Update the blur button label to reflect the active tier."""
        self._current_blur_level = level
        if self._compact_mode:
            self.btn_blur.setText(f"B{level}")
        else:
            label = BLUR_LABELS.get(level, f"B:{level}")
            self.btn_blur.setText(label)

    def set_compact_mode(self, compact: bool) -> None:
        """Adapt button layout and font padding for small diameters (<190px)."""
        if self._compact_mode == compact:
            return
        self._compact_mode = compact
        layout = self.layout()
        if compact:
            self.setStyleSheet(HUD_STYLE_COMPACT)
            if isinstance(layout, QHBoxLayout):
                layout.setContentsMargins(3, 2, 3, 2)
                layout.setSpacing(2)
            self.btn_size_down.setText("−")
            self.btn_size_up.setText("+")
            self.btn_flip.setVisible(False)
            self.btn_ghost.setVisible(False)
            self.btn_close.setVisible(False)
            self.btn_light.setText("☀")
            self.btn_settings.setText("⚙")
            self.btn_pin.setText("📌")
            self.update_blur_label(self._current_blur_level)
        else:
            self.setStyleSheet(HUD_STYLE)
            if isinstance(layout, QHBoxLayout):
                layout.setContentsMargins(5, 3, 5, 3)
                layout.setSpacing(3)
            self.btn_size_down.setText("−")
            self.btn_size_up.setText("+")
            self.btn_flip.setVisible(True)
            self.btn_flip.setText("Flip")
            self.btn_ghost.setVisible(True)
            self.btn_ghost.setText("Ghost")
            self.btn_close.setVisible(True)
            self.btn_close.setText("✕")
            self.btn_light.setText("Light")
            self.btn_settings.setText("⚙")
            self.btn_pin.setText("📌")
            self.update_blur_label(self._current_blur_level)

    def trigger_show(self) -> None:
        """Trigger fast fade-in (150ms)."""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._hide_timer.stop()
        self._anim.stop()
        self._anim.setDuration(150)
        self._anim.setStartValue(self._opacity_effect.opacity())
        self._anim.setEndValue(0.92)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _start_fade_out(self) -> None:
        """Trigger smooth fade-out (300ms) if not pinned."""
        if self._is_pinned:
            return
        self._anim.stop()
        self._anim.setDuration(300)
        self._anim.setStartValue(self._opacity_effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.start()

    def trigger_hide_delayed(self) -> None:
        """Start the 1.2s inactivity timer before fading out if not pinned."""
        if not self._is_pinned:
            self._hide_timer.start()

    def enterEvent(self, event: QEvent) -> None:
        """Hover enter on HUD."""
        super().enterEvent(event)
        self.trigger_show()

    def leaveEvent(self, event: QEvent) -> None:
        """Hover leave on HUD."""
        super().leaveEvent(event)
        self.trigger_hide_delayed()
