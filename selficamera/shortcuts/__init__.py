"""Shortcuts and IPC subsystem supporting X11 global hotkeys and Wayland socket IPC."""
from selficamera.shortcuts.manager import ShortcutManager
from selficamera.shortcuts.ipc import ShortcutIPCServer, ShortcutIPCClient

__all__ = ["ShortcutManager", "ShortcutIPCServer", "ShortcutIPCClient"]
