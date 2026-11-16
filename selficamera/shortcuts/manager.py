"""Global shortcuts: X11 key grabs plus the IPC server (used by GNOME Wayland keybindings)."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from selficamera.shortcuts.ipc import ShortcutIPCServer, Validator

logger = logging.getLogger(__name__)

# key -> (action, params). Combined with Super+Alt.
HOTKEYS: Dict[str, Tuple[str, Dict[str, Any]]] = {
    "c": ("toggle_visibility", {}),
    "z": ("toggle_spotlight", {}),
    "b": ("cycle_background", {}),
    "m": ("toggle_mirror", {}),
    "x": ("toggle_ghost", {}),
    "o": ("toggle_settings", {}),
    "1": ("snap", {"position": 1}),
    "2": ("snap", {"position": 2}),
    "3": ("snap", {"position": 3}),
    "4": ("snap", {"position": 4}),
    "5": ("snap", {"position": 5}),
}


class ShortcutManager(QObject):
    """Emits ``action_requested(action, params)`` on the GUI thread for every trigger."""

    action_requested = Signal(str, dict)

    def __init__(
        self,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        socket_path: Optional[str] = None,
        validator: Optional[Validator] = None,
        enable_x11: bool = True,
    ) -> None:
        super().__init__()
        self.ipc_server = ShortcutIPCServer(state_provider=state_provider, socket_path=socket_path, validator=validator)
        self.ipc_server.action_received.connect(self.action_requested)
        self.enable_x11 = enable_x11
        self._x11_thread: Optional[threading.Thread] = None
        self._x11_running = False
        self._x11_display = None
        self.x11_active = False

    @property
    def is_listening(self) -> bool:
        return self.ipc_server.is_listening

    def start(self) -> None:
        self.ipc_server.start()
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_x11 = session == "x11" or (not os.environ.get("WAYLAND_DISPLAY") and bool(os.environ.get("DISPLAY")))
        if self.enable_x11 and is_x11:
            self._start_x11()
        else:
            logger.info("Global keys via desktop keybindings + IPC (Wayland or headless session).")

    def stop(self) -> None:
        self._x11_running = False
        if self._x11_display is not None:
            try:
                self._x11_display.close()
            except Exception:
                pass
        self.ipc_server.stop()

    def _start_x11(self) -> None:
        try:
            from Xlib import X, XK
            from Xlib.display import Display
        except ImportError:
            logger.info("python-xlib not installed; X11 global keys disabled.")
            return
        try:
            display = Display()
            root = display.screen().root
            base = X.Mod4Mask | X.Mod1Mask
            keymap: Dict[int, Tuple[str, Dict[str, Any]]] = {}
            for key, action in HOTKEYS.items():
                keycode = display.keysym_to_keycode(XK.string_to_keysym(key))
                if not keycode:
                    continue
                for extra in (0, X.Mod2Mask, X.LockMask, X.Mod2Mask | X.LockMask):
                    root.grab_key(keycode, base | extra, True, X.GrabModeAsync, X.GrabModeAsync)
                keymap[keycode] = action
            display.sync()
        except Exception as exc:
            logger.info("X11 key grab unavailable (%s).", exc)
            return

        self._x11_display = display
        self._x11_running = True
        self.x11_active = True

        def loop() -> None:
            while self._x11_running:
                try:
                    event = display.next_event()
                except Exception:
                    break
                if event.type == X.KeyPress and event.detail in keymap:
                    action, params = keymap[event.detail]
                    self.action_requested.emit(action, dict(params))

        self._x11_thread = threading.Thread(target=loop, name="x11-hotkeys", daemon=True)
        self._x11_thread.start()
        logger.info("X11 global hotkeys registered (Super+Alt+…).")
