"""Hover controls shown on the bubble (fade in on hover, never shown in clean mode)."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QToolButton, QWidget

from selficamera.config import BACKGROUND_LABELS
from selficamera.ui import icons
from selficamera.ui.theme import HUD_STYLESHEET

BUTTON_SIZE = 28
FULL_ORDER = ("background", "mirror", "spotlight", "settings", "hide")
COMPACT_ORDER = ("background", "spotlight", "settings")


class HoverControls(QWidget):
    """Pill toolbar with icon buttons."""

    background_clicked = Signal()
    mirror_clicked = Signal()
    spotlight_clicked = Signal()
    settings_clicked = Signal()
    hide_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("Hud")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(HUD_STYLESHEET)
        self._compact = False
        self._enabled = True

        specs = {
            "background": ("background", "Background effect", self.background_clicked),
            "mirror": ("flip", "Mirror", self.mirror_clicked),
            "spotlight": ("spotlight", "Spotlight (Super+Alt+Z)", self.spotlight_clicked),
            "settings": ("sliders", "Settings", self.settings_clicked),
            "hide": ("eye_off", "Hide camera (Super+Alt+C)", self.hide_clicked),
        }
        self.buttons: Dict[str, QToolButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(2)
        for key in FULL_ORDER:
            icon_name, tip, signal = specs[key]
            btn = QToolButton(self)
            btn.setIcon(icons.icon(icon_name, 18))
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(signal)
            layout.addWidget(btn)
            self.buttons[key] = btn

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.finished.connect(self._after_anim)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(900)
        self._hide_timer.timeout.connect(self.fade_out)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    # ----------------------------------------------------------------- layout
    @property
    def compact(self) -> bool:
        return self._compact

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        order = COMPACT_ORDER if compact else FULL_ORDER
        for key, btn in self.buttons.items():
            btn.setVisible(key in order)
        self.adjustSize()

    def preferred_size(self) -> QSize:
        n = len(COMPACT_ORDER if self._compact else FULL_ORDER)
        return QSize(n * BUTTON_SIZE + (n - 1) * 2 + 8, BUTTON_SIZE + 6)

    def set_background_mode(self, mode: str) -> None:
        self.buttons["background"].setToolTip(f"Background: {BACKGROUND_LABELS.get(mode, mode)} (click to change)")
        self.buttons["background"].setDown(False)

    # ------------------------------------------------------------- visibility
    @property
    def opacity(self) -> float:
        return float(self._effect.opacity())

    def set_controls_enabled(self, enabled: bool) -> None:
        """Clean mode: when disabled, hover never reveals the controls."""
        self._enabled = enabled
        if not enabled:
            self.hide_now()

    def reveal(self) -> None:
        if not self._enabled:
            return
        self._hide_timer.stop()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._anim.stop()
        self._anim.setDuration(140)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def schedule_hide(self) -> None:
        self._hide_timer.start()

    def fade_out(self) -> None:
        self._anim.stop()
        self._anim.setDuration(260)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.start()

    def hide_now(self) -> None:
        self._hide_timer.stop()
        self._anim.stop()
        self._effect.setOpacity(0.0)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _after_anim(self) -> None:
        if self._effect.opacity() <= 0.01:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def enterEvent(self, event: QEvent) -> None:
        super().enterEvent(event)
        self.reveal()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self.schedule_hide()
