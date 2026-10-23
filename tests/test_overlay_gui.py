"""Headless Qt GUI interaction tests for OverlayWindow and AutoHidingHUD."""

import random
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from selficamera.ui.overlay import OverlayWindow, PRESET_DIAMETERS


def test_overlay_window_flags_and_geometry(qtbot):
    """Verify window flags, translucent background attribute, and geometry dimensions."""
    overlay = OverlayWindow(initial_diameter=260, shadow_margin=16)
    qtbot.addWidget(overlay)
    overlay.show()

    flags = overlay.windowFlags()
    assert bool(flags & Qt.WindowType.FramelessWindowHint) is True
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint) is True
    assert bool(flags & Qt.WindowType.Tool) is True
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) is True

    # Geometry: diameter (260) + 2 * shadow_margin (16) = 292
    assert overlay.width() == 292
    assert overlay.height() == 292


def test_scroll_step_resize_presets(qtbot):
    """Verify stepping through preset diameters (160 -> 260 -> 380) and boundary clamping."""
    overlay = OverlayWindow(initial_diameter=160, shadow_margin=16)
    qtbot.addWidget(overlay)
    overlay.show()

    assert overlay.get_diameter() == 160

    # Step up -> 260
    overlay.step_resize(step_up=True)
    qtbot.waitUntil(lambda: overlay.get_diameter() == 260, timeout=1000)
    assert overlay.width() == 260 + 32

    # Step up -> 380
    overlay.step_resize(step_up=True)
    qtbot.waitUntil(lambda: overlay.get_diameter() == 380, timeout=1000)
    assert overlay.width() == 380 + 32

    # Clamp at 380: stepping up again leaves diameter at 380
    overlay.step_resize(step_up=True)
    assert overlay.get_diameter() == 380

    # Step down -> 260
    overlay.step_resize(step_up=False)
    qtbot.waitUntil(lambda: overlay.get_diameter() == 260, timeout=1000)

    # Step down -> 160
    overlay.step_resize(step_up=False)
    qtbot.waitUntil(lambda: overlay.get_diameter() == 160, timeout=1000)

    # Clamp at 160: stepping down again leaves diameter at 160
    overlay.step_resize(step_up=False)
    assert overlay.get_diameter() == 160


def test_ghost_mode_toggle(qtbot):
    """Verify click-through ghost mode toggling."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    assert overlay.is_ghost_mode is False
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False

    overlay.set_click_through(True)
    assert overlay.is_ghost_mode is True
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True

    overlay.set_click_through(False)
    assert overlay.is_ghost_mode is False
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False


def test_hud_opacity_transitions(qtbot):
    """Verify HUD hover fade-in and opacity states."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    assert overlay.hud.current_opacity == 0.0
    assert overlay.hud.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True

    overlay.hud.trigger_show()
    qtbot.waitUntil(lambda: abs(overlay.hud.current_opacity - 0.92) < 0.05, timeout=1000)
    assert abs(overlay.hud.current_opacity - 0.92) < 0.05
    assert overlay.hud.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is False


def test_corner_snapping(qtbot):
    """Verify corner snapping calculates valid desktop coordinates."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    # Snap Top-Left (Corner 1)
    overlay.snap_to_corner(1)
    qtbot.waitUntil(lambda: overlay.pos().x() >= 0, timeout=1000)
    pos1 = overlay.pos()

    # Snap Bottom-Right (Corner 4)
    overlay.snap_to_corner(4)
    qtbot.waitUntil(lambda: overlay.pos() != pos1, timeout=1000)
    pos4 = overlay.pos()

    assert pos4.x() > pos1.x()
    assert pos4.y() > pos1.y()


def test_hud_mouse_transparency_allows_bottom_drag(qtbot, monkeypatch):
    """Verify that clicking in the bottom 32px of the circle when HUD is hidden initiates window drag."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    assert overlay.hud.current_opacity == 0.0
    assert overlay.hud.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) is True

    # Disable wayland startSystemMove in test to verify client-side drag tracking flag
    wh = overlay.windowHandle()
    if wh is not None and hasattr(wh, "startSystemMove"):
        monkeypatch.setattr(wh, "startSystemMove", lambda: False)

    # Coordinates in bottom portion of the circle: center_x, center_y + 100 (inside circle of radius 130)
    cx = overlay.width() / 2.0
    cy = overlay.height() / 2.0
    click_pos = QPointF(cx, cy + 100.0)

    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        click_pos,
        click_pos.toPoint() + overlay.pos(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(press_ev)
    assert overlay._is_dragging is True

    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        click_pos,
        click_pos.toPoint() + overlay.pos(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseReleaseEvent(release_ev)
    assert overlay._is_dragging is False


def test_zero_drift_center_anchoring(qtbot):
    """Verify that repeated continuous resizing maintains stationary center coordinate with 0.0px drift."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.move(400, 300)
    overlay.show()

    initial_center_x = overlay.x() + overlay.width() / 2.0
    initial_center_y = overlay.y() + overlay.height() / 2.0

    random.seed(42)
    for _ in range(100):
        test_d = random.randint(120, 600)
        overlay.set_diameter(test_d)
        curr_center_x = overlay.x() + overlay.width() / 2.0
        curr_center_y = overlay.y() + overlay.height() / 2.0
        assert abs(curr_center_x - initial_center_x) <= 0.5
        assert abs(curr_center_y - initial_center_y) <= 0.5

    # Revert to 260: must return exactly to (400, 300)
    overlay.set_diameter(260)
    assert (overlay.x(), overlay.y()) == (400, 300)


def test_smooth_wheel_continuous_resizing(qtbot):
    """Verify smooth continuous scroll-wheel diameter adjustment (+/- 15px per notch)."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    # Wheel up (+120 delta) -> 260 + 15 = 275
    wheel_up = QWheelEvent(
        QPointF(overlay.width() / 2.0, overlay.height() / 2.0),
        QPointF(overlay.width() / 2.0, overlay.height() / 2.0),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    overlay.wheelEvent(wheel_up)
    assert overlay.get_diameter() == 275

    # Wheel down (-120 delta) -> 275 - 15 = 260
    wheel_down = QWheelEvent(
        QPointF(overlay.width() / 2.0, overlay.height() / 2.0),
        QPointF(overlay.width() / 2.0, overlay.height() / 2.0),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    overlay.wheelEvent(wheel_down)
    assert overlay.get_diameter() == 260


def test_always_on_top_toggle(qtbot):
    """Verify dynamic always-on-top toggle updates window flags and keeps window visible."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    assert bool(overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) is True
    assert overlay.is_always_on_top is True

    # Disable Always-On-Top
    with qtbot.waitSignal(overlay.always_on_top_changed, timeout=1000):
        overlay.set_always_on_top(False)

    assert bool(overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) is False
    assert overlay.is_always_on_top is False
    assert overlay.isVisible() is True

    # Re-enable Always-On-Top
    with qtbot.waitSignal(overlay.always_on_top_changed, timeout=1000):
        overlay.set_always_on_top(True)

    assert bool(overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) is True
    assert overlay.is_always_on_top is True
    assert overlay.isVisible() is True


def test_radial_perimeter_resize_drag(qtbot):
    """Verify clicking and dragging on the radial perimeter ring initiates resizing."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    cx = overlay.width() / 2.0
    cy = overlay.height() / 2.0

    # Perimeter zone: r - 5 = 125, within [r - 14, r + 16] = [116, 146]
    press_pos = QPointF(cx + 125.0, cy)
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        press_pos,
        press_pos.toPoint() + overlay.pos(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(press_ev)
    assert overlay._is_dragging_resize is True

    # Move outward to 160 distance (diameter = 320)
    move_pos = QPointF(cx + 160.0, cy)
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos.toPoint() + overlay.pos(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseMoveEvent(move_ev)
    assert overlay.get_diameter() == 320

    # Release
    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        move_pos,
        move_pos.toPoint() + overlay.pos(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseReleaseEvent(release_ev)
    assert overlay._is_dragging_resize is False


def test_small_diameter_hud_compact_adaptation(qtbot):
    """Verify that HUD switches to compact mode and stays within bounds for small diameters (<180px)."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    overlay.set_diameter(140)
    assert overlay.get_diameter() == 140
    assert overlay.hud._compact_mode is True
    assert overlay.hud.width() <= 140
    assert overlay.hud.x() >= 0
    assert overlay.hud.x() + overlay.hud.width() <= overlay.width()

    # Restore to normal diameter
    overlay.set_diameter(260)
    assert overlay.hud._compact_mode is False
    assert overlay.hud.width() in (230, 264)


def test_hud_pin_toggle_and_stay_visible(qtbot):
    """Verify that clicking HUD pin button locks visibility and prevents fade-out."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    assert overlay.hud.is_pinned is False
    # Click pin button
    overlay.hud.btn_pin.click()
    assert overlay.hud.is_pinned is True

    # When pinned, trigger_hide_delayed does not start the hide timer
    overlay.hud.trigger_hide_delayed()
    assert overlay.hud._hide_timer.isActive() is False

    # Unpin
    overlay.hud.btn_pin.click()
    assert overlay.hud.is_pinned is False
    overlay.hud.trigger_hide_delayed()
    assert overlay.hud._hide_timer.isActive() is True


def test_hud_step_resize_buttons(qtbot):
    """Verify on-bubble HUD [-] and [+] step buttons resize diameter by 25px."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    assert overlay.get_diameter() == 260

    # Step down (-25) -> 235
    overlay.hud.btn_size_down.click()
    qtbot.waitUntil(lambda: overlay.get_diameter() == 235, timeout=1000)
    assert overlay.get_diameter() == 235

    # Step up (+25) -> 260
    overlay.hud.btn_size_up.click()
    qtbot.waitUntil(lambda: overlay.get_diameter() == 260, timeout=1000)
    assert overlay.get_diameter() == 260


def test_snap_to_center(qtbot):
    """Verify snap_to_corner(5) centers the overlay on screen."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    overlay.snap_to_corner(5)
    qtbot.wait(250)

    from PySide6.QtGui import QGuiApplication
    screen = overlay.screen() or QGuiApplication.primaryScreen()
    avail = screen.availableGeometry()
    expected_x = avail.left() + (avail.width() - overlay.width()) // 2
    expected_y = avail.top() + (avail.height() - overlay.height()) // 2

    assert abs(overlay.pos().x() - expected_x) <= 2
    assert abs(overlay.pos().y() - expected_y) <= 2


def test_cursor_feedback_states(qtbot):
    """Verify cursor shapes during hover and client-side drag."""
    overlay = OverlayWindow(initial_diameter=260)
    qtbot.addWidget(overlay)
    overlay.show()

    cx = overlay.width() / 2.0
    cy = overlay.height() / 2.0

    # Move inside circle (radius = 130) at dist = 50 -> OpenHandCursor
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(cx, cy + 50),
        QPointF(cx, cy + 50).toPoint() + overlay.pos(),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseMoveEvent(move_ev)
    assert overlay.cursor().shape() == Qt.CursorShape.OpenHandCursor

    # Press inside circle -> ClosedHandCursor
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(cx, cy + 50),
        QPointF(cx, cy + 50).toPoint() + overlay.pos(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(press_ev)
    assert overlay._is_dragging is True
    assert overlay.cursor().shape() == Qt.CursorShape.ClosedHandCursor

    # Release -> unset cursor
    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(cx, cy + 50),
        QPointF(cx, cy + 50).toPoint() + overlay.pos(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mouseReleaseEvent(release_ev)
    assert overlay._is_dragging is False
