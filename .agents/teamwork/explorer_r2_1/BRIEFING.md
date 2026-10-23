# BRIEFING — 2026-10-22T12:47:00Z

## Mission
Investigate R1: Reliable Mouse Drag-to-Move & Guaranteed Always-On-Top for SelfiCamera on Ubuntu GNOME (Wayland & X11).

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_r2_1
- Original parent: eed809cc-41aa-462e-9bbf-e6fa9831a900
- Milestone: R1 Analysis (Drag-to-Move & Always-On-Top)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Analyze mouse drag event handling (overlay, HUD, child widgets, startSystemMove vs client move)
- Analyze Always-On-Top flags and Wayland/XWayland/X11 behavior on Ubuntu GNOME
- Deliver comprehensive handoff.md in working directory and message caller

## Current Parent
- Conversation ID: eed809cc-41aa-462e-9bbf-e6fa9831a900
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `run.sh`
  - `selficamera/__main__.py`
  - `selficamera/app.py`
  - `selficamera/config.py`
  - `selficamera/ui/overlay.py`
  - `selficamera/ui/hud.py`
  - `selficamera/ui/aura.py`
  - `selficamera/ui/tray.py`
  - `tests/test_overlay_gui.py`
  - `tests/test_shortcuts.py`
  - `tests/test_edge_cases.py`
- **Key findings**:
  1. Invisible HUD child buttons consume mouse events even at 0.0 opacity (`QGraphicsOpacityEffect`), preventing drag initiation in bottom half of circle.
  2. Synchronous disk write with `os.fsync()` triggered on every single pixel movement in `mouseMoveEvent` via `position_changed.emit()` -> `config.update(auto_save=True)`.
  3. Window drag clamped strictly to `QGuiApplication.primaryScreen()`, blocking movement to secondary/multi-monitors.
  4. On native Wayland, GNOME Mutter silently ignores `WindowStaysOnTopHint` and client `move()`. Under XWayland (`QT_QPA_PLATFORM=xcb`), GNOME Mutter strictly enforces `_NET_WM_STATE_ABOVE` over full-screen IDEs/browsers and allows smooth client moves.
  5. `QT_QPA_PLATFORM="xcb;wayland"` fallback syntax prevents crash code 134 if `libxcb-cursor0` is missing, while preferring XWayland.
  6. `setWindowFlag(WindowStaysOnTopHint)` hides the QWidget; `self.show()` must follow.
- **Unexplored areas**: None for R1 scope.

## Key Decisions Made
- Fully analyzed mouse drag pipeline, child widget event tree, platform flags, and multi-monitor handling.
- Formulated concrete implementation strategies for R1.

## Artifact Index
- /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_r2_1/DISPATCH.md — Dispatch instructions
- /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_r2_1/BRIEFING.md — Working memory
- /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_r2_1/progress.md — Liveness heartbeat
- /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_r2_1/handoff.md — Final 5-component report
