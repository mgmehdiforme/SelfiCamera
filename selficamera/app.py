"""Application controller and lifecycle manager for SelfiCamera."""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, Optional
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication

from selficamera.audio.voice_monitor import AudioMonitorWorker
from selficamera.capture.camera import CameraCaptureWorker
from selficamera.config import ConfigManager
from selficamera.processor.pipeline import FrameProcessor
from selficamera.shortcuts.manager import ShortcutManager
from selficamera.ui.overlay import OverlayWindow
from selficamera.ui.settings_panel import SettingsPanel
from selficamera.ui.tray import SystemTrayController

logger = logging.getLogger(__name__)


class SelfiCameraApp(QObject):
    """Main application orchestrator coordinating capture, processing, audio, UI, and shortcuts."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        mock_mode: bool = False,
        cli_overrides: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__()
        self.mock_mode = mock_mode
        self.config = ConfigManager(config_path)

        # Apply CLI overrides if present
        if cli_overrides:
            for k, v in cli_overrides.items():
                if v is not None:
                    self.config.set(k, v, auto_save=False)

        # Subsystems
        self.overlay: Optional[OverlayWindow] = None
        self.processor: Optional[FrameProcessor] = None
        self.capture_worker: Optional[CameraCaptureWorker] = None
        self.audio_worker: Optional[AudioMonitorWorker] = None
        self.tray: Optional[SystemTrayController] = None
        self.shortcuts: Optional[ShortcutManager] = None
        self.settings_panel: Optional[SettingsPanel] = None

    def get_state(self) -> Dict[str, Any]:
        """Return runtime state dictionary for IPC status queries."""
        return {
            "visible": self.overlay.isVisible() if self.overlay else False,
            "ghost_mode": self.overlay.is_ghost_mode if self.overlay else False,
            "always_on_top": self.overlay.is_always_on_top if self.overlay else self.config.get("always_on_top", True),
            "diameter": self.overlay.get_diameter() if self.overlay else self.config.get("diameter"),
            "blur_level": self.processor.blur_level if self.processor else self.config.get("blur_level"),
            "blur_intensity": self.processor.blur_intensity if self.processor else self.config.get("blur_intensity", 50),
            "mirror": self.processor.mirror_enabled if self.processor else self.config.get("mirror"),
            "auto_light": self.processor.auto_light_enabled if self.processor else self.config.get("auto_light"),
            "manual_gamma": self.processor.manual_gamma if self.processor else self.config.get("manual_gamma", 1.0),
            "target_luminance": self.processor.target_luminance if self.processor else self.config.get("target_luminance", 125.0),
            "device": self.config.get("device_path"),
            "resolution": self.config.get("resolution"),
            "fps": self.config.get("fps"),
            "settings_open": self.settings_panel.isVisible() if self.settings_panel else False,
        }

    def initialize(self) -> None:
        """Instantiate and connect all application components."""
        cfg = self.config.as_dict()

        # 1. Overlay Window
        pos = (cfg["x"], cfg["y"]) if "x" in cfg and "y" in cfg else None
        self.overlay = OverlayWindow(
            initial_diameter=cfg.get("diameter", 260),
            initial_pos=pos,
            always_on_top=cfg.get("always_on_top", True),
        )
        self.overlay.diameter_changed.connect(lambda d: self.config.set("diameter", d, auto_save=False))
        self.overlay.diameter_completed.connect(lambda d: self.config.set("diameter", d, auto_save=True))
        self.overlay.position_changed.connect(lambda x, y: self.config.update(auto_save=False, x=x, y=y))
        self.overlay.drag_completed.connect(lambda x, y: self.config.update(auto_save=True, x=x, y=y))
        self.overlay.always_on_top_changed.connect(lambda aot: self.config.set("always_on_top", aot))
        self.overlay.light_toggle_requested.connect(lambda: self.set_auto_light(not self.processor.auto_light_enabled))

        # 2. Image Processing Pipeline
        self.processor = FrameProcessor(
            mirror=cfg.get("mirror", True),
            auto_light=cfg.get("auto_light", True),
            blur_level=cfg.get("blur_level", 2),
            manual_gamma=cfg.get("manual_gamma", 1.0),
            target_luminance=cfg.get("target_luminance", 125.0),
            blur_intensity=cfg.get("blur_intensity", 50),
        )

        # 3. Settings Panel
        self.settings_panel = SettingsPanel()
        self._wire_settings_panel()

        # 4. Camera Capture Worker
        res = cfg.get("resolution", [1280, 720])
        self.capture_worker = CameraCaptureWorker(
            device_path=cfg.get("device_path", "/dev/video0"),
            width=res[0],
            height=res[1],
            fps=cfg.get("fps", 30),
            mock_mode=self.mock_mode,
        )
        self.capture_worker.frame_ready.connect(self._on_frame_ready)

        # 5. Audio Monitor Worker
        self.audio_worker = AudioMonitorWorker(
            device=None if cfg.get("mic_device") == "default" else cfg.get("mic_device"),
            mock_mode=self.mock_mode,
        )
        self.audio_worker.energy_updated.connect(self.overlay.update_voice_energy)

        # 6. System Tray & HUD wiring
        self.tray = SystemTrayController(self.overlay)
        self._wire_tray_and_hud()

        # 7. Shortcut & IPC Manager
        self.shortcuts = ShortcutManager(state_provider=self.get_state)
        self._wire_shortcuts()

        # Sync initial UI states
        self.overlay.hud.update_blur_label(self.processor.blur_level)
        self.tray.set_active_blur_level(self.processor.blur_level)
        self.tray.set_mirror_checked(self.processor.mirror_enabled)
        self.tray.set_light_checked(self.processor.auto_light_enabled)
        if cfg.get("click_through", False):
            self.overlay.set_click_through(True)
            self.tray.set_ghost_mode_checked(True)

    def _on_frame_ready(self, raw_frame) -> None:
        """Process incoming raw BGR frame and pass QImage to overlay."""
        if self.processor and self.overlay:
            qimg = self.processor.process_to_qimage(raw_frame)
            self.overlay.update_frame_image(qimg)

    def _wire_settings_panel(self) -> None:
        """Connect SettingsPanel signals bidirectionally with App, Overlay, and Processor."""
        assert self.settings_panel is not None and self.overlay is not None and self.processor is not None

        cfg = self.config.as_dict()

        # Initial UI values
        self.settings_panel.populate_devices(cfg.get("device_path", "/dev/video0"))
        self.settings_panel.set_diameter_value(cfg.get("diameter", 260))
        self.settings_panel.set_manual_gamma_value(cfg.get("manual_gamma", 1.0))
        self.settings_panel.set_target_luminance_value(cfg.get("target_luminance", 125.0))
        self.settings_panel.set_auto_light_checked(cfg.get("auto_light", True))
        self.settings_panel.set_blur_intensity_value(cfg.get("blur_intensity", 50))
        self.settings_panel.set_blur_tier_value(cfg.get("blur_level", 2))
        self.settings_panel.set_mirror_checked(cfg.get("mirror", True))
        self.settings_panel.set_always_on_top_checked(cfg.get("always_on_top", True))
        self.settings_panel.set_ghost_mode_checked(cfg.get("click_through", False))
        res = cfg.get("resolution", [1280, 720])
        self.settings_panel.set_resolution_selection(res[0], res[1])

        # Signal connections from SettingsPanel
        self.settings_panel.diameter_changed.connect(self.overlay.set_diameter)
        self.overlay.diameter_completed.connect(self.settings_panel.set_diameter_value)
        self.settings_panel.manual_gamma_changed.connect(self.set_manual_gamma)
        self.settings_panel.target_luminance_changed.connect(self.set_target_luminance)
        self.settings_panel.auto_light_toggled.connect(self.set_auto_light)
        self.settings_panel.blur_tier_selected.connect(self.set_blur_level)
        self.settings_panel.blur_intensity_changed.connect(self.set_blur_intensity)
        self.settings_panel.device_selected.connect(self.set_device)
        self.settings_panel.resolution_selected.connect(self.set_resolution)
        self.settings_panel.mirror_toggled.connect(self.set_mirror)
        self.settings_panel.always_on_top_toggled.connect(self.set_always_on_top)
        self.settings_panel.ghost_mode_toggled.connect(self.set_ghost_mode)
        self.settings_panel.corner_snap_requested.connect(self.overlay.snap_to_corner)
        self.settings_panel.reset_defaults_requested.connect(self.reset_to_defaults)

    def _wire_tray_and_hud(self) -> None:
        """Connect actions between Tray, HUD, Overlay, and Config."""
        assert self.tray is not None and self.overlay is not None and self.processor is not None

        # Tray signals
        self.tray.device_selected.connect(self.set_device)
        self.tray.resolution_selected.connect(self.set_resolution)
        self.tray.mirror_toggled.connect(self.set_mirror)
        self.tray.auto_light_toggled.connect(self.set_auto_light)
        self.tray.blur_level_selected.connect(self.set_blur_level)
        self.tray.ghost_mode_toggled.connect(self.set_ghost_mode)
        self.tray.settings_requested.connect(self.toggle_settings_panel)
        self.tray.reset_requested.connect(self.reset_layout)
        self.tray.quit_requested.connect(self.quit)

        # HUD signals
        self.overlay.hud.flip_clicked.connect(lambda: self.set_mirror(not self.processor.mirror_enabled))
        self.overlay.hud.blur_clicked.connect(self.cycle_blur)
        self.overlay.hud.light_clicked.connect(lambda: self.set_auto_light(not self.processor.auto_light_enabled))
        self.overlay.hud.ghost_clicked.connect(lambda: self.set_ghost_mode(not self.overlay.is_ghost_mode))
        self.overlay.hud.close_clicked.connect(self.quit)

        # Overlay settings request (emitted from HUD settings button or context menu)
        self.overlay.settings_requested.connect(self.toggle_settings_panel)

    def _wire_shortcuts(self) -> None:
        """Connect global shortcuts and IPC triggers."""
        assert self.shortcuts is not None and self.overlay is not None

        self.shortcuts.toggle_visibility_requested.connect(self.toggle_visibility)
        self.shortcuts.toggle_ghost_requested.connect(lambda: self.set_ghost_mode(not self.overlay.is_ghost_mode))
        self.shortcuts.toggle_settings_requested.connect(self.toggle_settings_panel)
        self.shortcuts.snap_corner_requested.connect(self.overlay.snap_to_corner)
        self.shortcuts.cycle_blur_requested.connect(self.cycle_blur)
        self.shortcuts.quit_requested.connect(self.quit)

    def toggle_settings_panel(self) -> None:
        """Toggle settings panel visibility alongside camera overlay."""
        if not self.settings_panel:
            return
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
        else:
            if self.overlay:
                self.settings_panel.position_alongside_overlay(self.overlay)
            self.settings_panel.show()
            self.settings_panel.raise_()
            self.settings_panel.activateWindow()

    def set_device(self, device_path: str) -> None:
        """Switch camera device."""
        res = self.config.get("resolution", [1280, 720])
        if self.capture_worker:
            self.capture_worker.change_device(device_path, res[0], res[1])
        if self.settings_panel:
            self.settings_panel.set_device_selection(device_path)
        self.config.set("device_path", device_path)
        logger.info("Switched camera device to %s", device_path)

    def set_resolution(self, width: int, height: int) -> None:
        """Switch capture resolution."""
        dev = self.config.get("device_path", "/dev/video0")
        if self.capture_worker:
            self.capture_worker.change_device(dev, width, height)
        if self.settings_panel:
            self.settings_panel.set_resolution_selection(width, height)
        self.config.set("resolution", [width, height])
        logger.info("Switched camera resolution to %dx%d", width, height)

    def set_mirror(self, enabled: bool) -> None:
        """Set horizontal mirror."""
        if self.processor:
            self.processor.mirror_enabled = enabled
        if self.tray:
            self.tray.set_mirror_checked(enabled)
        if self.settings_panel:
            self.settings_panel.set_mirror_checked(enabled)
        self.config.set("mirror", enabled)

    def set_auto_light(self, enabled: bool) -> None:
        """Set Auto-Light Boost."""
        if self.processor:
            self.processor.auto_light_enabled = enabled
        if self.tray:
            self.tray.set_light_checked(enabled)
        if self.settings_panel:
            self.settings_panel.set_auto_light_checked(enabled)
        self.config.set("auto_light", enabled)

    def set_manual_gamma(self, gamma: float) -> None:
        """Set manual brightness/gamma factor."""
        if self.processor:
            self.processor.set_manual_gamma(gamma)
        if self.settings_panel:
            self.settings_panel.set_manual_gamma_value(gamma)
        self.config.set("manual_gamma", gamma)

    def set_target_luminance(self, target: float) -> None:
        """Set target luminance for Auto-Light Boost."""
        if self.processor:
            self.processor.set_target_luminance(target)
        if self.settings_panel:
            self.settings_panel.set_target_luminance_value(target)
        self.config.set("target_luminance", target)

    def set_blur_intensity(self, intensity: int) -> None:
        """Set continuous background blur intensity."""
        if self.processor:
            self.processor.set_blur_intensity(intensity)
            tier = self.processor.blur_level
            if self.overlay and self.overlay.hud:
                self.overlay.hud.update_blur_label(tier)
            if self.tray:
                self.tray.set_active_blur_level(tier)
        if self.settings_panel:
            self.settings_panel.set_blur_intensity_value(intensity)
        self.config.update(auto_save=True, blur_intensity=intensity, blur_level=self.processor.blur_level if self.processor else 2)

    def set_blur_level(self, level: int) -> None:
        """Set background blur tier."""
        if self.processor:
            self.processor.set_blur_tier(level)
            intensity = self.processor.blur_intensity
        else:
            intensity = 50
        if self.overlay and self.overlay.hud:
            self.overlay.hud.update_blur_label(level)
        if self.tray:
            self.tray.set_active_blur_level(level)
        if self.settings_panel:
            self.settings_panel.set_blur_tier_value(level)
        self.config.update(auto_save=True, blur_level=level, blur_intensity=intensity)

    def cycle_blur(self) -> None:
        """Cycle blur tier to next level."""
        new_level = (self.processor.blur_level + 1) % 4
        self.set_blur_level(new_level)

    def set_ghost_mode(self, enabled: bool) -> None:
        """Set click-through Ghost Mode."""
        if self.overlay:
            self.overlay.set_click_through(enabled)
        if self.tray:
            self.tray.set_ghost_mode_checked(enabled)
        if self.settings_panel:
            self.settings_panel.set_ghost_mode_checked(enabled)
        self.config.set("click_through", enabled)

    def set_always_on_top(self, enabled: bool) -> None:
        """Set Always-On-Top window state."""
        if self.overlay:
            self.overlay.set_always_on_top(enabled)
        if self.settings_panel:
            self.settings_panel.set_always_on_top_checked(enabled)
        self.config.set("always_on_top", enabled)

    def reset_to_defaults(self) -> None:
        """Reset all configuration and settings to standard defaults."""
        self.config.reset_to_defaults()
        cfg = self.config.as_dict()
        self.set_device(cfg["device_path"])
        self.set_resolution(cfg["resolution"][0], cfg["resolution"][1])
        self.set_mirror(cfg["mirror"])
        self.set_auto_light(cfg["auto_light"])
        self.set_manual_gamma(cfg.get("manual_gamma", 1.0))
        self.set_target_luminance(cfg.get("target_luminance", 125.0))
        self.set_blur_intensity(cfg.get("blur_intensity", 50))
        self.set_always_on_top(cfg.get("always_on_top", True))
        self.set_ghost_mode(cfg.get("click_through", False))
        self.reset_layout()
        if self.settings_panel:
            self.settings_panel.set_diameter_value(260)

    def toggle_visibility(self) -> None:
        """Toggle overlay window visibility."""
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()
            self.overlay.raise_()

    def reset_layout(self) -> None:
        """Reset size to 260px and center on primary screen."""
        self.overlay.set_diameter(260)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.left() + (geo.width() - self.overlay.width()) // 2
            y = geo.top() + (geo.height() - self.overlay.height()) // 2
            self.overlay.move(x, y)

    def start(self) -> None:
        """Start workers, display overlay, and auto-open floating controls panel."""
        self.capture_worker.start()
        self.audio_worker.start()
        self.shortcuts.start()
        self.tray.show()
        self.overlay.show()
        if self.settings_panel:
            self.settings_panel.position_alongside_overlay(self.overlay)
            self.settings_panel.show()
            self.settings_panel.raise_()

    def quit(self) -> None:
        """Perform clean application shutdown."""
        logger.info("Initiating SelfiCamera shutdown...")
        if self.settings_panel:
            self.settings_panel.close()
        if self.shortcuts:
            self.shortcuts.stop()
        if self.capture_worker:
            self.capture_worker.stop()
        if self.audio_worker:
            self.audio_worker.stop()
        if self.tray:
            self.tray.hide()
        if self.overlay:
            self.overlay.close()
        self.config.save()
        app = QApplication.instance()
        if app:
            app.quit()
