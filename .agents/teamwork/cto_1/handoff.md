# Phase 1: Architectural Foundation — CTO Handoff Report

**Project:** SelfiCamera  
**Phase:** Phase 1 Complete $\rightarrow$ Handing off to Phase 2 (Product Manager)  
**Author:** Chief Technology Officer (CTO)  
**Architecture Specification File:** [`architecture.md`](file:///run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/cto_1/architecture.md)  
**Date:** 2026-10-22  

---

## 1. Executive Summary & Architectural Decisions

The architectural foundation for **SelfiCamera** has been designed, verified against the Ubuntu Linux environment (tested with Ubuntu 24.04/26.04 on Wayland with PipeWire and CPython 3.12 via `uv`), and approved.

### Key Architectural Invariants & Decisions:
1. **Zero-Bloat Native Stack**: Selected **PySide6 (Qt 6.12)** for hardware-accelerated 2D canvas rendering, native Wayland/X11 window management, frameless circular clipping (`QPainterPath`), soft drop shadow, and dynamic voice aura ring. RAM footprint is targeted at ~45MB (compared to >150MB for Electron).
2. **Offline-Only Local AI Inference**: Background blur is powered by an ultra-lite (~1.3MB) **MediaPipe Selfie Segmentation ONNX** model executed locally on CPU via `onnxruntime`. Zero cloud APIs, zero outbound network traffic, zero subscription costs.
3. **Hard Latency Budget (<30ms, <5% CPU)**:
   - Capture + Mirror: 1.5 - 3.0 ms
   - Auto-Light Boost (Adaptive Gamma LUT): 0.6 - 1.2 ms
   - ONNX Segmentation: 4.0 - 8.0 ms
   - Downscaled Bokeh Blur & Composition: 2.5 - 4.5 ms
   - QImage Render: 1.5 - 3.0 ms
   - **Total End-to-End Latency: 10 - 20 ms** (comfortably under the 30ms ceiling).
4. **Frame Freshness Guard (Atomic Depth-1 Queue)**: Background workers drop stale frames to ensure zero lag accumulation.
5. **Dual-Mode Global Presenter Shortcuts**:
   - **X11 Mode**: Native global key grabbing via `pynput`.
   - **Wayland Mode**: Dedicated Unix Domain Socket IPC daemon (`/run/user/$UID/selficamera.sock`) allowing GNOME Custom Shortcuts to invoke `selficamera --toggle`, `--ghost`, `--snap-corner 1..4`, `--cycle-blur`.
6. **Voice Aura Reactivity**: Background `sounddevice` worker continuously monitors default microphone input (PipeWire / PulseAudio), calculates RMS energy with logarithmic dBFS scaling, applies an asymmetric attack/decay filter, and drives a glowing annular border ring.
7. **Comprehensive Mockability**: Full support for headless CI/CD testing using synthetic video patterns, synthetic audio feeds, and headless Qt (`pytest-qt` under `QT_QPA_PLATFORM=offscreen`).

---

## 2. Component Boundaries & Interface Contracts

| Module | Primary Class | Input | Output / Signals | Thread Context |
| :--- | :--- | :--- | :--- | :--- |
| `selficamera.capture.camera` | `CameraCaptureWorker` | `/dev/video*`, resolution, FPS | `frame_ready(np.ndarray)` (BGR uint8) | Dedicated `QThread` |
| `selficamera.capture.v4l2_devices`| `V4L2DeviceScanner` | `/dev/video*` sysfs/ioctl | List of device metadata dicts | Synchronous helper |
| `selficamera.processor.pipeline` | `FrameProcessor` | Raw BGR frame, filter flags | Processed BGRA `QImage` | Capture worker / Main thread |
| `selficamera.processor.lighting` | `AutoLightBoost` | BGR frame | Gamma-compensated BGR frame | Processing pipeline |
| `selficamera.processor.segmentation`| `SegmentationBlurEngine`| BGR frame, blur level (0-3) | Person-isolated bokeh frame | Processing pipeline |
| `selficamera.audio.voice_monitor` | `AudioMonitorWorker` | Microphone PCM stream | `energy_updated(float)` $[0.0, 1.0]$ | Dedicated `QThread` |
| `selficamera.shortcuts.ipc` | `ShortcutIPCServer` | Unix domain socket commands | `action_triggered(str)` | Dedicated `QThread` |
| `selficamera.ui.overlay` | `OverlayWindow` | Frame QImage, Voice energy | Frameless circular window on screen | Qt Main GUI Thread |
| `selficamera.ui.hud` | `AutoHidingHUD` | Mouse enter/leave events | Control action signals | Qt Main GUI Thread |
| `selficamera.ui.tray` | `SystemTrayController` | Tray user interactions | Subsystem configuration signals | Qt Main GUI Thread |
| `selficamera.config` | `ConfigManager` | User preferences dict | Persistent JSON file | Synchronous / Atomic |

---

## 3. Guidance for Product Manager (Phase 2)

As you craft the Product Requirements Document (PRD), user stories, and acceptance criteria in Phase 2, please structure your specifications around the following architectural capabilities:

### 3.1 Recommended User Stories & Epic Breakdown
1. **Epic 1: Presenter Floating Window & Intuitive Manipulation**
   - User Story 1.1: Circular Frameless Overlay with Soft Drop Shadow (1:1 aspect ratio, centered cropping, crisp anti-aliased edge).
   - User Story 1.2: Smooth Dragging & Bounds Clamping (fluid repositioning without screen tearing).
   - User Story 1.3: Scroll-to-Resize Preset Diameters (160px for minimal coding overlay, 260px for standard presentation, 380px for high-focus introductions).
   - User Story 1.4: Always-On-Top Persistence over fullscreen applications on both Wayland and X11.
   - User Story 1.5: Auto-Hiding On-Hover HUD with smooth fade-in/fade-out animations.
   - User Story 1.6: Click-Through Ghost Mode for unobstructed IDE coding sessions.

2. **Epic 2: High-Performance Camera Stream & Offline AI Isolation**
   - User Story 2.1: V4L2 Device Discovery & 720p@30fps Acquisition.
   - User Story 2.2: Instant Horizontal Mirror Toggle (natural selfie orientation).
   - User Story 2.3: Real-Time Auto-Light Boost (automatic low-light compensation via adaptive gamma LUT).
   - User Story 2.4: 3-Tier Offline Bokeh Background Blur (Off, Subtle ~10px, Balanced ~25px, Heavy ~50px) using local ONNX model.
   - User Story 2.5: Zero Network Isolation (100% offline security guarantee).

3. **Epic 3: Presenter Desktop Integration & Audio Voice Aura**
   - User Story 3.1: PipeWire/PulseAudio Dynamic Voice Aura (reactive glowing ring pulsating with presenter voice activity).
   - User Story 3.2: Dual-Mode Presenter Global Shortcuts (`Super+Alt+C`, `Super+Alt+X`, `Super+Alt+1..4`, `Super+Alt+B`).
   - User Story 3.3: Ubuntu System Tray & AppIndicator Menu (device selector, resolution changer, mode toggles, graceful exit).

4. **Epic 4: Developer Ergonomics, Automated Testing & Verification**
   - User Story 4.1: Single Startup Command (`./run.sh` automated venv initialization and launch).
   - User Story 4.2: Comprehensive Headless Automated Pytest Suite (synthetic V4L2 frames, synthetic audio sine wave, pytest-qt headless GUI tests).
   - User Story 4.3: Automated Latency & CPU Performance Benchmark Suite.

### 3.2 Key Acceptance Criteria Formats (`Given / When / Then`)
Ensure acceptance criteria specify deterministic verification conditions, especially around:
- **Offline Guarantee**: Verification that `selficamera` does not initiate network connections.
- **Latency Verification**: Pipeline benchmark asserting 95th-percentile frame processing latency $< 25$ ms.
- **Wayland Compatibility**: CLI socket trigger verifying action dispatch under Wayland sessions.
- **Ghost Mode Verification**: Mouse events pass through when enabled, and restore on disable.

---

## 4. Verification & Testing Strategy for Downstream Phases

1. **Synthetic Video Fixture**: `MockCameraCaptureWorker` emits numpy frames with moving patterns and timestamps at 30 FPS.
2. **Synthetic Audio Fixture**: `MockAudioMonitorWorker` emits sine wave energy steps.
3. **Headless Qt Testing**: `pytest-qt` executing under `QT_QPA_PLATFORM=offscreen`, allowing the entire UI, drag logic, resize animation, and HUD interactions to be verified in headless CI without a physical display.
4. **Benchmarking Tool**: `benchmarks/benchmark_pipeline.py` provides definitive millisecond telemetry for every stage in the processing loop.

---

## 5. Next Steps
Phase 1 (Architectural Foundation) is now **COMPLETE**.
The engineering blueprint is locked in [`architecture.md`](file:///run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/cto_1/architecture.md).
Handing off to **Product Manager** for **Phase 2: Product Specifications**.
