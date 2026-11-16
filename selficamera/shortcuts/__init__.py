"""Global shortcuts, IPC and desktop integration."""

from selficamera.shortcuts.manager import HOTKEYS, ShortcutManager
from selficamera.shortcuts.ipc import ShortcutIPCClient, ShortcutIPCServer

__all__ = ["HOTKEYS", "ShortcutManager", "ShortcutIPCServer", "ShortcutIPCClient"]
