# SelfiCamera: Product Requirements & Specification Document (PRD)

**Document Version:** 1.0.0  
**Phase:** Phase 2: Product Specifications & Acceptance Criteria  
**Author:** Product Manager (PM)  
**Target Platform:** Ubuntu Linux 24.04 / 26.04 LTS (GNOME on Wayland & X11)  
**Engineering Leads:** Full-Stack & AI Engineer (Phase 3), QA & Code Reviewer (Phase 4)  
**Status:** Approved / Authoritative Product Specification  

---

## 1. Product Overview & Strategic Vision

### 1.1 Executive Summary
SelfiCamera is a lightweight, zero-bloat, 100% offline desktop circular presenter camera overlay engineered specifically for Ubuntu Linux. Built for live presenters, software developers, technical interviewers, and streamers, SelfiCamera provides a distraction-free circular webcam viewport that floats persistently above full-screen IDEs, web browsers, slide decks, and terminals.

Unlike resource-heavy Electron applications or privacy-compromising web overlays, SelfiCamera runs as a native Python 3.12 / PySide6 (Qt6) application with hardware-accelerated 2D rendering, sub-millisecond LUT lighting compensation, an ultra-lite (<2MB) local neural segmentation model for photographic bokeh blur, and real-time PipeWire/PulseAudio voice reactivity.

### 1.2 Target Personas & Primary User Journeys
1. **The Live Coding Streamer ("Alex")**:
   - *Journey*: Alex opens VS Code in fullscreen on Ubuntu Wayland. Alex launches SelfiCamera, which floats in the bottom-right corner at 260px. Alex presses `Super+Alt+X` to engage "Ghost Mode" so mouse clicks and text selections pass straight through the camera circle to the editor code beneath. Alex speaks, and the circular border subtly glows cyan to indicate microphone pickup.
2. **The Tech Conference / Remote Keynote Speaker ("Elena")**:
   - *Journey*: Elena presents slides from a hotel room. She toggles background blur to Level 2 (Balanced) via `Super+Alt+B` to mask the busy room behind her. As her lighting fluctuates, Auto-Light Boost automatically normalizes her video luminance. She uses `Super+Alt+2` to snap the presenter bubble to the top-right corner to avoid covering slide bullet points.
3. **The Engineering Interviewer & Educator ("Marcus")**:
   - *Journey*: Marcus conducts live technical interviews on Google Meet or Zoom while sharing his desktop. He adjusts the camera diameter on the fly using the mouse scroll wheel (from 260px down to 160px when reviewing dense architecture diagrams, then up to 380px for direct 1-on-1 dialogue).

### 1.3 Core Product Invariants & Non-Negotiables
- **100% Offline / Zero-Cloud**: No network requests, telemetry, analytics, or remote API calls. All neural network weights and assets are stored and executed locally.
- **Strict Latency Budget**: Total per-frame pipeline latency must stay below **30.0 milliseconds** (enabling 30 FPS with headroom for 60 FPS).
- **Minimal Resource Footprint**: Idle CPU < 1%, Active streaming CPU < 5% on modern 4-core+ x86_64 CPUs; RAM usage < 60MB.
- **Dual-Session Display Support**: Flawless functionality across both GNOME Wayland sessions and classic X11 sessions.
- **Hardware-Agnostic Testability**: 100% automated test coverage in headless CI environments without requiring physical webcams or microphones.

---

## 2. Product Architecture & Subsystem Mapping

| Subsystem Module | Primary Responsibility | Architectural Layer |
| :--- | :--- | :--- |
| `selficamera.ui.overlay` | Frameless circular window, drop shadow, circular clipping, voice aura ring, mouse events, snapping | Presentation / UI |
| `selficamera.ui.hud` | Auto-hiding on-hover controls (Mirror, Blur, Ghost, Light, Close) | Presentation / UI |
| `selficamera.ui.tray` | Ubuntu AppIndicator / System Tray icon and context menu | Presentation / Desktop Integration |
| `selficamera.capture` | V4L2 camera enumeration, threaded acquisition, resolution/FPS configuration | Acquisition Engine |
| `selficamera.processor.lighting` | Real-time Auto-Light Boost (Adaptive gamma correction with precomputed LUT) | Processing Pipeline |
| `selficamera.processor.segmentation` | 3-tier offline bokeh blur using local ONNX model (<2MB) and vectorized blending | Processing Pipeline |
| `selficamera.processor.pipeline` | Frame processing coordinator linking capture to rendering | Processing Pipeline |
| `selficamera.audio.voice_monitor` | PipeWire/PulseAudio mic listener, RMS energy computation, attack/decay envelope | Audio Reactivity |
| `selficamera.shortcuts` | Dual-mode shortcuts: X11 global grab + Wayland Unix domain socket IPC daemon | Desktop Integration |
| `selficamera.config` | Atomic JSON configuration store (`~/.config/selficamera/config.json`) | State & Persistence |

---

## 3. Epic & User Story Breakdown

The functional requirements are structured into four comprehensive Epics:

```
[Epic 1: Presenter Floating Window & Intuitive Manipulation]
  ├── US-1.1: Frameless Circular Presentation Window & Gaussian Drop Shadow
  ├── US-1.2: Fluid Drag-to-Move & Screen Boundary Clamping
  ├── US-1.3: Scroll-to-Resize Preset Diameters (160px, 260px, 380px)
  ├── US-1.4: Always-On-Top Persistence over Fullscreen Applications
  ├── US-1.5: Auto-Hiding On-Hover HUD Controls
  └── US-1.6: Click-Through Ghost Mode for Unobstructed Desktop Access

[Epic 2: Camera Pipeline & Offline AI Background Blur]
  ├── US-2.1: V4L2 Device Discovery, Selection & 720p@30fps Acquisition
  ├── US-2.2: Instant Horizontal Mirror Toggle (Selfie Orientation)
  ├── US-2.3: Real-Time Auto-Light Boost (Adaptive Gamma LUT)
  ├── US-2.4: 3-Tier Offline Bokeh Background Blur via Local ONNX Model
  └── US-2.5: Zero-Network Privacy & Offline Execution Guarantee

[Epic 3: Presenter Desktop Integration & Voice Aura]
  ├── US-3.1: PipeWire/PulseAudio Dynamic Voice Aura Border Ring
  ├── US-3.2: Dual-Mode Presenter Global Shortcuts (Wayland IPC & X11 Grab)
  ├── US-3.3: Presenter Desktop Corner Snapping (Super+Alt+1..4)
  └── US-3.4: Ubuntu System Tray & AppIndicator Menu

[Epic 4: Developer Ergonomics, Automated Testing & Verification]
  ├── US-4.1: Single Startup Command & Virtual Environment Isolation
  ├── US-4.2: Comprehensive Headless Automated Pytest Suite with Mock Feeds
  ├── US-4.3: Headless Qt GUI Interaction Tests (pytest-qt)
  └── US-4.4: Automated Latency & CPU Performance Benchmark Suite
```

---

## 4. Detailed Functional Specifications & Acceptance Criteria

### Epic 1: Presenter Floating Window & Intuitive Manipulation

#### US-1.1: Frameless Circular Presentation Window & Gaussian Drop Shadow
- **Description**: As a presenter, I want my webcam feed displayed inside a pristine, anti-aliased 1:1 circular window with a soft outer drop shadow, so that my face appears modern and integrated into the screen without harsh window borders or title bars.
- **Specification**:
  - The window must be frameless (`Qt.WindowType.FramelessWindowHint`) with a translucent background (`Qt.WidgetAttribute.WA_TranslucentBackground`).
  - Total window dimensions are `Diameter + (2 * ShadowMargin)`. Default `ShadowMargin` = 16px.
  - Video feed must be aspect-ratio locked, center-cropped into a square, and clipped using an anti-aliased `QPainterPath.addEllipse()`.
  - Outer drop shadow must be smoothly rendered with a soft Gaussian/radial gradient fading from 35% black (`#000000` alpha ~90) at the circle boundary to transparent (`alpha 0`) at the window edge.
  - A subtle 1px inner border stroke (`#ffffff` with 25% alpha) surrounds the circle to cleanly separate the video feed from dark or busy backgrounds.
- **Acceptance Criteria**:
  - **AC-1.1.1 (Circular Masking)**:
    - *Given* the overlay window is instantiated and rendering a 1280x720 video feed,
    - *When* the window `paintEvent` executes,
    - *Then* the video content is strictly clipped inside an exact 1:1 circular ellipse with anti-aliasing enabled, and no pixels outside the circle diameter are rendered.
  - **AC-1.1.2 (Drop Shadow Geometry)**:
    - *Given* the active diameter is set to 260px and shadow margin is 16px,
    - *When* the window geometry is inspected,
    - *Then* the total window width and height are exactly 292x292px, and pixels outside the outer shadow boundary remain completely transparent.
  - **AC-1.1.3 (Aspect Ratio Integrity)**:
    - *Given* a 16:9 widescreen camera feed,
    - *When* rendered inside the circular viewport,
    - *Then* the feed is center-cropped without horizontal or vertical stretching, distortion, or anamorphic skewing.

#### US-1.2: Fluid Drag-to-Move & Screen Boundary Clamping
- **Description**: As a presenter, I want to click and drag the circular camera anywhere on my screen, so that I can position myself away from active content without cursor jitter or window tearing.
- **Specification**:
  - Dragging initiates when the left mouse button is pressed anywhere on the circular viewport (excluding interactive HUD buttons).
  - Position updates track the cursor delta using global screen coordinates.
  - The window position must be automatically clamped within the virtual desktop's available geometry (`QGuiApplication.primaryScreen().availableGeometry()`), preventing the window from being dragged entirely offscreen.
  - Must support multi-monitor setups: when dragging across screen boundaries, the window smoothly transitions across the virtual desktop coordinates.
- **Acceptance Criteria**:
  - **AC-1.2.1 (Fluid Repositioning)**:
    - *Given* the overlay window is visible at coordinate `(100, 100)`,
    - *When* the user presses the left mouse button and drags to delta `(+250, +150)`,
    - *Then* the window smoothly updates its position to `(350, 250)` without flicker or visual artifacts.
  - **AC-1.2.2 (Screen Boundary Clamping)**:
    - *Given* a screen resolution of 1920x1080 and a window size of 292x292px,
    - *When* the user attempts to drag the overlay past coordinate `(2000, 1200)`,
    - *Then* the window coordinate is clamped so that the entire window remains within `(0, 0, 1920 - 292, 1080 - 292)`.
  - **AC-1.2.3 (HUD Button Exclusion)**:
    - *Given* the HUD is visible,
    - *When* the user clicks on an active HUD control button (e.g., Flip or Blur),
    - *Then* the button action triggers and window dragging does not initiate.

#### US-1.3: Scroll-to-Resize Preset Diameters (160px, 260px, 380px)
- **Description**: As a presenter, I want to step through preset diameters by scrolling my mouse wheel over the bubble, so that I can instantly switch between compact coding mode, standard speaking mode, and high-impact full-focus mode.
- **Specification**:
  - Supported discrete preset diameters:
    - **Compact (Small)**: `160px` (ideal for dense code reviews and terminal screencasts).
    - **Standard (Medium - Default)**: `260px` (ideal for typical presentations and meetings).
    - **Focus (Large)**: `380px` (ideal for intros, conclusions, and keynote speeches).
  - Scrolling UP steps to the next larger preset ($160 \rightarrow 260 \rightarrow 380$).
  - Scrolling DOWN steps to the next smaller preset ($380 \rightarrow 260 \rightarrow 160$).
  - Scrolling beyond limits is safely clamped (no rollover or out-of-range sizing).
  - Transitions animate smoothly using `QPropertyAnimation` targeting the diameter with duration 180ms and `QEasingCurve.OutCubic`.
  - Window center coordinate `(cx, cy)` remains anchored during resizing so the bubble does not jump across the screen.
- **Acceptance Criteria**:
  - **AC-1.3.1 (Scroll Step Up)**:
    - *Given* the overlay diameter is currently `160px`,
    - *When* a vertical scroll-up event (`deltaY > 0`) is received,
    - *Then* the target diameter steps to `260px`, the window geometry updates smoothly over 180ms, and the center point of the circle remains stationary.
  - **AC-1.3.2 (Scroll Step Down)**:
    - *Given* the overlay diameter is currently `380px`,
    - *When* a vertical scroll-down event (`deltaY < 0`) is received,
    - *Then* the target diameter steps to `260px`.
  - **AC-1.3.3 (Boundary Clamp)**:
    - *Given* the overlay diameter is currently `380px`,
    - *When* another vertical scroll-up event is received,
    - *Then* the diameter remains `380px` without jitter or state mutation.
  - **AC-1.3.4 (State Persistence on Resize)**:
    - *Given* the user resizes to `380px`,
    - *When* the animation finishes,
    - *Then* the new diameter is persisted to `~/.config/selficamera/config.json`.

#### US-1.4: Always-On-Top Persistence over Fullscreen Applications
- **Description**: As a presenter, I want the camera bubble to stay permanently visible above fullscreen IDEs, slides, and browser windows on both Wayland and X11, so that my presentation is never accidentally covered by active windows.
- **Specification**:
  - The window sets `Qt.WindowType.WindowStaysOnTopHint` and `Qt.WindowType.Tool`.
  - Under GNOME Wayland, the window registers as a floating top-level overlay so that clicking or focusing underlying windows does not push SelfiCamera to the background.
  - Setting `Qt.WindowType.Tool` ensures SelfiCamera does not produce an unwanted icon in the GNOME Alt-Tab switcher or taskbar dock.
- **Acceptance Criteria**:
  - **AC-1.4.1 (Window Hint Verification)**:
    - *Given* the overlay window is initialized,
    - *When* its window flags are inspected,
    - *Then* `Qt.WindowStaysOnTopHint`, `Qt.FramelessWindowHint`, and `Qt.Tool` are all present.
  - **AC-1.4.2 (Z-Order Stays on Top)**:
    - *Given* SelfiCamera is visible on screen,
    - *When* a fullscreen application (e.g. browser or IDE) is focused and clicked,
    - *Then* SelfiCamera remains visible and unobstructed above the focused window.

#### US-1.5: Auto-Hiding On-Hover HUD Controls
- **Description**: As a presenter, I want controls to appear only when I hover my mouse over the camera bubble and vanish when I move my mouse away, so that my camera feed remains clean and cinematic during presentations.
- **Specification**:
  - The HUD is a semi-transparent floating control bar situated in the upper or lower segment of the circle.
  - **HUD Buttons**:
    - `[Flip]`: Toggles horizontal mirror.
    - `[Blur]`: Cycles blur level ($0 \rightarrow 1 \rightarrow 2 \rightarrow 3 \rightarrow 0$).
    - `[Light]`: Toggles Auto-Light Boost.
    - `[Ghost]`: Toggles click-through Ghost Mode.
    - `[Close]`: Minimizes or closes the overlay.
  - **Animation & Timing Curves**:
    - `enterEvent`: Triggers smooth fade-in from opacity `0.0` to `0.92` over `150ms`.
    - `leaveEvent`: Starts a `1200ms` inactivity timer. If no mouse re-enters before the timer expires, triggers smooth fade-out from `0.92` to `0.0` over `300ms`.
    - Opacity transitions are managed via `QPropertyAnimation` on `QGraphicsOpacityEffect`.
- **Acceptance Criteria**:
  - **AC-1.5.1 (HUD Invisibility on Idle)**:
    - *Given* the application is running and the mouse cursor is outside the window,
    - *When* inspected,
    - *Then* the HUD opacity is `0.0` and HUD buttons are completely transparent.
  - **AC-1.5.2 (Fast Fade-In on Enter)**:
    - *Given* the HUD is hidden,
    - *When* the mouse cursor enters the circular overlay boundary,
    - *Then* the HUD animates from opacity `0.0` to `0.92` within `150ms`.
  - **AC-1.5.3 (Smooth Fade-Out on Exit)**:
    - *Given* the HUD is visible,
    - *When* the mouse cursor exits the window boundary,
    - *Then* the HUD remains visible for `1200ms`, then fades out to `0.0` over `300ms`.
  - **AC-1.5.4 (Timer Reset on Rapid Re-Enter)**:
    - *Given* the mouse has exited and the 1200ms countdown has begun,
    - *When* the mouse re-enters the window at 600ms,
    - *Then* the countdown timer is cancelled and HUD opacity returns to `0.92` immediately.

#### US-1.6: Click-Through Ghost Mode for Unobstructed Desktop Access
- **Description**: As a live coder, I want to enable "Ghost Mode" so that all mouse clicks and scrolls pass directly through the camera bubble to the IDE underneath, allowing me to code anywhere on screen without moving the webcam.
- **Specification**:
  - Activated via global hotkey (`Super+Alt+X`), HUD `[Ghost]` button, or System Tray menu.
  - When enabled:
    - `Qt.WidgetAttribute.WA_TransparentForMouseEvents` is set to `True`.
    - Under X11, an empty input region is applied (`setMask(QRegion())` or `XShapeCombineRectangles`).
    - Under Wayland, the input region is cleared via `wl_surface_set_input_region(surface, NULL)`.
    - The overlay remains 100% visible, but all mouse clicks, drags, and scroll events bypass SelfiCamera entirely.
    - A subtle visual indicator (a faint dotted glow or icon badge in the aura ring) indicates Ghost Mode is active.
  - Deactivation:
    - Can be toggled OFF at any time via the global hotkey (`Super+Alt+X`) or the System Tray menu.
    - When deactivated, mouse events are restored (`WA_TransparentForMouseEvents = False`, full input mask restored).
- **Acceptance Criteria**:
  - **AC-1.6.1 (Mouse Pass-Through)**:
    - *Given* Ghost Mode is active,
    - *When* the user clicks or scrolls directly over the circular camera viewport,
    - *Then* SelfiCamera does not consume the event, and the underlying application window receives the click/scroll.
  - **AC-1.6.2 (Hotkey Deactivation)**:
    - *Given* Ghost Mode is active,
    - *When* the user triggers `Super+Alt+X` (via X11 grab or Wayland CLI IPC),
    - *Then* Ghost Mode is disabled, mouse interaction returns to normal, and the tray menu reflects the unchecked state.
  - **AC-1.6.3 (State Synchronization)**:
    - *Given* Ghost Mode is toggled via the HUD button,
    - *When* the mode activates,
    - *Then* the HUD immediately hides and the system tray checkbox is updated to checked.

---

### Epic 2: Camera Pipeline & Offline AI Background Blur

#### US-2.1: V4L2 Device Discovery, Selection & 720p@30fps Acquisition
- **Description**: As a presenter, I want SelfiCamera to automatically discover my available Linux V4L2 webcams and acquire smooth 720p@30fps video, so that my stream is sharp and reliable.
- **Specification**:
  - Scans `/dev/video0` through `/dev/video63` using `ioctl(VIDIOC_QUERYCAP)` to identify capture-capable devices.
  - Extracts human-readable device card names (e.g. "Integrated Camera", "Logitech C920").
  - Configures capture stream using OpenCV `CAP_V4L2` backend with MJPG hardware decoding.
  - Default resolution: `1280x720` @ `30 FPS`. Supports switching to `640x480` and `1920x1080`.
  - Runs in a dedicated background `QThread` (`CameraCaptureWorker`).
  - Implements **Atomic Depth-1 Queue**: If downstream rendering or segmentation takes longer than a frame interval, the worker drops old frames immediately. Zero queue buildup or lag accumulation.
- **Acceptance Criteria**:
  - **AC-2.1.1 (Device Enumeration)**:
    - *Given* one or more V4L2 camera nodes exist in `/dev/video*`,
    - *When* `V4L2DeviceScanner.list_devices()` is called,
    - *Then* a list of available devices with paths and card names is returned, filtering out non-capture metadata nodes.
  - **AC-2.1.2 (Threaded 30 FPS Ingestion)**:
    - *Given* a valid camera device `/dev/video0` supporting 720p,
    - *When* `CameraCaptureWorker` starts,
    - *Then* it emits `frame_ready(np.ndarray)` at approximately 30 FPS without blocking the main Qt thread.
  - **AC-2.1.3 (Zero Queue Lag Accumulation)**:
    - *Given* the processing thread is artificially delayed by 100ms,
    - *When* the processing thread resumes,
    - *Then* it receives the single most recent camera frame, and stale historical frames are discarded.
  - **AC-2.1.4 (Graceful Camera Disconnection)**:
    - *Given* the active camera device is unplugged or fails during streaming,
    - *When* `read()` fails consecutively for 3 frames,
    - *Then* the worker emits an `error_occurred(str)` signal and displays a clean "Camera Unavailable" placeholder without crashing.

#### US-2.2: Instant Horizontal Mirror Toggle (Selfie Orientation)
- **Description**: As a presenter, I want my video feed horizontally mirrored by default, so that moving my hand to the right moves to the right on screen (natural mirror view), with the ability to un-mirror if presenting physical text.
- **Specification**:
  - Default state: `mirror = True`.
  - Applied via in-place contiguous memory flip: `cv2.flip(frame, 1)`.
  - Execution time must be $< 0.5\text{ ms}$ for a 720p frame.
  - Toggled via HUD `[Flip]` button, System Tray menu, or CLI IPC command.
- **Acceptance Criteria**:
  - **AC-2.2.1 (Horizontal Flip Correctness)**:
    - *Given* an input frame with distinct pixel values on the left versus right edge,
    - *When* `mirror = True`,
    - *Then* the left edge pixels are transposed to the right edge and vice-versa.
  - **AC-2.2.2 (Latency Budget)**:
    - *Given* a 1280x720 uint8 BGR frame,
    - *When* the mirror operation executes,
    - *Then* the elapsed execution time is measured at $\le 0.8\text{ ms}$.
  - **AC-2.2.3 (Toggle Responsiveness)**:
    - *Given* video is actively rendering,
    - *When* the user toggles the mirror option,
    - *Then* the very next frame rendered reflects the updated horizontal orientation without dropping frames.

#### US-2.3: Real-Time Auto-Light Boost (Adaptive Gamma LUT)
- **Description**: As a presenter, I want automatic lighting enhancement, so that my face remains clearly visible and well-exposed even in dim room lighting.
- **Specification**:
  - Algorithm: Subsamples frame by factor of 4, converts to YCrCb or Lab to compute mean luminance $\bar{Y}$.
  - If $\bar{Y} < 100.0$ (low-light threshold), computes adaptive gamma:
    $$\gamma = \text{clip}\left(\frac{\log(125.0 / 255.0)}{\log(\max(\bar{Y}, 10.0) / 255.0)}, 0.45, 1.0\right)$$
  - Applies exponential moving average temporal smoothing on $\gamma$ ($\alpha = 0.15$) to prevent visual flicker during sudden lighting shifts.
  - Generates a 256-entry Look-Up Table (LUT) and applies it via `cv2.LUT()`.
  - Performance: Entire lighting step must execute in $< 1.2\text{ ms}$.
  - Can be toggled On/Off via HUD `[Light]` button, System Tray, or config.
- **Acceptance Criteria**:
  - **AC-2.3.1 (Luminance Enhancement in Low Light)**:
    - *Given* a dark synthetic test frame with mean luminance $Y = 40.0$,
    - *When* Auto-Light Boost is enabled,
    - *Then* the output frame has mean luminance $Y \ge 90.0$ and gamma $\gamma < 1.0$.
  - **AC-2.3.2 (No-Op in Bright Lighting)**:
    - *Given* a well-lit test frame with mean luminance $Y = 140.0$,
    - *When* Auto-Light Boost is evaluated,
    - *Then* gamma is $1.0$, the LUT is an identity mapping, and the frame is unmodified.
  - **AC-2.3.3 (Temporal Anti-Flicker Smoothing)**:
    - *Given* a sudden 1-frame brightness spike (e.g. flash),
    - *When* the next frame is processed,
    - *Then* $\gamma_{\text{applied}}$ transitions smoothly by $\le 15\%$ per frame rather than jumping instantaneously.
  - **AC-2.3.4 (Sub-Millisecond Execution)**:
    - *Given* a 720p frame,
    - *When* `AutoLightBoost.process()` runs,
    - *Then* execution completes in $< 1.5\text{ ms}$.

#### US-2.4: 3-Tier Offline Bokeh Background Blur via Local ONNX Model
- **Description**: As a presenter, I want discrete levels of background blur (Off, Subtle, Balanced, Heavy) powered by an offline local neural network, so that my background is blurred cleanly without cloud latency, subscription fees, or privacy risks.
- **Specification**:
  - Model: MediaPipe Selfie Segmentation ONNX model (~1.3MB), bundled locally at `selficamera/models/selfie_segmentation.onnx`.
  - Inference Provider: `onnxruntime.InferenceSession` with `CPUExecutionProvider` (vectorized AVX2 SIMD).
  - Model Input: `1 x 256 x 256 x 3` float32 normalized RGB. Output: `1 x 256 x 256 x 1` person probability mask $P \in [0.0, 1.0]$.
  - **Discrete Blur Tiers**:
    - **Tier 0 (Off)**: Model inference bypassed completely ($0\text{ ms}$ overhead).
    - **Tier 1 (Subtle)**: Gaussian blur with effective radius ~12px.
    - **Tier 2 (Balanced - Default)**: Downsample $2\times \rightarrow$ Gaussian blur $(31, 31) \rightarrow$ Upsample ($2.0\text{ ms}$ bokeh).
    - **Tier 3 (Heavy)**: Downsample $4\times \rightarrow$ Gaussian blur $(41, 41) \rightarrow$ Upsample ($2.5\text{ ms}$ heavy bokeh).
  - Mask Blending: Upscale mask to cropped viewport size, apply $5\times 5$ box blur for edge feathering, and perform vectorized alpha blend:
    $$\text{Output} = \text{Frame} \times \text{Mask} + \text{BlurFrame} \times (1.0 - \text{Mask})$$
  - Model inference latency must be $\le 8.0\text{ ms}$ on CPU; blending $\le 4.0\text{ ms}$.
- **Acceptance Criteria**:
  - **AC-2.4.1 (Tier 0 Bypass)**:
    - *Given* blur tier is set to `0` (Off),
    - *When* a frame is processed,
    - *Then* ONNX model inference is not called and the original frame passes through in $0.0\text{ ms}$.
  - **AC-2.4.2 (Tier 1 Subtle Blur)**:
    - *Given* blur tier is set to `1`,
    - *When* a synthetic frame with a person and background is processed,
    - *Then* the background region exhibits subtle Gaussian smoothing while the person region remains sharp ($>95\%$ edge gradient retention).
  - **AC-2.4.3 (Tier 2 Balanced Bokeh)**:
    - *Given* blur tier is set to `2`,
    - *When* processed,
    - *Then* background details (e.g. books, text) are illegible due to bokeh blur, while facial contours remain crisp.
  - **AC-2.4.4 (Tier 3 Heavy Bokeh)**:
    - *Given* blur tier is set to `3`,
    - *When* processed,
    - *Then* background is heavily diffused into soft color blobs.
  - **AC-2.4.5 (Cycling via Shortcut / HUD)**:
    - *Given* blur is currently Tier 2,
    - *When* `Super+Alt+B` or HUD `[Blur]` is pressed,
    - *Then* blur steps to Tier 3; pressing again steps to Tier 0.

#### US-2.5: Zero-Network Privacy & Offline Execution Guarantee
- **Description**: As a security-conscious developer, I want absolute certainty that SelfiCamera never sends my video feed, audio, or system metadata to the cloud or over the local network, so that I comply with strict privacy policies.
- **Specification**:
  - The codebase must not import `urllib`, `urllib3`, `requests`, `httpx`, `aiohttp`, or standard networking libraries.
  - No external downloads during runtime: all weights, icons, and dependencies are packaged locally.
  - Outbound network sockets must never be created (verified by automated tests).
- **Acceptance Criteria**:
  - **AC-2.5.1 (Codebase Import Audit)**:
    - *Given* the entire `selficamera` package source tree,
    - *When* an automated AST / grep scan searches for network libraries (`requests`, `urllib`, `http.client`, `httpx`),
    - *Then* zero occurrences are found.
  - **AC-2.5.2 (Socket Creation Prohibition)**:
    - *Given* a running instance of SelfiCamera executing video and audio pipelines,
    - *When* the Linux process file descriptors and socket table (`/proc/$PID/net/tcp`, `ss -tup`) are audited,
    - *Then* zero external TCP or UDP sockets exist (only the local Unix domain socket IPC file).

---

### Epic 3: Presenter Desktop Integration & Voice Aura

#### US-3.1: PipeWire/PulseAudio Dynamic Voice Aura Border Ring
- **Description**: As a presenter, I want a glowing visual border around my camera circle that pulses in real time with my voice, so that I and my audience have immediate visual feedback that my microphone is picking up speech.
- **Specification**:
  - Worker: `AudioMonitorWorker` runs in a dedicated `QThread` tapping PipeWire / PulseAudio default source via `sounddevice.InputStream`.
  - Parameters: 44.1 kHz sample rate, mono, 512 block size (~11.6ms latency).
  - Calculation: Root-Mean-Square (RMS) converted to logarithmic dBFS normalized between $[-48\text{ dB}, -12\text{ dB}]$ to yield raw energy $\in [0.0, 1.0]$.
  - Asymmetric Envelope Filter:
    - Fast Attack: $E(t) = 0.65 \cdot E(t-1) + 0.35 \cdot E_{\text{raw}}$ (responds in ~30ms).
    - Smooth Decay: $E(t) = 0.88 \cdot E(t-1) + 0.12 \cdot E_{\text{raw}}$ (smooth falloff over ~120ms without visual stutter).
  - Visual Aura Rendering:
    - Dynamic Border Pen Width: $W = 2.5\text{px} + (4.5\text{px} \times E)$.
    - Color Transitions:
      - Silence ($E \le 0.05$): Subtle slate / transparent cyan (`#00e5ff`, 25% alpha).
      - Normal Speech ($0.10 \le E \le 0.75$): Vibrant neon cyan/blue (`#00e5ff`, 85% alpha).
      - High Peak ($E > 0.75$): Electric purple / emerald glow (`#d500f9` / `#00e676`, 100% alpha).
  - Emits Qt signal `energy_updated(float)` to trigger repainting of the aura ring.
- **Acceptance Criteria**:
  - **AC-3.1.1 (Audio Ingestion & Energy Emission)**:
    - *Given* the audio monitor is running with microphone input,
    - *When* audio buffers arrive,
    - *Then* `energy_updated(float)` is emitted with values strictly bounded in $[0.0, 1.0]$.
  - **AC-3.1.2 (Visual Ring Expansion on Speech)**:
    - *Given* silent ambient noise ($E < 0.05$),
    - *When* speech commences ($E \approx 0.60$),
    - *Then* the outer ring stroke width expands from $2.5\text{px}$ to $\approx 5.2\text{px}$ and alpha increases to $>80\%$.
  - **AC-3.1.3 (Smooth Decay without Jitter)**:
    - *Given* speech suddenly stops,
    - *When* subsequent paint events occur,
    - *Then* the aura smoothly contracts over 100-150ms rather than snapping to zero in a single frame.
  - **AC-3.1.4 (Graceful Audio Device Fallback)**:
    - *Given* no physical microphone is connected or audio server is uninitialized,
    - *When* `AudioMonitorWorker` starts,
    - *Then* it catches the exception, logs a warning, sets energy to `0.0`, and does not crash the camera overlay.

#### US-3.2: Dual-Mode Presenter Global Shortcuts (Wayland IPC & X11 Grab)
- **Description**: As a presenter on Ubuntu Linux, I want global hotkeys to toggle camera visibility, ghost mode, blur levels, and corner snapping whether I am logged into a Wayland or X11 session.
- **Specification**:
  - **Action Catalog**:
    - `Super+Alt+C`: Toggle overlay visibility (Show / Hide).
    - `Super+Alt+X`: Toggle click-through Ghost Mode.
    - `Super+Alt+1`: Snap to Top-Left corner.
    - `Super+Alt+2`: Snap to Top-Right corner.
    - `Super+Alt+3`: Snap to Bottom-Left corner.
    - `Super+Alt+4`: Snap to Bottom-Right corner.
    - `Super+Alt+B`: Cycle blur mode ($0 \rightarrow 1 \rightarrow 2 \rightarrow 3$).
  - **Session Dual-Mode Strategy**:
    - **X11 Session** (`XDG_SESSION_TYPE=x11`): Uses `pynput.keyboard.GlobalHotKeys` to register direct system-wide hotkeys.
    - **Wayland Session** (`XDG_SESSION_TYPE=wayland`): Starts a Unix Domain Socket server at `/run/user/<UID>/selficamera.sock`. Users or GNOME Custom Shortcuts invoke `selficamera --toggle`, `--ghost`, `--snap 1..4`, `--blur-cycle`. The CLI client connects to the socket, sends the command JSON, and the running instance executes the action immediately.
- **Acceptance Criteria**:
  - **AC-3.2.1 (X11 Global Key Grab)**:
    - *Given* SelfiCamera is running in an X11 session,
    - *When* the user presses `Super+Alt+C` while another window is focused,
    - *Then* the overlay visibility toggles immediately.
  - **AC-3.2.2 (Wayland Socket IPC Dispatch)**:
    - *Given* SelfiCamera is running in a Wayland session,
    - *When* `selficamera --toggle` is executed in a terminal,
    - *Then* the running overlay toggles visibility within $< 20\text{ ms}$, and the CLI command exits with code 0.
  - **AC-3.2.3 (Wayland Single Instance Guarantee)**:
    - *Given* SelfiCamera is already running,
    - *When* a user launches `selficamera` without arguments,
    - *Then* the existing instance is brought to front and no duplicate process is spawned.

#### US-3.3: Presenter Desktop Corner Snapping (Super+Alt+1..4)
- **Description**: As a presenter, I want to snap my camera circle to any of the four desktop corners instantly with a keystroke, so that I can quickly move out of the way of changing slide layouts.
- **Specification**:
  - Snapping calculates coordinates based on `availableGeometry()` (respecting the Ubuntu top bar and side dock) with a standard `24px` margin offset.
  - Formulae:
    - `Corner 1 (Top-Left)`: `x = screen_x + margin`, `y = screen_y + margin`
    - `Corner 2 (Top-Right)`: `x = screen_x + screen_w - win_w - margin`, `y = screen_y + margin`
    - `Corner 3 (Bottom-Left)`: `x = screen_x + margin`, `y = screen_y + screen_h - win_h - margin`
    - `Corner 4 (Bottom-Right)`: `x = screen_x + screen_w - win_w - margin`, `y = screen_y + screen_h - win_h - margin`
  - Position changes transition smoothly using `QPropertyAnimation` targeting the `pos` property over `200ms` with `QEasingCurve.OutCubic`.
- **Acceptance Criteria**:
  - **AC-3.3.1 (Top-Left Snapping)**:
    - *Given* a screen with origin `(0, 0)` and a 292x292 window,
    - *When* `Super+Alt+1` or `--snap 1` is triggered,
    - *Then* the window smoothly animates to `(24, 24)`.
  - **AC-3.3.2 (Bottom-Right Snapping)**:
    - *Given* a 1920x1080 screen with 24px margin and 292x292 window,
    - *When* `Super+Alt+4` or `--snap 4` is triggered,
    - *Then* the window animates to `(1920 - 292 - 24, 1080 - 292 - 24) = (1604, 764)`.
  - **AC-3.3.3 (Dock & Panel Avoidance)**:
    - *Given* an Ubuntu GNOME desktop where the top panel occupies 32px height,
    - *When* snapping to Top-Left,
    - *Then* the window y-coordinate respects `availableGeometry().top()` and places the window at `y = 32 + 24 = 56px`.

#### US-3.4: Ubuntu System Tray & AppIndicator Menu
- **Description**: As a user, I want an icon in my Ubuntu top panel system tray with a comprehensive menu, so that I can configure camera devices, resolutions, filters, and exit gracefully without CLI commands.
- **Specification**:
  - Implemented using `QSystemTrayIcon` with clean SVG/PNG camera iconography and D-Bus StatusNotifierItem compatibility.
  - **Menu Structure**:
    - `● SelfiCamera (Active: 720p @ 30fps)` [Disabled header]
    - `---`
    - `Camera Device ▶` (Radio list of detected V4L2 devices + `Refresh Devices`)
    - `Resolution ▶` (`640x480 (SD)`, `● 1280x720 (HD - Recommended)`, `1920x1080 (FHD)`)
    - `---`
    - `☑ Horizontal Mirror (Flip)`
    - `☑ Auto-Light Boost`
    - `Background Blur ▶` (`○ Level 0: Off`, `○ Level 1: Subtle`, `● Level 2: Balanced`, `○ Level 3: Heavy`)
    - `☐ Click-Through Ghost Mode`
    - `---`
    - `Reset Position & Size` (re-centers overlay at 260px)
    - `Quit SelfiCamera`
- **Acceptance Criteria**:
  - **AC-3.4.1 (Tray Icon Visibility)**:
    - *Given* SelfiCamera is running on Ubuntu GNOME,
    - *When* the top bar system tray is viewed,
    - *Then* the SelfiCamera icon is visible and responsive to right-click.
  - **AC-3.4.2 (Device Switching via Menu)**:
    - *Given* two webcams are connected,
    - *When* the user selects the second webcam from the tray menu,
    - *Then* the current capture worker is stopped cleanly and the new camera stream starts within $< 1.0\text{ s}$.
  - **AC-3.4.3 (Clean Exit)**:
    - *Given* the application is running,
    - *When* `Quit SelfiCamera` is clicked,
    - *Then* camera worker, audio worker, and IPC socket are stopped cleanly, configuration is saved, and process exits with code 0.

---

### Epic 4: Developer Ergonomics, Automated Testing & Verification

#### US-4.1: Single Startup Command & Virtual Environment Isolation
- **Description**: As a developer or user on Ubuntu Linux, I want to clone the repository and run a single command `./run.sh` to automatically set up the virtual environment, install dependencies, and launch SelfiCamera, so that setup requires zero manual tinkering.
- **Specification**:
  - Root script: `./run.sh` (executable bash script).
  - Checks for Python 3.10+ (prefers `python3.12` or `uv`).
  - Automatically creates `.venv` if not present (`python3 -m venv .venv`).
  - Installs/updates dependencies from `pyproject.toml` / `requirements.txt`.
  - Downloads or validates the local ultra-lite ONNX segmentation model if absent.
  - Launches `python -m selficamera "$@"` forwarding any CLI arguments.
  - Strict Ubuntu policy: never touches global system Python (`sudo pip` is forbidden).
- **Acceptance Criteria**:
  - **AC-4.1.1 (Automated Bootstrapping)**:
    - *Given* a clean environment without `.venv`,
    - *When* `./run.sh` is executed,
    - *Then* `.venv` is created, dependencies are installed, and the application initializes.
  - **AC-4.1.2 (CLI Argument Forwarding)**:
    - *Given* `./run.sh --help` or `./run.sh --headless-mock`,
    - *When* executed,
    - *Then* the arguments are passed directly to `selficamera.__main__`.

#### US-4.2: Comprehensive Headless Automated Pytest Suite with Mock Feeds
- **Description**: As a QA engineer or CI/CD runner, I want a complete automated test suite that tests all camera, lighting, segmentation, audio, and configuration code using synthetic test feeds without requiring physical hardware, so that tests run deterministically anywhere.
- **Specification**:
  - Fixtures in `tests/conftest.py`:
    - `mock_frame`: Generates synthetic `1280x720` uint8 BGR frames with colored geometric patterns and timestamps.
    - `mock_camera_worker`: Emits synthetic video frames at 30 FPS or in batch mode.
    - `mock_audio_worker`: Emits synthetic sine wave RMS energy values.
    - `mock_segmentation_engine`: Fast mask generator returning a synthetic centered circular mask for lightning-fast unit tests.
  - Test suites:
    - `test_capture.py`: Tests device scanner, worker lifecycle, frame emission, error handling.
    - `test_lighting.py`: Tests low-light gamma computation, LUT creation, temporal smoothing.
    - `test_segmentation.py`: Tests ONNX model loading, input tensor normalization, mask upscaling, and 3-tier blur composition.
    - `test_audio.py`: Tests RMS energy calculation, dBFS normalization, asymmetric attack/decay filter.
    - `test_shortcuts.py`: Tests IPC socket message serialization, command routing, and error responses.
    - `test_config.py`: Tests JSON persistence, atomic writing, schema migration, and default fallbacks.
- **Acceptance Criteria**:
  - **AC-4.2.1 (Zero Hardware Dependency)**:
    - *Given* a headless Linux environment with no camera and no sound card,
    - *When* `pytest tests/` is run,
    - *Then* 100% of the unit and pipeline tests pass without errors or skipped hardware warnings.
  - **AC-4.2.2 (Execution Speed)**:
    - *Given* the entire unit test suite,
    - *When* executed via `pytest`,
    - *Then* total execution time is under 15 seconds.

#### US-4.3: Headless Qt GUI Interaction Tests (pytest-qt)
- **Description**: As a QA engineer, I want headless GUI interaction tests that verify window rendering, drag-to-move, scroll-to-resize, HUD auto-hide transitions, and ghost mode, so that regressions in UI behavior are caught automatically.
- **Specification**:
  - Leverages `pytest-qt` under `QT_QPA_PLATFORM=offscreen`.
  - Exercises `qtbot.mouseMove()`, `qtbot.mouseClick()`, `qtbot.wheel()`, and `qtbot.keyClick()`.
  - Verifies:
    - Window creation, flags, and size.
    - Scroll-to-resize transitions ($160 \leftrightarrow 260 \leftrightarrow 380$).
    - Corner snapping coordinate math.
    - HUD opacity changes upon mouse enter/leave.
    - Ghost mode attribute changes.
- **Acceptance Criteria**:
  - **AC-4.3.1 (Headless Execution)**:
    - *Given* `QT_QPA_PLATFORM=offscreen`,
    - *When* `pytest tests/test_overlay_gui.py` is executed,
    - *Then* all GUI tests run and pass without opening an X11/Wayland display window.
  - **AC-4.3.2 (Resize Interaction Verification)**:
    - *Given* an initialized `OverlayWindow` with diameter `260px`,
    - *When* `qtbot` sends a wheel event stepping up,
    - *Then* `window.diameter` updates to `380px` and geometry resizes accordingly.

#### US-4.4: Automated Latency & CPU Performance Benchmark Suite
- **Description**: As a performance engineer, I want benchmark scripts that measure per-stage frame latency and CPU utilization across 500 frames, so that performance regressions are detected before release.
- **Specification**:
  - Benchmark script: `benchmarks/benchmark_pipeline.py`.
  - Runs 500 synthetic 720p frames through the complete pipeline (Mirror + Auto-Light + Segmentation Blur + Composition).
  - Measures:
    - Mean, median, 95th-percentile, and max latency per stage.
    - Total end-to-end frame processing time.
    - CPU utilization percentage during benchmark execution.
  - Assertion gate: 95th-percentile frame processing latency must be $< 25.0\text{ ms}$ (strict ceiling: $30.0\text{ ms}$).
- **Acceptance Criteria**:
  - **AC-4.4.1 (Latency Ceiling Gate)**:
    - *Given* 500 consecutive 720p frames processed through Tier 2 Balanced Blur,
    - *When* benchmark telemetry is compiled,
    - *Then* the 95th-percentile end-to-end latency is $< 25.0\text{ ms}$.
  - **AC-4.4.2 (Structured Telemetry Output)**:
    - *Given* `python benchmarks/benchmark_pipeline.py` is invoked,
    - *When* execution completes,
    - *Then* a clean markdown/JSON summary table is printed with per-stage millisecond timings.

---

## 5. UI/UX Interaction & Visual Design System

### 5.1 Geometry & Spatial Layout
```
+-------------------------------------------------------------+
| Total Window Geometry: (Diameter + 32px) x (Diameter + 32px) |
|                                                             |
|   + - - - - - - - Outer Shadow Margin (16px) - - - - - -+   |
|   |                                                     |   |
|   |         +---------------------------------+         |   |
|   |        /       Voice Aura Glow Ring        \        |   |
|   |       /   +-----------------------------+   \       |   |
|   |      |   /    Inner Border Stroke (1px)  \   |      |   |
|   |      |  |                                 |  |      |   |
|   |      |  |       Circular Video Feed       |  |      |   |
|   |      |  |        (Center-Cropped)         |  |      |   |
|   |      |  |                                 |  |      |   |
|   |      |   \         [Auto-Hide HUD]       /   |      |   |
|   |       \   +-----------------------------+   /       |   |
|   |        \                                   /        |   |
|   |         +---------------------------------+         |   |
|   |                                                     |   |
|   + - - - - - - - - - - - - - - - - - - - - - - - - - - +   |
+-------------------------------------------------------------+
```

### 5.2 Preset Sizing Dimensions
| Size Tier | Diameter | Shadow Margin | Window Size | Recommended Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Small (Compact)** | `160 px` | `16 px` | `192 x 192 px` | Live coding, dense IDEs, terminal demonstrations |
| **Medium (Standard)** | `260 px` | `16 px` | `292 x 292 px` | Default presentation, teaching, code walkthroughs |
| **Large (Focus)** | `380 px` | `16 px` | `412 x 412 px` | Keynote introductions, direct 1-on-1 dialogue, Q&A |

### 5.3 Color Palette & Styling Tokens
- **Drop Shadow**: Gaussian falloff, base color `#000000`, peak opacity `0.38` at radius, decaying to `0.0` at boundary margin.
- **Inner Stroke**: `#FFFFFF` with `0.22` opacity, width `1.0 px`.
- **Voice Aura (Dynamic Ring)**:
  - *Silence / Ambient* ($E \le 0.05$): `#00E5FF` (Cyan), alpha `0.20`, pen width `2.5 px`.
  - *Active Speech* ($0.05 < E \le 0.75$): Linear gradient `#00E5FF` $\rightarrow$ `#00B0FF`, alpha `0.85`, pen width `3.5 - 5.5 px`.
  - *High Vocal Energy* ($E > 0.75$): Glowing gradient `#D500F9` (Electric Magenta) $\rightarrow$ `#00E676` (Neon Green), alpha `1.0`, pen width `6.5 px`.
- **Auto-Hiding HUD**:
  - Background capsule: `#1E1E2E` (Deep Charcoal) with `0.88` alpha and `8px` rounded corner radius.
  - Button text / glyphs: `#CDD6F4` (High contrast crisp white/lavender).
  - Button hover: `#313244` with `#89B4FA` accent highlight.

### 5.4 Screen Corner Snapping Layout
- **Margin**: `24 px` offset from active screen boundary.
- Snapping respects GNOME Top Panel (`~32px`) and GNOME Dash/Dock.
```
+-------------------------------------------------------------+
| Top Bar (Panel)                                             |
+-------------------------------------------------------------+
| [Corner 1: Top-Left]                   [Corner 2: Top-Right]|
| (x: 24, y: 56)                         (x: W - 292 - 24,    |
|                                         y: 56)              |
|                                                             |
|                                                             |
|                                                             |
| [Corner 3: Bottom-Left]             [Corner 4: Bottom-Right]|
| (x: 24,                             (x: W - 292 - 24,       |
|  y: H - 292 - 24)                    y: H - 292 - 24)       |
+-------------------------------------------------------------+
```

---

## 6. Command Line Interface (CLI) & Options Specification

SelfiCamera provides a unified executable entrypoint supporting daemon execution, testing modes, and client IPC actions.

### 6.1 Invocation Syntax
```bash
selficamera [OPTIONS]
# or via python module
python -m selficamera [OPTIONS]
```

### 6.2 CLI Arguments Table
| Option Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `-d, --device` | `STRING` | `"/dev/video0"` | V4L2 camera device node path. |
| `-W, --width` | `INT` | `1280` | Capture frame width in pixels. |
| `-H, --height` | `INT` | `720` | Capture frame height in pixels. |
| `-f, --fps` | `INT` | `30` | Capture frames per second. |
| `-s, --size` | `CHOICE` | `260` | Initial circle diameter (`160`, `260`, or `380`). |
| `-b, --blur` | `INT` | `2` | Initial background blur tier (`0`, `1`, `2`, or `3`). |
| `--no-mirror` | `FLAG` | `False` | Start with horizontal mirror disabled. |
| `--no-light` | `FLAG` | `False` | Start with Auto-Light Boost disabled. |
| `--ghost` | `FLAG` | `False` | Start immediately in click-through Ghost Mode. |
| `--headless-mock` | `FLAG` | `False` | Run with synthetic mock video & audio feeds (no webcam needed). |
| `--version` | `FLAG` | - | Display version and exit. |
| `-h, --help` | `FLAG` | - | Display help menu and exit. |

### 6.3 Client IPC Commands (Wayland & Remote Control)
When SelfiCamera is already running, invoking the CLI with an action flag communicates with the running instance over the Unix Domain Socket:

| IPC Action Flag | Target Action | Behavior on Running Instance |
| :--- | :--- | :--- |
| `--toggle` | `toggle_visibility` | Toggles overlay visibility (Show / Hide). |
| `--toggle-ghost` | `toggle_ghost_mode` | Toggles click-through Ghost Mode on/off. |
| `--snap <1-4>` | `snap_corner <1-4>` | Snaps overlay to specified desktop corner (1..4). |
| `--blur-cycle` | `cycle_blur` | Steps blur tier ($0 \rightarrow 1 \rightarrow 2 \rightarrow 3 \rightarrow 0$). |
| `--status` | `query_status` | Prints JSON status of running instance to stdout. |
| `--exit` | `exit_app` | Gracefully closes running SelfiCamera process. |

---

## 7. IPC Socket Protocol & Wire Specification

### 7.1 Socket Addressing & Lifecycle
- **Path**: `/run/user/<UID>/selficamera.sock` (standard XDG runtime directory).
  - Fallback: `/tmp/selficamera-<UID>.sock` if `XDG_RUNTIME_DIR` is undefined.
- **Permissions**: `0600` (strictly readable/writable only by the current Linux user).
- **Lifecycle**:
  - The primary application instance binds and listens on this socket on startup.
  - Upon clean shutdown or crash recovery, stale socket files are unlinked.
  - If a socket exists, new CLI invocations attempt a 50ms connection handshake to check if an active instance is alive before declaring a port conflict.

### 7.2 Message Framing & JSON Schemas
Communication uses single-line JSON messages terminated by newline (`\n`).

#### Request Schema (Client $\rightarrow$ Server):
```json
{
  "action": "toggle_visibility" | "toggle_ghost" | "snap_corner" | "cycle_blur" | "get_status" | "quit",
  "params": {
    "corner": 1
  }
}
```

#### Response Schema (Server $\rightarrow$ Client):
```json
{
  "success": true,
  "action": "snap_corner",
  "message": "Snapped to corner 1 (Top-Left)",
  "state": {
    "visible": true,
    "ghost_mode": false,
    "diameter": 260,
    "blur_level": 2,
    "device": "/dev/video0",
    "fps": 30.0
  }
}
```

---

## 8. Configuration Management & State Persistence

### 8.1 Storage Location & Atomic Writing
- **File Location**: `~/.config/selficamera/config.json`.
- **Safety Guarantee**: State updates are written atomically:
  1. Write JSON data to temporary file `~/.config/selficamera/config.json.tmp.<PID>`.
  2. Flush and sync file buffers to disk (`os.fsync`).
  3. Atomic POSIX rename via `os.replace` to replace `config.json`.
  4. Guarantees zero file corruption even on sudden power loss or kernel panics.

### 8.2 JSON Schema & Default Values
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SelfiCameraConfiguration",
  "type": "object",
  "properties": {
    "diameter": { "type": "integer", "enum": [160, 260, 380], "default": 260 },
    "x": { "type": "integer", "default": 1600 },
    "y": { "type": "integer", "default": 760 },
    "device_path": { "type": "string", "default": "/dev/video0" },
    "resolution": {
      "type": "array",
      "items": { "type": "integer" },
      "minItems": 2,
      "maxItems": 2,
      "default": [1280, 720]
    },
    "fps": { "type": "integer", "default": 30 },
    "mirror": { "type": "boolean", "default": true },
    "auto_light": { "type": "boolean", "default": true },
    "blur_level": { "type": "integer", "minimum": 0, "maximum": 3, "default": 2 },
    "click_through": { "type": "boolean", "default": false },
    "mic_device": { "type": "string", "default": "default" },
    "aura_enabled": { "type": "boolean", "default": true }
  },
  "required": ["diameter", "device_path", "resolution", "blur_level"]
}
```

---

## 9. Definition of Done (DoD)

To maintain absolute engineering rigor across our pipeline, features must satisfy the following criteria before passing Phase 3 (Implementation) and Phase 4 (QA):

### 9.1 Definition of Done for Phase 3 (Full-Stack & AI Engineer)
1. **Architecture & Scope Compliance**:
   - All modules correspond exactly to the layout defined in CTO `architecture.md` and this specification.
   - All 19 User Stories (US-1.1 through US-4.4) are fully implemented.
2. **Offline & Privacy Integrity**:
   - Zero external network dependencies or remote API calls.
   - Local ONNX model bundled at `selficamera/models/selfie_segmentation.onnx` (<2MB).
3. **Packaging & Execution Standards**:
   - Clean `pyproject.toml` and locked `requirements.txt`.
   - Single-command bootstrap `./run.sh` initializes `.venv` and starts the app cleanly.
   - No `sudo` or global `pip` requirements.
4. **Code Quality**:
   - 100% Python 3.12 type annotations (`mypy` compliant where applicable).
   - Clean docstrings and separation of concerns across Qt threads and workers.
5. **Initial Unit Tests & Verification**:
   - Core unit tests implemented in `tests/` passing cleanly with synthetic fixtures.

### 9.2 Definition of Done for Phase 4 (QA & Code Reviewer)
1. **Automated Test Coverage**:
   - 100% passing test suite across `test_capture.py`, `test_processor.py`, `test_lighting.py`, `test_segmentation.py`, `test_audio.py`, `test_overlay_gui.py`, `test_shortcuts.py`, and `test_config.py`.
   - Tests execute in headless environments (`QT_QPA_PLATFORM=offscreen`) without physical camera/mic hardware.
2. **Performance & Latency Gates**:
   - End-to-end processing latency benchmark verifies 95th-percentile frame time $< 25.0\text{ ms}$ (hard limit: $30.0\text{ ms}$) on 720p frames.
   - Active CPU utilization verified at $< 5\%$ on modern multi-core systems.
3. **Acceptance Verification**:
   - Every `Given / When / Then` acceptance criterion specified in this document has been explicitly verified with automated or automated-mock test cases.
4. **Packaging & Clean Handoff**:
   - Clean forensic test run log and QA sign-off report produced.
