## 2026-10-22T12:49:49Z
You are Worker M6 implementing Milestone 6: Reliable Drag-to-Move, Guaranteed Always-On-Top, and Zero-Drift Responsive Resizing (Requirements R1 and R2) for SelfiCamera.

Read the authoritative requirements in:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/ORIGINAL_REQUEST.md
Specifically review the request dated 2026-10-22T12:34:05Z (R1 and R2 and Acceptance Criteria).
Also review the project specification in:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your working directory is:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/worker_m6

Exclusive Write Ownership:
- selficamera/ui/overlay.py
- selficamera/ui/hud.py
- selficamera/config.py
- selficamera/app.py
- selficamera/__main__.py
- run.sh
- tests/test_config.py (updating diameter validation test for 120-600 range)
- tests/test_overlay_gui.py (updating/adding drag & resize tests)

Detailed Implementation Specifications (synthesized from explorer_r2_1 and explorer_r2_2 handoff reports):
1. HUD Mouse Click Transparency (Fix for bottom-half drag block):
   In selficamera/ui/hud.py:
   - When AutoHidingHUD opacity is 0.0 (at initialization and when fade-out animation finishes), set self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True).
   - In trigger_show(), set self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False).
   This ensures faded-out child QPushButtons never swallow mousePressEvent in the bottom 32px of the circle.

2. Mouse Drag Hit-Testing & Multi-Monitor Clamping:
   In selficamera/ui/overlay.py:
   - Expand hit-test radius in mousePressEvent by 4px: radius = (self._diameter / 2.0) + 4.0 so clicking on the glowing voice aura border also initiates dragging.
   - If QGuiApplication.platformName() == "wayland", check if windowHandle().startSystemMove() is available and invoke it.
   - In mouseMoveEvent: calculate target position and clamp against the bounding union of all connected displays (QGuiApplication.screens()), allowing dragging seamlessly across multi-monitor setups.
   - Debounce/defer disk fsync: During mouseMoveEvent, update in-memory coordinates only: emit position_changed(x, y) connected to config.update(auto_save=False, x=x, y=y). In mouseReleaseEvent, emit drag_completed(x, y) connected to config.update(auto_save=True, x=x, y=y) so blocking os.fsync is NEVER executed at 60fps on the GUI thread.

3. Dynamic Always-On-Top Toggle:
   In selficamera/ui/overlay.py:
   - Implement set_always_on_top(self, enabled: bool) -> None:
     flags = self.windowFlags()
     if enabled:
         flags |= Qt.WindowType.WindowStaysOnTopHint
     else:
         flags &= ~Qt.WindowType.WindowStaysOnTopHint
     self.setWindowFlags(flags)
     self.show()  # Crucial: Qt hides window upon flag modification!
     self.always_on_top_changed.emit(enabled)
   In selficamera/app.py:
   - Add set_always_on_top method on SelfiCameraApp and wire with config.

4. Canonical Float Center-Point Anchoring (Zero-Drift Architecture):
   In selficamera/ui/overlay.py:
   - Store persistent self._center_point: QPointF = QPointF(x + w / 2.0, y + h / 2.0).
   - In moveEvent (when not in a resize operation), after window drag, or during snap_to_corner, update self._center_point to the current exact float center.
   - In set_diameter(val: int): clamp val to [120, 600]. Calculate total_dim = val + 2 * self.shadow_margin.
     Compute new_x = int(round(self._center_point.x() - total_dim / 2.0)) and new_y = int(round(self._center_point.y() - total_dim / 2.0)) using the frozen self._center_point.
     This mathematically guarantees 0.0px cumulative drift across thousands of continuous resize steps.
   - Emit diameter_changed.emit(self._diameter).

5. Mouse Resizing Modalities:
   In selficamera/ui/overlay.py:
   - Smooth continuous scroll wheel: In wheelEvent, adjust diameter by round(delta_y / 120.0 * 15.0) px (e.g. +/- 15px per notch) clamped to [120, 600].
   - Retain step_resize(step_up: bool) cycling PRESET_DIAMETERS = [160, 260, 380] for preset buttons and shortcut compatibility.
   - Radial perimeter drag: If mouse distance from center is between r - 14 and r + 16, set cursor to Qt.CursorShape.SizeAllCursor. On left mouse press in this zone, set _is_dragging_resize = True and track diameter with cursor distance 2.0 * dist.
   - In mouseReleaseEvent: if _is_dragging_resize, clear flag and emit diameter_completed(self._diameter) to save config.

6. Small-Diameter HUD Adaptation:
   - When diameter < 180px, adjust HUD geometry and padding so it does not overflow the circular window boundary.

7. Config Range Validation & New Keys:
   In selficamera/config.py:
   - Update validation so diameter accepts any int/float in range [120, 600], falling back to 260 if outside or invalid.
   - Add new default keys to DEFAULT_CONFIG:
     "always_on_top": True,
     "manual_gamma": 1.0,
     "target_luminance": 125.0,
     "blur_intensity": 50,
   In tests/test_config.py:
   - Update tests that checked strict tuple validation to test range [120, 600] and continuous persistence.

8. Launcher Platform Configuration:
   In run.sh:
   - Set export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb;wayland}"
   In selficamera/__main__.py:
   - Before QApplication creation, if "QT_QPA_PLATFORM" not in os.environ, set os.environ["QT_QPA_PLATFORM"] = "xcb;wayland".

Verification:
- Run all tests: QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
- Ensure 100% of tests pass without regressions.
- Verify zero-drift center anchoring and smooth dragging.
- Write your comprehensive handoff report to:
  /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/worker_m6/handoff.md
- When done, send a message to caller with a summary of changes and test outcomes.
