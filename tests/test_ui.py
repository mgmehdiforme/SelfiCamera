"""Bubble window, settings window and app controller (headless Qt)."""

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QApplication

from selficamera.config import ConfigManager
from selficamera.ui.overlay import BOTTOM_RIGHT, CENTER, MARGIN, TOP_LEFT, BubbleWindow
from selficamera.ui.shapes import content_size, edge_distance_px, normalized_distance, shape_path


# ------------------------------------------------------------------ shapes
@pytest.mark.parametrize("shape,expected", [("circle", (260, 260)), ("rounded", (260, 260)), ("landscape", (462, 260)), ("portrait", (260, 462))])
def test_content_size(shape, expected):
    assert content_size(shape, 260) == expected


def test_edge_metrics():
    rect = QRectF(0, 0, 200, 200)
    assert abs(normalized_distance("circle", rect, QPointF(200, 100)) - 1.0) < 1e-6
    assert edge_distance_px("circle", rect, QPointF(100, 100)) == -100
    assert abs(edge_distance_px("rounded", rect, QPointF(205, 100)) - 5) < 1e-6
    assert shape_path("circle", rect).contains(QPointF(100, 100))


# ------------------------------------------------------------------ bubble
@pytest.fixture
def bubble(qtbot):
    b = BubbleWindow(shape="circle", size=260)
    qtbot.addWidget(b)
    b.show()
    return b


def test_bubble_geometry_includes_margin(bubble):
    assert bubble.width() == 260 + 2 * MARGIN
    assert bubble.render_size[0] >= 260


def test_resize_keeps_center(bubble):
    c0 = bubble.center
    bubble.set_size(400)
    assert bubble.size_value == 400
    assert abs(bubble.center.x() - c0.x()) < 1 and abs(bubble.center.y() - c0.y()) < 1
    bubble.set_size(10_000)
    assert bubble.size_value == 800


def test_shape_change_keeps_center_and_updates_render_size(bubble, qtbot):
    c0 = bubble.center
    with qtbot.waitSignal(bubble.render_size_changed):
        bubble.set_shape("landscape")
    assert bubble.width() == 462 + 2 * MARGIN
    assert abs(bubble.center.x() - c0.x()) < 1


def test_snap_targets_are_on_screen(bubble, qtbot):
    avail = QGuiApplication.primaryScreen().availableGeometry()
    for pos in (TOP_LEFT, BOTTOM_RIGHT, CENTER):
        bubble.snap_to(pos, animate=False)
        r = bubble.content_rect().translated(bubble.x(), bubble.y())
        assert avail.contains(r.toRect())


def test_animated_snap_commits_position(bubble, qtbot):
    with qtbot.waitSignal(bubble.position_committed, timeout=2000) as blocker:
        bubble.snap_to(TOP_LEFT)
    target = bubble.snap_target(TOP_LEFT)
    assert blocker.args == [int(target.x()), int(target.y())]


def test_spotlight_round_trip(bubble, qtbot):
    c0, s0 = bubble.center, bubble.size_value
    bubble.toggle_spotlight()
    qtbot.waitUntil(lambda: not bubble.is_animating, timeout=2000)
    assert bubble.in_spotlight and bubble.size_value > s0
    bubble.toggle_spotlight()
    qtbot.waitUntil(lambda: not bubble.is_animating, timeout=2000)
    assert not bubble.in_spotlight and bubble.size_value == s0
    assert abs(bubble.center.x() - c0.x()) < 1.5


def test_drag_moves_bubble(bubble, qtbot):
    start = bubble.center
    mid = QPoint(int(bubble.width() / 2), int(bubble.height() / 2))
    qtbot.mousePress(bubble, Qt.MouseButton.LeftButton, pos=mid)
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QMouseEvent

    move_global = bubble.mapToGlobal(mid) + QPoint(-40, -30)
    ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(bubble.mapFromGlobal(move_global)), QPointF(move_global), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(bubble, ev)
    with qtbot.waitSignal(bubble.position_committed):
        qtbot.mouseRelease(bubble, Qt.MouseButton.LeftButton, pos=bubble.mapFromGlobal(move_global))
    assert bubble.center.x() < start.x() - 30 or bubble.center.x() <= bubble.content_rect().width() / 2 + 1


def test_wheel_resizes(bubble, qtbot):
    from PySide6.QtGui import QWheelEvent

    s0 = bubble.size_value
    pos = QPointF(bubble.width() / 2, bubble.height() / 2)
    ev = QWheelEvent(pos, bubble.mapToGlobal(pos), QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    with qtbot.waitSignal(bubble.size_committed):
        QApplication.sendEvent(bubble, ev)
    assert bubble.size_value == s0 + 20


def test_click_through_flags(bubble):
    bubble.set_click_through(True)
    assert bubble.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert bubble.is_click_through
    bubble.set_click_through(False)
    assert not bubble.windowFlags() & Qt.WindowType.WindowTransparentForInput


def test_always_on_top_flag(bubble):
    assert bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    bubble.set_always_on_top(False)
    assert not bubble.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert bubble.isVisible()


def test_clean_mode_never_shows_controls(bubble):
    bubble.set_controls_on_hover(False)
    bubble.hud.reveal()
    assert bubble.hud.opacity == 0.0


def test_paints_all_states(bubble):
    for state in ("starting", "error"):
        bubble.set_status(state, "Camera not found.")
        assert not bubble.grab().isNull()
    img = QImage(64, 64, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    bubble.set_status("live", "")
    bubble.set_frame(img)
    bubble.set_voice_energy(0.8)
    bubble.show_toast("hello")
    assert bubble.toast_text == "hello"
    for shape in ("rounded", "landscape", "portrait"):
        bubble.set_shape(shape)
        assert not bubble.grab().isNull()


# --------------------------------------------------------------------- app
def test_app_receives_frames(app_controller, qtbot):
    qtbot.waitUntil(lambda: app_controller.bubble._frame is not None, timeout=3000)
    assert app_controller.get_state()["camera_state"] == "live"


def test_set_routes_to_subsystems_and_persists(app_controller, qtbot, config_path):
    c = app_controller
    c.set("background_mode", "blur")
    c.set("zoom", 1.7)
    c.set("shape", "portrait")
    c.set("border_width", 6)
    assert c.processor.background_mode == "blur" and c.processor.zoom == 1.7
    assert c.bubble.shape == "portrait" and c.bubble._border_width == 6
    assert c.set("shape", "hexagon") is None  # rejected
    qtbot.waitUntil(lambda: config_path.exists() and ConfigManager(config_path).get("zoom") == 1.7, timeout=3000)


def test_bubble_size_changes_sync_back_to_config(app_controller):
    received = []
    app_controller.setting_changed.connect(lambda k, v: received.append((k, v)))
    app_controller.bubble.set_size(300)
    assert app_controller.get("size") == 300
    assert ("size", 300) in received


def test_spotlight_is_not_persisted(app_controller, qtbot):
    c = app_controller
    size = c.get("size")
    c.toggle_spotlight()
    qtbot.waitUntil(lambda: not c.bubble.is_animating, timeout=2000)
    assert c.in_spotlight() and c.get("size") == size
    c.toggle_spotlight()
    qtbot.waitUntil(lambda: not c.bubble.is_animating, timeout=2000)
    assert c.bubble.size_value == size


def test_background_cycle_skips_image_without_file(app_controller):
    c = app_controller
    seen = [c.cycle_background() for _ in range(4)]
    assert "image" not in seen and seen[-1] == "none"
    c.set("background_image", "/tmp/whatever.png")
    assert "image" in c.background_cycle_order()


def test_scenes_apply_restore_look(app_controller, qtbot):
    c = app_controller
    c.set("shape", "landscape")
    c.set("background_mode", "color")
    c.bubble.snap_to(TOP_LEFT, animate=False)
    c.save_scene("Intro")
    c.set("shape", "circle")
    c.set("background_mode", "none")
    assert c.apply_scene("Intro")
    qtbot.waitUntil(lambda: not c.bubble.is_animating, timeout=2000)
    assert c.get("shape") == "landscape" and c.get("background_mode") == "color"
    target = c.bubble.snap_target(TOP_LEFT)
    assert abs(c.bubble.center.x() - target.x()) < 2
    assert not c.apply_scene("Missing")
    c.delete_scene("Intro")
    assert c.scene_names() == []


def test_hide_pauses_camera(app_controller):
    c = app_controller
    c.set("visible", False)
    assert not c.bubble.isVisible() and c.camera._paused
    c.toggle_visibility()
    assert c.bubble.isVisible() and not c.camera._paused


def test_ipc_validation_and_dispatch(app_controller):
    c = app_controller
    assert c.validate_ipc("set", {"key": "size", "value": 300}) == (True, "")
    assert not c.validate_ipc("set", {"key": "size", "value": "huge"})[0]
    assert not c.validate_ipc("set", {"key": "scenes", "value": {}})[0]
    assert not c.validate_ipc("scene", {"name": "nope"})[0]
    assert not c.validate_ipc("launch_rockets", {})[0]
    assert not c.validate_ipc("snap", {"position": 9})[0]
    c.dispatch("set", {"key": "brightness", "value": 12})
    assert c.get("brightness") == 12
    c.dispatch("toggle_mirror", {})
    assert c.get("mirror") is False
    c.dispatch("toggle_ghost", {})
    assert c.bubble.is_click_through


def test_ipc_end_to_end(app_controller, qtbot):
    from selficamera.ipc_client import send_command

    qtbot.waitUntil(lambda: app_controller.shortcuts.is_listening, timeout=3000)
    res = send_command("set", {"key": "background_mode", "value": "remove"})
    assert res["success"]
    qtbot.waitUntil(lambda: app_controller.get("background_mode") == "remove", timeout=2000)
    status = send_command("get_status")
    assert status["state"]["background_mode"] == "remove"
    assert not send_command("set", {"key": "shape", "value": "blob"})["success"]


def test_reset_all_keeps_scenes(app_controller):
    c = app_controller
    c.save_scene("Keep")
    c.set("size", 500)
    c.set("background_mode", "blur")
    c.reset_all()
    assert c.get("size") == 260 and c.get("background_mode") == "none"
    assert c.scene_names() == ["Keep"]
    assert c.bubble.size_value == 260


# --------------------------------------------------------------- settings
def test_settings_window_two_way_binding(app_controller, qtbot):
    c = app_controller
    c.open_settings()
    w = c.settings_window
    qtbot.addWidget(w)
    assert w.isVisible()
    # UI -> app
    w.seg_shape.buttons["portrait"].click()
    assert c.get("shape") == "portrait"
    w.sl_zoom.setValue(200)
    assert c.get("zoom") == 2.0
    w.seg_bg.buttons["blur"].click()
    assert c.get("background_mode") == "blur" and not w.sl_blur.isHidden()
    w.sw_mirror.click()
    assert c.get("mirror") is False
    # app -> UI (no feedback loop)
    c.set("brightness", -20)
    assert w.sl_brightness.value() == -20
    c.set("background_mode", "color")
    assert w.seg_bg.current() == "color" and not w.bg_color_box.isHidden()
    c.bubble.set_size(333)
    assert w.sl_size.value() == 333


def test_settings_pages_and_model_badge(app_controller, qtbot):
    c = app_controller
    c.open_settings("background")
    w = c.settings_window
    qtbot.addWidget(w)
    assert w.stack.currentWidget() is w.pages["background"]
    assert w.lbl_model_badge.text() == "Basic"
    assert not w.sw_autoframe.isEnabled()
    for key in w.pages:
        w.show_page(key)
        assert not w.grab().isNull()
    w.close()
    assert not w.isVisible()


def test_scene_list_refreshes(app_controller, qtbot):
    c = app_controller
    c.open_settings("scenes")
    w = c.settings_window
    qtbot.addWidget(w)
    c.save_scene("Tutorial")
    assert [w.list_scenes.item(i).text() for i in range(w.list_scenes.count())] == ["Tutorial"]


def test_context_menu_builds(app_controller):
    from PySide6.QtWidgets import QMenu

    from selficamera.ui.tray import populate_quick_menu

    menu = QMenu()
    populate_quick_menu(menu, app_controller)
    texts = [a.text() for a in menu.actions()]
    assert "Settings…" in texts and "Quit SelfiCamera" in texts and "Click-through" in texts


def test_voice_wave_reacts_and_settles(qapp):
    from selficamera.ui.voice_wave import VoiceWave

    w = VoiceWave()
    assert not w.active
    for i in range(30):
        w.set_energy(0.05 if i < 3 else 0.8)
        w.tick(1 / 60)
    assert w.level > 0.5 and w.ripples  # loud speech: big wave and a ripple
    w.set_energy(0.0)
    for _ in range(300):
        w.tick(1 / 60)
    assert not w.active and w.level == 0.0  # quiet: nothing drawn


def test_voice_wave_paints_outside_the_video_only(qapp):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from selficamera.ui.voice_wave import VoiceWave

    w = VoiceWave()
    for _ in range(20):
        w.set_energy(0.9)
        w.tick(1 / 60)
    img = QImage(200, 200, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    rect = QRectF(30, 30, 140, 140)
    w.paint(p, "circle", rect, QColor("#2ECC71"), 2.0, 24.0, QRectF(0, 0, 200, 200))
    p.end()
    assert img.pixelColor(100, 100).alpha() == 0  # never over the face
    ring = [img.pixelColor(100 + int(80 * np.cos(a)), 100 + int(80 * np.sin(a))).alpha() for a in np.linspace(0, 6.2, 24)]
    assert max(ring) > 0  # wave visible around the edge


def test_bubble_wave_timer_starts_and_stops(qapp):
    b = BubbleWindow(size=200)
    b.show()
    b.set_voice_energy(0.8)
    assert b._wave_timer.isActive()
    b.set_voice_glow(False)
    assert not b._wave_timer.isActive() and not b.wave.active
    b.close()


def test_enhance_controls_bind_both_ways(app_controller, qtbot):
    c = app_controller
    c.open_settings()
    w = c.settings_window
    w.sl_soft_skin.setEnabled(True)
    w.sl_denoise.slider.setValue(70)
    assert c.get("denoise") == 70 and c.processor.denoise == 70
    c.set("sharpen", 35)
    assert w.sl_sharpen.slider.value() == 35 and c.processor.sharpen == 35
    c.set("soft_skin", 40)
    c.reset_enhance()
    assert (c.get("denoise"), c.get("soft_skin"), c.get("sharpen")) == (30, 0, 0)
