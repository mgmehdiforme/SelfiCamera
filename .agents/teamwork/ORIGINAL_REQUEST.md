# Original User Request

## 2026-10-22T09:10:08Z

Use our software development team agents to build fully. Build SelfiCamera, a lightweight, zero-bloat, fully offline desktop floating circular presenter camera overlay application for Ubuntu Linux (Wayland and X11) designed for live presenters, coders, and streamers.

Working directory: /run/media/mehdi/Projects/PersonalProjects/SelfiCamera
Integrity mode: development

## Requirements

### R1. Frameless Circular Presentation Overlay Window
A floating, borderless circular camera window (1:1 aspect ratio with centered cropping and soft drop shadow) running on Ubuntu Linux (GNOME on Wayland and X11). The overlay must support fluid drag-to-move, scroll-to-resize (supporting predefined diameters 160px, 260px, 380px), always-on-top persistence over full-screen IDEs/browsers, and auto-hiding on-hover HUD controls (fading out after mouse exit).

### R2. Real-Time Camera Pipeline & Offline 3-Tier Background Blur
V4L2 camera capture with horizontal mirror toggle, real-time exposure/gamma/white-balance lighting compensation ("Auto-Light Boost"), and a 3-level bokeh background blur (Level 0: Off, Level 1: Subtle, Level 2: Balanced, Level 3: Heavy) powered by an ultra-lightweight (~2MB) offline segmentation model running purely locally on CPU/GPU without cloud APIs, achieving <30ms latency and <5% CPU utilization.

### R3. Presenter Shortcuts, Audio Voice Aura & System Tray
Presenter desktop workflow integration including:
- Dual-mode global shortcuts (X11 global grab + Wayland portal/CLI trigger) for toggling visibility (`Super+Alt+C`), click-through ghost mode (`Super+Alt+X`), snapping to desktop corners (`Super+Alt+1-4`), and cycling blur levels (`Super+Alt+B`).
- PipeWire / PulseAudio voice aura visual mic indicator around the circular border that pulses/glows dynamically with voice activity.
- Ubuntu AppIndicator / System Tray menu for device selection (`/dev/video*`), resolution switching, horizontal flip toggle, click-through toggle, and clean exit.

### R4. Automated Testing, Benchmarking & Environment Isolation
All code must run inside an isolated Python virtual environment (`.venv`) adhering to Ubuntu standards. Provide comprehensive automated pytest suites with mock V4L2 video feeds, mock audio sources, headless Qt GUI tests (pytest-qt), and performance benchmark scripts verifying end-to-end latency and CPU consumption.

## Verification Resources
- The agent team will create automated test fixtures with synthetic/mock V4L2 video frames and audio sine waves to verify all processing pipelines headlessly.
- Benchmark scripts measuring frame processing time per stage (capture, lighting boost, segmentation, render).

## Acceptance Criteria

### Overlay Window & Interaction
- [ ] Circular viewport renders as a clean anti-aliased 1:1 circle with aspect-ratio locked video feed and transparent outer background with Gaussian drop shadow.
- [ ] Window drags smoothly across monitors without cursor tearing and supports scroll-wheel resizing through preset diameters (160px, 260px, 380px).
- [ ] Stays pinned above active windows (always-on-top) on both X11 and Wayland sessions.
- [ ] On-hover HUD controls fade in on mouse enter and smoothly fade out after mouse exit.
- [ ] Click-through ghost mode passes mouse clicks directly to underlying windows when activated.

### Camera Pipeline & Offline Blur
- [ ] V4L2 device capture pipeline enumerates and reads available video inputs with configurable resolutions (default 720p @ 30fps).
- [ ] Horizontal mirror toggle flips video stream horizontally without latency degradation.
- [ ] Lighting enhancement applies fast gamma/exposure compensation to correct low-light scenes.
- [ ] 3 discrete background blur levels (Off, Subtle ~10px, Balanced ~25px, Heavy ~50px) toggle seamlessly using an ultra-lite (<5MB) offline segmentation model.
- [ ] No network requests or cloud APIs are called during video processing or model execution.

### Presenter Integration & System Tray
- [ ] Voice aura border ring smoothly reacts to microphone input volume in real time without audio glitches.
- [ ] Presenter keyboard shortcuts trigger visibility toggle, click-through toggle, corner snapping, and blur cycling.
- [ ] Ubuntu system tray icon provides quick access to device selection, resolution, mirror toggle, click-through toggle, and quit.

### Quality, Tests & Performance
- [ ] All unit and integration tests run and pass via `pytest` without requiring physical webcam hardware (using mock feeds).
- [ ] Headless GUI interaction tests verify window state, resizing, and HUD visibility.
- [ ] Processing pipeline operates under 30ms latency per frame on typical CPU hardware.
- [ ] Virtual environment setup and launch instructions are documented and executable via a single startup command.

## 2026-10-22T12:34:05Z

Fix and enhance SelfiCamera on Ubuntu Linux so mouse drag-and-drop movement and Always-On-Top work reliably without compositor blocking, and add an intuitive on-screen floating Settings Panel to manage lighting, blur, size, and camera directly from the UI.

Working directory: /run/media/mehdi/Projects/PersonalProjects/SelfiCamera
Integrity mode: development

## Requirements

### R1. Reliable Mouse Drag-to-Move & Guaranteed Always-On-Top
Ensure the circular camera bubble can be clicked and dragged anywhere by mouse to reposition it smoothly across monitors. Configure Ubuntu window platform flags (`QT_QPA_PLATFORM=xcb` / XWayland and `WindowStaysOnTopHint`) so GNOME Shell never blocks client-side movement and the window strictly remains Always-On-Top over full-screen IDEs, terminals, and browsers.

### R2. Responsive Resizing via Mouse & UI
Support dynamic resizing through both mouse interaction (scroll wheel / drag) and a live continuous diameter slider (120px to 600px) that resizes the circular viewport in real time while maintaining center-point anchoring.

### R3. On-Screen Floating Settings & Controls Panel
Add an intuitive, floating Settings Panel opened directly from the camera bubble (via a visible gear button on the bubble and right-click context menu) with live controls:
- **Lighting**: Real-time brightness/gamma slider, target luminance adjustment, and Auto-Light toggle.
- **Background Blur**: Blur intensity slider and discrete tier selectors (Off, Subtle, Balanced, Heavy).
- **Size**: Live diameter slider and preset buttons (160px, 260px, 380px).
- **Camera & Video**: Camera device dropdown, resolution picker, and horizontal mirror (flip) toggle.
- **Window Management**: Always-On-Top toggle switch and Click-Through Ghost mode toggle.

### R4. Automated Testing & Verification
Update and expand the automated pytest suite (`tests/`) to test mouse drag movement, slider resizing, Settings Panel signals/persistence, and headless Qt window flag verifications.

## Acceptance Criteria

### Window Movement & Always-On-Top
- [ ] Left-click and dragging inside the camera bubble moves the window smoothly across the desktop on Ubuntu GNOME.
- [ ] The camera bubble remains persistently on top of other active and full-screen windows (VS Code, terminal, browser).
- [ ] Launcher script `run.sh` ensures proper platform compatibility (`QT_QPA_PLATFORM=xcb` fallback) so GNOME Shell Wayland does not reject move or stay-on-top requests.

### Resizing Controls
- [ ] Scrolling mouse wheel over the bubble resizes the circle smoothly.
- [ ] Adjusting the size slider in the Settings Panel continuously resizes the bubble in real time.

### Floating Settings Panel
- [ ] A gear icon button on the bubble (or right-click menu) opens the floating Settings Panel.
- [ ] Lighting slider adjusts gamma/exposure live with immediate visual feedback.
- [ ] Blur slider/buttons adjust background blur intensity live without freezing video capture.
- [ ] Camera dropdown lists available `/dev/video*` devices and switches cameras seamlessly.
- [ ] Always-on-top switch can be toggled directly from the UI.

### Test & Regression Suite
- [ ] Automated pytest suite passes with 100% success rate under headless Qt (`QT_QPA_PLATFORM=offscreen`).
- [ ] Performance benchmarks continue to meet the <30ms latency budget.


## 2026-10-22T19:59:23Z

Use our software development team agents to build fully.

Review all documentation, specs, and PRD for SelfiCamera, ensuring that the 5 core features (move/drag-and-drop, resize, lighting control, blur control, always-on-top) are comfortably and intuitively configurable directly from the UI, add 1-click corner snap buttons to the Settings Panel, and verify correct implementation by software development team agents.

Working directory: /run/media/mehdi/Projects/PersonalProjects/SelfiCamera
Integrity mode: development

## Requirements

### R1. UI Configurable Window Move & Snapping
Provide seamless and comfortable window movement via direct drag-and-drop on the circular camera bubble, and enhance UI accessibility by adding 1-click corner snapping buttons in the Settings Panel (`↖ TL`, `↗ TR`, `↙ BL`, `↘ BR`) connected to `OverlayWindow.snap_to_corner`.

### R2. Responsive UI Resizing (Continuous & Discrete Presets)
Allow the user to effortlessly change the camera bubble size through multiple intuitive UI mechanisms: smooth mouse scroll wheel over the bubble, radial edge dragging, and live continuous slider (120px to 600px) plus discrete one-click preset buttons (160px, 260px, 380px) in the Settings Panel with zero center-point drift.

### R3. Intuitive UI Lighting Control
Ensure exposure and lighting compensation are immediately accessible and comfortable to configure from the UI: single-click Auto-Light Boost toggle on the on-hover HUD and Settings Panel, live brightness/gamma compensation slider (0.40x - 2.20x) with quick reset, and target luminance adjustment slider.

### R4. Intuitive UI Background Blur Control
Provide comfortable real-time bokeh background blur adjustments directly from the UI: one-click cycling button on the HUD (Off -> Subtle -> Balanced -> Heavy), discrete tier buttons in the Settings Panel, and a continuous blur intensity slider (0% to 100%) with bidirectional synchronization.

### R5. UI Configurable Always-On-Top & Window Management
Enable quick and comfortable toggling of Always-On-Top persistence from the UI (Settings Panel checkbox and right-click context menu), keeping the presenter overlay persistently visible above full-screen IDEs, browsers, and terminal windows on Ubuntu GNOME (Wayland & X11).

### R6. Automated Verification & Agent Implementation Audit
Ensure 100% of automated tests pass cleanly under both local Wayland/X11 and headless CI (`QT_QPA_PLATFORM=offscreen`), eliminating test flakiness, verifying signal wiring and UI responsiveness, and maintaining <25ms P95 latency.

## Acceptance Criteria

### Window Movement & Snapping
- [ ] Left-click dragging inside the circular camera bubble smoothly moves the window across monitors without getting trapped by HUD or widgets.
- [ ] Window positions clamp within visible desktop bounds preventing off-screen loss.
- [ ] Settings Panel includes 1-click corner snapping buttons (`↖ TL`, `↗ TR`, `↙ BL`, `↘ BR`) that reposition the camera overlay to the corresponding desktop corners.

### Resizing Controls
- [ ] Scrolling mouse wheel over the bubble resizes the circle smoothly.
- [ ] Settings Panel size slider resizes the bubble continuously in real time with instant visual feedback and center anchoring.
- [ ] Preset buttons (160px, 260px, 380px) instantly snap to standard presentation sizes.

### Lighting & Blur UI Controls
- [ ] HUD "Light" button toggles Auto-Light Boost with active visual indicator.
- [ ] Settings Panel gamma and luminance sliders adjust video exposure in real time with live numeric readouts.
- [ ] HUD blur button cycles through all 4 blur tiers (`B:Off`, `B:Sub`, `B:Bal`, `B:Hvy`).
- [ ] Settings Panel blur tier buttons and continuous intensity slider stay bidirectionally synchronized without feedback loops.

### Always-On-Top & Window Management
- [ ] Right-click context menu on the bubble offers an Always-On-Top toggle and quick Settings access.
- [ ] Settings Panel checkbox toggles Always-On-Top state live and synchronizes with config.

### Test & Code Quality
- [ ] Automated pytest suite passes 100% (all 63+ tests) under both active desktop session and `QT_QPA_PLATFORM=offscreen`.
- [ ] Latency benchmark verifies P95 processing remains < 25ms.
