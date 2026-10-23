# CTO Architectural Briefing - SelfiCamera

## 1. Executive Summary & Mission
SelfiCamera is an ultra-lightweight, zero-bloat, offline desktop circular presenter camera overlay for Ubuntu Linux (supporting both Wayland and X11 sessions). Designed specifically for live presenters, coders, and streamers, it renders a floating borderless circular webcam feed with real-time Auto-Light Boost, an offline 3-tier background blur engine, a dynamic microphone-reactive voice aura border, global presenter hotkeys, and an Ubuntu system tray indicator.

## 2. Target Constraints & Performance Objectives
- **OS Platform**: Ubuntu Linux (GNOME Desktop on Wayland and X11).
- **Python Environment**: Isolated virtual environment (`.venv` managed via `uv` using CPython 3.12.15).
- **Offline Guarantee**: Zero outbound network requests, zero telemetry, zero cloud APIs.
- **Latency Budget**: Total end-to-end frame processing (capture -> lighting -> segmentation/blur -> render) < 30ms (targeting 30-60 FPS).
- **Resource Budget**: Idle CPU < 1%, Active video pipeline CPU < 5% on typical multi-core Linux systems.
- **Display Server Compatibility**: Wayland native (`QT_QPA_PLATFORM=wayland;xcb`) with Xwayland fallback; click-through via Qt window flags / X11 shape masks / Wayland input regions.

## 3. Technology Stack Selection
| Subsystem | Selected Technology | Rationale & Trade-offs |
| :--- | :--- | :--- |
| **GUI & Rendering** | PySide6 (Qt 6.12) | High-performance hardware-accelerated 2D canvas, native Wayland/X11 support, transparent frameless window with anti-aliasing, QPainter custom drawing for circular mask, shadow, and voice aura ring. |
| **Video Acquisition** | OpenCV (`cv2.VideoCapture`) with V4L2 backend (`CAP_V4L2`) | Native Linux V4L2 ioctls, MJPG/YUYV hardware decoding, sub-millisecond frame acquisition in a dedicated `QThread`. |
| **Offline Segmentation** | ONNX Runtime (`onnxruntime`) + MediaPipe Selfie Segmentation (<2MB ONNX model) | Quantized/float32 ultra-lite model (~1.5 MB), inference takes ~3-8ms on modern x86 CPU without GPU overhead; 100% offline. |
| **Audio Reactivity** | `sounddevice` / PortAudio (PipeWire / PulseAudio bridge) | Sub-10ms audio RMS sampling in a worker thread; non-blocking ring buffer; lightweight energy calculation. |
| **Global Shortcuts** | Dual-mode: Local Qt hotkeys + IPC CLI trigger (`selficamera --toggle`, `--ghost`, etc.) for Wayland + `pynput` / X11 grab when on X11. | Wayland security model intentionally restricts global key grabbing; IPC CLI socket allows GNOME Custom Shortcuts to control the app seamlessly, while X11 uses standard grabs. |
| **Tray / Indicator** | `QSystemTrayIcon` with fallback to `AppIndicator3` / D-Bus StatusNotifierWatcher | Native integration with Ubuntu GNOME top bar. |
| **Testing Harness** | `pytest`, `pytest-qt`, mock synthetic V4L2 video & mock audio sine feeds | 100% deterministic, headless CI/CD execution without physical webcam or microphone hardware. |
