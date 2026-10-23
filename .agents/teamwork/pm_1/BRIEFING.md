# Product Manager Briefing - SelfiCamera

## 1. Executive Summary & Vision
SelfiCamera is a specialized, zero-bloat, offline desktop circular presenter camera overlay for Ubuntu Linux (supporting both GNOME Wayland and X11 sessions). Built specifically for developers, live streamers, educators, and presenters, SelfiCamera provides a distraction-free, floating circular camera feed that sits elegantly above full-screen IDEs, slide decks, terminal windows, and browsers.

It eliminates the bloated resource drain and privacy vulnerabilities of web-based or Electron presenter tools by executing 100% locally with high-performance CPython/Qt6 primitives, an ultra-lite (<2MB) local neural segmentation model, and PipeWire/PulseAudio voice reactivity.

## 2. Target Personas
1. **The Live Coding Streamer / Screencaster ("Alex")**:
   - Needs a floating presenter webcam overlay that stays permanently pinned above VS Code, terminal, and browser windows.
   - Requires click-through "Ghost Mode" so that typing or clicking code underneath the webcam is never obstructed.
   - Demands sub-5% CPU overhead to preserve system resources for compilers, test runners, and live encoding.

2. **The Tech Conference & Keynote Presenter ("Elena")**:
   - Needs instant presenter controls via global hotkeys (`Super+Alt+*`) to toggle overlay visibility, cycle background blur, or snap to any screen corner.
   - Relies on offline AI background blur to conceal untidy hotel rooms or crowded co-working spaces with zero cloud dependencies or privacy leaks.
   - Values the subtle, pulsing Voice Aura border ring to provide immediate visual feedback that her microphone is live and picking up speech.

3. **The Remote Technical Interviewer / Educator ("Marcus")**:
   - Uses an Ubuntu Linux workstation (Wayland session) and needs an intuitive UI that "just works" with USB webcams and integrated laptop cameras.
   - Needs preset resizing (160px for compact code reviews, 260px for standard teaching, 380px for opening/closing discussions) via simple scroll-wheel manipulation.
   - Demands Auto-Light Boost so video appears crisp and clear even in dimly lit offices.

## 3. Product Pillars
- **Zero Bloat & Peak Performance**: Sub-30ms end-to-end latency, <5% CPU usage, ~45MB RAM footprint.
- **Privacy & 100% Offline Integrity**: Zero telemetry, zero cloud APIs, zero outbound network sockets.
- **Presenter Ergonomics**: Minimalist frameless circular viewport, auto-hiding HUD, corner snapping, and click-through ghost mode.
- **Native Ubuntu Linux Experience**: Dual-mode shortcuts (X11 global grab + Wayland IPC socket), AppIndicator system tray, and PipeWire/PulseAudio voice reactivity.
- **Bulletproof Reliability & Testability**: 100% reproducible headless test suite using synthetic video/audio mocks without requiring physical webcam/mic hardware.

## 4. Phase 2 Scope & PM Deliverables
- [x] Authoritative PRD & Product Specifications Document (`specifications.md`).
- [x] Comprehensive User Stories across 4 core Epics.
- [x] Gherkin `Given / When / Then` testable Acceptance Criteria for every user story and feature.
- [x] UI/UX Specifications, geometry formulas, animation timings, and color palettes.
- [x] CLI & IPC Socket Communication Protocol specifications.
- [x] Formal Definition of Done (DoD) for Phase 3 (Engineer) and Phase 4 (QA).
- [x] Phase 2 Handoff Report (`handoff.md`).
