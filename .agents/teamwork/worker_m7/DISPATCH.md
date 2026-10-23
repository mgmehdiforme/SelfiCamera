## 2026-10-22T13:12:31Z

You are Worker M7 implementing Milestone 7: On-Screen Floating Settings & Controls Panel and Pipeline Controls (Requirement R3) for SelfiCamera.

Read the authoritative requirements in:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/ORIGINAL_REQUEST.md
Specifically review the request dated 2026-10-22T12:34:05Z (R3 and Acceptance Criteria for Floating Settings Panel).
Also review the project specification in:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your working directory is:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/worker_m7

Exclusive Write Ownership:
- selficamera/ui/settings_panel.py (new)
- selficamera/ui/hud.py
- selficamera/ui/overlay.py
- selficamera/ui/tray.py
- selficamera/processor/lighting.py
- selficamera/processor/segmentation.py
- selficamera/processor/pipeline.py
- selficamera/app.py

Detailed Implementation Specifications (synthesized from explorer_r2_3 handoff report):
1. selficamera/ui/settings_panel.py (New Component):
   - Standalone top-level QWidget with flags:
     Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
   - Signals:
     diameter_changed = Signal(int)
     manual_gamma_changed = Signal(float)
     target_luminance_changed = Signal(float)
     auto_light_toggled = Signal(bool)
     blur_tier_selected = Signal(int)
     blur_intensity_changed = Signal(int)
     device_selected = Signal(str)
     resolution_selected = Signal(int, int)
     mirror_toggled = Signal(bool)
     always_on_top_toggled = Signal(bool)
     ghost_mode_toggled = Signal(bool)
     reset_defaults_requested = Signal()
   - Draggable custom title bar: "⚙ SelfiCamera Settings" and close button "✕".
   - 5 Control Cards:
     * Card 1 (Lighting & Exposure):
       - Auto-Light Boost QCheckBox
       - Brightness/Gamma QSlider: range 40 to 220 (0.40x to 2.20x), label readout ("1.00x"), reset button
       - Target Luminance QSlider: range 50 to 220, label readout ("125")
     * Card 2 (Background Blur):
       - Button row: [Off], [Subtle], [Balanced], [Heavy]
       - Blur intensity QSlider: range 0 to 100, label readout ("50%")
       - Bidirectional synchronization between buttons and slider (updating slider updates active button; clicking button sets slider to 0, 25, 50, 85) without feedback loops
     * Card 3 (Bubble Size):
       - Live continuous diameter QSlider: range 120 to 600 px with readout ("260 px")
       - Preset buttons: [160 px], [260 px], [380 px]
     * Card 4 (Camera & Video):
       - Device QComboBox populated from V4L2DeviceScanner.list_devices(), with "🔄" button to rescan
       - Resolution QComboBox (640x480, 1280x720, 1920x1080)
       - Horizontal mirror flip QCheckBox
     * Card 5 (Window Management):
       - Always-On-Top QCheckBox
       - Click-Through Ghost Mode QCheckBox (with note: Super+Alt+X to exit)
     * Footer: Reset Defaults QPushButton and Close QPushButton.
   - Dynamic positioning method position_alongside_overlay(overlay):
     Docks to right of overlay (x + w + 12, y), or flips to left (overlay.x() - panel.width() - 12) if overflowing right screen edge. Clamps vertically within visible screen geometry.
   - Top-level window decoupling: Because SettingsPanel is an independent top-level tool window, it receives clicks and stays fully interactive even if the camera bubble enters Ghost Mode!

2. selficamera/ui/hud.py:
   - Add btn_settings ("⚙") to HUD capsule emitting settings_clicked = Signal().
   - Normal capsule width expanded (e.g. 264px) so all 6 buttons (Flip, Blur, Light, Settings, Ghost, Close) fit cleanly with tooltips.

3. selficamera/ui/overlay.py:
   - Connect hud.settings_clicked to settings_requested = Signal().
   - Implement contextMenuEvent(self, event: QContextMenuEvent):
     If not in ghost mode, pop up dark styled QMenu with "⚙ Settings..." triggering settings_requested, plus quick toggles.

4. selficamera/processor/lighting.py:
   - Add manual_gamma: float = 1.0 and set_manual_gamma(gamma: float).
   - Add set_target_luminance(target: float).
   - Apply manual_gamma when Auto-Light is off via LUT; apply effective_gamma = computed_gamma * manual_gamma when on.

5. selficamera/processor/segmentation.py:
   - Add set_intensity(intensity: int) dynamically scaling Gaussian blur kernel size (e.g. k = max(3, int(intensity * 0.35) * 2 + 1)).
   - Map set_tier(tier) to corresponding intensities (0 -> 0, 1 -> 25, 2 -> 50, 3 -> 85).

6. selficamera/processor/pipeline.py:
   - Expose set_manual_gamma, set_target_luminance, set_blur_intensity, set_blur_tier.

7. selficamera/ui/tray.py:
   - Add "⚙ Settings..." action to tray menu connected to settings toggle signal.

8. selficamera/app.py:
   - Instantiate self.settings_panel = SettingsPanel().
   - Implement toggle_settings_panel(): show/hide with position_alongside_overlay.
   - Wire all signals bidirectionally between settings panel, overlay, processor, capture, and tray.

Verification:
- Run all tests: QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
- Verify 100% test pass rate without regressions.
- Write handoff report to:
  /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/worker_m7/handoff.md
- When done, send a message to caller with summary and results.
