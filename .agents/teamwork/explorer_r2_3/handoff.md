# Handoff Report: R3 (On-Screen Floating Settings & Controls Panel) and R4 (Automated Testing & Verification)

## 1. Observation

Direct inspection of the current SelfiCamera codebase reveals the existing implementation state and integration surfaces across UI, image processing, camera capture, configuration, and testing:

### 1.1 Overlay & HUD (`selficamera/ui/overlay.py`, `selficamera/ui/hud.py`)
- **HUD Capsule (`selficamera/ui/hud.py:59-94`)**:
  - Contains five buttons: `Flip`, `B:Bal`, `Light`, `Ghost`, and `✕` (`close_clicked`).
  - Currently has **no settings gear button** (`btn_settings`) or `settings_clicked` Qt Signal.
  - HUD is fixed at width 230px, height 32px (`overlay.py:129-130`), fading in on hover and auto-hiding after 1200ms.
- **Overlay Window (`selficamera/ui/overlay.py:43-260`)**:
  - Window flags (`overlay.py:98-102`): `Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool`.
  - Resizing (`overlay.py:171-183`): Currently only supports discrete preset stepping (`step_resize` cycling `[160, 260, 380]`) via scroll wheel.
  - Center-point anchoring (`overlay.py:116-120`): `new_top_left = QPoint(center.x() - total_dim // 2, center.y() - total_dim // 2)`. Uses integer `center.x()`, which can accumulate rounding drift during continuous slider movements.
  - Mouse event handling (`overlay.py:213-250`): Handles LeftButton drag-to-move, but **completely lacks a `contextMenuEvent` or `Qt.MouseButton.RightButton` handler**. Right-clicking on the bubble currently does nothing.
  - Always-On-Top toggle: Currently lacks a runtime toggle method (`set_always_on_top(enabled)`).

### 1.2 System Tray (`selficamera/ui/tray.py:42-217`)
- Manages device selection, resolution, flip, light, blur, ghost mode, reset, and quit.
- Does not currently have an action to open/toggle the on-screen Settings Panel.

### 1.3 Configuration Subsystem (`selficamera/config.py:13-76`)
- `DEFAULT_CONFIG` (`config.py:13-26`) has: `diameter`, `x`, `y`, `device_path`, `resolution`, `fps`, `mirror`, `auto_light`, `blur_level`, `click_through`, `mic_device`, `aura_enabled`.
- **Critical Bug / Constraint Violation (`config.py:28, 64-65`)**:
  ```python
  VALID_DIAMETERS = (160, 260, 380)
  ...
  if merged.get("diameter") not in VALID_DIAMETERS:
      merged["diameter"] = DEFAULT_CONFIG["diameter"]
  ```
  This strict tuple validation forces any continuous diameter (e.g., 210px or 450px) to revert back to default 260px upon reload!
- Missing keys for: `always_on_top` (bool), `manual_gamma` (float), `target_luminance` (float), `blur_intensity` (int).

### 1.4 Image Processing Pipeline (`selficamera/processor/lighting.py`, `segmentation.py`, `pipeline.py`)
- **Lighting (`lighting.py:14-91`)**:
  - `AutoLightBoost` only computes adaptive gamma when `enabled=True` and luminance is low (`< 100`).
  - If `enabled=False`, line 62 immediately returns the frame untouched: `if not self.enabled: return frame`.
  - There is currently **no manual brightness/gamma adjustment** slider support. If Auto-Light is turned off or if a presenter wants manual exposure compensation, the pipeline does not support it.
  - `target_luminance` is currently hardcoded to `125.0` in `__init__` and cannot be adjusted live via UI.
- **Segmentation Blur (`segmentation.py:17-229`)**:
  - Only supports 4 discrete tiers: 0 (Off), 1 (Subtle), 2 (Balanced), 3 (Heavy) via `set_tier(tier)`.
  - Lacks a continuous blur intensity slider (e.g., 0 to 100).
- **Pipeline (`pipeline.py:17-91`)**:
  - Encapsulates `AutoLightBoost` and `SegmentationBlurEngine`, but does not expose setters for `manual_gamma`, `target_luminance`, or continuous `blur_intensity`.

### 1.5 Automated Testing Suite (`tests/`)
- Current status: 44 tests pass in 5.72s under `QT_QPA_PLATFORM=offscreen`.
- Coverage gaps:
  - No tests for `SettingsPanel` UI widgets, signals, or panel positioning.
  - `test_overlay_gui.py` only tests geometry and preset stepping; it does not test `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` drag simulation, context menus, or continuous slider resizing.
  - `test_config.py` explicitly tests clamping to `(160, 260, 380)`, which will fail if continuous diameter is implemented without updating tests.

---

## 2. Logic Chain

From the authoritative requirements in `ORIGINAL_REQUEST.md` (R3 and R4) and the observations above, the logical derivation of the solution proceeds as follows:

### Step 1: Settings Panel Invocation & Lifecycle
- **Requirement**: "Add an intuitive, floating Settings Panel opened directly from the camera bubble (via a visible gear button on the bubble and right-click context menu)"
- **Observation**: HUD has space for an extra control, and `OverlayWindow` currently swallows or ignores right-clicks.
- **Deduction**:
  1. Add `btn_settings` (`"⚙"`) to `AutoHidingHUD` emitting `settings_clicked = Signal()`.
  2. Implement `contextMenuEvent(event)` in `OverlayWindow` with a modern styled `QMenu` featuring `"⚙ Settings..."` alongside quick toggles.
  3. Wire both to a single `settings_requested = Signal()` on `OverlayWindow`.
  4. In `SelfiCameraApp`, manage an instance of `SettingsPanel`. Calling `toggle_settings_panel()` opens it if hidden or closes it if visible.

### Step 2: Floating Window Architecture & Positioning
- **Requirement**: "Modern dark theme styling matching Ubuntu / presenter aesthetics, floating window with Qt.Tool or frameless tool window, staying linked or floating alongside the camera bubble."
- **Deduction**:
  1. Base class: `QWidget` with flags `Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint`.
     - `Tool` ensures it does not pollute the Ubuntu dock or taskbar.
     - `FramelessWindowHint` enables 100% custom dark styling with rounded corners (12px radius) and custom draggable header bar.
     - `WindowStaysOnTopHint` ensures it remains accessible alongside the overlay above full-screen IDEs.
  2. Positioning algorithm:
     - Anchor to the right of the bubble: `target_x = overlay.x() + overlay.width() + 12`, `target_y = overlay.y()`.
     - Flip detection: If `target_x + panel.width() > screen.availableGeometry().right()`, flip to the left: `target_x = overlay.x() - panel.width() - 12`.
     - Clamp within vertical screen bounds: `target_y = max(screen_top, min(screen_bottom - panel.height(), target_y))`.
  3. Movability: The custom header bar handles mouse dragging so the presenter can reposition it anywhere across multiple monitors.

### Step 3: Five Control Sections & Processor Integration
- **Requirement**: Real-time lighting, background blur, size, camera/video, and window controls with immediate visual feedback without freezing video capture.
- **Deduction**:
  1. **Lighting Section**:
     - `AutoLightBoost` must support:
       * `auto_light: bool` (toggle adaptive mode).
       * `manual_gamma: float` (slider 0.40 to 2.20, default 1.00). When Auto-Light is off, `effective_gamma = manual_gamma`. When on, `effective_gamma = computed_gamma * manual_gamma`.
       * `target_luminance: float` (slider 50.0 to 220.0, default 125.0).
       * All adjustments update LUT instantly (`<0.1ms`), zero frame drop.
  2. **Background Blur Section**:
     - Both discrete tier buttons (`[Off]`, `[Subtle]`, `[Balanced]`, `[Heavy]`) and a continuous intensity slider (`0` to `100`).
     - Clicking a tier sets the slider (`0`, `25`, `50`, `85`); dragging the slider updates the active tier button and dynamically scales Gaussian blur kernel (`ksize = (k, k)` with `k = int(intensity * 0.4) * 2 + 1`).
     - Emits signals directly to `FrameProcessor.segmentation` without recreating ONNX session.
  3. **Size Section**:
     - Continuous slider (`120` to `600` px) with value readout label (`"260 px"`).
     - Preset buttons (`160 px`, `260 px`, `380 px`) for instant preset jumping.
     - Center-point anchoring must use float center coordinates to eliminate integer truncation drift:
       `center_x = self.x() + self.width() / 2.0; new_x = int(round(center_x - new_total_dim / 2.0))`.
  4. **Camera & Video Section**:
     - Camera device dropdown (`QComboBox`) dynamically populated from `V4L2DeviceScanner.list_devices()`.
     - Includes a `"🔄"` refresh button to rescan USB webcams.
     - Resolution dropdown (`640x480`, `1280x720`, `1920x1080`).
     - Horizontal Mirror (Flip) switch.
  5. **Window Management Section**:
     - Always-On-Top switch: toggles `Qt.WindowType.WindowStaysOnTopHint` on `OverlayWindow`.
     - Ghost mode switch: toggles click-through mode with warning reminder of exit shortcut (`Super+Alt+X`).

### Step 4: Configuration Subsystem Update
- Change `VALID_DIAMETERS` from `(160, 260, 380)` to a continuous range validation:
  `120 <= diameter <= 600`.
- Add new keys to `DEFAULT_CONFIG`:
  ```python
  "always_on_top": True,
  "manual_gamma": 1.0,
  "target_luminance": 125.0,
  "blur_intensity": 50,
  ```

### Step 5: Automated Testing Strategy (R4)
- **Requirement**: 100% pass rate under `QT_QPA_PLATFORM=offscreen`, covering mouse drag, slider resizing, Settings Panel signals/persistence, and window flags.
- **Deduction**:
  1. Add `tests/test_settings_panel.py` covering:
     - Initialization of all widgets and default states.
     - Lighting signals: gamma slider, target luminance slider, auto-light checkbox.
     - Blur signals: discrete tier buttons and continuous intensity slider with bidirectional synchronization.
     - Size signals: continuous slider (120-600) and preset buttons.
     - Camera/Video signals: device selection, resolution picker, flip toggle.
     - Window management signals: always-on-top and ghost mode toggles.
     - External state updates (`set_diameter_value`, `set_blur_tier`, etc.) without circular signal emission.
     - Panel positioning relative to parent overlay.
  2. Expand `tests/test_overlay_gui.py`:
     - Mouse drag simulation: `mousePressEvent` inside circle sets `_is_dragging=True`, outside circle does not; `mouseMoveEvent` updates window position; `mouseReleaseEvent` clears `_is_dragging`.
     - Right-click context menu event triggering.
     - Always-on-top runtime flag toggling.
     - Continuous slider center-point anchoring preservation.
  3. Update `tests/test_config.py`:
     - Test that continuous diameters (e.g. 210, 450) persist and reload without being clobbered.
     - Test persistence of new lighting and window keys.

---

## 3. Caveats

1. **Wayland Floating Tool Windows**:
   - In native Wayland sessions, sub-windows created with `Qt.WindowType.Tool` or `FramelessWindowHint` can sometimes be positioned arbitrarily by the Wayland compositor (Mutter/GNOME Shell) if not parented or if absolute `move()` is restricted.
   - Using `run.sh` with `QT_QPA_PLATFORM=xcb` (XWayland fallback) guarantees predictable absolute client positioning across multi-monitor setups.
2. **Click-Through Ghost Mode Interaction**:
   - When click-through ghost mode is activated on `OverlayWindow`, the overlay becomes transparent to mouse events (`WA_TransparentForMouseEvents`).
   - The `SettingsPanel` MUST be an independent top-level tool window (`parent=None` or top-level `QWidget`), so that mouse clicks on the SettingsPanel continue to function even while the camera bubble itself is in ghost mode. This allows presenters to easily toggle ghost mode back off directly from the panel.
3. **Camera Switching Latency**:
   - V4L2 device switching in `CameraCaptureWorker` happens asynchronously on the background capture thread. The UI dropdown updates immediately, and the capture worker performs a clean release-and-reopen cycle without blocking the Qt event loop.

---

## 4. Conclusion & Recommended Implementation Blueprint

### 4.1 Architecture Diagram: Settings Panel & Application Coordination

```
                                +---------------------------+
                                |      SelfiCameraApp       |
                                +-------------+-------------+
                                              |
                   +--------------------------+--------------------------+
                   |                          |                          |
                   v                          v                          v
       +-----------------------+  +-----------------------+  +-----------------------+
       |     OverlayWindow     |  |     SettingsPanel     |  | SystemTrayController  |
       |  - Gear Button (HUD)  |  |  - Lighting Controls  |  |  - Menu actions       |
       |  - Right-Click Menu   |  |  - Blur Tiers+Slider  |  |  - Settings action    |
       |  - Drag & Anchoring   |  |  - Continuous Size    |  +-----------------------+
       +-----------+-----------+  |  - Camera & Res Combo |
                   |              |  - Always-On-Top      |
                   |              +-----------+-----------+
                   |                          |
                   +------------+-------------+
                                | (Signals & State Sync)
                                v
                   +---------------------------+
                   |      FrameProcessor       |
                   |  - AutoLightBoost (gamma) |
                   |  - Segmentation (blur)    |
                   |  - Center-Crop & Mirror   |
                   +---------------------------+
```

### 4.2 Concrete Implementation Specifications

#### Component 1: `selficamera/ui/settings_panel.py` (New File)
A complete, standalone floating panel widget with 5 distinct control cards, dark theme styling matching Ubuntu/Catppuccin (`#1E1E2E`), and draggable header.

**Key Architecture**:
```python
class SettingsPanel(QWidget):
    # Signals for all controls
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
```

**Layout Hierarchy**:
- `QVBoxLayout` (main)
  - Custom Title Bar: Drag label `"⚙ SelfiCamera Settings"`, Close button `"✕"`.
  - `QScrollArea` (frameless with thin dark scrollbar) containing container with:
    - **Card 1: Lighting & Exposure (`QGroupBox`)**:
      * Auto-Light Boost `QCheckBox`
      * Brightness/Gamma: `QSlider` (range 40-220, maps to 0.40x-2.20x), label, and Reset button
      * Target Luminance: `QSlider` (range 50-220), label
    - **Card 2: Background Blur (`QGroupBox`)**:
      * Button row: `QButtonGroup` with `[Off]`, `[Subtle]`, `[Balanced]`, `[Heavy]`
      * Intensity: `QSlider` (range 0-100), label
    - **Card 3: Bubble Size (`QGroupBox`)**:
      * Diameter: `QSlider` (range 120-600), label (`"260 px"`)
      * Presets row: `[160 px]`, `[260 px]`, `[380 px]`
    - **Card 4: Camera & Video (`QGroupBox`)**:
      * Device row: `QComboBox` (lists `/dev/video*`), `QPushButton("🔄")` (refresh)
      * Resolution: `QComboBox` (`640x480`, `1280x720`, `1920x1080`)
      * Mirror: `QCheckBox("Horizontal Mirror (Flip)")`
    - **Card 5: Window & Behavior (`QGroupBox`)**:
      * `QCheckBox("Always-On-Top Persistence")`
      * `QCheckBox("Click-Through Ghost Mode (Super+Alt+X to exit)")`
  - Footer Bar: `QPushButton("Reset Defaults")` and `QPushButton("Close")`.

**Positioning Logic**:
```python
def position_alongside_overlay(self, overlay: QWidget) -> None:
    screen = QGuiApplication.primaryScreen()
    avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
    
    # Try right side first
    target_x = overlay.x() + overlay.width() + 12
    target_y = overlay.y()
    
    # If overflows right screen edge, flip to left side
    if target_x + self.width() > avail.right():
        target_x = overlay.x() - self.width() - 12
    
    # Clamp within screen bounds
    target_x = max(avail.left(), min(avail.right() - self.width(), target_x))
    target_y = max(avail.top(), min(avail.bottom() - self.height(), target_y))
    self.move(target_x, target_y)
```

#### Component 2: `selficamera/ui/hud.py` & `selficamera/ui/overlay.py` Updates
1. In `AutoHidingHUD` (`hud.py`):
   - Add `settings_clicked = Signal()`
   - Add `self.btn_settings = QPushButton("⚙", self)`
   - Set tooltip: `"Open Settings & Controls Panel (or Right-Click)"`
   - Connect `self.btn_settings.clicked.connect(self.settings_clicked)`
   - Adjust HUD capsule width to `264px` (`hud_w = 264`).
2. In `OverlayWindow` (`overlay.py`):
   - Add `settings_requested = Signal()`
   - Add `always_on_top_changed = Signal(bool)`
   - Implement `contextMenuEvent(self, event: QContextMenuEvent)`:
     ```python
     def contextMenuEvent(self, event) -> None:
         if self._is_ghost_mode:
             return
         menu = QMenu(self)
         # Modern dark stylesheet
         act_settings = menu.addAction("⚙ Settings...")
         act_settings.triggered.connect(self.settings_requested.emit)
         menu.addSeparator()
         # Quick toggles (Flip, Light, Blur submenu, Always-on-top, Ghost)
         menu.exec(event.globalPos())
     ```
   - Connect `self.hud.settings_clicked.connect(self.settings_requested.emit)`.
   - Implement `set_always_on_top(self, enabled: bool) -> None`:
     ```python
     def set_always_on_top(self, enabled: bool) -> None:
         flags = self.windowFlags()
         if enabled:
             flags |= Qt.WindowType.WindowStaysOnTopHint
         else:
             flags &= ~Qt.WindowType.WindowStaysOnTopHint
         was_visible = self.isVisible()
         self.setWindowFlags(flags)
         if was_visible:
             self.show()
         self.always_on_top_changed.emit(enabled)
     ```
   - Update `set_diameter` with floating-point center calculations to eliminate continuous slider rounding drift:
     ```python
     center_x = self.x() + self.width() / 2.0
     center_y = self.y() + self.height() / 2.0
     self._diameter = max(120, min(600, int(val)))
     total_dim = self._diameter + (2 * self.shadow_margin)
     new_x = int(round(center_x - total_dim / 2.0))
     new_y = int(round(center_y - total_dim / 2.0))
     self.setGeometry(new_x, new_y, total_dim, total_dim)
     self._reposition_hud()
     self.update()
     self.diameter_changed.emit(self._diameter)
     ```

#### Component 3: `selficamera/config.py` Updates
- Update validation in `load()`:
  ```python
  # Before:
  # if merged.get("diameter") not in VALID_DIAMETERS:
  #     merged["diameter"] = DEFAULT_CONFIG["diameter"]
  
  # After:
  diameter = merged.get("diameter", DEFAULT_CONFIG["diameter"])
  if not isinstance(diameter, (int, float)) or not (120 <= diameter <= 600):
      merged["diameter"] = DEFAULT_CONFIG["diameter"]
  else:
      merged["diameter"] = int(diameter)
  ```
- Add default keys:
  ```python
  "always_on_top": True,
  "manual_gamma": 1.0,
  "target_luminance": 125.0,
  "blur_intensity": 50,
  ```

#### Component 4: Processor Updates (`lighting.py`, `segmentation.py`, `pipeline.py`)
1. In `AutoLightBoost` (`lighting.py`):
   - Add `self.manual_gamma: float = 1.0`
   - In `process(frame)`:
     ```python
     if not self.enabled:
         if abs(self.manual_gamma - 1.0) < 0.02:
             return frame
         lut = self._build_lut(self.manual_gamma)
         return cv2.LUT(frame, lut)
     ```
     When enabled:
     ```python
     effective_gamma = computed_gamma * self.manual_gamma
     self._current_gamma = (1.0 - self.smoothing_alpha) * self._current_gamma + self.smoothing_alpha * float(effective_gamma)
     ```
   - Add setters: `set_manual_gamma(float)` and `set_target_luminance(float)`.
2. In `SegmentationBlurEngine` (`segmentation.py`):
   - Add `self.intensity: int = 50`
   - Add `set_intensity(val: int)`: dynamically calculates Gaussian kernel size `k = max(3, int(val * 0.35) * 2 + 1)`.
   - Keep `set_tier(tier)` mapped to intensities: `0 -> 0`, `1 -> 25`, `2 -> 50`, `3 -> 85`.

#### Component 5: Application Wiring (`selficamera/app.py`)
- Instantiate `self.settings_panel = SettingsPanel()`
- Connect all signals between `settings_panel`, `overlay`, `processor`, `capture_worker`, `config`, and `tray`:
  - `overlay.settings_requested` -> `toggle_settings_panel`
  - `settings_panel.diameter_changed` -> `overlay.set_diameter`
  - `overlay.diameter_changed` -> `settings_panel.set_diameter_value` (with `blockSignals`)
  - `settings_panel.blur_tier_selected` -> `app.set_blur_level`
  - `settings_panel.manual_gamma_changed` -> `processor.set_gamma`
  - `settings_panel.target_luminance_changed` -> `processor.set_target_luminance`
  - `settings_panel.auto_light_toggled` -> `app.set_auto_light`
  - `settings_panel.always_on_top_toggled` -> `overlay.set_always_on_top`
  - `settings_panel.ghost_mode_toggled` -> `overlay.set_click_through`
  - `settings_panel.device_selected` -> `app.set_device`
  - `settings_panel.resolution_selected` -> `app.set_resolution`

---

## 5. Verification Method

### 5.1 Automated Test Execution Command
Execute the full test suite in headless offscreen mode inside the virtual environment:
```bash
source .venv/bin/activate && QT_QPA_PLATFORM=offscreen pytest -v
```

### 5.2 Required Test Matrix for R3 & R4

| Test Target | Test Function | Verification Description |
| :--- | :--- | :--- |
| **Settings Panel UI** | `test_settings_panel_initialization` | Verifies all 5 cards, sliders, combos, and buttons initialize with default values. |
| **Lighting Signals** | `test_settings_panel_lighting_signals` | Tests gamma slider, target luminance slider, and auto-light toggle emit expected signals with accurate numeric ranges. |
| **Blur Signals & Sync** | `test_settings_panel_blur_controls` | Tests tier buttons (0..3) and continuous slider (0..100) emit signals and synchronize bidirectionally without feedback loops. |
| **Size Controls & Slider** | `test_settings_panel_size_controls` | Tests continuous slider (120-600) and preset buttons (160, 260, 380) emit diameter changes. |
| **Camera & Video** | `test_settings_panel_camera_controls` | Tests device dropdown selection, resolution dropdown selection, and mirror toggle signals. |
| **Window Flags** | `test_settings_panel_window_flags_signals` | Tests Always-On-Top and Ghost mode toggle signals. |
| **Mouse Drag Lifecycle** | `test_mouse_drag_lifecycle` | In `test_overlay_gui.py`: simulates `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`. Confirms window position updates and `position_changed` signal emits. |
| **Screen Clamping** | `test_mouse_drag_screen_clamping` | Tests dragging toward and past screen edges cleanly clamps within available screen geometry. |
| **Center Anchoring** | `test_continuous_slider_center_anchoring` | Sets diameters across 120-600 range and verifies `center == (x + w/2, y + h/2)` remains stationary. |
| **Context Menu** | `test_right_click_context_menu` | Simulates right-click on overlay and verifies context menu opens with Settings option. |
| **Config Persistence** | `test_continuous_diameter_persistence` | In `test_config.py`: verifies continuous values (e.g., 210, 475) persist and reload without being reset to 260. |

### 5.3 Performance Benchmark Command
Verify that live lighting and blur intensity adjustments maintain the strict `<30ms` latency budget:
```bash
source .venv/bin/activate && python3 benchmarks/benchmark_pipeline.py
```
Expected result: Pipeline total latency `< 25ms` per frame, CPU utilization `< 15%`.

### 5.4 Invalidation Conditions
- Any test failure under `QT_QPA_PLATFORM=offscreen`.
- Diameter resetting to 260px when set to a non-preset value (e.g., 210px) and reloaded from disk.
- Center coordinate drifting by more than 1 pixel during continuous slider resizing.
- Settings panel becoming unresponsive or blocked when click-through ghost mode is enabled on the camera bubble.
