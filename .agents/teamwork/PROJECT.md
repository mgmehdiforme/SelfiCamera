# Project: SelfiCamera

## Architecture
SelfiCamera is structured as a modular, decoupled Python desktop application leveraging PySide6 (Qt6 for Python) for rendering, V4L2 / OpenCV for video acquisition, an ultra-lite ONNX / TFLite offline segmentation engine for background isolation, sounddevice / pulsectl for audio reactivity, and a dual-mode shortcut & system tray integration.

### Subsystem Modules:
1. `selficamera.capture`: Camera pipeline wrapping V4L2 via OpenCV / v4l2py with resolution configuration and device enumeration.
2. `selficamera.processor`: Lighting compensation ("Auto-Light Boost"), horizontal mirror, and offline 3-tier background blur via ultra-lite local segmentation.
3. `selficamera.audio`: Background audio listener tapping PipeWire/PulseAudio to compute RMS voice activity energy.
4. `selficamera.ui.overlay`: Frameless, transparent, circular presentation window with drop shadow, drag, scroll-resize, corner snapping, voice aura ring, and auto-hiding HUD.
5. `selficamera.ui.tray`: Ubuntu AppIndicator / QSystemTrayIcon menu.
6. `selficamera.shortcuts`: Dual-mode global shortcuts (X11 grab + Wayland IPC/CLI trigger).
7. `selficamera.config`: Application settings and state persistence.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Frameless Circular Window | 1:1 circle, anti-aliased mask, transparent window with soft Gaussian drop shadow | Phase 3 (M3) | R1 |
| F2 | Window Interaction & Snapping | Smooth drag-to-move, scroll-to-resize (160, 260, 380px), corner snapping (Super+Alt+1-4) | Phase 3 (M3) | R1, R3 |
| F3 | Always-on-Top Persistence | Pinned over fullscreen IDEs/browsers on both Wayland and X11 | Phase 3 (M3) | R1 |
| F4 | Auto-Hiding On-Hover HUD | Controls fade in on enter, smoothly fade out on exit | Phase 3 (M3) | R1 |
| F5 | Click-Through Ghost Mode | Passes mouse clicks directly through to underlying windows | Phase 3 (M3) | R1, R3 |
| F6 | V4L2 Camera Capture | Enumerate `/dev/video*`, configure 720p@30fps, threaded acquisition | Phase 3 (M3) | R2 |
| F7 | Horizontal Mirror Toggle | Instant horizontal flip without latency penalty | Phase 3 (M3) | R2 |
| F8 | Auto-Light Boost | Real-time adaptive exposure/gamma enhancement for low-light conditions | Phase 3 (M3) | R2 |
| F9 | 3-Tier Offline Blur | Off (0), Subtle (~10px), Balanced (~25px), Heavy (~50px) using ultra-lite (<5MB) offline model | Phase 3 (M3) | R2 |
| F10 | Voice Aura Indicator | Dynamic pulsing aura border ring reacting to microphone audio levels via PipeWire/PulseAudio | Phase 3 (M3) | R3 |
| F11 | Presenter Global Shortcuts | Super+Alt+C, Super+Alt+X, Super+Alt+1-4, Super+Alt+B on X11 and Wayland | Phase 3 (M3) | R3 |
| F12 | Ubuntu AppIndicator / Tray | System tray menu for devices, resolutions, mirror, ghost mode, and exit | Phase 3 (M3) | R3 |
| F13 | Isolated Environment & Packaging | Clean virtualenv (.venv), pyproject.toml / requirements.txt, single launch command | Phase 3 (M3) | R4 |
| F14 | Comprehensive Automated Test Suite | Unit tests with mock V4L2 video & mock audio, headless pytest-qt tests | Phase 4 (M4) | R4 |
| F15 | Performance Benchmarks | Benchmark scripts verifying <30ms frame processing and low CPU utilization | Phase 4 (M4) | R4 |
| F16 | Always-On-Top & Platform Fallback | Guaranteed Always-On-Top over full-screen apps, `QT_QPA_PLATFORM=xcb;wayland` launcher fallback | Phase 6 (M6) | R1 |
| F17 | Unblocked Drag-to-Move | HUD click transparency fix, deferred fsync, multi-monitor virtual desktop clamping | Phase 6 (M6) | R1 |
| F18 | Zero-Drift Responsive Resizing | Canonical float anchor architecture, continuous 120-600px scroll/drag, small-diameter HUD adaptation | Phase 6 (M6) | R2 |
| F19 | Floating Settings Panel | Standalone top-level tool window with 5 control cards, dark theme, live sliders, gear icon & context menu | Phase 7 (M7) | R3 |
| F20 | Expanded Automated Verification Suite | Headless pytest tests for drag lifecycle, continuous slider resize, settings panel signals, and window flags | Phase 8 (M8) | R4 |
| F21 | 1-Click Corner Snapping in SettingsPanel | 2x2 grid buttons (↖ TL, ↗ TR, ↙ BL, ↘ BR) in Card 5, multi-monitor bounds clamping | Phase 10 (M10) | R1 |

## Milestones & Pipeline Phases
| # | Phase / Milestone | Assigned Role | Description | Dependencies | Status |
|---|-------------------|---------------|-------------|--------------|--------|
| M1 | Phase 1: Architecture Foundation | `cto` | Technical architecture blueprint, stack selection, offline model design, latency budget | none | COMPLETED |
| M2 | Phase 2: Product Specifications | `product-manager` | PRD, user stories, Given/When/Then acceptance criteria, CLI & UX specs | M1 | COMPLETED |
| M3 | Phase 3: Full-Stack Implementation | `fullstack-ai-engineer` | Full implementation of selficamera package, UI, pipeline, models, shortcuts, tray | M2 | COMPLETED |
| M4 | Phase 4: Automated Testing & Benchmarks | `qa-code-reviewer` | Mock feeds, pytest suites, pytest-qt headless GUI tests, benchmark runners | M3 | COMPLETED |
| M5 | Phase 5: Verification & Forensic Audit | `teamwork_preview_auditor` | Integrity forensics, zero-mock production smoke testing, acceptance verification | M4 | COMPLETED |
| M6 | Phase 6: Drag, Always-On-Top & Resizing (R1 & R2) | `teamwork_preview_worker` | Fix HUD click trap, deferred fsync, multi-monitor clamping, float anchor, continuous diameter, platform fallback | M5 | COMPLETED |
| M7 | Phase 7: Floating Settings Panel & Pipeline Controls (R3) | `teamwork_preview_worker` | `SettingsPanel` widget, 5 control cards, HUD gear button, context menu, lighting/blur pipeline setters | M6 | COMPLETED |
| M8 | Phase 8: Automated Test Suite Expansion (R4) | `teamwork_preview_test_writer` | Add `test_settings_panel.py`, expand `test_overlay_gui.py` and `test_config.py`, verify 100% headless pass | M7 | COMPLETED |
| M9 | Phase 9: Verification, Review & Forensic Integrity Audit | `teamwork_preview_auditor` & reviewers | Reviewers, Challengers, and Forensic Auditor verification | M8 | COMPLETED |
| M10 | Phase 10: 1-Click Corner Snapping & 5-Core Controls UI | `fullstack-ai-engineer` | Card 5 2x2 corner snap buttons, multi-monitor geometry clamping, test_settings_panel.py expansion | M9 | COMPLETED |
| M11 | Phase 11: QA Sign-off & Forensic Integrity Verification | `qa-code-reviewer` & `teamwork_preview_auditor` | 66/66 automated tests passing, P95 latency 13.12ms, 0 AST stubs, clean audit sign-off | M10 | COMPLETED |

## Interface Contracts
### `CameraCapture` ↔ `FrameProcessor`
- Input: Frame index, BGR numpy array `(H, W, 3)` uint8.
- Output: Processed BGR / BGRA numpy array `(H, W, 4)` uint8.
- Operations: mirror, auto_light_boost, apply_segmentation_blur(level).

### `AudioMonitor` ↔ `OverlayWindow`
- Event / Signal: `voice_energy_updated(float energy)` normalized `[0.0, 1.0]`.
- Thread safety: Emitted via Qt signals (`Signal(float)`) across QThread boundary.

### `OverlayWindow` ↔ `SystemTray` & `ShortcutController`
- Actions: `toggle_visibility()`, `set_click_through(bool)`, `set_blur_level(int)`, `snap_to_corner(int corner_id)`, `set_device(str)`, `set_mirror(bool)`.

## Code Layout
```
SelfiCamera/
├── pyproject.toml
├── requirements.txt
├── README.md
├── run.sh
├── selficamera/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── config.py
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── camera.py
│   │   └── v4l2_devices.py
│   ├── processor/
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   ├── lighting.py
│   │   └── segmentation.py
│   ├── audio/
│   │   ├── __init__.py
│   │   └── voice_monitor.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── overlay.py
│   │   ├── hud.py
│   │   ├── settings_panel.py
│   │   ├── tray.py
│   │   └── aura.py
│   ├── shortcuts/
│   │   ├── __init__.py
│   │   └── manager.py
│   └── models/
│       └── selfie_segmentation.onnx (or lightweight tflite/onnx < 2MB)
├── tests/
│   ├── conftest.py
│   ├── test_capture.py
│   ├── test_processor.py
│   ├── test_lighting.py
│   ├── test_segmentation.py
│   ├── test_audio.py
│   ├── test_overlay_gui.py
│   ├── test_settings_panel.py
│   ├── test_shortcuts.py
│   └── test_config.py
└── benchmarks/
    ├── benchmark_pipeline.py
    └── benchmark_latency.py
```
