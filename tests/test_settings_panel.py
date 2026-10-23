"""Tests for Floating SettingsPanel, UI controls, signal wiring, and pipeline setters."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication

from selficamera.app import SelfiCameraApp
from selficamera.processor.pipeline import FrameProcessor
from selficamera.ui.overlay import OverlayWindow
from selficamera.ui.settings_panel import SettingsPanel


def test_settings_panel_window_flags_and_properties(qtbot):
    """Verify SettingsPanel initializes as a top-level stay-on-top frameless tool window."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    flags = panel.windowFlags()
    assert bool(flags & Qt.WindowType.Tool) is True
    assert bool(flags & Qt.WindowType.FramelessWindowHint) is True
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint) is True
    assert panel.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is True
    assert panel.width() == 330


def test_settings_panel_lighting_controls(qtbot):
    """Verify Auto-Light toggle, Gamma slider, and Target Luminance slider emit expected signals."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    signals_received = {
        "auto_light": None,
        "gamma": None,
        "luminance": None,
    }
    panel.auto_light_toggled.connect(lambda val: signals_received.update(auto_light=val))
    panel.manual_gamma_changed.connect(lambda val: signals_received.update(gamma=val))
    panel.target_luminance_changed.connect(lambda val: signals_received.update(luminance=val))

    # 1. Toggle Auto-Light CheckBox
    panel.cb_auto_light.setChecked(False)
    assert signals_received["auto_light"] is False
    panel.cb_auto_light.setChecked(True)
    assert signals_received["auto_light"] is True

    # 2. Adjust Gamma Slider (40-220 -> 0.40x to 2.20x)
    panel.slider_gamma.setValue(150)
    assert abs(signals_received["gamma"] - 1.50) < 0.001
    assert panel.lbl_gamma.text() == "1.50x"

    # Reset Gamma Button
    panel.btn_gamma_reset.click()
    assert abs(signals_received["gamma"] - 1.00) < 0.001
    assert panel.lbl_gamma.text() == "1.00x"
    assert panel.slider_gamma.value() == 100

    # 3. Adjust Target Luminance Slider (50-220)
    panel.slider_luminance.setValue(160)
    assert abs(signals_received["luminance"] - 160.0) < 0.001
    assert panel.lbl_luminance.text() == "160"


def test_settings_panel_blur_controls_bidirectional_sync(qtbot):
    """Verify bidirectional synchronization between tier buttons and intensity slider without loops."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    tiers_emitted = []
    intensities_emitted = []
    panel.blur_tier_selected.connect(tiers_emitted.append)
    panel.blur_intensity_changed.connect(intensities_emitted.append)

    # 1. Click 'Off' button (tier 0) -> should set slider to 0
    panel.blur_buttons[0].click()
    assert panel.slider_blur.value() == 0
    assert panel.lbl_blur.text() == "0%"
    assert 0 in tiers_emitted
    assert 0 in intensities_emitted

    # 2. Click 'Heavy' button (tier 3) -> should set slider to 85
    panel.blur_buttons[3].click()
    assert panel.slider_blur.value() == 85
    assert panel.lbl_blur.text() == "85%"
    assert 3 in tiers_emitted
    assert 85 in intensities_emitted

    # 3. Move slider to 25 -> button should switch to Subtle (tier 1)
    panel.slider_blur.setValue(25)
    assert panel.blur_buttons[1].isChecked() is True
    assert panel.lbl_blur.text() == "25%"
    assert 1 in tiers_emitted

    # 4. Move slider to 50 -> button should switch to Balanced (tier 2)
    panel.slider_blur.setValue(50)
    assert panel.blur_buttons[2].isChecked() is True
    assert panel.lbl_blur.text() == "50%"
    assert 2 in tiers_emitted


def test_settings_panel_size_controls(qtbot):
    """Verify continuous diameter slider and preset buttons."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    diameters = []
    panel.diameter_changed.connect(diameters.append)

    # Live slider adjustment
    panel.slider_diameter.setValue(320)
    assert diameters[-1] == 320
    assert panel.lbl_diameter.text() == "320 px"

    # External setter without loop
    panel.set_diameter_value(200)
    assert panel.slider_diameter.value() == 200
    assert panel.lbl_diameter.text() == "200 px"


def test_settings_panel_camera_and_window_controls(qtbot):
    """Verify camera options, mirror, always-on-top, and ghost mode controls."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    signals_received = {}
    panel.mirror_toggled.connect(lambda v: signals_received.update(mirror=v))
    panel.always_on_top_toggled.connect(lambda v: signals_received.update(aot=v))
    panel.ghost_mode_toggled.connect(lambda v: signals_received.update(ghost=v))
    panel.resolution_selected.connect(lambda w, h: signals_received.update(res=(w, h)))
    panel.reset_defaults_requested.connect(lambda: signals_received.update(reset=True))

    # Mirror toggle
    panel.cb_mirror.setChecked(False)
    assert signals_received["mirror"] is False
    panel.cb_mirror.setChecked(True)
    assert signals_received["mirror"] is True

    # Always-On-Top toggle
    panel.cb_always_on_top.setChecked(False)
    assert signals_received["aot"] is False
    panel.cb_always_on_top.setChecked(True)
    assert signals_received["aot"] is True

    # Ghost mode toggle
    panel.cb_ghost_mode.setChecked(True)
    assert signals_received["ghost"] is True

    # Resolution selection
    panel.combo_res.setCurrentIndex(0)
    panel.combo_res.activated.emit(0)
    assert signals_received["res"] == (640, 480)

    # Reset defaults button
    panel.btn_reset_defaults.click()
    assert signals_received["reset"] is True

    # Close button hides panel
    panel.show()
    assert panel.isVisible() is True
    panel.btn_footer_close.click()
    assert panel.isVisible() is False


def test_settings_panel_position_alongside_overlay(qtbot):
    """Verify panel docks to right of overlay, flipping to left if overflow, and clamps to screen."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    screen = QApplication.primaryScreen()
    avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    # 1. Overlay on left side -> docks to right (x + w + 12)
    overlay.move(avail.left() + 100, avail.top() + 100)
    panel.position_alongside_overlay(overlay)
    expected_x = overlay.x() + overlay.width() + 12
    assert panel.x() == expected_x

    # 2. Overlay near right edge -> flips to left
    overlay.move(avail.right() - overlay.width() - 50, avail.top() + 100)
    panel.position_alongside_overlay(overlay)
    assert panel.x() < overlay.x()
    assert panel.x() >= avail.left()


def test_top_level_decoupling_with_ghost_mode(qtbot):
    """Verify SettingsPanel remains fully interactive and clickable even when Overlay is in Ghost Mode."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    # Put camera bubble into Ghost Mode
    overlay.set_click_through(True)
    assert overlay.is_ghost_mode is True
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True

    # SettingsPanel is decoupled top-level window and must NOT be transparent for mouse events
    assert panel.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False

    clicked = []
    panel.btn_gamma_reset.clicked.connect(lambda: clicked.append(True))
    panel.slider_gamma.setValue(180)
    panel.btn_gamma_reset.click()
    assert len(clicked) == 1
    assert panel.slider_gamma.value() == 100


def test_app_settings_panel_bidirectional_integration(qtbot, tmp_path):
    """Verify end-to-end integration between SelfiCameraApp, SettingsPanel, Overlay, Tray, and Processor."""
    cfg_file = tmp_path / "test_config.json"
    app = SelfiCameraApp(config_path=str(cfg_file), mock_mode=True)
    app.initialize()

    qtbot.addWidget(app.overlay)
    qtbot.addWidget(app.settings_panel)

    # 1. Toggle visibility from app
    assert app.settings_panel.isVisible() is False
    app.toggle_settings_panel()
    assert app.settings_panel.isVisible() is True
    app.toggle_settings_panel()
    assert app.settings_panel.isVisible() is False

    # 2. Toggle visibility from HUD settings button
    app.overlay.hud.btn_settings.click()
    assert app.settings_panel.isVisible() is True

    # 3. Settings panel gamma slider -> pipeline & config
    app.settings_panel.slider_gamma.setValue(140)
    assert abs(app.processor.manual_gamma - 1.40) < 0.01
    assert abs(app.config.get("manual_gamma") - 1.40) < 0.01

    # 4. Settings panel blur slider -> pipeline & HUD readout & config
    app.settings_panel.slider_blur.setValue(85)
    assert app.processor.blur_intensity == 85
    assert app.processor.blur_level == 3
    assert app.overlay.hud.btn_blur.text() == "B:Hvy"
    assert app.config.get("blur_intensity") == 85
    assert app.config.get("blur_level") == 3

    # 5. Settings panel diameter slider -> overlay geometry & config
    app.settings_panel.slider_diameter.setValue(300)
    assert app.overlay.get_diameter() == 300
    assert app.config.get("diameter") == 300

    # 6. Reset defaults from settings panel
    app.settings_panel.btn_reset_defaults.click()
    assert app.overlay.get_diameter() == 260
    assert app.processor.blur_level == 2
    assert app.processor.blur_intensity == 50
    assert abs(app.processor.manual_gamma - 1.0) < 0.01

    app.quit()


def test_processor_manual_gamma_and_intensity_processing(dark_frame):
    """Verify FrameProcessor applies manual gamma and continuous blur intensity correctly."""
    proc = FrameProcessor(mirror=False, auto_light=False, blur_level=2, manual_gamma=1.0)

    # 1. Neutral manual gamma with auto_light off -> frame unmodified
    res1 = proc.process(dark_frame)
    # cropped square
    cropped = proc.crop_center_square(dark_frame)
    # blur was on level 2 so check with blur off
    proc.blur_level = 0
    res_bypass = proc.process(dark_frame)
    import numpy as np
    np.testing.assert_array_equal(res_bypass, cropped)

    # 2. Modify manual gamma to 0.50 (brighter) with auto_light off
    proc.set_manual_gamma(0.50)
    res_boosted = proc.process(dark_frame)
    assert float(np.mean(res_boosted)) > float(np.mean(cropped))

    # 3. Blur intensity scaling
    proc.set_blur_intensity(75)
    assert proc.blur_intensity == 75
    assert proc.blur_level == 3
    qimg = proc.process_to_qimage(dark_frame)
    assert not qimg.isNull()


def test_overlay_context_menu_settings_request(qtbot, monkeypatch):
    """Verify right-click contextMenuEvent on overlay emits settings_requested."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)

    signals_emitted = []
    overlay.settings_requested.connect(lambda: signals_emitted.append(True))

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QContextMenuEvent
    ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(50, 50), QPoint(100, 100))

    import selficamera.ui.overlay as overlay_mod
    orig_qmenu = overlay_mod.QMenu

    class MockMenu(orig_qmenu):
        def exec(self, *args, **kwargs):
            for act in self.actions():
                if "Settings" in act.text():
                    act.trigger()
                    break
            return None

    monkeypatch.setattr(overlay_mod, "QMenu", MockMenu)
    overlay.contextMenuEvent(ev)

    assert len(signals_emitted) == 1


def test_settings_panel_dragging_movement(qtbot):
    """Verify dragging the SettingsPanel header repositions the window."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.move(100, 100)
    panel.show()

    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF

    # Mouse press at (20, 10) relative to panel
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(20, 10),
        QPointF(120, 110),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    panel.mousePressEvent(press_ev)
    assert panel._dragging_panel is True

    # Mouse move to global (170, 160) -> dx = +50, dy = +50
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(70, 60),
        QPointF(170, 160),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    panel.mouseMoveEvent(move_ev)
    assert panel.pos() == QPoint(150, 150)

    # Mouse release
    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(70, 60),
        QPointF(170, 160),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    panel.mouseReleaseEvent(release_ev)
    assert panel._dragging_panel is False


def test_tray_settings_action_triggers_panel(qtbot, tmp_path):
    """Verify tray settings action opens and toggles SettingsPanel."""
    cfg_file = tmp_path / "test_tray_cfg.json"
    app = SelfiCameraApp(config_path=str(cfg_file), mock_mode=True)
    app.initialize()

    qtbot.addWidget(app.overlay)
    qtbot.addWidget(app.settings_panel)

    assert app.settings_panel.isVisible() is False
    app.tray.action_settings.trigger()
    assert app.settings_panel.isVisible() is True
    app.tray.action_settings.trigger()
    assert app.settings_panel.isVisible() is False

    app.quit()


def test_settings_panel_corner_snap_buttons_render(qtbot):
    """Verify that SettingsPanel renders the 4 corner snapping buttons in Card 5 with correct text and tooltips."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    assert hasattr(panel, "btn_snap_tl")
    assert hasattr(panel, "btn_snap_tr")
    assert hasattr(panel, "btn_snap_bl")
    assert hasattr(panel, "btn_snap_br")

    assert panel.btn_snap_tl.text() == "↖ TL"
    assert panel.btn_snap_tr.text() == "↗ TR"
    assert panel.btn_snap_bl.text() == "↙ BL"
    assert panel.btn_snap_br.text() == "↘ BR"

    assert "Top-Left" in panel.btn_snap_tl.toolTip()
    assert "Top-Right" in panel.btn_snap_tr.toolTip()
    assert "Bottom-Left" in panel.btn_snap_bl.toolTip()
    assert "Bottom-Right" in panel.btn_snap_br.toolTip()


def test_settings_panel_corner_snap_signals(qtbot):
    """Verify that clicking each corner snap button emits corner_snap_requested and alias with proper ID."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    emitted_ids = []
    alias_emitted_ids = []
    panel.corner_snap_requested.connect(emitted_ids.append)
    panel.snap_corner_requested.connect(alias_emitted_ids.append)

    panel.btn_snap_tl.click()
    assert emitted_ids[-1] == 1
    assert alias_emitted_ids[-1] == 1

    panel.btn_snap_tr.click()
    assert emitted_ids[-1] == 2
    assert alias_emitted_ids[-1] == 2

    panel.btn_snap_bl.click()
    assert emitted_ids[-1] == 3
    assert alias_emitted_ids[-1] == 3

    panel.btn_snap_br.click()
    assert emitted_ids[-1] == 4
    assert alias_emitted_ids[-1] == 4


def test_app_settings_panel_corner_snap_integration(qtbot, tmp_path):
    """Verify end-to-end integration: clicking SettingsPanel snap button moves OverlayWindow."""
    cfg_file = tmp_path / "test_corner_cfg.json"
    app = SelfiCameraApp(config_path=str(cfg_file), mock_mode=True)
    app.initialize()

    qtbot.addWidget(app.overlay)
    qtbot.addWidget(app.settings_panel)

    screen = QApplication.primaryScreen()
    avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
    margin = 24

    # 1. Snap Top-Left (1)
    app.settings_panel.btn_snap_tl.click()
    qtbot.wait(250)
    expected_tl = QPoint(avail.left() + margin, avail.top() + margin)
    assert app.overlay.pos() == expected_tl

    # 2. Snap Top-Right (2)
    app.settings_panel.btn_snap_tr.click()
    qtbot.wait(250)
    expected_tr = QPoint(avail.right() - app.overlay.width() - margin + 1, avail.top() + margin)
    assert app.overlay.pos() == expected_tr

    # 3. Snap Bottom-Right (4)
    app.settings_panel.btn_snap_br.click()
    qtbot.wait(250)
    expected_br = QPoint(
        avail.right() - app.overlay.width() - margin + 1,
        avail.bottom() - app.overlay.height() - margin + 1,
    )
    assert app.overlay.pos() == expected_br

    # 4. Snap Bottom-Left (3)
    app.settings_panel.btn_snap_bl.click()
    qtbot.wait(250)
    expected_bl = QPoint(avail.left() + margin, avail.bottom() - app.overlay.height() - margin + 1)
    assert app.overlay.pos() == expected_bl

    # 5. Snap Center (5)
    app.settings_panel.btn_snap_center.click()
    qtbot.wait(250)
    expected_center_x = avail.left() + (avail.width() - app.overlay.width()) // 2
    expected_center_y = avail.top() + (avail.height() - app.overlay.height()) // 2
    assert abs(app.overlay.pos().x() - expected_center_x) <= 2
    assert abs(app.overlay.pos().y() - expected_center_y) <= 2

    app.quit()


def test_settings_panel_size_step_buttons(qtbot):
    """Verify that [-] and [+] step buttons in Card 3 decrement and increment diameter slider."""
    panel = SettingsPanel()
    qtbot.addWidget(panel)

    panel.slider_diameter.setValue(260)
    assert panel.slider_diameter.value() == 260

    panel.btn_size_minus.click()
    assert panel.slider_diameter.value() == 235

    panel.btn_size_plus.click()
    assert panel.slider_diameter.value() == 260


def test_app_start_auto_opens_settings_panel(qtbot, tmp_path):
    """Verify that starting SelfiCamera auto-opens the floating settings panel docked alongside."""
    cfg_file = tmp_path / "test_start_cfg.json"
    app = SelfiCameraApp(config_path=str(cfg_file), mock_mode=True)
    app.initialize()

    qtbot.addWidget(app.overlay)
    qtbot.addWidget(app.settings_panel)

    assert app.settings_panel.isVisible() is False
    app.start()
    assert app.overlay.isVisible() is True
    assert app.settings_panel.isVisible() is True

    app.quit()


