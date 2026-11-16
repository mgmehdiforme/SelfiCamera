"""Quick-action menu (shared by the tray icon and the bubble's right-click menu)."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QObject, QPoint
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from selficamera.config import BACKGROUND_LABELS, BACKGROUND_MODES, SHAPE_LABELS, SHAPES, SIZE_PRESETS
from selficamera.ui import icons
from selficamera.ui.overlay import POSITION_LABELS
from selficamera.ui.theme import MENU_STYLESHEET


def populate_quick_menu(menu: QMenu, c: Any, include_visibility: bool = True) -> None:
    """Fill ``menu`` with actions reflecting the controller's current state."""
    menu.clear()
    menu.setStyleSheet(MENU_STYLESHEET)

    if include_visibility:
        visible = bool(c.get("visible"))
        act = menu.addAction(icons.icon("eye_off" if visible else "eye", 16), "Hide camera" if visible else "Show camera")
        act.triggered.connect(c.toggle_visibility)

    act = menu.addAction(icons.icon("sliders", 16), "Settings…")
    act.triggered.connect(lambda: c.open_settings())

    act = menu.addAction(icons.icon("spotlight", 16), "Exit spotlight" if c.in_spotlight() else "Spotlight")
    act.triggered.connect(c.toggle_spotlight)
    menu.addSeparator()

    bg_menu = menu.addMenu(icons.icon("background", 16), "Background")
    bg_menu.setStyleSheet(MENU_STYLESHEET)
    group = QActionGroup(bg_menu)
    current_bg = c.get("background_mode")
    for mode in BACKGROUND_MODES:
        a = bg_menu.addAction(BACKGROUND_LABELS[mode])
        a.setCheckable(True)
        a.setChecked(mode == current_bg)
        a.setActionGroup(group)
        a.triggered.connect(lambda _=False, m=mode: c.set("background_mode", m))

    shape_menu = menu.addMenu(icons.icon("shape", 16), "Shape")
    shape_menu.setStyleSheet(MENU_STYLESHEET)
    sgroup = QActionGroup(shape_menu)
    current_shape = c.get("shape")
    for shape in SHAPES:
        a = shape_menu.addAction(SHAPE_LABELS[shape])
        a.setCheckable(True)
        a.setChecked(shape == current_shape)
        a.setActionGroup(sgroup)
        a.triggered.connect(lambda _=False, s=shape: c.set("shape", s))
    shape_menu.addSeparator()
    for label, px in SIZE_PRESETS.items():
        a = shape_menu.addAction({"S": "Small", "M": "Medium", "L": "Large"}[label])
        a.triggered.connect(lambda _=False, v=px: c.set_size_animated(v))

    pos_menu = menu.addMenu(icons.icon("move", 16), "Move to")
    pos_menu.setStyleSheet(MENU_STYLESHEET)
    for pos, label in POSITION_LABELS.items():
        a = pos_menu.addAction(label)
        a.triggered.connect(lambda _=False, p=pos: c.snap(p))

    scenes = c.scene_names()
    scene_menu = menu.addMenu(icons.icon("layers", 16), "Scenes")
    scene_menu.setStyleSheet(MENU_STYLESHEET)
    if scenes:
        for name in scenes:
            a = scene_menu.addAction(name)
            a.triggered.connect(lambda _=False, n=name: c.apply_scene(n))
    else:
        a = scene_menu.addAction("No scenes yet — save one in Settings")
        a.setEnabled(False)

    menu.addSeparator()
    a = menu.addAction(icons.icon("flip", 16), "Mirror")
    a.setCheckable(True)
    a.setChecked(bool(c.get("mirror")))
    a.toggled.connect(lambda v: c.set("mirror", v))

    a = menu.addAction(icons.icon("pin", 16), "Always on top")
    a.setCheckable(True)
    a.setChecked(bool(c.get("always_on_top")))
    a.toggled.connect(lambda v: c.set("always_on_top", v))

    a = menu.addAction(icons.icon("ghost", 16), "Click-through")
    a.setCheckable(True)
    a.setChecked(bool(c.get("click_through")))
    a.toggled.connect(lambda v: c.set("click_through", v))

    menu.addSeparator()
    a = menu.addAction(icons.icon("power", 16), "Quit SelfiCamera")
    a.triggered.connect(c.quit)


class TrayController(QObject):
    """System tray icon. Left click shows/hides the camera; the menu has every quick action."""

    def __init__(self, controller: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.c = controller
        self.tray_icon = QSystemTrayIcon(icons.app_icon(), parent)
        self.tray_icon.setToolTip("SelfiCamera")
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.refresh)
        self.refresh()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_activated)

    @property
    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def refresh(self) -> None:
        populate_quick_menu(self.menu, self.c)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.c.toggle_visibility()

    def set_tooltip(self, text: str) -> None:
        self.tray_icon.setToolTip(text)

    def show(self) -> None:
        self.tray_icon.show()

    def hide(self) -> None:
        self.tray_icon.hide()


def exec_context_menu(controller: Any, global_pos: QPoint, parent: Optional[QWidget] = None) -> None:
    menu = QMenu(parent)
    populate_quick_menu(menu, controller)
    menu.exec(global_pos)
