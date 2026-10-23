# Phase 2: Product Specifications & Requirements Handoff

**Project:** SelfiCamera — Lightweight Circular Desktop Presenter Camera Overlay  
**Phase:** Phase 2 (Product Specifications & Requirements Engineering) $\rightarrow$ Handing off to Phase 3 (Full-Stack Engineer) & Phase 4 (QA & Code Reviewer)  
**Author:** Product Manager (PM)  
**Target File:** `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/pm_2/handoff.md`  
**Date:** 2026-10-22  
**Status:** APPROVED & READY FOR IMPLEMENTATION  

---

## 1. Executive Summary & Purpose

Following the architectural foundation established by the CTO (`cto_2/handoff.md`) and the latest feature request (`2026-10-22T19:59:23Z`), this document provides the formal Product Requirements Document (PRD), User Stories, and Gherkin-style `Given / When / Then` Acceptance Criteria for the next iteration of SelfiCamera.

### Strategic Objective
Ensure that the **5 core presenter overlay capabilities** (Window Movement/Dragging, Resizing, Lighting Control, Blur Control, Always-on-Top Persistence) and the newly added **1-Click Corner Snapping Buttons** in the floating `SettingsPanel` are maximally intuitive, accessible, ergonomically comfortable, and configurable directly from the graphical user interface on Ubuntu Linux (Wayland & X11/XWayland).

### Baseline Metrics & Guardrails
- **Zero Test Regressions**: All 63 existing tests in `tests/` must remain passing under `QT_QPA_PLATFORM=offscreen`.
- **Latency Budget**: End-to-end frame processing P95 latency must remain $< 25.0$ ms at 720p with Tier 2 (Balanced) bokeh blur (current baseline: 16.17 ms).
- **Process Footprint**: Offline, zero-cloud, $< 50$ MB RSS memory footprint.

---

## 2. Product Personas & User Journey

### Primary Persona: "The Live Presenter & Technical Streamer"
- **Profile**: A software engineer, educator, or live streamer presenting code in VS Code, terminal windows, and browsers on Ubuntu Linux with GNOME Shell (Wayland/X11).
- **Pain Points**:
  - Dragging a camera bubble during live talks can be clumsy or slow when trying to park it out of the way of slides or terminal output.
  - Complicated menu hierarchies or hidden shortcut keys cause panic during live presentations.
  - Accidental center-point drift when resizing makes the presenter re-align the bubble manually.
  - Sub-optimal ambient lighting requires rapid gamma compensation without digging through system settings.
- **Value Delivered**:
  - 1-click deterministic corner docking (`↖ TL`, `↗ TR`, `↙ BL`, `↘ BR`) directly inside the Settings Panel.
  - Instant live control over bubble size (scroll, edge drag, slider, presets) with zero center drift.
  - Direct lighting and bokeh blur control with live sliders and discrete tier selectors.
  - Persistent visibility over full-screen IDEs and presentations.

---

## 3. Epics & User Stories (MoSCoW Prioritized)

| Epic ID | Title | Priority | Core Component |
| :--- | :--- | :--- | :--- |
| **EP-01** | 1-Click Corner Snapping UI | **MUST HAVE** | `SettingsPanel` (Card 5) & `OverlayWindow` |
| **EP-02** | Fluid Drag-to-Move & HUD Click Transparency | **MUST HAVE** | `OverlayWindow` & `AutoHidingHUD` |
| **EP-03** | Multi-Modal Zero-Drift Resizing | **MUST HAVE** | `OverlayWindow` & `SettingsPanel` (Card 3) |
| **EP-04** | Intuitive UI Lighting Controls | **MUST HAVE** | `SettingsPanel` (Card 1) & `OverlayWindow.hud` |
| **EP-05** | Intuitive UI Background Blur Controls | **MUST HAVE** | `SettingsPanel` (Card 2) & `OverlayWindow.hud` |
| **EP-06** | Reliable Always-On-Top UI Toggles | **MUST HAVE** | `SettingsPanel` (Card 5) & Context Menu |

---

### Epic 1: 1-Click Corner Snapping Buttons in SettingsPanel (MUST HAVE)

#### User Story US-1.1: Spatial 2x2 Corner Snapping Grid
> **As a** live presenter,  
> **I want** a dedicated 2x2 spatial grid of corner snapping buttons (`↖ TL`, `↗ TR`, `↙ BL`, `↘ BR`) in the Settings Panel,  
> **So that** I can instantly dock the camera bubble into any screen corner with a single mouse click without needing to remember keyboard shortcuts.

#### User Story US-1.2: Smooth Animated Docking & Multi-Monitor Clamping
> **As a** multi-monitor Ubuntu user,  
> **I want** corner snapping to animate smoothly into position and automatically respect my active display's Ubuntu Dock and GNOME Top Bar,  
> **So that** the camera bubble never overlaps system panels or lands off-screen on a secondary monitor.

#### User Story US-1.3: Atomic Position Persistence
> **As a** user,  
> **I want** the snapped corner position to be saved immediately to my user configuration,  
> **So that** subsequent launches of SelfiCamera reopen the bubble in my preferred corner.

---

### Epic 2: Fluid Drag-to-Move with HUD Click Transparency (MUST HAVE)

#### User Story US-2.1: Non-Blocking Bubble Dragging
> **As a** presenter,  
> **I want** to left-click anywhere inside the circular camera bubble (or along the voice aura ring) to drag it smoothly across my screen,  
> **So that** I can reposition my camera feed on-the-fly without stutters or lag.

#### User Story US-2.2: Transparent HUD Pass-Through
> **As a** user,  
> **I want** the auto-hiding capsule HUD to be completely mouse-transparent while faded out,  
> **So that** initial drag clicks are never trapped or swallowed by invisible overlay widgets.

#### User Story US-2.3: Screen Boundary Clamping
> **As a** user,  
> **I want** the window drag logic to clamp coordinates within the available virtual desktop area,  
> **So that** the camera circle cannot be accidentally dragged beyond the screen edge into an unreachable void.

---

### Epic 3: Smooth Resizing with Zero Center-Point Drift (MUST HAVE)

#### User Story US-3.1: Continuous & Discrete Sizing in Settings Panel
> **As a** presenter,  
> **I want** both a continuous diameter slider (120 px to 600 px) with live monospace pixel readout and one-click preset buttons (`160 px`, `260 px`, `380 px`) in Card 3 of the Settings Panel,  
> **So that** I can either fine-tune my camera size or jump instantly to standard presentation dimensions.

#### User Story US-3.2: Direct Mouse Scroll & Radial Edge Dragging
> **As a** user,  
> **I want** to resize the bubble directly using the mouse scroll wheel over the bubble or by dragging the perimeter ring (`[r - 14, r + 16]`),  
> **So that** I have immediate on-canvas sizing controls without opening the Settings Panel.

#### User Story US-3.3: Canonical Zero-Drift Center Anchor
> **As a** user,  
> **I want** resizing by any method to strictly anchor around the bubble's center point ($0.0\text{ px}$ drift),  
> **So that** expanding or shrinking the bubble does not shift my face off-center on the desktop.

---

### Epic 4: Intuitive UI Lighting Controls (MUST HAVE)

#### User Story US-4.1: Single-Click Auto-Light Boost Toggle
> **As a** presenter in fluctuating lighting conditions,  
> **I want** a 1-click "Light" button on the HUD and an "Auto-Light Boost" checkbox in the Settings Panel,  
> **So that** I can immediately toggle automatic low-light exposure boost with active visual feedback.

#### User Story US-4.2: Manual Gamma & Target Luminance Fine-Tuning
> **As a** user with specific lighting preferences,  
> **I want** a continuous manual gamma compensation slider ($0.40\times$ to $2.20\times$), a target luminance slider ($50$ to $220$), and a quick reset button (`↺`) to restore $1.00\times$,  
> **So that** I can calibrate my video feed's exposure in real time with immediate visual updates.

---

### Epic 5: Intuitive UI Background Blur Controls (MUST HAVE)

#### User Story US-5.1: HUD Blur Cycling
> **As a** presenter,  
> **I want** a 1-click button on the HUD that cycles through the 4 background blur tiers (`B:Off`, `B:Sub`, `B:Bal`, `B:Hvy`),  
> **So that** I can adjust my background privacy instantly during a presentation.

#### User Story US-5.2: Bidirectional Synchronization of Tier Buttons & Slider
> **As a** user configuring blur in the Settings Panel,  
> **I want** 4 discrete tier buttons and a continuous intensity slider ($0\%$ to $100\%$) that stay bidirectionally synchronized without recursive event feedback loops,  
> **So that** selecting a tier updates the slider, and moving the slider automatically highlights the corresponding tier button.

---

### Epic 6: Reliable Always-On-Top UI Toggles (MUST HAVE)

#### User Story US-6.1: Dual UI Access for Always-On-Top
> **As a** presenter,  
> **I want** to toggle Always-On-Top persistence both from the Settings Panel checkbox and via right-click context menu on the camera bubble,  
> **So that** I can ensure my presenter camera never gets buried under full-screen browser tabs or IDE windows.

#### User Story US-6.2: State Persistence & Wayland/X11 Guarantee
> **As a** user,  
> **I want** my Always-On-Top setting to persist across application restarts and operate reliably under GNOME Shell,  
> **So that** I don't have to reconfigure window layering every time I start SelfiCamera.

---

## 4. Comprehensive Acceptance Criteria (Given / When / Then)

### Feature 1: 1-Click Corner Snapping Buttons (Card 5)

#### AC-1.1: UI Grid & Button Rendering
```gherkin
Scenario: SettingsPanel renders spatial 2x2 corner snap buttons
  Given the SettingsPanel is instantiated and visible
  When inspecting Card 5 ("Window Management")
  Then there is a "Snap to Corner:" section positioned above the window checkboxes
  And there is a 2x2 QGridLayout containing four QPushButton widgets:
    | Button Attribute | Top-Left       | Top-Right      | Bottom-Left    | Bottom-Right   |
    | Variable Name    | btn_snap_tl    | btn_snap_tr    | btn_snap_bl    | btn_snap_br    |
    | Button Label     | "↖ TL"         | "↗ TR"         | "↙ BL"         | "↘ BR"         |
    | Grid Coordinates | (row 0, col 0) | (row 0, col 1) | (row 1, col 0) | (row 1, col 1) |
  And each button displays a descriptive tooltip referencing the presenter shortcut:
    | Button      | Tooltip Text                                      |
    | btn_snap_tl | "Snap to Top-Left corner (Super+Alt+1)"           |
    | btn_snap_tr | "Snap to Top-Right corner (Super+Alt+2)"          |
    | btn_snap_bl | "Snap to Bottom-Left corner (Super+Alt+3)"         |
    | btn_snap_br | "Snap to Bottom-Right corner (Super+Alt+4)"       |
```

#### AC-1.2: Signal Emission Contract
```gherkin
Scenario Outline: Clicking corner snap button emits corner_snap_requested signal
  Given the SettingsPanel is displayed
  When the user clicks the "<button>" button
  Then the signal "corner_snap_requested" is emitted with integer value <corner_id>
  And the semantic alias signal "snap_corner_requested" emits the same integer value <corner_id>

  Examples:
    | button      | corner_id |
    | btn_snap_tl | 1         |
    | btn_snap_tr | 2         |
    | btn_snap_bl | 3         |
    | btn_snap_br | 4         |
```

#### AC-1.3: Window Snapping Animation & Multi-Monitor Geometry Clamping
```gherkin
Scenario Outline: Overlay snaps to the correct display corner with margin and panel avoidance
  Given the SelfiCamera application is running with active display geometry
  When the application receives "corner_snap_requested(<corner_id>)"
  Then "OverlayWindow.snap_to_corner(<corner_id>)" is executed
  And the active screen is identified via self.screen(), screenAt(center_point), or primaryScreen()
  And the target coordinates are calculated using "availableGeometry()" with 24px margin:
    | corner_id | target_x Calculation                                | target_y Calculation                                 |
    | 1 (TL)    | avail_geo.left() + 24                               | avail_geo.top() + 24                                 |
    | 2 (TR)    | avail_geo.right() - window_width - 24 + 1           | avail_geo.top() + 24                                 |
    | 3 (BL)    | avail_geo.left() + 24                               | avail_geo.bottom() - window_height - 24 + 1          |
    | 4 (BR)    | avail_geo.right() - window_width - 24 + 1           | avail_geo.bottom() - window_height - 24 + 1          |
  And a smooth 200ms QPropertyAnimation transitions the overlay window position
  And the bubble does not overlap the GNOME Shell Top Bar or Ubuntu Dock
  And the new window position is saved atomically to "config.json" upon animation completion

  Examples:
    | corner_id | description   |
    | 1         | Top-Left      |
    | 2         | Top-Right     |
    | 3         | Bottom-Left   |
    | 4         | Bottom-Right  |
```

---

### Feature 2: Fluid Window Drag-to-Move with HUD Click Transparency

#### AC-2.1: Canvas Drag Initiation & Wayland/X11 Compatibility
```gherkin
Scenario: Dragging anywhere inside the bubble moves the window smoothly
  Given the OverlayWindow is visible and not in Ghost Mode
  When the user presses the left mouse button at distance <= (diameter / 2 + 4.0) from center
  And moves the cursor across the desktop
  Then on native Wayland, "windowHandle().startSystemMove()" is invoked if available
  And on X11/XWayland or fallback, position deltas are applied directly to "self.move()"
  And the center-point tracking variable "self._center_point" is updated on every delta
  And the window position remains clamped within the combined virtual desktop bounds
```

#### AC-2.2: Dormant HUD Mouse Transparency
```gherkin
Scenario: Clicking over dormant HUD passes mouse events directly to bubble
  Given the AutoHidingHUD has an opacity of 0.0 (dormant/hidden)
  When the user left-clicks on the bubble area where the HUD resides
  Then the HUD widget has "WA_TransparentForMouseEvents = True"
  And the click event falls through directly to "OverlayWindow.mousePressEvent"
  And window dragging initiates immediately without delay or event drop
```

---

### Feature 3: Smooth Multi-Modal Resizing with Zero Center-Point Drift

#### AC-3.1: Zero Center-Point Drift Guarantee
```gherkin
Scenario Outline: Resizing the camera bubble preserves the exact center coordinate
  Given an OverlayWindow centered at floating point coordinates (center_x, center_y)
  When the bubble is resized from diameter <start_dia> to <target_dia> via <resize_method>
  Then the new window dimensions become (target_dia + 2 * shadow_margin, target_dia + 2 * shadow_margin)
  And the new center point (x + width / 2.0, y + height / 2.0) has 0.0 px drift from (center_x, center_y)

  Examples:
    | start_dia | target_dia | resize_method                |
    | 260       | 380        | Mouse wheel scroll           |
    | 260       | 160        | Radial edge perimeter drag   |
    | 260       | 320        | SettingsPanel slider_diameter|
    | 260       | 160        | SettingsPanel 160px preset   |
    | 160       | 380        | SettingsPanel 380px preset   |
```

#### AC-3.2: SettingsPanel Size Slider & Monospace Readout
```gherkin
Scenario: Adjusting SettingsPanel diameter slider updates overlay and readout
  Given the SettingsPanel is displayed
  When the user moves "slider_diameter" to 340
  Then "lbl_diameter" displays "340 px" in monospace font
  And "diameter_changed.emit(340)" is emitted
  And the OverlayWindow resizes dynamically to diameter 340 px
  And clicking preset "260 px" sets "slider_diameter" to 260 and updates the bubble instantly
```

---

### Feature 4: Intuitive UI Lighting Controls

#### AC-4.1: HUD Auto-Light Toggle
```gherkin
Scenario: HUD Light button toggles Auto-Light Boost
  Given the OverlayWindow is visible and HUD is faded in
  When the user clicks the "Light" button on the HUD
  Then the Auto-Light Boost state is toggled in the FrameProcessor
  And the HUD "Light" button updates visual style (highlighted when active)
  And the "cb_auto_light" checkbox in SettingsPanel synchronizes state
```

#### AC-4.2: SettingsPanel Gamma & Luminance Controls
```gherkin
Scenario: Adjusting manual gamma and target luminance in SettingsPanel
  Given the SettingsPanel is open
  When the user moves "slider_gamma" to 160
  Then "lbl_gamma" displays "1.60x"
  And "manual_gamma_changed.emit(1.60)" is emitted
  And FrameProcessor generates a 256-element uint8 gamma LUT in < 1.5 ms
  When the user clicks the "btn_gamma_reset" ("↺") button
  Then "slider_gamma" resets to 100
  And "lbl_gamma" displays "1.00x"
  And FrameProcessor manual gamma returns to 1.00
```

---

### Feature 5: Intuitive UI Background Blur Controls

#### AC-5.1: HUD Blur Tier Cycling
```gherkin
Scenario Outline: HUD Blur button cycles sequentially through tiers
  Given the HUD blur button is currently in state <current_tier> ("<current_label>")
  When the user clicks the HUD blur button
  Then the blur level advances to <next_tier>
  And the HUD button text updates to "<next_label>"
  And the FrameProcessor blur tier is updated immediately

  Examples:
    | current_tier | current_label | next_tier | next_label |
    | 0            | "B:Off"       | 1         | "B:Sub"    |
    | 1            | "B:Sub"       | 2         | "B:Bal"    |
    | 2            | "B:Bal"       | 3         | "B:Hvy"    |
    | 3            | "B:Hvy"       | 0         | "B:Off"    |
```

#### AC-5.2: SettingsPanel Bidirectional Blur Synchronization
```gherkin
Scenario: Discrete blur buttons and continuous intensity slider synchronize without loops
  Given the SettingsPanel is open
  When the user clicks tier button "Heavy" (tier 3)
  Then "slider_blur" moves to 85%
  And "lbl_blur" displays "85%"
  When the user drags "slider_blur" to 25%
  Then tier button "Subtle" (tier 1) becomes exclusively checked
  And "lbl_blur" displays "25%"
  And the re-entrancy guard "_syncing_blur" prevents recursive signal loops
```

---

### Feature 6: Reliable Always-On-Top UI Toggles & Persistence

#### AC-6.1: Context Menu & SettingsPanel AOT Toggling
```gherkin
Scenario: Toggling Always-On-Top updates window flags and persists state
  Given the SelfiCamera overlay is running
  When the user unchecks "cb_always_on_top" in the SettingsPanel
  Then "always_on_top_toggled.emit(False)" is emitted
  And "OverlayWindow.set_always_on_top(False)" clears "WindowStaysOnTopHint"
  And "OverlayWindow.show()" is called immediately to prevent Qt hide-on-flag-change
  And the right-click context menu "Always-On-Top" action reflects unchecked state
  And "always_on_top: false" is saved to user configuration
```

---

## 5. UI Layout & Visual Specifications (Card 5 Extension)

### 5.1 Card 5 Layout Structure
Inside `selficamera/ui/settings_panel.py`, method `_build_card_window_mgmt()` must be laid out as follows:

```
+-------------------------------------------------------------+
| CONTROL CARD: WINDOW MANAGEMENT                             |
|                                                             |
| [Label] "WINDOW MANAGEMENT" (class: card_title, color:#89B4FA)
|                                                             |
| [Label] "Snap to Corner:"                                   |
| +-----------------------------+---------------------------+ |
| | [Button] "↖ TL"             | [Button] "↗ TR"           | |
| | (btn_snap_tl, row 0, col 0) | (btn_snap_tr, row 0, col 1)| |
| +-----------------------------+---------------------------+ |
| | [Button] "↙ BL"             | [Button] "↘ BR"           | |
| | (btn_snap_bl, row 1, col 0) | (btn_snap_br, row 1, col 1)| |
| +-----------------------------+---------------------------+ |
|                                                             |
| [QCheckBox] [x] Always-On-Top (Pin above windows)           |
| [QCheckBox] [ ] Click-Through Ghost Mode                    |
| [Label]     "Exit Ghost Mode: Press Super+Alt+X" (hint)     |
+-------------------------------------------------------------+
```

### 5.2 Style and Theming Specifications
- **Button Palette**:
  - Normal: `#313244` background, `#CDD6F4` text, `border: 1px solid rgba(255, 255, 255, 20)`.
  - Hover: `#45475A` background, `#89B4FA` border highlight.
  - Pressed: `#585B70` background.
  - Border radius: `6px`, padding: `4px 8px`, font: bold `11px`.
- **Layout Spacing**:
  - Grid horizontal and vertical spacing: `4px`.
  - Card padding: `contents margins (8, 6, 8, 6)`, spacing: `5px`.

---

## 6. Definition of Done (DoD)

To declare this feature set fully accepted and ready for delivery:

1. **Code Completeness**:
   - `SettingsPanel` declares signals `corner_snap_requested = Signal(int)` and alias `snap_corner_requested`.
   - `SettingsPanel._build_card_window_mgmt()` includes the 2x2 grid with `btn_snap_tl`, `btn_snap_tr`, `btn_snap_bl`, and `btn_snap_br`.
   - `SelfiCameraApp._wire_settings_panel()` connects `settings_panel.corner_snap_requested` to `overlay.snap_to_corner`.
   - `OverlayWindow.snap_to_corner()` includes multi-monitor screen resolution using `self.screen() or QGuiApplication.screenAt(center) or primaryScreen()`.

2. **Automated Test Suite Pass Rate**:
   - All 63 existing unit and integration tests must pass with 0 failures under `QT_QPA_PLATFORM=offscreen`.
   - New automated tests added to `tests/test_settings_panel.py`:
     - `test_settings_panel_corner_snap_buttons_render`
     - `test_settings_panel_corner_snap_signals`
     - `test_app_settings_panel_corner_snap_integration`
   - Total test count must be $\ge 66$ tests, passing 100%.

3. **Performance & Latency Budget**:
   - Benchmarking via `benchmarks/benchmark_pipeline.py` confirms 500 frames at 720p maintain **P95 latency $< 25.0$ ms** and throughput $> 60$ FPS.

4. **Forensic Integrity & Architecture Adherence**:
   - No mock leakage into production runtime.
   - Clean headless compatibility on Ubuntu Linux.
   - Zero recursion loops on bidirectional UI synchronization.

---

## 7. Phased Implementation Tasks for Full-Stack & AI Engineer (Phase 3)

| Task ID | Component | File | Action Required |
| :--- | :--- | :--- | :--- |
| **T3.1** | Signals | `selficamera/ui/settings_panel.py` | Declare `corner_snap_requested = Signal(int)` and `snap_corner_requested = corner_snap_requested`. |
| **T3.2** | Card 5 UI | `selficamera/ui/settings_panel.py` | Add 2x2 grid layout with buttons `btn_snap_tl`, `btn_snap_tr`, `btn_snap_bl`, `btn_snap_br` emitting corner IDs 1, 2, 3, 4. |
| **T3.3** | Multi-Monitor | `selficamera/ui/overlay.py` | Enhance `snap_to_corner(self, corner_id)` to resolve screen via `self.screen() or QGuiApplication.screenAt(self._center_point.toPoint()) or QGuiApplication.primaryScreen()`. |
| **T3.4** | App Wiring | `selficamera/app.py` | In `_wire_settings_panel()`, connect `self.settings_panel.corner_snap_requested.connect(self.overlay.snap_to_corner)`. |
| **T3.5** | Unit Tests | `tests/test_settings_panel.py` | Add rendering, signal emission, and app integration test cases for corner snapping. |
| **T3.6** | Verification | CLI / Pytest | Run `pytest tests/` and `python benchmarks/benchmark_pipeline.py` to verify full pass and latency budget. |

---

## 8. QA Validation Matrix for QA & Code Reviewer (Phase 4)

| Test ID | Test Category | Target Scope | Expected Result |
| :--- | :--- | :--- | :--- |
| **QA-01** | Visual & Layout | `SettingsPanel.btn_snap_*` | 4 buttons rendered in 2x2 grid with exact labels `"↖ TL"`, `"↗ TR"`, `"↙ BL"`, `"↘ BR"`. |
| **QA-02** | Signal Verification | Qt Signal Spy on `corner_snap_requested` | Emits `1` for TL, `2` for TR, `3` for BL, `4` for BR. |
| **QA-03** | End-to-End Docking | `SelfiCameraApp` integration | Clicking button animates overlay to expected desktop corner coordinates taking 24px margin into account. |
| **QA-04** | Multi-Monitor Dock | Screen geometry resolution | When bubble is moved to secondary screen, corner snap docks to the secondary screen's corners, not primary screen. |
| **QA-05** | Regression Suite | All test files in `tests/` | 100% pass rate under `QT_QPA_PLATFORM=offscreen`. |
| **QA-06** | Latency Gate | `benchmark_pipeline.py` | P95 latency $< 25.0$ ms. |

---

## 9. Handoff Sign-off

The Phase 2 Product Specifications are **COMPLETE**, unambiguously defined, and officially signed off by the Product Manager. The task is ready for Phase 3 implementation by the Full-Stack & AI Engineer.
