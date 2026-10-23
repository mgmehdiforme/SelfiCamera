"""Ubuntu AppIndicator and QSystemTrayIcon controller."""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from selficamera.capture.v4l2_devices import STANDARD_RESOLUTIONS, V4L2DeviceScanner, VideoDeviceInfo

logger = logging.getLogger(__name__)


def create_default_tray_icon() -> QIcon:
    """Generate a clean 64x64 neon circular camera icon."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Neon circle border
    painter.setPen(QColor(0, 229, 255, 230))
    painter.setBrush(QColor(30, 30, 46, 220))
    painter.drawEllipse(4, 4, 56, 56)

    # Camera body
    painter.setPen(QColor(255, 255, 255, 220))
    painter.setBrush(QColor(0, 229, 255, 180))
    painter.drawRoundedRect(18, 24, 28, 20, 3, 3)

    # Lens circle
    painter.setBrush(QColor(30, 30, 46, 255))
    painter.drawEllipse(26, 28, 12, 12)

    painter.end()
    return QIcon(pixmap)


class SystemTrayController(QObject):
    """Manages system tray icon, device selection menus, and action signals."""

    device_selected = Signal(str)
    resolution_selected = Signal(int, int)
    mirror_toggled = Signal(bool)
    auto_light_toggled = Signal(bool)
    blur_level_selected = Signal(int)
    ghost_mode_toggled = Signal(bool)
    settings_requested = Signal()
    reset_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._parent = parent

        self.tray_icon = QSystemTrayIcon(create_default_tray_icon(), parent)
        self.tray_icon.setToolTip("SelfiCamera - Presenter Bubble")

        self.menu = QMenu(parent)
        self._build_menu()
        self.tray_icon.setContextMenu(self.menu)

    def _build_menu(self) -> None:
        """Construct full tray context menu."""
        self.menu.clear()

        # Header status item
        self.action_header = QAction("● SelfiCamera (Active)", self.menu)
        self.action_header.setEnabled(False)
        self.menu.addAction(self.action_header)

        # Settings Action
        self.action_settings = QAction("⚙ Settings...", self.menu)
        self.action_settings.triggered.connect(self.settings_requested)
        self.menu.addAction(self.action_settings)
        self.menu.addSeparator()

        # Camera Device Submenu
        self.device_menu = self.menu.addMenu("Camera Device")
        self.device_action_group = QActionGroup(self.device_menu)
        self.device_action_group.setExclusive(True)
        self.populate_devices()

        # Resolution Submenu
        self.res_menu = self.menu.addMenu("Resolution")
        self.res_action_group = QActionGroup(self.res_menu)
        self.res_action_group.setExclusive(True)
        self._populate_resolutions()

        self.menu.addSeparator()

        # Mirror toggle
        self.action_mirror = QAction("Horizontal Mirror (Flip)", self.menu)
        self.action_mirror.setCheckable(True)
        self.action_mirror.setChecked(True)
        self.action_mirror.toggled.connect(self.mirror_toggled)
        self.menu.addAction(self.action_mirror)

        # Auto-Light Boost toggle
        self.action_light = QAction("Auto-Light Boost", self.menu)
        self.action_light.setCheckable(True)
        self.action_light.setChecked(True)
        self.action_light.toggled.connect(self.auto_light_toggled)
        self.menu.addAction(self.action_light)

        # Background Blur Submenu
        self.blur_menu = self.menu.addMenu("Background Blur")
        self.blur_action_group = QActionGroup(self.blur_menu)
        self.blur_action_group.setExclusive(True)
        self._populate_blur_tiers()

        # Ghost Mode toggle
        self.action_ghost = QAction("Click-Through Ghost Mode", self.menu)
        self.action_ghost.setCheckable(True)
        self.action_ghost.setChecked(False)
        self.action_ghost.toggled.connect(self.ghost_mode_toggled)
        self.menu.addAction(self.action_ghost)

        self.menu.addSeparator()

        # Reset & Quit
        self.action_reset = QAction("Reset Position & Size", self.menu)
        self.action_reset.triggered.connect(self.reset_requested)
        self.menu.addAction(self.action_reset)

        self.action_quit = QAction("Quit SelfiCamera", self.menu)
        self.action_quit.triggered.connect(self.quit_requested)
        self.menu.addAction(self.action_quit)

    def populate_devices(self, current_path: str = "/dev/video0") -> None:
        """Scan and populate available V4L2 cameras in the submenu."""
        self.device_menu.clear()
        devices = V4L2DeviceScanner.list_devices()

        if not devices:
            action = QAction("No cameras detected (Mock Mode)", self.device_menu)
            action.setEnabled(False)
            self.device_menu.addAction(action)
        else:
            for dev in devices:
                action = QAction(dev.display_name, self.device_menu)
                action.setCheckable(True)
                if dev.device_path == current_path:
                    action.setChecked(True)
                # Capture dev.device_path in closure
                action.triggered.connect(lambda checked, p=dev.device_path: self.device_selected.emit(p))
                self.device_action_group.addAction(action)
                self.device_menu.addAction(action)

        self.device_menu.addSeparator()
        action_refresh = QAction("Refresh Devices", self.device_menu)
        action_refresh.triggered.connect(lambda: self.populate_devices(current_path))
        self.device_menu.addAction(action_refresh)

    def _populate_resolutions(self) -> None:
        """Populate standard resolution options."""
        labels = {
            (640, 480): "640 x 480 (SD)",
            (1280, 720): "1280 x 720 (HD - Recommended)",
            (1920, 1080): "1920 x 1080 (FHD)",
        }
        for (w, h), label in labels.items():
            action = QAction(label, self.res_menu)
            action.setCheckable(True)
            if (w, h) == (1280, 720):
                action.setChecked(True)
            action.triggered.connect(lambda checked, width=w, height=h: self.resolution_selected.emit(width, height))
            self.res_action_group.addAction(action)
            self.res_menu.addAction(action)

    def _populate_blur_tiers(self) -> None:
        """Populate blur tier radio options."""
        tiers = [
            (0, "Level 0: Off"),
            (1, "Level 1: Subtle"),
            (2, "Level 2: Balanced"),
            (3, "Level 3: Heavy"),
        ]
        self._blur_actions = {}
        for level, label in tiers:
            action = QAction(label, self.blur_menu)
            action.setCheckable(True)
            if level == 2:
                action.setChecked(True)
            action.triggered.connect(lambda checked, lvl=level: self.blur_level_selected.emit(lvl))
            self.blur_action_group.addAction(action)
            self.blur_menu.addAction(action)
            self._blur_actions[level] = action

    def set_active_blur_level(self, level: int) -> None:
        """Sync check state of blur tier in menu."""
        if hasattr(self, "_blur_actions") and level in self._blur_actions:
            self._blur_actions[level].setChecked(True)

    def set_ghost_mode_checked(self, checked: bool) -> None:
        """Sync ghost mode checkbox."""
        self.action_ghost.blockSignals(True)
        self.action_ghost.setChecked(checked)
        self.action_ghost.blockSignals(False)

    def set_mirror_checked(self, checked: bool) -> None:
        """Sync mirror checkbox."""
        self.action_mirror.blockSignals(True)
        self.action_mirror.setChecked(checked)
        self.action_mirror.blockSignals(False)

    def set_light_checked(self, checked: bool) -> None:
        """Sync light checkbox."""
        self.action_light.blockSignals(True)
        self.action_light.setChecked(checked)
        self.action_light.blockSignals(False)

    def show(self) -> None:
        """Show system tray icon."""
        self.tray_icon.show()

    def hide(self) -> None:
        """Hide system tray icon."""
        self.tray_icon.hide()
