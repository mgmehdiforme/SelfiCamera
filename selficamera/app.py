"""Application controller.

Every setting change, from the settings window, tray, hover controls, hotkeys or
IPC, goes through :meth:`SelfiCameraApp.set`. It validates the value, applies it
to the subsystem that owns it, emits :attr:`setting_changed` so all views resync,
and schedules a debounced save.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtWidgets import QApplication

from selficamera import desktop
from selficamera.audio.voice_monitor import AudioMonitorWorker, list_input_devices
from selficamera.capture.camera import CameraStatus, CameraWorker
from selficamera.capture.v4l2_devices import V4L2DeviceScanner
from selficamera.config import (
    DEFAULT_CONFIG,
    SCENE_KEYS,
    ConfigManager,
    validate_value,
)
from selficamera.processor.pipeline import PROCESSOR_KEYS, FrameProcessor
from selficamera.shortcuts.manager import ShortcutManager
from selficamera.ui.overlay import BubbleWindow
from selficamera.ui.tray import TrayController, exec_context_menu

logger = logging.getLogger(__name__)

SAVE_DELAY_MS = 600
CAMERA_KEYS = ("device_path", "resolution", "fps")
IPC_ACTIONS = {
    "ping",
    "get_status",
    "status",
    "toggle_visibility",
    "toggle",
    "show",
    "hide",
    "toggle_spotlight",
    "spotlight",
    "cycle_background",
    "cycle_blur",
    "toggle_mirror",
    "toggle_ghost",
    "toggle_settings",
    "settings",
    "snap",
    "snap_corner",
    "scene",
    "set",
    "quit",
    "exit",
}


class SelfiCameraApp(QObject):
    """Owns all subsystems and is the single source of truth for settings."""

    setting_changed = Signal(str, object)
    scenes_changed = Signal()

    def __init__(
        self,
        config_path: Optional[str] = None,
        mock_mode: bool = False,
        cli_overrides: Optional[Dict[str, Any]] = None,
        enable_tray: bool = True,
        enable_audio: bool = True,
        enable_shortcuts: bool = True,
        socket_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.mock_mode = mock_mode
        self.config = ConfigManager(config_path)
        for key, value in (cli_overrides or {}).items():
            try:
                self.config.set(key, value)
            except (KeyError, ValueError) as exc:
                logger.warning("Ignoring CLI override %s=%r: %s", key, value, exc)
        self._enable_tray = enable_tray
        self._enable_audio = enable_audio
        self._enable_shortcuts = enable_shortcuts
        self._socket_path = socket_path

        self.bubble: Optional[BubbleWindow] = None
        self.processor: Optional[FrameProcessor] = None
        self.camera: Optional[CameraWorker] = None
        self.audio: Optional[AudioMonitorWorker] = None
        self.tray: Optional[TrayController] = None
        self.shortcuts: Optional[ShortcutManager] = None
        self.settings_window = None
        self.gnome = desktop.GnomeShortcuts()
        self._camera_state: Tuple[str, str] = (CameraStatus.STARTING, "Starting camera…")
        self._fps = 0.0
        self._quitting = False
        self.limited_wayland = False  # set by __main__ when Qt runs as a native Wayland client

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self.config.save_if_dirty)

    # Backwards-compatible alias used by older tests/scripts.
    @property
    def overlay(self) -> Optional[BubbleWindow]:
        return self.bubble

    # ------------------------------------------------------------ lifecycle
    def initialize(self) -> None:
        cfg = self.config.as_dict()
        center = (cfg["x"], cfg["y"]) if cfg.get("x") is not None and cfg.get("y") is not None else None

        self.bubble = BubbleWindow(shape=cfg["shape"], size=cfg["size"], center=center, always_on_top=cfg["always_on_top"])
        self.bubble.set_border(cfg["border_width"], cfg["border_color"])
        self.bubble.set_voice_glow(cfg["voice_glow"])
        self.bubble.set_shadow(cfg["shadow"])
        self.bubble.set_controls_on_hover(cfg["show_controls_on_hover"])
        self.bubble.hud.set_background_mode(cfg["background_mode"])
        self._wire_bubble()
        if center is None:
            self.config.update(x=int(self.bubble.center.x()), y=int(self.bubble.center.y()))

        self.processor = FrameProcessor(settings=cfg, output_size=self.bubble.render_size or (cfg["size"], cfg["size"]))
        res = cfg["resolution"]
        self.camera = CameraWorker(self.processor, cfg["device_path"], res[0], res[1], cfg["fps"], mock_mode=self.mock_mode)
        self.camera.frame_available.connect(self._on_frame_available)
        self.camera.status_changed.connect(self._on_camera_status)
        self.camera.fps_measured.connect(self._on_fps)

        if self._enable_audio:
            self.audio = AudioMonitorWorker(device=cfg.get("mic_device"), mock_mode=self.mock_mode)
            self.audio.energy_updated.connect(self._on_voice_energy)

        if self._enable_tray:
            self.tray = TrayController(self)

        if self._enable_shortcuts:
            self.shortcuts = ShortcutManager(
                state_provider=self.get_state, socket_path=self._socket_path, validator=self.validate_ipc
            )
            self.shortcuts.action_requested.connect(self.dispatch)

        if cfg.get("click_through"):
            self.bubble.set_click_through(True)

    def _wire_bubble(self) -> None:
        b = self.bubble
        assert b is not None
        b.size_changed.connect(self._on_bubble_size)
        b.size_committed.connect(lambda _s: self._schedule_save())
        b.position_committed.connect(self._on_bubble_moved)
        b.render_size_changed.connect(self._on_render_size)
        b.settings_requested.connect(lambda: self.open_settings())
        b.context_menu_requested.connect(self._show_context_menu)
        b.hud.background_clicked.connect(self.cycle_background)
        b.hud.mirror_clicked.connect(lambda: self.set("mirror", not self.get("mirror")))
        b.hud.hide_clicked.connect(lambda: self.set("visible", False))

    def start(self) -> None:
        assert self.bubble and self.camera
        self.camera.start()
        if self.audio and self.config.get("voice_glow"):
            self.audio.start()
        if self.shortcuts:
            self.shortcuts.start()
        if self.tray:
            self.tray.show()
        self.config.set("visible", True)
        self.bubble.show()
        self.bubble.clamp_on_screen()
        if self.limited_wayland:
            self.bubble.show_toast("Limited mode — see Settings › General", 7000)
        if self.config.get("first_run"):
            self.config.set("first_run", False)
            self._schedule_save()
            self.bubble.show_toast("Drag to move · scroll to resize · right-click for options", 6000)
            QTimer.singleShot(400, lambda: self.open_settings())

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        logger.info("Shutting down…")
        self._save_timer.stop()
        if self.shortcuts:
            self.shortcuts.stop()
        if self.camera:
            self.camera.stop()
        if self.audio:
            self.audio.stop()
        if self.tray:
            self.tray.hide()
        if self.settings_window is not None:
            self.settings_window.hide()
        if self.bubble:
            self.bubble.hide()
        self.config.save()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # ------------------------------------------------------------- settings
    def get(self, key: str) -> Any:
        return self.config.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any) -> Any:
        """Validate, store, apply and broadcast a setting."""
        try:
            clean = self.config.set(key, value)
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Rejected setting %s=%r: %s", key, value, exc)
            return None
        self._apply(key, clean)
        self.setting_changed.emit(key, clean)
        self._schedule_save()
        return clean

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _apply(self, key: str, value: Any) -> None:
        b, proc = self.bubble, self.processor
        if key in PROCESSOR_KEYS and proc is not None:
            proc.configure(**{key: value})
        if b is None:
            return
        if key in CAMERA_KEYS and self.camera is not None:
            res = self.config.get("resolution")
            self.camera.change_source(self.config.get("device_path"), res[0], res[1], self.config.get("fps"))
        elif key == "shape":
            b.set_shape(value)
            b.clamp_on_screen()
        elif key == "size":
            if b.size_value != value:
                b.set_size(value)
        elif key in ("x", "y"):
            x, y = self.config.get("x"), self.config.get("y")
            if x is not None and y is not None and (int(b.center.x()), int(b.center.y())) != (x, y):
                b.move_center_to(x, y)
        elif key in ("border_width", "border_color"):
            b.set_border(self.config.get("border_width"), self.config.get("border_color"))
        elif key == "voice_glow":
            b.set_voice_glow(value)
            if self.audio is not None:
                if value and not self.audio.isRunning():
                    self.audio.start()
                elif not value and self.audio.isRunning():
                    self.audio.stop()
                    b.set_voice_energy(0.0)
        elif key == "mic_device":
            if self.audio is not None and self.config.get("voice_glow"):
                self.audio.restart_with_device(value)
            elif self.audio is not None:
                self.audio.device = value
        elif key == "shadow":
            b.set_shadow(value)
        elif key == "always_on_top":
            b.set_always_on_top(value)
        elif key == "click_through":
            b.set_click_through(value)
            if value:
                b.show_toast("Click-through is on. Turn it off from the tray icon or Super+Alt+X.", 4500)
        elif key == "show_controls_on_hover":
            b.set_controls_on_hover(value)
        elif key == "visible":
            if value:
                b.show()
                b.raise_()
            else:
                b.hide()
            if self.camera is not None:
                self.camera.set_paused(not value)
        elif key == "background_mode":
            b.hud.set_background_mode(value)
            if value == "image" and not self.config.get("background_image"):
                b.show_toast("Choose an image in Settings → Background", 3000)

    # ----------------------------------------------------------- callbacks
    def _on_bubble_size(self, size: int) -> None:
        if self.bubble is not None and self.bubble.in_spotlight:
            return
        if self.config.get("size") != size:
            self.config.set("size", size)
            self.setting_changed.emit("size", size)

    def _on_bubble_moved(self, cx: int, cy: int) -> None:
        if self.bubble is not None and self.bubble.in_spotlight:
            return
        self.config.update(x=cx, y=cy)
        self._schedule_save()

    def _on_render_size(self, w: int, h: int) -> None:
        if self.processor is not None:
            self.processor.set_output_size(w, h)

    def _on_frame_available(self) -> None:
        if self.camera is not None and self.bubble is not None:
            img = self.camera.take_frame()
            if img is not None:
                self.bubble.set_frame(img)

    def _on_camera_status(self, state: str, message: str) -> None:
        self._camera_state = (state, message)
        if self.bubble is not None:
            self.bubble.set_status(state, message)
        if self.tray is not None:
            self.tray.set_tooltip("SelfiCamera" + (f" — {message.splitlines()[0]}" if message else ""))
        self._update_settings_status()

    def _on_fps(self, fps: float) -> None:
        self._fps = fps
        self._update_settings_status()

    def _update_settings_status(self) -> None:
        if self.settings_window is None:
            return
        state, message = self._camera_state
        if state == CameraStatus.LIVE:
            res = self.camera.actual_resolution if self.camera else (0, 0)
            ms = self.processor.last_timings.get("total_ms", 0.0) if self.processor else 0.0
            text = f"● Live · {res[0]}×{res[1]} · {self._fps:.0f} fps · {ms:.1f} ms per frame"
        else:
            text = message.replace("\n", " ")
        self.settings_window.set_camera_status(text)

    def _on_voice_energy(self, energy: float) -> None:
        if self.bubble is not None:
            self.bubble.set_voice_energy(energy)

    def _show_context_menu(self, pos: QPoint) -> None:
        exec_context_menu(self, pos, self.bubble)

    # --------------------------------------------------------------- actions
    def toggle_visibility(self) -> None:
        self.set("visible", not (self.bubble.isVisible() if self.bubble else self.get("visible")))

    def open_settings(self, page: Optional[str] = None) -> None:
        if self.settings_window is None:
            from selficamera.ui.settings_window import SettingsWindow

            self.settings_window = SettingsWindow(self)
            self.scenes_changed.connect(self.settings_window.refresh_scenes)
            self._update_settings_status()
        self.settings_window.open(page)

    def toggle_settings(self) -> None:
        if self.settings_window is not None and self.settings_window.isVisible():
            self.settings_window.hide()
        else:
            self.open_settings()

    def in_spotlight(self) -> bool:
        return bool(self.bubble and self.bubble.in_spotlight)

    def toggle_spotlight(self) -> None:
        if self.bubble is None:
            return
        if not self.bubble.isVisible():
            self.set("visible", True)
        self.bubble.toggle_spotlight(self.get("spotlight_scale"))

    def snap(self, position: int) -> None:
        if self.bubble is not None:
            self.bubble.snap_to(int(position))

    def set_size_animated(self, size: int) -> None:
        if self.bubble is not None:
            self.bubble.set_size(int(size), animate=True)

    def background_cycle_order(self) -> List[str]:
        order = ["none", "blur", "color"]
        if self.get("background_image"):
            order.append("image")
        order.append("remove")
        return order

    def cycle_background(self) -> str:
        order = self.background_cycle_order()
        current = self.get("background_mode")
        nxt = order[(order.index(current) + 1) % len(order)] if current in order else "blur"
        self.set("background_mode", nxt)
        return nxt

    def reset_framing(self) -> None:
        for key in ("zoom", "pan_x", "pan_y", "auto_frame"):
            self.set(key, DEFAULT_CONFIG[key])

    def reset_light(self) -> None:
        for key in ("auto_light", "brightness", "contrast", "saturation", "warmth"):
            self.set(key, DEFAULT_CONFIG[key])

    def reset_enhance(self) -> None:
        for key in ("denoise", "soft_skin", "sharpen"):
            self.set(key, DEFAULT_CONFIG[key])

    def reset_all(self) -> None:
        self.config.reset_to_defaults(auto_save=False)
        cfg = self.config.as_dict()
        for key, value in cfg.items():
            if key in ("scenes", "first_run", "version", "visible", "x", "y"):
                continue
            self._apply(key, value)
            self.setting_changed.emit(key, value)
        self.snap(4)
        self._schedule_save()

    # ---------------------------------------------------------------- scenes
    def scene_names(self) -> List[str]:
        return self.config.scene_names()

    def save_scene(self, name: str) -> None:
        if self.bubble is not None and not self.bubble.in_spotlight:
            self.config.update(x=int(self.bubble.center.x()), y=int(self.bubble.center.y()))
        self.config.save_scene(name)
        self._schedule_save()
        self.scenes_changed.emit()

    def delete_scene(self, name: str) -> None:
        if self.config.delete_scene(name):
            self._schedule_save()
            self.scenes_changed.emit()

    def apply_scene(self, name: str) -> bool:
        scene = self.config.get_scene(name)
        if scene is None or self.bubble is None:
            return False
        b = self.bubble
        if b.in_spotlight:
            b._leave_spotlight_silently()
        geometry = {k: scene.pop(k) for k in ("x", "y", "size") if k in scene}
        if "shape" in scene:
            self.set("shape", scene.pop("shape"))
        for key in SCENE_KEYS:
            if key in scene:
                self.set(key, scene[key])
        size = int(geometry.get("size", b.size_value))
        x, y = geometry.get("x"), geometry.get("y")
        if x is not None and y is not None:
            from PySide6.QtCore import QPointF

            target = QPointF(x, y)
            if not b._point_on_any_screen(target):
                target = b.snap_target(4, size)
            b._animate_to(target, size, commit_size=True, duration=360)
        else:
            b.set_size(size, animate=True)
        logger.info("Applied scene %s", name)
        return True

    # ---------------------------------------------------------- integration
    def camera_devices(self) -> List[Tuple[str, str]]:
        if self.mock_mode:
            return [("/dev/video0", "Demo camera (mock)")]
        return [(d.device_path, d.card_name) for d in V4L2DeviceScanner.list_devices()]

    def mic_devices(self) -> List[Tuple[str, str]]:
        return [] if self.mock_mode else list_input_devices()

    def model_info(self) -> Tuple[bool, str]:
        if self.processor is None:
            return False, ""
        seg = self.processor.segmentation
        return seg.is_neural, seg.model_name

    def auto_light_source(self) -> str:
        return self.processor.auto_light_source if self.processor is not None else "center"

    def gnome_shortcuts_state(self) -> Tuple[bool, bool, str]:
        return self.gnome.state()

    def install_gnome_shortcuts(self) -> Tuple[bool, str]:
        return self.gnome.install()

    def remove_gnome_shortcuts(self) -> Tuple[bool, str]:
        return self.gnome.remove()

    def autostart_enabled(self) -> bool:
        return desktop.autostart_enabled()

    def set_autostart(self, enabled: bool) -> bool:
        return desktop.set_autostart(enabled)

    def config_path(self) -> str:
        return str(self.config.path)

    def log_path(self) -> str:
        return str(desktop.log_path())

    # ------------------------------------------------------------------- IPC
    def get_state(self) -> Dict[str, Any]:
        cfg = self.config.as_dict()
        state = {k: cfg[k] for k in cfg if k not in ("scenes", "version", "first_run")}
        state.update(
            {
                "visible": bool(self.bubble.isVisible()) if self.bubble else False,
                "spotlight": self.in_spotlight(),
                "camera_state": self._camera_state[0],
                "camera_message": self._camera_state[1],
                "fps": round(self._fps, 1),
                "segmentation": self.model_info()[1],
                "auto_light_source": self.auto_light_source(),
                "scenes": self.scene_names(),
            }
        )
        return state

    def validate_ipc(self, action: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        if action not in IPC_ACTIONS:
            return False, f"Unknown action '{action}'"
        if action == "set":
            key = params.get("key")
            try:
                validate_value(str(key), params.get("value"))
            except (KeyError, ValueError, TypeError) as exc:
                return False, f"Invalid setting: {exc}"
            if key in ("scenes", "version"):
                return False, f"'{key}' cannot be set from the command line"
        if action == "scene" and params.get("name") not in self.config.scene_names():
            names = ", ".join(self.config.scene_names()) or "none saved"
            return False, f"No scene named '{params.get('name')}' (available: {names})"
        if action in ("snap", "snap_corner"):
            pos = params.get("position", params.get("corner"))
            if pos not in (1, 2, 3, 4, 5):
                return False, "position must be 1-5"
        return True, ""

    def dispatch(self, action: str, params: Dict[str, Any]) -> None:
        logger.debug("Action %s %s", action, params)
        if action in ("toggle_visibility", "toggle"):
            self.toggle_visibility()
        elif action == "show":
            self.set("visible", True)
        elif action == "hide":
            self.set("visible", False)
        elif action in ("toggle_spotlight", "spotlight"):
            self.toggle_spotlight()
        elif action in ("cycle_background", "cycle_blur"):
            self.cycle_background()
        elif action == "toggle_mirror":
            self.set("mirror", not self.get("mirror"))
        elif action == "toggle_ghost":
            self.set("click_through", not self.get("click_through"))
        elif action in ("toggle_settings", "settings"):
            self.toggle_settings()
        elif action in ("snap", "snap_corner"):
            self.snap(int(params.get("position", params.get("corner", 4))))
        elif action == "scene":
            self.apply_scene(str(params.get("name")))
        elif action == "set":
            self.set(str(params.get("key")), params.get("value"))
        elif action in ("quit", "exit"):
            QTimer.singleShot(50, self.quit)
