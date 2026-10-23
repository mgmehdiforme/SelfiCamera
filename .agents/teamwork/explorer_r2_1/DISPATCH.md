## 2026-10-22T12:37:38Z
You are Explorer 1 investigating R1 (Reliable Mouse Drag-to-Move & Guaranteed Always-On-Top) for SelfiCamera.

Read the authoritative requirements in:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/ORIGINAL_REQUEST.md
Specifically review the request dated 2026-10-22T12:34:05Z (R1 and Acceptance Criteria for Window Movement & Always-On-Top).

Your working directory is:
/run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_r2_1

Tasks:
1. Examine selficamera/ui/overlay.py, selficamera/app.py, run.sh, and any window management code.
2. Analyze mouse drag event handling (mousePressEvent, mouseMoveEvent, mouseReleaseEvent). Check how mouse click-and-drag currently works, whether child widgets (HUD, buttons) block event propagation, and how client-side move() vs startSystemMove() behave.
3. Analyze Always-On-Top persistence on Ubuntu GNOME on both Wayland and X11. Check Qt window flags (Qt.WindowStaysOnTopHint, Qt.FramelessWindowHint, Qt.Tool, etc.), XWayland behavior, and run.sh platform configuration (QT_QPA_PLATFORM=xcb fallback when running on Wayland to ensure GNOME Shell allows dragging and stay-on-top over full-screen IDEs/browsers).
4. Identify any issues or gaps with current implementation and recommend exact, concrete implementation strategies for R1.
5. Write your complete findings to /run/media/mehdi/Projects/PersonalProjects/SelfiCamera/.agents/teamwork/explorer_r2_1/handoff.md.
6. When finished, send a message to caller with a brief summary of your findings.
