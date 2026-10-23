# Briefing: SelfiCamera Engineering Implementation (Phase 3)

## Role & Mission
- **Role**: Full-Stack & AI Engineer
- **Working Directory**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/eng_1`
- **Target Codebase**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/selficamera/`
- **Objective**: Execute Phase 3 Full-Stack & AI Implementation of SelfiCamera, delivering a 100% offline, ultra-lite (<2MB model), <30ms latency circular presenter camera overlay for Ubuntu Linux (Wayland and X11).

## Authoritative Documentation References
- **Original User Request**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/ORIGINAL_REQUEST.md`
- **Project Structure & Tracking**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/PROJECT.md`
- **CTO Architecture**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/cto_1/architecture.md`
- **PM Specifications**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/pm_1/specifications.md`
- **PM Handoff**: `/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/pm_1/handoff.md`

## Key Technical Decisions & Constraints
1. **Isolated Environment**: Python 3.12 virtualenv (`.venv`) managed via `uv` / standard python venv. No global packages.
2. **Offline AI Segmentation**: MediaPipe Selfie Segmentation ONNX float32 model (~1.3MB) running on local CPU via `onnxruntime` with SIMD execution. Zero network calls or cloud APIs.
3. **Hardware-Agnostic Testability**: Synthetic BGR video frames and synthetic audio sine waves for 100% deterministic testing without physical webcam/microphone hardware.
4. **Presentation & Overlay**:
   - Frameless, translucent circular window with 16px shadow margin.
   - Discrete diameter presets: 160px (Compact), 260px (Standard), 380px (Focus) with cubic easing animation.
   - Screen boundary clamping and 24px desktop corner snapping (`Super+Alt+1..4`).
   - Click-through ghost mode (`Super+Alt+X`).
   - Dynamic voice aura ring reacting to PipeWire/PulseAudio mic energy.
   - Auto-hiding HUD controls on hover (150ms fade-in, 1200ms hold, 300ms fade-out).
   - Ubuntu System Tray (`QSystemTrayIcon`) menu.
5. **Shortcuts & IPC**: Dual-mode global shortcuts: direct X11 grab + Unix domain socket IPC daemon (`/run/user/<UID>/selficamera.sock`) for Wayland.
6. **Persistence**: Atomic JSON config storage (`~/.config/selficamera/config.json`).
7. **Verification Gates**:
   - Comprehensive pytest suite under `QT_QPA_PLATFORM=offscreen`.
   - Latency benchmark verifying 95th-percentile frame processing < 25ms (strict limit < 30ms).
