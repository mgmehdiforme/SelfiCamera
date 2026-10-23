"""Dual-mode shortcut coordinator supporting X11 global grabs and Wayland IPC."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Dict, Optional
from PySide6.QtCore import QObject, Signal

from selficamera.shortcuts.ipc import ShortcutIPCServer

logger = logging.getLogger(__name__)


class ShortcutManager(QObject):
    """Coordinates system-wide presenter hotkeys across Wayland and X11 sessions."""

    toggle_visibility_requested = Signal()
    toggle_ghost_requested = Signal()
    snap_corner_requested = Signal(int)
    cycle_blur_requested = Signal()
    quit_requested = Signal()

    def __init__(
        self,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        socket_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.state_provider = state_provider
        self.ipc_server = ShortcutIPCServer(state_provider=state_provider, socket_path=socket_path)
        self.ipc_server.action_received.connect(self._handle_ipc_action)

        self._x11_thread: Optional[threading.Thread] = None
        self._x11_running = False

    @property
    def is_listening(self) -> bool:
        """Return True when underlying IPC server is ready."""
        return self.ipc_server.is_listening

    def start(self) -> None:
        """Start IPC server and, if in an X11 session, initialize X11 key grabber."""
        self.ipc_server.start()

        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        has_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        is_x11 = session_type == "x11" or (not has_wayland and bool(os.environ.get("DISPLAY")))

        if is_x11:
            self._start_x11_grabber()
        else:
            logger.info("Session is Wayland (or headless). Relying on Unix domain socket IPC for shortcuts.")

    def stop(self) -> None:
        """Stop IPC server and X11 thread."""
        self.ipc_server.stop()
        self._x11_running = False

    def _handle_ipc_action(self, action: str, params: dict) -> None:
        """Route IPC actions to corresponding Qt signals."""
        logger.info("ShortcutManager handling action: %s (params: %s)", action, params)

        if action in ("toggle_visibility", "toggle"):
            self.toggle_visibility_requested.emit()
        elif action in ("toggle_ghost", "ghost"):
            self.toggle_ghost_requested.emit()
        elif action in ("snap_corner", "snap"):
            corner = int(params.get("corner", 4))
            self.snap_corner_requested.emit(corner)
        elif action in ("cycle_blur", "blur_cycle"):
            self.cycle_blur_requested.emit()
        elif action in ("quit", "exit"):
            self.quit_requested.emit()

    def _start_x11_grabber(self) -> None:
        """Start background X11 key grab listener using python-xlib if available."""
        try:
            from Xlib import X, XK
            from Xlib.display import Display

            display = Display()
            root = display.screen().root

            # Key combinations: Super+Alt+C, Super+Alt+X, Super+Alt+B, Super+Alt+1..4
            # Modifiers: Mod4 (Super) + Mod1 (Alt)
            mod_mask = X.Mod4Mask | X.Mod1Mask

            def register_key(keysym_name: str) -> Optional[int]:
                keysym = XK.string_to_keysym(keysym_name)
                if not keysym:
                    return None
                keycode = display.keysym_to_keycode(keysym)
                if keycode:
                    root.grab_key(keycode, mod_mask, 1, X.GrabModeAsync, X.GrabModeAsync)
                    # Also grab with NumLock and CapsLock combinations
                    root.grab_key(keycode, mod_mask | X.Mod2Mask, 1, X.GrabModeAsync, X.GrabModeAsync)
                    root.grab_key(keycode, mod_mask | X.LockMask, 1, X.GrabModeAsync, X.GrabModeAsync)
                return keycode

            key_map = {
                register_key("c"): lambda: self.toggle_visibility_requested.emit(),
                register_key("C"): lambda: self.toggle_visibility_requested.emit(),
                register_key("x"): lambda: self.toggle_ghost_requested.emit(),
                register_key("X"): lambda: self.toggle_ghost_requested.emit(),
                register_key("b"): lambda: self.cycle_blur_requested.emit(),
                register_key("B"): lambda: self.cycle_blur_requested.emit(),
                register_key("1"): lambda: self.snap_corner_requested.emit(1),
                register_key("2"): lambda: self.snap_corner_requested.emit(2),
                register_key("3"): lambda: self.snap_corner_requested.emit(3),
                register_key("4"): lambda: self.snap_corner_requested.emit(4),
            }

            self._x11_running = True

            def x11_loop():
                while self._x11_running:
                    try:
                        event = display.next_event()
                        if event.type == X.KeyPress and event.detail in key_map:
                            cb = key_map[event.detail]
                            if cb:
                                cb()
                    except Exception:
                        break

            self._x11_thread = threading.Thread(target=x11_loop, daemon=True)
            self._x11_thread.start()
            logger.info("X11 Global hotkeys registered successfully via python-xlib.")
        except Exception as e:
            logger.info("Native X11 key grabber bypassed (%s). IPC socket active.", e)
