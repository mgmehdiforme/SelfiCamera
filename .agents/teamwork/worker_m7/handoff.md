# Handoff Report — Milestone 7: Floating Settings Panel & Pipeline Controls

## 1. Observation
- Requirements and specifications:
  * File `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/ORIGINAL_REQUEST.md` (lines 73-80, Requirement R3) mandates an on-screen floating Settings Panel opened from the camera bubble (via gear button on the bubble and right-click context menu) with live controls for lighting, background blur, bubble size, camera & video, and window management.
  * File `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/PROJECT.md` (Feature F19, Phase 7 M7) defines `SettingsPanel` as a standalone top-level tool window with 5 control cards, dark theme, live sliders, gear icon & context menu.
- Codebase state prior to modification:
  * `selficamera/ui/settings_panel.py` did not exist.
  * `selficamera/processor/lighting.py` supported only automatic thresholded gamma boosting without manual gamma or adjustable target luminance setters.
  * `selficamera/processor/segmentation.py` supported only discrete tier integers (0, 1, 2, 3) without continuous blur intensity [0..100] scaling.
  * `selficamera/processor/pipeline.py` lacked delegation methods for manual gamma, target luminance, and blur intensity.
  * `selficamera/ui/hud.py` contained 5 buttons (Flip, Blur, Light, Ghost, Close) with 230px capsule width, lacking a settings gear button.
  * `selficamera/ui/overlay.py` lacked `contextMenuEvent` and `settings_requested` signal.
  * `selficamera/ui/tray.py` lacked a direct "⚙ Settings..." action in its menu.
  * `selficamera/app.py` did not instantiate or wire `SettingsPanel`.
- Test execution output:
  * Initial baseline had 51 passed tests.
  * Final test run with new `tests/test_settings_panel.py` executed:
    `QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v`
    Result: 63 passed in 5.86s (100% pass rate).
  * Benchmark execution:
    `.venv/bin/python benchmarks/benchmark_pipeline.py` -> Mean Latency 16.11 ms, P95 19.99 ms (under 25 ms gate).
    `.venv/bin/python benchmarks/benchmark_latency.py` -> 50 frames @ 720p mean latency 2.76 ms, 30 FPS target sustained with 0 dropped frames.

## 2. Logic Chain
1. **Decoupled Top-Level Tool Window Architecture**:
   To ensure that `SettingsPanel` remains completely clickable and interactive even when the camera bubble is placed in Click-Through Ghost Mode (`WA_TransparentForMouseEvents` enabled and mask cleared), `SettingsPanel` was created as an independent top-level `QWidget` with flags `Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`. Because it is an independent window rather than a child of `OverlayWindow`, Qt's event dispatcher routes mouse clicks and drags directly to the panel without interference from the overlay's mouse transparency.

2. **5-Card Control Architecture**:
   `SettingsPanel` implements all 5 required cards:
   - Card 1 (Lighting & Exposure): `QCheckBox` for Auto-Light Boost, `QSlider` (40 to 220 -> 0.40x to 2.20x) with readout ("1.00x") and reset button, and Target Luminance `QSlider` (50 to 220, default 125).
   - Card 2 (Background Blur): 4 checkable tier buttons [Off], [Subtle], [Balanced], [Heavy] and continuous intensity `QSlider` (0 to 100). Guarded with `_syncing_blur` to guarantee bidirectional synchronization without recursive event loops.
   - Card 3 (Bubble Size): Continuous diameter `QSlider` (120 to 600 px) with readout, plus preset buttons [160 px], [260 px], [380 px].
   - Card 4 (Camera & Video): V4L2 device `QComboBox` populated via `V4L2DeviceScanner.list_devices()` with rescan button `🔄`, resolution `QComboBox` (480p, 720p, 1080p), and horizontal mirror `QCheckBox`.
   - Card 5 (Window Management): Always-On-Top `QCheckBox`, Click-Through Ghost Mode `QCheckBox` with shortcut guidance ("Exit shortcut: Super+Alt+X").
   - Header & Footer: Draggable custom title bar with close button `✕`, Reset Defaults button, and Close button.

3. **Dynamic Screen Clamping & Docking**:
   Method `position_alongside_overlay(overlay)` calculates the available geometry from `overlay.screen()`. It docks 12px to the right of the overlay (`x = overlay.x() + overlay.width() + 12`). If this geometry exceeds the right screen edge, it flips to the left (`x = overlay.x() - panel_w - 12`). Both X and Y positions are clamped within visible screen boundaries (`avail_geo.left()`, `avail_geo.right()`, `avail_geo.top()`, `avail_geo.bottom()`).

4. **Pipeline Enhancements**:
   - In `AutoLightBoost`: Added `manual_gamma` factor and `target_luminance`. When Auto-Light is off, `manual_gamma` is applied directly via precomputed LUT (bypassing when `abs(manual_gamma - 1.0) < 0.02`). When Auto-Light is on, `effective_gamma = self._current_gamma * self.manual_gamma` is applied via LUT.
   - In `SegmentationBlurEngine`: Added `set_intensity(intensity)` and mapped `set_tier(tier)` to `(0 -> 0, 1 -> 25, 2 -> 50, 3 -> 85)`. Calibrated preset scale/ksize parameters are preserved for tiers 1, 2, and 3 to maintain strict monotonic bokeh progression and foreground sharpness, while dynamic continuous scaling is applied for arbitrary slider values.
   - In `FrameProcessor`: Delegated setters `set_manual_gamma`, `set_target_luminance`, `set_blur_intensity`, and `set_blur_tier`.

5. **Overlay & HUD & Tray Integration**:
   - Added `btn_settings` ("⚙") with tooltip to `AutoHidingHUD` emitting `settings_clicked`. Expanded HUD capsule width to 264px so all 6 buttons fit cleanly with tooltips.
   - Connected `hud.settings_clicked` to `overlay.settings_requested`.
   - Implemented `OverlayWindow.contextMenuEvent` presenting a dark-themed context menu with "⚙ Settings..." action triggering `settings_requested`, quick Always-On-Top toggle, Ghost Mode activation, and size presets.
   - Added "⚙ Settings..." to `SystemTrayController` menu emitting `settings_requested`.
   - In `SelfiCameraApp`: Wired `overlay.settings_requested` and `tray.settings_requested` to `toggle_settings_panel()`. Wired all 12 `SettingsPanel` signals bidirectionally with `OverlayWindow`, `FrameProcessor`, `CameraCaptureWorker`, `SystemTrayController`, and `ConfigManager`.

## 3. Caveats
- Wayland fractional scaling may report slightly adjusted screen geometries under some compositor configurations; `screen.availableGeometry()` was used to respect panels and docks.
- When running in headless test environments (`QT_QPA_PLATFORM=offscreen`), physical V4L2 webcams are mocked or simulated via `mock_mode=True`, while device enumeration gracefully falls back to empty or placeholder lists.

## 4. Conclusion
Milestone 7 (Requirement R3) is fully implemented, verified, and integrated into SelfiCamera. The floating settings panel provides live, responsive adjustments for lighting, blur, diameter, camera, resolution, mirror, always-on-top, and ghost mode without compositor blocking or feedback loops, and remains fully interactive even during ghost mode. 100% of automated tests (63/63) pass headlessly without regressions, and latency benchmarks remain well below the 30ms real-time budget.

## 5. Verification Method
1. Run automated test suite:
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/ -v
   ```
   Expected: 63 passed in ~6 seconds with 0 failures.

2. Run settings panel specific tests:
   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/pytest tests/test_settings_panel.py -v
   ```
   Expected: 12 passed in < 1 second.

3. Run pipeline and latency benchmarks:
   ```bash
   .venv/bin/python benchmarks/benchmark_pipeline.py
   .venv/bin/python benchmarks/benchmark_latency.py
   ```
   Expected: Mean latency < 20ms, P95 < 25ms, FPS > 30.

4. Inspect files for structural compliance:
   - `selficamera/ui/settings_panel.py`
   - `selficamera/ui/hud.py`
   - `selficamera/ui/overlay.py`
   - `selficamera/ui/tray.py`
   - `selficamera/processor/lighting.py`
   - `selficamera/processor/segmentation.py`
   - `selficamera/processor/pipeline.py`
   - `selficamera/app.py`
