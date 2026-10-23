# Phase 2: Product Specifications — PM Handoff Report

**Project:** SelfiCamera  
**Phase:** Phase 2 Complete $\rightarrow$ Handing off to Phase 3 (Full-Stack & AI Engineer)  
**Author:** Product Manager (PM)  
**Authoritative Specification File:** [`specifications.md`](file:///run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/pm_1/specifications.md)  
**Architecture Reference:** [`architecture.md`](file:///run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/cto_1/architecture.md)  
**Date:** 2026-10-22  

---

## 1. Executive Summary & Deliverables

Phase 2 (Product Specifications & Acceptance Criteria) is officially **COMPLETE**. 

All user requirements (R1, R2, R3, R4) and the CTO's architectural blueprint have been synthesized into an actionable, unambiguous engineering product specification:
- **19 User Stories** across 4 core Epics.
- **Strict Gherkin (`Given / When / Then`) Acceptance Criteria** for every story and feature.
- **Detailed UI/UX Visual & Geometry Guidelines** (canvas geometry, 160/260/380px diameter presets, 16px shadow margins, 24px corner snap margins, dynamic voice aura color/pen modulation, HUD fade animations).
- **CLI & Unix Domain Socket IPC Specifications** (daemon invocation, mock flags, client action flags, JSON wire protocol schemas).
- **Configuration Management Schema** with atomic writing rules.
- **Formal Definition of Done (DoD)** for Phase 3 Implementation and Phase 4 QA Verification.

---

## 2. Epic & Feature Mapping for Phase 3 Implementation

The Full-Stack & AI Engineer can execute implementation in structured sprints / stages aligned with these 4 Epics:

### Epic 1: Presenter Floating Window & Intuitive Manipulation
- **US-1.1**: Frameless 1:1 circular presentation window (`PySide6.QtWidgets.QWidget`) with anti-aliased circular clipping (`QPainterPath`) and soft Gaussian drop shadow.
- **US-1.2**: Fluid drag-to-move repositioning with screen boundary clamping.
- **US-1.3**: Scroll-wheel resizing stepping through 160px (Compact), 260px (Standard), and 380px (Focus) with smooth 180ms cubic easing animation and anchored center coordinates.
- **US-1.4**: Always-on-top persistence (`Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool`) over fullscreen IDEs/browsers on Wayland and X11.
- **US-1.5**: Auto-hiding HUD controls (Flip, Blur, Light, Ghost, Close) fading in on hover (150ms) and smoothly fading out after 1.2s inactivity (300ms).
- **US-1.6**: Click-through Ghost Mode (`WA_TransparentForMouseEvents`, empty input region on Wayland/X11) passing mouse events directly to underlying IDEs.

### Epic 2: Camera Pipeline & Offline AI Background Blur
- **US-2.1**: V4L2 device scanner (`/dev/video*`), background acquisition worker (`CameraCaptureWorker`), 720p@30fps default, atomic depth-1 queue to drop stale frames.
- **US-2.2**: Instant horizontal mirror toggle (`cv2.flip(frame, 1)` with $<0.5\text{ms}$ latency).
- **US-2.3**: Real-time Auto-Light Boost (downsampled luminance estimation, adaptive gamma calculation, anti-flicker smoothing, precomputed 256-byte LUT).
- **US-2.4**: 3-tier offline bokeh blur (Tier 0: Off, Tier 1: Subtle ~12px, Tier 2: Balanced ~28px, Tier 3: Heavy ~56px) using local MediaPipe Selfie Segmentation ONNX model (~1.3MB) via `onnxruntime` CPU execution and downscale-blur-upscale bokeh trick.
- **US-2.5**: 100% offline isolation guarantee (no outbound network imports, sockets, or telemetry).

### Epic 3: Presenter Desktop Integration & Voice Aura
- **US-3.1**: PipeWire / PulseAudio background microphone monitor (`sounddevice.InputStream`), RMS dBFS calculation, asymmetric attack/decay filter, driving dynamic glowing aura border (cyan $\rightarrow$ blue $\rightarrow$ magenta/emerald).
- **US-3.2**: Dual-mode global presenter shortcuts (`Super+Alt+C`, `Super+Alt+X`, `Super+Alt+1..4`, `Super+Alt+B`): direct `pynput` key grab on X11; Unix Domain Socket IPC daemon (`/run/user/<UID>/selficamera.sock`) for Wayland.
- **US-3.3**: Screen corner snapping (`Super+Alt+1..4`) with 24px screen margin and desktop panel/dock avoidance.
- **US-3.4**: Ubuntu System Tray (`QSystemTrayIcon`) context menu for device switching, resolution picking, mirror/light/ghost toggles, and clean exit.

### Epic 4: Developer Ergonomics, Automated Testing & Verification
- **US-4.1**: Single-command bootstrapping script `./run.sh` creating `.venv`, installing dependencies from `pyproject.toml`, and launching the app.
- **US-4.2**: Complete headless automated unit test suite with mock video fixtures (`numpy` test patterns) and mock audio fixtures (sine waves).
- **US-4.3**: Headless Qt GUI interaction test suite (`pytest-qt` under `QT_QPA_PLATFORM=offscreen`).
- **US-4.4**: Performance benchmark runner (`benchmarks/benchmark_pipeline.py`) verifying $<30\text{ms}$ frame processing latency and $<5\%$ CPU usage.

---

## 3. Definition of Done Checklist for Full-Stack & AI Engineer

Before handing off from Phase 3 to Phase 4, verify that:
- [ ] Code is organized cleanly under `selficamera/` matching the layout in CTO `architecture.md`.
- [ ] All 19 User Stories are implemented and satisfy the Gherkin Acceptance Criteria in `specifications.md`.
- [ ] The ultra-lite MediaPipe Selfie Segmentation ONNX model (~1.3MB) is committed locally in `selficamera/models/selfie_segmentation.onnx`.
- [ ] `./run.sh` cleanly installs virtual environment and runs the application without manual intervention.
- [ ] Zero network libraries are imported (`requests`, `urllib`, `httpx` are prohibited).
- [ ] Unit tests and synthetic fixtures are implemented in `tests/` and pass with `pytest`.
- [ ] Benchmarks in `benchmarks/` run and report latencies within budget.

---

## 4. Immediate Next Step

Phase 2 is formally completed. Orchestrator can now dispatch **Phase 3: Full-Stack & AI Engineer** (`fullstack-ai-engineer`) to begin implementation.
